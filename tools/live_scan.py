#!/usr/bin/env python3
"""Live Setup scan: read-only look at Alex's Mac as it is now.

Collects NAMES and PATHS only (never key values): AI apps, their MCP connectors,
skill folders, repos, and simple problem checks. Writes app/.data/live-setup.json.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'app' / '.data' / 'live-setup.json'

APPS = {
    'app:claude': ('Claude desktop', [HOME / 'Library/Application Support/Claude/claude_desktop_config.json'], [HOME / '.claude/skills']),
    'app:cursor': ('Cursor', [HOME / '.cursor/mcp.json'], [HOME / '.cursor/skills']),
    'app:codex': ('Codex', [HOME / '.codex/config.toml'], [HOME / '.codex/skills']),
}
SHARED_SKILLS = HOME / '.agents' / 'skills'
REPO_ROOTS = [HOME / 'Projects', HOME / 'Documents', HOME]
HUBS = {'director-observatory'}  # codex-bridge links only Claude and Codex by design

nodes, edges, problems = {}, [], []


def node(nid, kind, label, **meta):
    nodes.setdefault(nid, {'id': nid, 'kind': kind, 'label': label, 'meta': meta})
    return nid


def edge(a, b, label):
    edges.append({'id': f'{a}->{b}:{label}', 'source': a, 'target': b, 'label': label})


def problem(severity, title, detail, ids):
    problems.append({'severity': severity, 'title': title, 'detail': detail, 'node_ids': ids})


def mcp_names(cfg: Path) -> list[str]:
    """Server NAMES only. Never returns commands, env values or headers."""
    if not cfg.exists():
        return []
    text = cfg.read_text(errors='ignore')
    if cfg.suffix == '.toml':
        names = re.findall(r'^\[mcp_servers\.([A-Za-z0-9_\-]+)\]', text, re.M)
        return sorted(set(names))
    try:
        return sorted((json.loads(text).get('mcpServers') or {}).keys())
    except Exception:
        return []


def skill_dirs(folder: Path) -> list[Path]:
    if not folder.exists():
        return []
    return sorted(p for p in folder.iterdir() if p.is_dir() and not p.name.startswith('.'))


def find_repos() -> list[Path]:
    found = set()
    for root in REPO_ROOTS:
        depth = 1 if root == HOME else 4
        try:
            out = subprocess.run(
                ['find', str(root), '-maxdepth', str(depth), '-name', '.git', '-type', 'd',
                 '-not', '-path', '*/node_modules/*', '-not', '-path', '*/Library/*'],
                capture_output=True, text=True, timeout=60,
            ).stdout
        except Exception:
            continue
        for line in out.splitlines():
            found.add(Path(line).parent)
    return sorted(found)


PATH_RE = re.compile(r'(~/[^\s`"\')\]]+|/Users/[^\s`"\')\]]+)')


# Sort a quiet Director mission from its own notes (read here, never copied out). Order matters:
# a decision waiting on Alex beats everything; then "nothing left to do right now"; else stuck.
NEEDS_ME = [
    (r'WAITING_ON_ALEX|READY_FOR_OWNER', 'Director finished its part and is waiting for your answer.'),
    (r"on Alex's word|items? (?:is|are) Alex's|item is Alex's", 'Paused until you say go. The rest of the list is yours to decide.'),
    (r"keep or drop", 'Waiting on your keep-or-drop decision.'),
    (r"Manny decisions|needs Alex's ready|Alex approves", 'Waiting on a decision from you (or Manny).'),
]
LOOKS_DONE = [
    (r'no further [a-z ]*work is ready', 'Director says nothing more can be done here right now.'),
    (r'safely PAUSED', 'Paused on purpose and set to stay paused.'),
]


def triage(remaining: str, next_play: str, owner: str, days: int) -> tuple[str, str]:
    text = ' '.join((remaining, next_play, owner))
    for pattern, why in NEEDS_ME:
        if re.search(pattern, text, re.I):
            return 'needs me', why
    for pattern, why in LOOKS_DONE:
        if re.search(pattern, text, re.I):
            return 'looks done', why
    if re.search(r'first genuine|first-new-lead|waiting for', text, re.I):
        return 'looks stuck', f'Waiting for something real to happen (like a new lead) and nothing has in {days} days.'
    return 'looks stuck', f'Director wrote down a next step, but nothing has moved in {days} days.'


def main():
    # 1. Apps -> connectors, apps -> their own skills
    app_servers = {}
    for aid, (label, cfgs, own_skill_dirs) in APPS.items():
        node(aid, 'app', label)
        servers = sorted({s for c in cfgs for s in mcp_names(c) if '.' not in s})
        app_servers[aid] = set(servers)
        for s in servers:
            sid = node(f'mcp:{s}', 'connector', s, hub=s in HUBS)
            edge(aid, sid, 'uses connector')
    for hub in HUBS:
        missing = [APPS[a][0] for a, s in app_servers.items() if hub not in s]
        if missing and any(hub in s for s in app_servers.values()):
            problem('medium', f'{hub} not connected everywhere',
                    f'Missing in: {", ".join(missing)}', [f'mcp:{hub}'] + [a for a in APPS if hub not in app_servers[a]])

    # 2. Skills: one shared home (~/.agents/skills) that every app reads, plus any real app-only folders.
    # App folders full of links back to the shared home are the SAME skill, not copies (unified 2026-10-10).
    hub = node('hub:shared-skills', 'hub', 'Shared skills (~/.agents/skills)', path='~/.agents/skills')
    composio = node('hub:composio', 'hub', 'Composio (one home for app connectors)')
    for aid in APPS:
        edge(aid, hub, 'loads skills from')
        edge(aid, composio, 'reaches apps through')
    skill_text = {}
    shared_real = SHARED_SKILLS.resolve()

    def add_skill(sid, d, scope, parent):
        md = d / 'SKILL.md'
        node(sid, 'skill', d.name, scope=scope, path=str(d).replace(str(HOME), '~'),
             director=bool(re.search(r'director', d.name, re.I)),
             conductor=bool(re.search(r'conductor', d.name, re.I)))
        edge(parent, sid, 'holds skill')
        if not md.exists():
            problem('low', f'Skill without SKILL.md: {d.name}', str(d).replace(str(HOME), '~'), [sid])
        else:
            skill_text[sid] = md.read_text(errors='ignore')[:20000]

    for d in skill_dirs(SHARED_SKILLS):
        if d.name.lower() == 'synced':
            continue  # Claude app's own download folder, not a skill
        add_skill(f'skill:shared:{d.name}', d, 'shared', hub)
    for aid, (_, _, ds) in APPS.items():
        for folder in ds:
            for d in skill_dirs(folder):
                if d.is_symlink():
                    if not d.exists():
                        problem('high', f'Broken skill link: {d.name}', f'{d} points to something that no longer exists', [aid])
                    elif str(d.resolve()).startswith(str(shared_real)):
                        continue  # a link to the shared home: same skill, already on the map
                if d.name.lower() == 'synced':
                    continue  # Claude Code's own download folder, not a skill of ours
                sid = f'skill:{aid.split(":")[1]}:{d.name}'
                add_skill(sid, d, aid.split(':')[1], aid)
                if (SHARED_SKILLS / d.name).exists():
                    problem('low', f'Real copy shadows a shared skill: {d.name}',
                            'An app-only copy with the same name as a shared skill can drift; link it instead.', [sid])


    # 3. Repos (projects) and skill -> repo / broken path references
    repos = find_repos()
    by_path = {}
    for r in repos:
        rid = node(f'repo:{r}', 'repo', r.name, path=str(r).replace(str(HOME), '~'),
                   director=bool(re.search(r'director', r.name, re.I)))
        by_path[str(r)] = rid
        if re.search(r'( \d+| \(\d+\))$', r.name):
            problem('low', f'Duplicate-looking project copy: {r.name}',
                    'Looks like a copy ("2" / "(2)"). Confirm which one is real.', [rid])
    for sid, text in skill_text.items():
        hit_repos = set()
        for raw in set(PATH_RE.findall(text)):
            p = raw.rstrip('.,:;')
            full = Path(p.replace('~', str(HOME), 1))
            for rpath, rid in by_path.items():
                if str(full).startswith(rpath + '/') or str(full) == rpath:
                    hit_repos.add(rid)
            if '<' in p or '*' in p or '$' in p:
                continue
            # A path cut off at a space ("Ai Helper", "Group Containers") is not missing.
            if not full.exists() and full.parent.exists():
                try:
                    if any(c.name.startswith(full.name + ' ') for c in full.parent.iterdir()):
                        continue
                except Exception:
                    pass
            if not full.exists() and len(nodes[sid]['meta'].get('missing', [])) < 5:
                nodes[sid]['meta'].setdefault('missing', []).append(p)
        for rid in hit_repos:
            edge(sid, rid, 'points to project')
        miss = nodes[sid]['meta'].get('missing')
        if miss:
            # Hidden dot-folders/files (~/.heygen, ~/.cf-token...) are logins, tokens or caches a tool
            # creates on first use: that is "needs setup", not a broken skill.
            hidden = all(Path(m.replace('~', str(HOME), 1)).relative_to(HOME).parts[0].startswith('.')
                         if m.startswith(('~/', str(HOME))) else False for m in miss)
            if hidden:
                problem('setup', f'Needs one-time setup: {nodes[sid]["label"]}',
                        'Expects (login, token or cache): ' + '; '.join(miss[:3]), [sid])
            else:
                problem('high', f'Skill points to missing path: {nodes[sid]["label"]}',
                        'Missing: ' + '; '.join(miss[:3]), [sid])

    # 4. Director / Conductor home
    if (HOME / 'Alex-Director').exists():
        did = node('home:alex-director', 'repo', 'Alex-Director (Director home)',
                   path='~/Alex-Director', director=True)
        for sid, n in nodes.items():
            if n['kind'] == 'skill' and (n['meta'].get('director') or n['meta'].get('conductor')):
                edge(sid, did, 'reads rules from')

    # 5. Hooks: the guards each AI app runs on its own (names, events and script paths only)
    hook_cfgs = {
        'app:claude': HOME / '.claude/settings.json',
        'app:cursor': HOME / '.cursor/hooks.json',
        'app:codex': HOME / '.codex/hooks.json',
    }
    for aid, cfg in hook_cfgs.items():
        if not cfg.exists():
            continue
        try:
            hooks = (json.loads(cfg.read_text(errors='ignore')).get('hooks') or {})
        except Exception:
            problem('medium', f'Unreadable hook settings: {APPS[aid][0]}', str(cfg).replace(str(HOME), '~'), [aid])
            continue
        for event, entries in hooks.items():
            for entry in entries or []:
                cmds = [h.get('command', '') for h in entry.get('hooks', [])] if 'hooks' in entry else [entry.get('command', '')]
                for cmd in cmds:
                    m = re.findall(r"(/[^\s']+\.(?:py|sh))", cmd)
                    if not m:
                        continue
                    script = Path(m[-1])
                    stem = script.stem
                    family = re.sub(r'^(codex|cursor)_', '', stem)  # codex_/cursor_composio_guard = same job
                    hid = node(f'hook:{family}', 'hook', family)
                    meta = nodes[hid]['meta']
                    meta.setdefault('runs', [])
                    run = f'{APPS[aid][0]}: {event}'
                    if run not in meta['runs']:
                        meta['runs'].append(run)
                    meta.setdefault('scripts', [])
                    sp = str(script).replace(str(HOME), '~')
                    if sp not in meta['scripts']:
                        meta['scripts'].append(sp)
                    if not any(e['source'] == aid and e['target'] == hid for e in edges):
                        edge(aid, hid, 'runs hook')
                    if not script.exists():
                        meta['broken'] = True
                        problem('high', f'Hook script missing: {stem}', f'{APPS[aid][0]} runs {sp} on {event}, but the file is gone', [hid, aid])

    # 6. GitHub check on the shared home (agents-home): latest run on main, and commits not pushed yet
    agents = HOME / '.agents'
    gid = node('check:github', 'check', 'GitHub check (agents-home)')
    edge('hub:shared-skills', gid, 'guarded by')
    gmeta = nodes[gid]['meta']
    try:
        out = subprocess.run(['gh', 'run', 'list', '-R', 'increase-roas/agents-home', '-b', 'main', '-L', '1',
                              '--json', 'status,conclusion,displayTitle,createdAt,url'],
                             capture_output=True, text=True, timeout=30)
        runs = json.loads(out.stdout or '[]') if out.returncode == 0 else None
    except Exception:
        runs = None
    if runs is None:
        gmeta['state'] = 'unknown'
        problem('setup', 'GitHub check not readable', 'The gh command could not read the last run (signed out or offline).', [gid])
    elif runs:
        r = runs[0]
        gmeta.update(state=r.get('conclusion') or r.get('status'), title=r.get('displayTitle', '')[:90],
                     at=r.get('createdAt'), url=r.get('url'))
        if r.get('conclusion') not in (None, '', 'success'):
            problem('high', 'GitHub check failing on main', f'Last run: {r.get("conclusion")} ({r.get("displayTitle", "")[:80]})', [gid])
    try:
        ahead = int(subprocess.run(['git', '-C', str(agents), 'rev-list', '--count', 'origin/main..HEAD'],
                                   capture_output=True, text=True, timeout=10).stdout.strip() or 0)
    except Exception:
        ahead = 0
    gmeta['unpushed'] = ahead
    if ahead:
        problem('low', f'{ahead} commit(s) not on GitHub yet', 'Run: cd ~/.agents && git push origin main', [gid])
    hooks_path = subprocess.run(['git', '-C', str(agents), 'config', 'core.hooksPath'], capture_output=True, text=True).stdout.strip()
    gmeta['local_gate'] = 'pre-commit key scan on' if (hooks_path or (agents / '.git/hooks/pre-commit').exists()) else 'off'

    # 7. What the Director is doing now: read-only parse of DIRECTOR_STATE.md (same source as mission-board.py)
    state = HOME / 'Alex-Director' / 'DIRECTOR_STATE.md'
    if state.exists():
        text = state.read_text(errors='ignore')
        today = datetime.now(timezone.utc).date()
        missions = []
        for block in re.split(r'(?m)^## Mission: ', text)[1:]:
            field = lambda k: (re.search(rf'^{k}: (.*)$', block, re.M) or [None, ''])[1].strip()
            status = (field('STATUS') or '?').split()[0]
            when = field('LAST_RECONCILED_AT')[:10]
            quiet = None
            try:
                quiet = (today - datetime.fromisoformat(when).date()).days
            except Exception:
                pass
            m = {'name': block.split('\n', 1)[0].strip()[:90], 'status': status,
                 'updated': when or None, 'quiet_days': quiet}
            if status == 'ACTIVE' and (quiet or 0) >= 5:
                m['bucket'], m['why'] = triage(field('REMAINING'), field('NEXT_PLAY'), field('OWNER_BOUNDARY'), quiet)
            missions.append(m)
        counts = {}
        for m in missions:
            counts[m['status']] = counts.get(m['status'], 0) + 1
        active = [m for m in missions if m['status'] == 'ACTIVE']
        waiting = [m for m in missions if m['status'] == 'WAITING_ON_ALEX']
        quiet = sorted([m for m in active if (m['quiet_days'] or 0) >= 5], key=lambda m: -(m['quiet_days'] or 0))
        nodes_quiet = [{k: m[k] for k in ('name', 'quiet_days', 'bucket', 'why')} for m in quiet]
        label = f'Director now: {len(active)} active' + (f', {len(waiting)} waiting on you' if waiting else '')
        did = node('director:now', 'director', label, director=True, counts=counts, quiet=nodes_quiet,
                   missions=sorted(active + waiting, key=lambda m: m['updated'] or '', reverse=True)[:15])
        if (HOME / 'Alex-Director').exists():
            edge(did, 'home:alex-director', 'state kept in')
        for m in waiting:
            problem('you', f'Director waiting on you: {m["name"]}', f'Last update {m["updated"] or "?"}', [did])
        if quiet:
            tally = {b: sum(1 for m in quiet if m['bucket'] == b) for b in ('needs me', 'looks stuck', 'looks done')}
            problem('watch', f'{len(quiet)} active mission(s) quiet 5+ days',
                    ', '.join(f'{n} {b}' for b, n in tally.items() if n), [did])
        receipts = HOME / 'Alex-Director' / 'inputs' / 'real-traces' / 'director-controller' / 'receipts.jsonl'
        if not receipts.exists():
            receipts = ROOT / 'inputs' / 'real-traces' / 'director-controller' / 'receipts.jsonl'
        if receipts.exists():
            last = None
            for line in receipts.read_text(errors='ignore').splitlines():
                try:
                    ts = json.loads(line).get('timestamps') or {}
                except Exception:
                    continue
                for v in ts.values():
                    if v and (last is None or v > last):
                        last = v
            nodes[did]['meta']['last_trace'] = last
            nodes[did]['meta']['trace_export'] = datetime.fromtimestamp(receipts.stat().st_mtime, timezone.utc).isoformat()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    summary = {k: sum(1 for n in nodes.values() if n['kind'] == k) for k in ('app', 'hub', 'connector', 'skill', 'repo', 'hook', 'check', 'director')}
    OUT.write_text(json.dumps({
        'scanned_at': datetime.now(timezone.utc).isoformat(),
        'summary': summary,
        'nodes': list(nodes.values()),
        'edges': edges,
        'problems': sorted(problems, key=lambda p: {'high': 0, 'medium': 1, 'you': 2, 'watch': 3, 'setup': 4, 'low': 5}[p['severity']]),
    }, indent=1))
    print(json.dumps({'summary': summary, 'edges': len(edges),
                      'problems': {s: sum(1 for p in problems if p['severity'] == s) for s in ('high', 'medium', 'you', 'watch', 'setup', 'low')}}))


if __name__ == '__main__':
    main()
