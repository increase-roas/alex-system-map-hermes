#!/usr/bin/env python3
"""Set up the guard for one Hermes profile.

  python3 install_hermes.py --home ~/.hermes/profiles/<name> --route mcp_ghl_contacts_list=ghl:ghl.md [--route ...]

What it does:
  1. Copies hermes_guard.py into <home>/agent-hooks/
  2. Makes <home>/connector-cards/<card> from the template for each route (only if missing; fill it in)
  3. Writes <home>/guard-policy.json and a private state folder ~/.hermes-guard-state/<profile> (0700)
  4. PRINTS the hooks block for <home>/config.yaml. It does not edit config.yaml:
     Hermes asks you to approve each hook, so you merge it and approve it yourself.
--route NAME=SERVER:CARD uses the exact tool name Hermes shows at runtime (run /tools in that profile).
"""
import argparse, json, os, shutil, subprocess, sys
from pathlib import Path

KIT = Path(__file__).resolve().parent
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--home", required=True, help="the profile folder (~/.hermes for the default profile)")
ap.add_argument("--route", action="append", default=[], help="TOOL=SERVER:CARD.md")
a = ap.parse_args()

home = Path(a.home).expanduser().resolve()
if not (home / "config.yaml").exists():
    sys.exit(f"STOP: {home} has no config.yaml, so it is not a Hermes profile folder")
profile = "default" if home == (Path.home() / ".hermes").resolve() else home.name
routes = {}
for r in a.route:
    try:
        tool, rest = r.split("=", 1)
        server, card = rest.split(":", 1)
    except ValueError:
        sys.exit(f"STOP: --route {r} must look like TOOL=SERVER:CARD.md")
    routes[tool] = {"server": server, "card": card}

cards = home / "connector-cards"
hooks = home / "agent-hooks"
state = Path.home() / ".hermes-guard-state" / profile
cards.mkdir(exist_ok=True)
hooks.mkdir(exist_ok=True)
state.mkdir(parents=True, exist_ok=True)
os.chmod(state.parent, 0o700)
os.chmod(state, 0o700)
shutil.copy2(KIT / "hermes_guard.py", hooks / "hermes_guard.py")
tmpl = (KIT.parent / "templates" / "connector-card.md").read_text()
made = []
for spec in routes.values():
    p = cards / spec["card"]
    if not p.exists():
        p.write_text(tmpl.replace("{{SERVER}}", spec["server"]))
        made.append(p.name)
policy = {"home": str(home), "profile": profile, "cards_dir": str(cards), "state_dir": str(state), "routes": routes}
pfile = home / "guard-policy.json"
pfile.write_text(json.dumps(policy, indent=2) + "\n")

block = subprocess.run([sys.executable, "-B", str(hooks / "hermes_guard.py"), "--policy", str(pfile), "--print-hook-config"], capture_output=True, text=True)
print(f"Profile {profile} at {home}")
print(f"Routes: {', '.join(routes) or 'none (every connector tool is refused until you add routes)'}")
if made:
    print(f"New cards to fill in: {', '.join(made)} in {cards}")
print("\nMerge this into", home / "config.yaml", "(keep everything else), then start Hermes and approve the hooks:\n")
print(block.stdout or block.stderr)
