#!/usr/bin/env python3
"""care journal: append-only JSON Lines log of check-ins, verbalized stress,
sessions and observed signals, plus derived stats. Pure standard library.
Data lives in $CARE_HOME (default ~/.care).

  journal.py init
  journal.py add TYPE key=value ... [--json '{...}']
  journal.py update ID key=value ... [--json '{...}']
  journal.py list [--type T] [--since DATE] [--last N] [--table]
  journal.py show ID
  journal.py stats [--weeks N]
  journal.py week [--date DATE]          # markdown digest of one ISO week (for /care review)
  journal.py status                      # config, pause state, persona, counts
  journal.py persona [--set SLUG]        # show or switch the active persona
  journal.py pause [--hours N] | resume  # silence the observer (hook) for a while / forever
"""
import argparse, datetime as dt, json, os, sys
from collections import Counter

TYPES = {
    "checkin": ["score"],          # 0-10 + optional word / note
    "words":   ["file"],           # path of the verbalized stress memo
    "session": ["persona", "gist"],
    "log":     ["text"],
    "signal":  ["score", "level"],  # written by observe.py (hook)
    "persona": ["slug", "action"],
}
LIST_FIELDS = {"words", "feelings", "triggers", "topics", "tags", "next"}
NUM_FIELDS = {"score", "start", "end"}


def home():
    return os.path.expanduser(os.environ.get("CARE_HOME", "~/.care"))


def path(*p):
    return os.path.join(home(), *p)


