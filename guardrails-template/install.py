#!/usr/bin/env python3
"""Install the guardrail hooks into one Claude Code project.

  python3 install.py --project /abs/path/to/project [--server NAME ...] [--tool mcp__server__tool ...] [--batches batches.json]

What it does (and nothing else):
  1. Copies hooks/asset_guard.py and hooks/read_gate.py into <project>/.claude/hooks/
  2. Makes one connector card per connector at <project>/.claude/connector-cards/<server>.md
     (from templates/connector-card.md, only if the card does not exist yet; you must fill it in)
  3. Writes <project>/.claude/guard-policy.json (which cards must be read before which tools)
  4. Makes a private state folder ~/.claude-guard-state/<project-id> (mode 0700)
  5. Adds the hooks to <project>/.claude/settings.json (backup first; your other settings are kept)
Re-running is safe: it never adds the same hook twice. Undo with uninstall.py.
"""
import argparse, hashlib, json, os, shutil, subprocess, sys, time
from pathlib import Path

KIT = Path(__file__).resolve().parent
MARK = ("asset_guard.py", "read_gate.py")


def fail(msg):
    sys.exit(f"STOP: {msg}")


def main():
    if sys.version_info < (3, 9):
        fail("needs Python 3.9 or newer")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True, help="absolute path of the project folder")
    ap.add_argument("--server", action="append", default=[], help="connector not listed in the project's .mcp.json (for example one added at user level)")
    ap.add_argument("--tool", action="append", default=[], help="exact tool name allowed after its card is read, e.g. mcp__ghl__contacts_list")
    ap.add_argument("--batches", help="optional JSON file for batch tools such as COMPOSIO_MULTI_EXECUTE_TOOL (see templates/batches.example.json)")
    ap.add_argument("--dry-run", action="store_true", help="show what would change, write nothing")
    a = ap.parse_args()

    proj = Path(a.project).expanduser()
    if not proj.is_absolute() or not proj.is_dir():
        fail(f"--project must be an existing absolute folder: {a.project}")
    proj = proj.resolve()
    claude = proj / ".claude"
    cards = claude / "connector-cards"

    servers = set(a.server)
    mcp = proj / ".mcp.json"
    if mcp.exists():
        try:
            servers |= set(json.loads(mcp.read_text()).get("mcpServers", {}))
        except ValueError:
            fail(".mcp.json is not valid JSON; fix it first")
    for t in a.tool:
        parts = t.split("__")
        if len(parts) < 3 or parts[0] != "mcp" or parts[1] not in servers:
            fail(f"--tool {t}: must look like mcp__<server>__<tool> with a known server ({sorted(servers) or 'none found'})")

    batches = {}
    if a.batches:
        batches = json.loads(Path(a.batches).read_text())
        for name, spec in batches.items():
            srv = name.split("__")[1] if name.startswith("mcp__") else None
            if srv not in servers:
                fail(f"batch {name}: server {srv} not known")
            spec["actions"] = {k: [str(cards / c) for c in v] for k, v in spec.get("actions", {}).items()}

    state = Path.home() / ".claude-guard-state" / hashlib.sha256(str(proj).encode()).hexdigest()[:12]
    policy = {"version": 1, "project_root": "${CLAUDE_PROJECT_DIR}",
              "servers": {s: [str(cards / f"{s}.md")] for s in sorted(servers)},
              "direct_tools": sorted(set(a.tool)), "batches": batches}

    def hook(cmd, timeout, block=True):
        h = {"type": "command", "command": cmd, "timeout": timeout}
        if block:
            h["onFailure"] = "block"
        return h
    asset = lambda ev: hook(f'python3 -B "${{CLAUDE_PROJECT_DIR}}/.claude/hooks/asset_guard.py" --root "${{CLAUDE_PROJECT_DIR}}" --event {ev}', 30, ev != "Stop")
    read = hook(f'python3 -B "${{CLAUDE_PROJECT_DIR}}/.claude/hooks/read_gate.py" --project "${{CLAUDE_PROJECT_DIR}}" '
                f'--policy "${{CLAUDE_PROJECT_DIR}}/.claude/guard-policy.json" --state-dir "{state}"', 10)
    add = {
        "PreToolUse": [{"matcher": "^(Write|Edit)$", "hooks": [asset("PreToolUse")]}, {"matcher": "^(Read|mcp__.*)$", "hooks": [read]}],
        "PostToolUse": [{"matcher": "^Read$", "hooks": [read]}, {"hooks": [asset("PostToolUse")]}],
        "PostToolUseFailure": [{"matcher": "^Read$", "hooks": [read]}],
        "PermissionDenied": [{"matcher": "^Read$", "hooks": [read]}],
        "Stop": [{"hooks": [asset("Stop")]}],
    }

    sfile = claude / "settings.json"
    settings = json.loads(sfile.read_text()) if sfile.exists() else {}
    hooks = settings.setdefault("hooks", {})
    for ev, groups in add.items():
        cur = hooks.setdefault(ev, [])
        cur[:] = [g for g in cur if not any(m in h.get("command", "") for h in g.get("hooks", []) for m in MARK)]
        cur.extend(groups)

    new_cards = [s for s in sorted(servers) if not (cards / f"{s}.md").exists()]
    print(f"Project:     {proj}")
    print(f"Connectors:  {', '.join(sorted(servers)) or 'none yet'}")
    print(f"Tools gated: {', '.join(policy['direct_tools']) or 'none (every connector tool will be blocked until you list it with --tool)'}")
    print(f"New cards:   {', '.join(new_cards) or 'none'}")
    if a.dry_run:
        print("\nDry run. Settings that would be written:\n" + json.dumps(settings, indent=2))
        return

    (claude / "hooks").mkdir(parents=True, exist_ok=True)
    cards.mkdir(parents=True, exist_ok=True)
    for f in MARK:
        shutil.copy2(KIT / "hooks" / f, claude / "hooks" / f)
    tmpl = (KIT / "templates" / "connector-card.md").read_text()
    for s in new_cards:
        (cards / f"{s}.md").write_text(tmpl.replace("{{SERVER}}", s))
    (claude / "guard-policy.json").write_text(json.dumps(policy, indent=2) + "\n")
    state.mkdir(parents=True, exist_ok=True)
    os.chmod(state.parent, 0o700)
    os.chmod(state, 0o700)
    if sfile.exists():
        shutil.copy2(sfile, sfile.with_name(f"settings.json.bak-guard-{time.strftime('%Y%m%d-%H%M%S')}"))
    sfile.write_text(json.dumps(settings, indent=2) + "\n")

    scan = subprocess.run([sys.executable, "-B", str(claude / "hooks" / "asset_guard.py"), "--root", str(proj), "--scan"], capture_output=True, text=True)
    print("\nInstalled. Setup scan:", "PASS" if scan.returncode == 0 else "FIX THESE FIRST")
    if scan.returncode:
        for e in json.loads(scan.stdout or "{}").get("errors", [])[:20]:
            print("  -", e)
    print("\nNext:")
    if new_cards:
        print(f"  1. Fill in every card in {cards} (replace each TODO line). check.py fails while any TODO is left.")
    print("  2. Run: python3 " + str(KIT / "check.py") + f" --project {proj}")
    print("  3. Restart Claude Code in that project and run /hooks to see them listed.")


if __name__ == "__main__":
    main()
