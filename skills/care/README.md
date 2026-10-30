# care — メンタルケア スキル

本人が「一番安心できる相手」の人格で話を聞き、ストレスを言葉にして残し、普段の作業中のプロンプトからしんどさの兆候を見つけて一言かける Claude Code スキル。

## インストール

```bash
git clone <this repo> ~/careskills
~/careskills/skills/care/scripts/install.sh
```

`install.sh` がやること:

1. `~/.claude/skills/care` → `skills/care` のシンボリックリンク
2. `~/.care/` の初期化（データはここ。`CARE_HOME` で変更可。リポジトリには入らない）
3. `~/.claude/settings.json` に `UserPromptSubmit` フック（`scripts/observe.py`）を追加（既存設定はバックアップ）

外すときは `scripts/uninstall.sh`（`~/.care` は残る）。

## 使い方

```
/care                      相談セッション（初回は「一番安心できる相手」の聞き取り）
/care persona              相手を設定・変更
/care words                ストレスの言語化（5〜10 分、本人の言葉でメモを作る）
/care check 4 焦り         30 秒チェックイン（0〜10 と一言）
/care log 今日は先生に怒られた   一行記録
/care review               週次の振り返り 1 枚
/care off [時間] / on      観察（声かけ）を止める／再開
/care status               状態表示
```

観察フック: 普段のプロンプトに「限界」「眠れない」「徹夜」などの語が強く出たとき、あるいは深夜に積み重なったときだけ、通常の回答の末尾に一言添わる。90 分に一度まで。プロンプト本文は保存されない（一致した語と点数のみ）。

## 構成

```
SKILL.md              手順
references/           persona（聞き取りと作法）、safety（危機対応・相談窓口）、words（言語化）、signals（観察の仕組みと調整）、journal-schema
scripts/journal.py    台帳（標準ライブラリのみ）
scripts/observe.py    UserPromptSubmit フック
scripts/install.sh    導入 / uninstall.sh 撤去
assets/               人格と言語化メモの雛形
evals/                テストケース（claude plugin eval 形式）
```

## 安全について

診断や治療はしない。希死念慮に当たる表現が出たときは、人格より安全確認を優先し、相談窓口を伝える（`references/safety.md`）。
