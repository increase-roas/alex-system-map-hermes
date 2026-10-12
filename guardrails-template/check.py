#!/usr/bin/env python3
"""Check an installed project without starting Claude.

  python3 check.py --project /abs/path/to/project

PASS means: hooks are registered, every card is filled in, the setup scan is clean,
and a connector call with no card read is refused. It does not prove Claude Code
loaded the settings; run /hooks inside Claude Code for that.
"""
import argparse, json, os, subprocess, sys, tempfile
from pathlib import Path

ok = True


def line(passed, msg):
    global ok
    ok &= passed
    print(("PASS  " if passed else "FAIL  ") + msg)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    proj = Path(ap.parse_args().project).expanduser().resolve()
    c = proj / ".claude"
    hooks_dir, pol, sfile = c / "hooks", c / "guard-policy.json", c / "settings.json"

    line(all((hooks_dir / f).exists() for f in ("asset_guard.py", "read_gate.py")), "hook scripts are in .claude/hooks")
    s = json.loads(sfile.read_text()) if sfile.exists() else {}
    cmds = [h.get("command", "") for gs in s.get("hooks", {}).values() for g in gs for h in g.get("hooks", [])]
    line(any("read_gate.py" in x for x in cmds) and any("asset_guard.py" in x for x in cmds), "both hooks registered in .claude/settings.json")
    policy = json.loads(pol.read_text()) if pol.exists() else {"servers": {}, "direct_tools": []}
    for srv, paths in policy["servers"].items():
        for p in paths:
            txt = Path(p).read_text() if Path(p).exists() else ""
            line(bool(txt.strip()) and "TODO" not in txt, f"card for {srv} is filled in ({p})")

    scan = subprocess.run([sys.executable, "-B", str(hooks_dir / "asset_guard.py"), "--root", str(proj), "--scan"], capture_output=True, text=True)
    line(scan.returncode == 0, "setup scan clean (skills, connectors, rules, agents, settings)")
    if scan.returncode:
        for e in json.loads(scan.stdout or "{}").get("errors", [])[:10]:
            print("        ", e)

    tools = policy.get("direct_tools", [])
    if not tools:
        print("NOTE  no tools listed in guard-policy.json, so every connector tool is refused until you add them (install.py --tool ...)")
    with tempfile.TemporaryDirectory() as tmp:
        state = os.path.realpath(tmp)  # macOS /var is a symlink; the gate refuses symlinked state folders
        for i, t in enumerate(tools):
            payload = {"session_id": f"check-{i}", "transcript_path": "/dev/null", "cwd": str(proj), "permission_mode": "default",
                       "hook_event_name": "PreToolUse", "tool_name": t, "tool_input": {}, "tool_use_id": f"check-{i}"}
            r = subprocess.run([sys.executable, "-B", str(hooks_dir / "read_gate.py"), "--project", str(proj), "--policy", str(pol), "--state-dir", state],
                               input=json.dumps(payload), capture_output=True, text=True, env={"CLAUDE_PROJECT_DIR": str(proj), "PATH": "/usr/bin:/bin"})
            line('"deny"' in r.stdout, f"{t} is refused before its card is read")
    print("\nRESULT:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
