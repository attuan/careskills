#!/usr/bin/env bash
# Link the skill into ~/.claude/skills, create ~/.care, and register the observer hook.
set -euo pipefail
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLAUDE_DIR="${CLAUDE_DIR:-$HOME/.claude}"
mkdir -p "$CLAUDE_DIR/skills"
ln -sfn "$SKILL_DIR" "$CLAUDE_DIR/skills/care"
echo "linked  $CLAUDE_DIR/skills/care -> $SKILL_DIR"
python3 -I "$SKILL_DIR/scripts/journal.py" init
python3 -I - "$CLAUDE_DIR/settings.json" <<'PY'
import json, os, sys, shutil, datetime as dt
p = sys.argv[1]
cfg = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
cmd = 'python3 -I "$HOME/.claude/skills/care/scripts/observe.py"'
hooks = cfg.setdefault("hooks", {}).setdefault("UserPromptSubmit", [])
if any("care/scripts/observe.py" in h.get("command", "") for g in hooks for h in g.get("hooks", [])):
    print("hook    already registered in", p); sys.exit(0)
if os.path.exists(p):
    bak = p + ".bak-" + dt.datetime.now().strftime("%Y%m%d%H%M%S")
    shutil.copy(p, bak); print("backup ", bak)
hooks.append({"hooks": [{"type": "command", "command": cmd, "timeout": 5}]})
json.dump(cfg, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2); open(p, "a").write("\n")
print("hook    registered in", p)
PY
echo "done. 新しい Claude Code セッションから /care が使えます。"
