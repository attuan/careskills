#!/usr/bin/env python3
"""care observe: UserPromptSubmit hook.

Reads the hook JSON on stdin, scans the prompt for stress signals (Japanese and
English lexicon + late-night hour), keeps a rolling score in $CARE_HOME/state.json,
and, when the signal is strong enough and the cooldown has passed, hands Claude a
short additionalContext asking it to add one gentle line to its normal answer.

The prompt itself is never stored: only matched words, a score and a level.
Never blocks a prompt. Any failure exits 0 silently.

Test:  echo '{"prompt":"もう無理、徹夜で間に合わない"}' | python3 -I observe.py
       python3 -I observe.py --dry "ちょっと疲れた"   (score only, no state change)
"""
import datetime as dt, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

CRISIS = ["死にたい", "消えたい", "自殺", "生きていたくない", "生きてる意味", "生きる意味がない",
          "死んだほうが", "死んだ方が", "いなくなりたい", "終わりにしたい", "もう終わりだ",
          "kill myself", "suicid", "want to die", "end it all", "no reason to live", "better off dead"]
HIGH = ["限界", "もう無理", "もうむり", "耐えられない", "辛すぎ", "つらすぎ", "しんどすぎ", "吐き気",
        "眠れない", "寝れない", "寝てない", "泣きそう", "泣いた", "泣いて", "助けて", "壊れそう",
        "パニック", "過呼吸", "動悸", "何も手につかない", "手が震え", "burnout", "burned out", "burnt out",
        "can't take", "cant take", "can't sleep", "breaking down", "panic", "falling apart"]
MEDIUM = ["疲れた", "つかれた", "疲れて", "しんどい", "つらい", "辛い", "怖い", "こわい", "不安", "焦る",
          "焦って", "焦り", "イライラ", "いらいら", "むかつく", "腹立つ", "最悪", "嫌だ", "いやだ", "やばい",
          "間に合わない", "締切", "締め切り", "徹夜", "怒られ", "叱られ", "失敗", "ミスった", "やらかした",
          "自分が悪い", "ダメだ", "だめだ", "意味ない", "どうせ", "無理かも", "もうやだ", "もういや",
          "情けない", "申し訳な", "憂鬱", "ゆううつ", "だるい", "やる気が", "集中できない",
          "stressed", "anxious", "overwhelmed", "frustrated", "exhausted", "so tired", "deadline",
          "hopeless", "worthless", "miserable"]

NUDGE = (
    "【care 観察】この入力にストレスの兆候があります（{level}: {words}{late}）。"
    "作業の依頼には普段どおり完全に答えてください。そのうえで回答の末尾に 1〜2 文だけ、"
    "本人の言葉を拾って様子を気遣う一言を添えてください（助言・分析・箇条書きはしない）。"
    "同じ会話で初めてなら「少し話したくなったら /care で聞けます」と一度だけ伝えてよい。"
    "本人が「大丈夫」「いいから」と流したら以後は添えない。すでに /care セッション中ならこの通知は無視。"
)
CRISIS_CTX = (
    "【care 観察・重要】この入力に自傷・希死の可能性がある表現が含まれます（{words}）。"
    "作業の話より先に、短く率直に、温かく本人の安全を確かめてください。説教や分析はしない。"
    "~/.claude/skills/care/references/safety.md の「危機のとき」に従い、相談窓口（よりそいホットライン 0120-279-338 など）を"
    "押しつけずに伝え、/care で話せることも伝える。人格モードで話している途中でも、この確認は Claude 自身の責任で行う。"
)


def scan(text):
    t = text.lower()
    hits, score, level = [], 0, None
    for w in CRISIS:
        if w.lower() in t:
            hits.append(w); level = "crisis"
    for w in HIGH:
        if w.lower() in t:
            hits.append(w); score += 2
    for w in MEDIUM:
        if w.lower() in t and not any(w in h for h in hits if h != w):
            hits.append(w); score += 1
    if level != "crisis":
        level = "high" if score >= 3 else ("medium" if score >= 1 else None)
    return hits, score, level


def main():
    if len(sys.argv) > 2 and sys.argv[1] == "--dry":
        hits, score, level = scan(" ".join(sys.argv[2:]))
        print(json.dumps({"words": hits, "score": score, "level": level}, ensure_ascii=False))
        return
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    prompt = str(data.get("prompt", ""))
    if not prompt or prompt.lstrip().startswith("/care"):
        return
    hits, score, level = scan(prompt)
    if not level:
        return

    import journal  # same directory
    now = dt.datetime.now()
    initialized = os.path.exists(journal.path("config.json"))
    cfg = journal.config().get("observe", {}) if initialized else {}
    ln = cfg.get("late_night", [1, 5])
    late = ln[0] <= now.hour <= ln[1]
    if late:
        score += 1
    st = journal.state() if initialized else {}
    paused = journal.is_paused(st) if initialized else False

    # rolling score over the last N hours
    horizon = (now - dt.timedelta(hours=cfg.get("rolling_hours", 3))).isoformat(timespec="minutes")
    recent = [r for r in st.get("recent", []) if r[0] >= horizon]
    recent.append([now.isoformat(timespec="minutes"), score])
    rolling = sum(r[1] for r in recent)

    nudge = False
    if level == "crisis":
        nudge = True
    elif initialized and not paused:  # before install there is no state, so no cooldown; stay quiet
        cooldown_ok = True
        if st.get("last_nudge"):
            try:
                cooldown_ok = now - dt.datetime.fromisoformat(st["last_nudge"]) >= dt.timedelta(minutes=cfg.get("cooldown_min", 90))
            except ValueError:
                pass
        nudge = cooldown_ok and (score >= cfg.get("threshold", 3) or rolling >= cfg.get("rolling_threshold", 5))

    if initialized:
        st["recent"] = recent
        if nudge:
            st["last_nudge"] = now.isoformat(timespec="minutes")
        journal.write_json(journal.path("state.json"), st)
        journal.add_event("signal", {"score": score, "level": level, "words": hits, "nudged": nudge, "paused": paused})

    if not nudge:
        return
    words = "、".join(hits[:6])
    ctx = CRISIS_CTX.format(words=words) if level == "crisis" else NUDGE.format(level=level, words=words, late="、深夜" if late else "")
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": ctx}}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
