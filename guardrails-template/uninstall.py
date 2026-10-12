#!/usr/bin/env python3
"""Remove the guardrail hooks from one project's .claude/settings.json.

  python3 uninstall.py --project /abs/path/to/project

Only the hook entries that run asset_guard.py or read_gate.py are removed; a backup is
written first. Cards, policy and scripts are left in place (delete them yourself if wanted).
"""
import argparse, json, shutil, time
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--project", required=True)
proj = Path(ap.parse_args().project).expanduser().resolve()
sfile = proj / ".claude" / "settings.json"
if not sfile.exists():
    raise SystemExit("No .claude/settings.json; nothing to remove.")
s = json.loads(sfile.read_text())
shutil.copy2(sfile, sfile.with_name(f"settings.json.bak-unguard-{time.strftime('%Y%m%d-%H%M%S')}"))
removed = 0
for ev in list(s.get("hooks", {})):
    keep = [g for g in s["hooks"][ev] if not any(m in h.get("command", "") for h in g.get("hooks", []) for m in ("asset_guard.py", "read_gate.py"))]
    removed += len(s["hooks"][ev]) - len(keep)
    if keep:
        s["hooks"][ev] = keep
    else:
        del s["hooks"][ev]
if not s.get("hooks"):
    s.pop("hooks", None)
sfile.write_text(json.dumps(s, indent=2) + "\n")
print(f"Removed {removed} hook groups. Restart Claude Code in the project.")
