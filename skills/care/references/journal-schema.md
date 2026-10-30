# journal schema

`$CARE_HOME/journal.jsonl`。1 行 1 事象、追記のみ（`update` は該当行を書き換える）。共通欄: `id`（c1, c2 …）、`ts`（ISO 分単位）、`type`。

| type | 必須 | 任意 | 誰が書く |
|---|---|---|---|
| `checkin` | `score` (0–10) | `word`, `note` | `/care check` |
| `words` | `file` | `feelings[]`, `triggers[]`, `need`, `step` | `/care words` |
| `session` | `persona`, `gist` | `topics[]`, `start`, `end`, `helped`, `followup` (bool) | 相談セッションの終わり |
| `log` | `text` | `tags[]` | `/care log`、危機時の記録（許可を得て） |
| `signal` | `score`, `level` (medium/high/crisis) | `words[]`, `nudged`, `paused` | `observe.py`（自動） |
| `persona` | `slug`, `action` (create/update/switch) | — | `/care persona` |

リスト欄（`words`, `feelings`, `triggers`, `topics`, `tags`, `next`）は `'key=[a,b]'` または `key=a,b`（角括弧はシェルが展開するのでクォート）。数値欄は `score`, `start`, `end`。

その他のファイル:

- `config.json` — `persona`（現在の slug）、`observe`（閾値）
- `state.json` — `paused`, `paused_until`, `recent`（直近の signal 点数）, `last_nudge`
- `persona/<slug>.md` — 人格
- `words/YYYY-MM-DD-HHMM.md` — 言語化メモ
