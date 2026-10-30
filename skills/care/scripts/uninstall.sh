#!/usr/bin/env bash
# Remove the observer hook and the skill link. Data in ~/.care is left untouched.
set -euo pipefail
CLAUDE_DIR="${CLAUDE_DIR:-$HOME/.claude}"
python3 -I - "$CLAUDE_DIR/settings.json" <<'PY'
import json, os, sys
p = sys.argv[1]
if not os.path.exists(p): sys.exit(0)
cfg = json.load(open(p, encoding="utf-8"))
groups = cfg.get("hooks", {}).get("UserPromptSubmit", [])
kept = [g for g in groups if not any("care/scripts/observe.py" in h.get("command", "") for h in g.get("hooks", []))]
if groups and kept != groups:
    if kept: cfg["hooks"]["UserPromptSubmit"] = kept
    else:
        cfg["hooks"].pop("UserPromptSubmit", None)
        if not cfg["hooks"]: cfg.pop("hooks")
    json.dump(cfg, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2); open(p, "a").write("\n")
    print("hook    removed from", p)
PY
rm -f "$CLAUDE_DIR/skills/care" && echo "unlinked $CLAUDE_DIR/skills/care"
echo "データ ~/.care はそのまま残しています。"