def load():
    p = path("journal.jsonl")
    if not os.path.exists(p):
        return []
    out = []
    with open(p, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as e:
                sys.exit(f"journal.jsonl line {n} is not valid JSON: {e}")
    return out


def save_all(events):
    with open(path("journal.jsonl"), "w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")


def append(event):
    os.makedirs(home(), exist_ok=True)
    with open(path("journal.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def next_id(events):
    mx = 0
    for e in events:
        try:
            mx = max(mx, int(str(e.get("id", "c0"))[1:]))
        except ValueError:
            pass
    return f"c{mx + 1}"


def read_json(p, default):
    if not os.path.exists(p):
        return default
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def write_json(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def config():
    return read_json(path("config.json"), {})


def state():
    return read_json(path("state.json"), {})


def parse_kv(pairs, extra_json=None):
    d = {}
    for kv in pairs:
        if "=" not in kv:
            sys.exit(f"expected key=value, got {kv!r}")
        k, v = kv.split("=", 1)
        if k in LIST_FIELDS:
            if v.startswith("["):
                try:
                    v = json.loads(v)
                except json.JSONDecodeError:
                    v = [x.strip() for x in v.strip("[]").split(",") if x.strip()]
            else:
                v = [x.strip() for x in v.split(",") if x.strip()]
        elif k in NUM_FIELDS:
            try:
                v = float(v) if "." in v else int(v)
            except ValueError:
                sys.exit(f"{k} must be a number, got {v!r}")
        elif v in ("true", "false"):
            v = v == "true"
        d[k] = v
    if extra_json:
        d.update(json.loads(extra_json))
    return d


def add_event(typ, fields):
    """Used by observe.py too. Returns the new event."""
    if typ not in TYPES:
        sys.exit(f"unknown type {typ!r}; one of {', '.join(TYPES)}")
    missing = [k for k in TYPES[typ] if k not in fields]
    if missing:
        sys.exit(f"{typ} requires {', '.join(missing)}")
    if typ == "checkin" and not (0 <= float(fields["score"]) <= 10):
        sys.exit("checkin score must be 0-10")
    events = load()
    ev = {"id": next_id(events), "ts": dt.datetime.now().isoformat(timespec="minutes"), "type": typ}
    ev.update(fields)
    append(ev)
    return ev


def is_paused(st=None):
    st = st if st is not None else state()
    if st.get("paused"):
        return True
    until = st.get("paused_until")
    if until:
        try:
            return dt.datetime.fromisoformat(until) > dt.datetime.now()
        except ValueError:
            return False
    return False


# ---------- commands ----------

def cmd_init(a):
    os.makedirs(path("persona"), exist_ok=True)
    os.makedirs(path("words"), exist_ok=True)
    if not os.path.exists(path("config.json")):
        write_json(path("config.json"), {
            "created": dt.date.today().isoformat(),
            "persona": None,
            "observe": {"cooldown_min": 90, "threshold": 3, "rolling_threshold": 5,
                        "rolling_hours": 3, "late_night": [1, 5]},
        })
    if not os.path.exists(path("state.json")):
        write_json(path("state.json"), {"paused": False, "recent": [], "last_nudge": None})
    open(path("journal.jsonl"), "a", encoding="utf-8").close()
    print(f"initialized {home()}")


def cmd_add(a):
    ev = add_event(a.type, parse_kv(a.kv, a.json))
    print(ev["id"])


def cmd_update(a):
    events = load()
    for e in events:
        if e.get("id") == a.id:
            e.update(parse_kv(a.kv, a.json))
            e["updated"] = dt.datetime.now().isoformat(timespec="minutes")
            save_all(events)
            print(json.dumps(e, ensure_ascii=False))
            return
    sys.exit(f"no event {a.id}")


def fmt_row(e):
    t = e["type"]
    if t == "checkin":
        body = f"{e.get('score')}/10 {e.get('word', '')} {e.get('note', '')}"
    elif t == "signal":
        body = f"{e.get('level')} {e.get('score')} {' '.join(e.get('words', []))}{' (声かけ)' if e.get('nudged') else ''}"
    elif t == "session":
        body = f"[{e.get('persona')}] {e.get('gist')}"
    elif t == "words":
        body = f"{os.path.basename(str(e.get('file')))} {' '.join(e.get('feelings', []))}"
    elif t == "log":
        body = e.get("text", "")
    else:
        body = json.dumps({k: v for k, v in e.items() if k not in ("id", "ts", "type")}, ensure_ascii=False)
    return f"{e['id']:>5}  {e['ts'][:16]}  {t:<8}  {body.strip()}"


def cmd_list(a):
    events = load()
    if a.type:
        events = [e for e in events if e["type"] == a.type]
    if a.since:
        events = [e for e in events if e["ts"] >= a.since]
    if a.last:
        events = events[-a.last:]
    for e in events:
        print(fmt_row(e) if a.table else json.dumps(e, ensure_ascii=False))


def cmd_show(a):
    for e in load():
        if e.get("id") == a.id:
            print(json.dumps(e, ensure_ascii=False, indent=2))
            return
    sys.exit(f"no event {a.id}")


def iso_week(ts):
    y, w, _ = dt.datetime.fromisoformat(ts).isocalendar()
    return f"{y}-W{w:02d}"


def cmd_stats(a):
    events = load()
    since = (dt.datetime.now() - dt.timedelta(weeks=a.weeks)).isoformat()
    events = [e for e in events if e["ts"] >= since]
    if not events:
        print(f"(直近 {a.weeks} 週の記録なし)")
        return
    cfg = config().get("observe", {})
    ln = cfg.get("late_night", [1, 5])
    print(f"## 直近 {a.weeks} 週\n")
    print("| 週 | チェックイン | 平均 | 最低〜最高 | 観察(中/高/危機) | 声かけ | 深夜 | 相談 | 言語化 |")
    print("|---|---|---|---|---|---|---|---|---|")
    for wk in sorted({iso_week(e["ts"]) for e in events}):
        es = [e for e in events if iso_week(e["ts"]) == wk]
        ch = [float(e["score"]) for e in es if e["type"] == "checkin"]
        sg = [e for e in es if e["type"] == "signal"]
        lv = Counter(e.get("level") for e in sg)
        late = sum(1 for e in sg if ln[0] <= dt.datetime.fromisoformat(e["ts"]).hour <= ln[1])
        avg = f"{sum(ch)/len(ch):.1f}" if ch else "-"
        rng = f"{min(ch):.0f}〜{max(ch):.0f}" if ch else "-"
        print(f"| {wk} | {len(ch)} | {avg} | {rng} | {lv.get('medium',0)}/{lv.get('high',0)}/{lv.get('crisis',0)} "
              f"| {sum(1 for e in sg if e.get('nudged'))} | {late} "
              f"| {sum(1 for e in es if e['type']=='session')} | {sum(1 for e in es if e['type']=='words')} |")
    words = Counter(w for e in events if e["type"] == "signal" for w in e.get("words", []))
    if words:
        print("\nよく出た語: " + "、".join(f"{w}×{n}" for w, n in words.most_common(8)))
    feel = Counter(w for e in events if e["type"] == "words" for w in e.get("feelings", []))
    if feel:
        print("言語化で付けた名前: " + "、".join(f"{w}×{n}" for w, n in feel.most_common(8)))
    trig = Counter(w for e in events if e["type"] in ("words", "session") for w in e.get("triggers", []) + e.get("topics", []))
    if trig:
        print("話題・引き金: " + "、".join(f"{w}×{n}" for w, n in trig.most_common(8)))
    hours = Counter(dt.datetime.fromisoformat(e["ts"]).hour for e in events if e["type"] == "signal")
    if hours:
        print("観察が多い時間帯: " + "、".join(f"{h:02d}時×{n}" for h, n in hours.most_common(4)))


def cmd_week(a):
    d = dt.date.fromisoformat(a.date) if a.date else dt.date.today()
    y, w, _ = d.isocalendar()
    wk = f"{y}-W{w:02d}"
    es = [e for e in load() if iso_week(e["ts"]) == wk]
    print(f"## {wk}\n")
    if not es:
        print("(記録なし)")
        return
    for t in ("checkin", "session", "words", "log", "signal"):
        rows = [e for e in es if e["type"] == t]
        if rows:
            print(f"### {t} ({len(rows)})")
            for e in rows:
                print("- " + fmt_row(e))
            print()


def cmd_status(a):
    cfg, st = config(), state()
    print(f"CARE_HOME: {home()}")
    print(f"persona: {cfg.get('persona') or '(未設定 → /care で聞き取り)'}")
    print(f"observer: {'一時停止中' if is_paused(st) else '観察中'}"
          + (f" (〜{st['paused_until'][:16]})" if st.get("paused_until") and is_paused(st) else ""))
    events = load()
    c = Counter(e["type"] for e in events)
    print("entries: " + ", ".join(f"{k}={v}" for k, v in sorted(c.items())) if c else "entries: 0")
    last_ch = [e for e in events if e["type"] == "checkin"]
    if last_ch:
        e = last_ch[-1]
        print(f"last checkin: {e['ts'][:16]} {e['score']}/10 {e.get('word','')}")
    last_s = [e for e in events if e["type"] == "session"]
    if last_s:
        e = last_s[-1]
        print(f"last session: {e['ts'][:16]} {e.get('gist','')}")


def cmd_persona(a):
    cfg = config()
    if a.set:
        p = path("persona", f"{a.set}.md")
        if not os.path.exists(p):
            sys.exit(f"no persona file {p}")
        cfg["persona"] = a.set
        write_json(path("config.json"), cfg)
        add_event("persona", {"slug": a.set, "action": "switch"})
        print(f"persona -> {a.set}")
        return
    slug = cfg.get("persona")
    if not slug:
        print("(persona 未設定)")
        return
    p = path("persona", f"{slug}.md")
    print(f"# {p}\n")
    if os.path.exists(p):
        print(open(p, encoding="utf-8").read())


def cmd_pause(a):
    st = state()
    if a.hours:
        st["paused"] = False
        st["paused_until"] = (dt.datetime.now() + dt.timedelta(hours=a.hours)).isoformat(timespec="minutes")
        msg = f"観察を {a.hours} 時間止めました（〜{st['paused_until'][:16]}）"
    else:
        st["paused"] = True
        st["paused_until"] = None
        msg = "観察を止めました（/care on で再開）"
    write_json(path("state.json"), st)
    print(msg)


def cmd_resume(a):
    st = state()
    st["paused"] = False
    st["paused_until"] = None
    write_json(path("state.json"), st)
    print("観察を再開しました")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init").set_defaults(fn=cmd_init)
    p = sub.add_parser("add"); p.add_argument("type"); p.add_argument("kv", nargs="*"); p.add_argument("--json"); p.set_defaults(fn=cmd_add)
    p = sub.add_parser("update"); p.add_argument("id"); p.add_argument("kv", nargs="*"); p.add_argument("--json"); p.set_defaults(fn=cmd_update)
    p = sub.add_parser("list"); p.add_argument("--type"); p.add_argument("--since"); p.add_argument("--last", type=int); p.add_argument("--table", action="store_true"); p.set_defaults(fn=cmd_list)
    p = sub.add_parser("show"); p.add_argument("id"); p.set_defaults(fn=cmd_show)
    p = sub.add_parser("stats"); p.add_argument("--weeks", type=int, default=2); p.set_defaults(fn=cmd_stats)
    p = sub.add_parser("week"); p.add_argument("--date"); p.set_defaults(fn=cmd_week)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    p = sub.add_parser("persona"); p.add_argument("--set"); p.set_defaults(fn=cmd_persona)
    p = sub.add_parser("pause"); p.add_argument("--hours", type=float); p.set_defaults(fn=cmd_pause)
    sub.add_parser("resume").set_defaults(fn=cmd_resume)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
