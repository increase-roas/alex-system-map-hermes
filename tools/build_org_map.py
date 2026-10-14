#!/usr/bin/env python3
"""Org-chart map: the live scan is the skeleton; the workbook catalog hangs on it only where it matches.

READ-ONLY on the Mac. Reads: app/.data/live-setup.json (live scan), the catalog (local_service.py
catalog-export), SKILL.md files, tool cards, rule files, Director state + mission graphs, the SDK build
plan and rule-audit output. Writes only app/.data/org-map.json.

Layers (top-down): You -> AI apps -> Rules (rules, guards, tool cards) -> Director -> Conductor
-> engine room (SDK) -> customers/projects with their missions -> skills -> connectors (each names the system it reaches).
Every node gets a purpose line and a 3-line explanation (what it is / should I care / what to do).
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from review_parse import parse_review

HOME = Path.home()
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'app' / '.data'
OUT = DATA / 'org-map.json'
SKILLS = HOME / '.agents' / 'skills'
CARDS = HOME / '.agents' / 'tools' / 'cards'
INSTR = HOME / '.agents' / 'instructions'
DIRECTOR = HOME / 'Alex-Director'
GATES = SKILLS / 'alex-director' / 'references' / 'gates.md'
SDK_PLAN_DIR = HOME / 'Documents' / 'Codex' / '2026-10-06' / 'can'
SDK_PLAN_LIVE = SDK_PLAN_DIR / 'outputs' / 'ai-money-agent-harness-build.md'
SDK_PLAN_BACKUP = SDK_PLAN_DIR / 'work' / 'sdk-write-skill-plan-20261008' / 'ai-money-agent-harness-build.md.before-general-decision'
RULE_AUDIT_BIN = HOME / 'Backups' / 'tighten-20261011' / 'ra-venv' / 'bin' / 'rule-audit'
VERDICTS = ROOT / 'tools' / 'rule-audit-verdicts.json'
JUNK_PURPOSE = re.compile(r'^\s*$|^—$|purpose unknown|^UNKNOWN|see source', re.I)

nodes: dict[str, dict] = {}
edges: list[dict] = []


def tilde(p) -> str:
    return str(p).replace(str(HOME), '~')


def read(p: Path, limit: int = 200_000) -> str:
    try:
        return p.read_text(errors='ignore')[:limit]
    except Exception:
        return ''


def explain(what: str, care: str, why: str, todo: str) -> dict:
    return {'what': what, 'care': care, 'why': why, 'todo': todo}


def add(nid: str, layer: str, kind: str, label: str, purpose: str, ex: dict, status: str = 'ok',
        sources: list | None = None, **meta) -> str:
    nodes[nid] = {'id': nid, 'layer': layer, 'kind': kind, 'label': label, 'purpose': purpose,
                  'explain': ex, 'status': status, 'sources': [tilde(s) for s in (sources or [])], 'meta': meta}
    return nid


def link(a: str, b: str, kind: str, label: str, evidence: str = '') -> None:
    if a in nodes and b in nodes and not any(e['source'] == a and e['target'] == b and e['kind'] == kind for e in edges):
        edges.append({'id': f'{kind}:{a}->{b}', 'source': a, 'target': b, 'kind': kind, 'label': label, 'evidence': tilde(evidence)})


def frontmatter(text: str) -> dict:
    m = re.match(r'^---\n(.*?)\n---', text, re.S)
    out = {}
    if m:
        for line in m.group(1).splitlines():
            k, _, v = line.partition(':')
            if v:
                out[k.strip()] = v.strip().strip('"')
    return out


def skill_description(name: str) -> str:
    fm = frontmatter(read(SKILLS / name / 'SKILL.md', 6000))
    return fm.get('description', '')


def first_sentence(text: str, limit: int = 220) -> str:
    text = re.sub(r'\s+', ' ', text).strip()
    m = re.match(r'(.+?[.!?])(\s|$)', text)
    s = m.group(1) if m else text
    return s if len(s) <= limit else s[:limit - 1].rsplit(' ', 1)[0] + '…'


# ---------------------------------------------------------------------------------------------- inputs
live = json.loads(read(DATA / 'live-setup.json') or '{}')
live_nodes = {n['id']: n for n in live.get('nodes', [])}
live_problems = live.get('problems', [])


def catalog() -> dict:
    try:
        out = subprocess.run([sys.executable, str(ROOT / 'tools' / 'local_service.py'), '--db', str(DATA / 'local.sqlite'),
                              'catalog-export'], capture_output=True, text=True, timeout=120)
        bundle = json.loads(out.stdout)
        return bundle.get('data') or bundle.get('payload', {}).get('data') or {}
    except Exception:
        return {}


cat = catalog()
components = cat.get('components', [])
sources_by_id = {s['id']: s for s in cat.get('sources', [])}

# ---------------------------------------------------------------------------------------------- 1. You
needs_me: list[dict] = []
add('you', 'you', 'you', 'You (Alex)', 'Sets goals and gives the only approvals that count ("Ask Alex first").',
    explain('You. Every agent works for you, and only your yes in chat approves spending, messaging people, going live or deleting.',
            'yes', 'Anything waiting on you stops until you answer.', 'Work the "Needs me" list at the top of the map.'))

# ---------------------------------------------------------------------------------------------- 2. AI apps
APP_FILES = {'app:claude': '~/.claude/CLAUDE.md', 'app:codex': '~/.codex/AGENTS.md', 'app:cursor': '~/.cursor/rules/agent-routing.mdc'}
for aid in ('app:claude', 'app:codex', 'app:cursor'):
    ln = live_nodes.get(aid)
    if not ln:
        continue
    conns = [e['target'].split(':', 1)[1] for e in live.get('edges', []) if e['source'] == aid and e['label'] == 'uses connector']
    add(aid, 'apps', 'app', ln['label'], f'Where you talk to AI. Reads its rules from {APP_FILES[aid]}.',
        explain(f'{ln["label"]} is one of the AI apps you talk through. It reads the same shared rules and skills as the others.',
                'no', 'It is scanned live and nothing on it is flagged.', 'Nothing.'),
        sources=[APP_FILES[aid].replace('~', str(HOME))], connectors=conns)
    link('you', aid, 'talks', 'you talk through')
# Claude Code is its own app (the CLI/desktop coding agent) reading ~/.claude; Manus is a cloud agent app.
if (HOME / '.claude').exists():
    add('app:claude-code', 'apps', 'app', 'Claude Code', 'Coding agent. Reads ~/.claude/CLAUDE.md and the shared skills.',
        explain('Claude Code is the coding version of Claude. It reads the same shared rules and skills folder.', 'no',
                'Its rules file is generated from the shared rules like the others.', 'Nothing.'),
        sources=[HOME / '.claude' / 'CLAUDE.md'])
    link('you', 'app:claude-code', 'talks', 'you talk through', str(HOME / '.claude' / 'CLAUDE.md'))
if Path('/Applications/Manus.app').exists() or (HOME / 'Documents' / 'Manus').exists():
    mp = Path('/Applications/Manus.app') if Path('/Applications/Manus.app').exists() else HOME / 'Documents' / 'Manus'
    add('app:manus', 'apps', 'app', 'Manus', 'Cloud agent app. Builds dealer sites with its own Manus skills.',
        explain('Manus is another AI app you hand jobs to. It runs in the cloud with its own skills, not your shared rules.', 'maybe',
                'It does not get your generated rules file.', 'Nothing unless Manus starts doing work that needs your gates.'),
        status='watch', sources=[mp])
    link('you', 'app:manus', 'talks', 'you talk through', str(mp))
if Path('/Applications/ChatGPT.app').exists():
    add('app:chatgpt', 'apps', 'app', 'ChatGPT', 'Installed on your Mac; reaches apps through the official Composio plugin (shared.md).',
        explain('ChatGPT is another AI app you talk through. It is installed, but its settings are not files the map can read.',
                'maybe', 'It does not receive your generated rules (see the red line).', 'Check its custom instructions include your "Ask Alex first" gates.'),
        status='watch', sources=['/Applications/ChatGPT.app'])
    link('you', 'app:chatgpt', 'talks', 'you talk through')

# ---------------------------------------------------------------------------------------------- 3. Rules layer
shared = read(INSTR / 'shared.md')
RULES = [
    ('rule:gates', 'Ask Alex first', 'Spending, messaging customers or other real people, going live or changing DNS, and deleting anything not backed up all wait for your yes in chat.',
     ['claude', 'codex', 'cursor', 'director'], [INSTR / 'shared.md', GATES]),
    ('rule:which-login', 'Name the login every time', 'Every Composio action names which account it runs as. Without it, Composio uses whatever login changed last (Gmail once sent as jay@).',
     ['claude', 'codex', 'cursor'], [INSTR / 'shared.md', CARDS / 'composio.md']),
    ('rule:keys-route', 'Keys go 1Password -> Composio', 'Passwords and API keys live in 1Password and reach apps only through Composio. Keys never go in chat, files or logs.',
     ['claude', 'codex', 'cursor'], [INSTR / 'shared.md', CARDS / '1password.md']),
    ('rule:rule-chain', 'One rule source, copied to each app', 'You edit rules once in ~/.agents/instructions; build_instructions.py writes them into Claude, Codex and Cursor.',
     ['claude', 'codex', 'cursor'], [HOME / '.agents/tools/unify/build_instructions.py', INSTR / 'shared.md']),
    ('rule:skill-onoff', 'Skill on/off per app', 'Skills live once in ~/.agents/skills. Claude and Cursor link to them; Codex reads them directly and switches some off in its config.',
     ['claude', 'codex', 'cursor'], [HOME / '.agents/tools/unify/skill-lifecycle.md', HOME / '.codex/config.toml']),
    ('rule:app-reach', 'How each app reaches tools', 'Apps with a terminal (Codex, Claude Code) use the Composio command line; chat apps (Claude app, ChatGPT) use the hosted Composio tools. A few cards name local routes.',
     ['claude', 'codex', 'cursor', 'chatgpt'], [INSTR / 'shared.md', CARDS / 'composio.md']),
    ('rule:look-before-redo', 'Look before redoing', 'Before redoing work or re-asking a past decision, search past chats (search-past-work) and the decision notes. Past approvals do not approve new actions.',
     ['claude', 'codex', 'cursor'], [SKILLS / 'search-past-work' / 'SKILL.md', DIRECTOR / 'owner-decisions-2026-10-03.md']),
    ('rule:cursor-grok-bot', 'Cursor only: Grok Bot rules', 'When Cursor works on Grok Bot / Ralph Jr: cite proof before "done", drafts only until you say send, and "Composio is the only connector".',
     ['cursor'], [HOME / '.cursor/rules/grok-bot-standing.mdc']),
    ('rule:cursor-observatory', 'Cursor only: Observatory first', 'Cursor always checks the Director Observatory before reading old evidence or history.',
     ['cursor'], [HOME / '.cursor/rules/observatory-first.mdc']),
]
codex_off = len(re.findall(r'enabled\s*=\s*false', read(HOME / '.codex/config.toml')))
for rid, label, plain, who, srcs in RULES:
    only_one = len(who) == 1
    extra = f' Codex has {codex_off} skills/plugins switched off.' if rid == 'rule:skill-onoff' else ''
    add(rid, 'rules', 'rule', label, plain + extra,
        explain(plain + extra,
                'maybe' if not only_one else 'maybe',
                ('Only ' + who[0].title() + ' sees this rule, so the other apps behave differently here.') if only_one
                else f'Every agent here follows it: {", ".join(w.title() for w in who)}.',
                'Nothing, unless a red line points at it.'),
        sources=srcs, followed_by=who)
    for w in who:
        if w == 'director':
            continue
        link(f'app:{w}', rid, 'follows', 'follows' if not only_one else 'only this app sees')

# Guards and the GitHub check from the live scan sit in the rules band: they enforce the rules.
for lid, ln in live_nodes.items():
    if ln['kind'] in ('hook', 'check'):
        broken = bool(ln['meta'].get('broken')) or (ln['kind'] == 'check' and ln['meta'].get('state') not in ('success',))
        purpose = {'composio_guard': 'Stops spend, customer messages and deletes through Composio until you say yes.',
                   'chat_guard': 'Keeps long chats and helper agents from using up memory and crashing the Mac.',
                   'herdr-agent-state': 'Tells the herdr app when an AI chat starts.',
                   'deny-fast-subagent': 'Blocks Cursor helper agents set to the "fast" model.'}.get(ln['label'],
                   'Automatic GitHub test on your shared settings (catches broken settings and leaked keys).')
        add(lid, 'rules', ln['kind'], ln['label'], purpose,
            explain(purpose, 'yes' if broken else 'no', 'It is broken or failing.' if broken else 'It is in place and passing.',
                    'Tell me to fix it.' if broken else 'Nothing.'),
            status='broken' if broken else 'ok', **{k: v for k, v in ln['meta'].items() if k in ('runs', 'scripts', 'state', 'url', 'title')})
        for e in live.get('edges', []):
            if e['target'] == lid and e['source'] in nodes:
                link(e['source'], lid, 'runs', 'runs guard')
if 'rule:gates' in nodes and 'hook:composio_guard' in nodes:
    link('rule:gates', 'hook:composio_guard', 'enforced', 'enforced by')
if 'rule:rule-chain' in nodes and 'check:github' in nodes:
    link('rule:rule-chain', 'check:github', 'enforced', 'checked by')

# Tool cards
card_routes: dict[str, list[str]] = {}
for f in sorted(CARDS.glob('*.md')):
    text = read(f)
    fm = frontmatter(text)
    title = (re.search(r'^# (.+)$', text, re.M) or [None, f.stem])[1]
    system = re.split(r':|\s+[—-]\s+', title)[0].strip()
    rule = fm.get('index') or first_sentence(fm.get('route', ''))
    why = ''
    nm = re.search(r'^(Never use[^\n]*|Never:[^\n]*)', text, re.M)
    if nm:
        line = nm.group(1).strip()
        why = line if len(line) <= 260 else line[:259].rsplit(' ', 1)[0] + '…'
    route = fm.get('route', '')
    # Toolkit slugs only: custom_* names not followed by "-" (those are login ids), and the word after "toolkit"/"native".
    kits = set(re.findall(r'\b(custom_[a-z0-9_]+)\b(?!-)', route))
    kits |= set(re.findall(r'(?:toolkits?|native(?: toolkit)?)\s+`?(_?[a-z0-9][a-z0-9_]*)\b(?!-)', route))
    if re.fullmatch(r'\s*composio\s*', route, re.I):
        kits.add(f.stem)  # card says only "composio": the toolkit carries the app's own name
    toolkits = sorted(k for k in kits if k not in ('custom', 'toolkit', 'toolkits', 'tools', 'tool', 'only', 'and', 'with'))
    local = re.search(r'\bnot Composio\b|Local stdio|Terminal only', fm.get('route', ''), re.I)
    card_routes[f.stem] = toolkits
    # Plain words: swap connection codes for names, one line per job ("which job goes where").
    def friendly(m):
        k = m.group(0)
        words = k.replace('custom_', '').replace('_', ' ').strip()
        words = re.sub(r'\bghl\b', 'GHL', words)
        words = re.sub(r'\boauth crm\b', 'CRM', words)
        words = re.sub(r'\b(api|ga4|crm)\b', lambda w: w.group(1).upper(), words)
        return f'the "{words}" connection'
    plain = re.sub(r'\bComposio\s+', '', rule or '')
    plain = re.sub(r'\bcustom_[a-z0-9_]+\b', friendly, plain)
    body = plain.split(':', 1)[-1] if ':' in plain[:30] else plain
    parts, depth, cur = [], 0, ''
    for ch in body:  # split on ";" only outside brackets
        depth += ch == '(' or -(ch == ')')
        if ch == ';' and depth == 0:
            parts.append(cur); cur = ''
        else:
            cur += ch
    parts.append(cur)
    rule_lines = [x.strip().rstrip('.') for x in parts if x.strip()]
    for k in toolkits:  # a line that opens with a bare connection code reads "Use the ... connection"
        if rule_lines and re.match(re.escape(k) + r'\b', rule_lines[0]):
            rule_lines[0] = f'Use the "{k.replace("_", " ")}" connection' + rule_lines[0][len(k):]
    cid = add(f'card:{f.stem}', 'rules', 'card', f'{system} card', ('; '.join(rule_lines) or 'Routing card')[:240],
              explain(f'Tells every agent how to reach {system}: ' + '; '.join(rule_lines) + '.',
                      'no', why or 'Agents read it before their first call to this app, so they use the right route and login.',
                      'Nothing. Edit the card only if a route changes.'),
              sources=[f], routes=toolkits, local=bool(local), system=system, route_text=fm.get('route', '')[:300], rule_lines=rule_lines)

# ---------------------------------------------------------------------------------------------- 4. Director, Conductor, engine room
state_text = read(DIRECTOR / 'DIRECTOR_STATE.md', 400_000)
dir_live = live_nodes.get('director:now', {}).get('meta', {})
quiet = dir_live.get('quiet', [])
add('director', 'director', 'director', 'Director', 'Decides what to do next on every mission and hands the work to the Conductor.',
    explain('Your Director is the AI that runs your projects: it keeps the mission list and decides the next move.',
            'yes' if quiet else 'no', f'{len(quiet)} active missions have not moved in 5+ days.' if quiet else 'Its missions are moving.',
            'Answer the "needs me" missions first.' if quiet else 'Nothing.'),
    status='watch' if quiet else 'ok', sources=[DIRECTOR / 'AGENTS.md', SKILLS / 'alex-director' / 'SKILL.md'], counts=dir_live.get('counts', {}))
add('conductor', 'director', 'conductor', 'Conductor', 'Carries out the plays the Director sends: the controllers (your Codex threads) load it, pick the tools and do the work.',
    explain('The Conductor is the worker playbook: it takes the Director\'s next play and carries it out with the right tools.',
            'no', 'It is installed for every app and its rules are in place.', 'Nothing.'),
    sources=[SKILLS / 'alex-workflow-conductor' / 'SKILL.md'])
add('reviewer', 'conductor', 'reviewer', 'Reviewer',
    "Checks the worker's proof before anything counts as done. Always the other AI family (GPT work gets a Claude check, and the reverse).",
    explain('The Reviewer opens the proof and checks it against the agreed finish line.',
            'maybe', 'A different AI family checks the work before the Director accepts it.',
            'Read the verdict. Failed checks go back to the Conductor.'),
    sources=[SKILLS / 'alex-reviewer' / 'SKILL.md'])
link('conductor', 'reviewer', 'reviews', 'sends proof to', '~/.agents/skills/alex-workflow-conductor/SKILL.md (Review packet)')
link('reviewer', 'director', 'verdict', 'pass / fail to', '~/.agents/skills/alex-reviewer/SKILL.md rule 5')
link('reviewer', 'conductor', 'sendback', 'fail: sends back', '~/.agents/skills/alex-director/SKILL.md rule 3')
link('director', 'conductor', 'dispatches', 'sends plays to')
for app in ('app:claude', 'app:codex', 'app:cursor'):
    link(app, 'director', 'loads', 'can run Director')
link('rule:gates', 'director', 'governs', 'gates')

# ---------------------------------------------------------------------------------------------- 4b. Your agents (top-down)
# One box per agent with role, host, model, tools, status and what stays switched off (Alex 2026-10-13: "a section
# for my agents ... the top-down view"). Facts come from Agent-Team-Setup; live health is not read here yet, so
# status is the recorded one and each box says when it was last checked.
TEAM = HOME / 'Documents' / 'Agent-Team-Setup' / 'agents'
HARDEN = HOME / 'Documents' / 'Codex' / '2026-10-12' / 'javar-hardening'


def _yaml_tools(p):
    t = read(p)
    m = re.search(r'(?ms)^provides_tools:\n((?:\s+-\s*.+\n?)+)', t)
    return [x.strip(' -\'"') for x in m.group(1).splitlines() if x.strip()] if m else []


def _manifest(role):
    try:
        return json.loads(read(TEAM / role / 'manifest.json') or '{}')
    except ValueError:
        return {}


try:
    _reg = json.loads(read(TEAM / 'team-template' / 'worker-registry.json') or '{}')
except ValueError:
    _reg = {}
_setter_models = ', '.join(m.get('model', '') for m in _reg.get('sales_b2b', {}).get('models', [])) or 'unknown'
AGENT_ROWS = [
    # id, name, role, host, model, tools, status, off, sources
    ('javar', 'Javar', 'Executive assistant: runs Alex\'s requests across GHL, Meta, Google, Cloudflare',
     'Hermes 0.21.5 on Orgo (javar-orgo)', 'z-ai/glm-5.2',
     'javar_ghl, javar_meta, Composio, GA4/GTM, Cloudflare, rea (166 after limits)', 'ok',
     'guard: protected setup + new connectors blocked; card-first and client wall in watch mode until about 2026-10-20',
     [HARDEN / 'HANDOFF-javar-to-A.md', TEAM / 'ea']),
    ('javante', 'Javante', 'Second Hermes agent on the Mac mini; takes work only when Alex asks Javar to hand it over',
     'Hermes on Mac mini (Tailscale exit node)', 'unknown', 'A2A handoff from Javar', 'unknown',
     'no customer sends without Alex', [TEAM / 'javante' / 'setup' / 'IDENTITY.md']),
    ('setter', 'Setter (sales B2B)', 'Qualifies new leads for Increase ROAS', 'Hermes worker',
     _setter_models, ', '.join(_yaml_tools(TEAM / 'setter' / 'plugin.yaml')) or 'setter tools', 'watch',
     'sends need Alex\'s exact-message yes', [TEAM / 'setter' / 'plugin.yaml', TEAM / 'team-template' / 'worker-registry.json']),
    ('hunter', 'Hunter', 'First touch: researches new prospects inside the Setter lane', 'Hermes on Orgo (Setter lane)',
     _setter_models, 'research + handoff', 'watch', 'no outreach accepted; research only (proven once, 2026-09-10)',
     [TEAM / 'hunter' / 'README.md']),
]
for role, name, job in (('csm', 'CSM', 'Customer success: check-ins and customer updates'),
                        ('finance', 'Finance', 'Books, reports and payments')):
    man = _manifest(role)
    caps = man.get('capabilities') or {}
    AGENT_ROWS.append((role, name, job, 'Hermes (not deployed)', 'not set',
                       ', '.join(sorted(caps.keys() if isinstance(caps, dict) else map(str, caps))) or 'planned',
                       'unknown', 'off until bound: ' + ', '.join(man.get('disabled_until_bound', [])[:6]),
                       [TEAM / role / 'manifest.json']))
for aid, name, role, host, model, tools, status, off, srcs in AGENT_ROWS:
    recorded = {'csm': _manifest('csm').get('status'), 'finance': _manifest('finance').get('status')}.get(aid)
    add(f'agent:{aid}', 'agents', 'agent', name, role,
        explain(f'{name}: {role}. Runs on {host}; model {model}. Tools: {tools}.',
                'no' if status == 'ok' else 'maybe',
                (f'Recorded status {recorded}. ' if recorded else '') + f'Switched off or gated: {off}.',
                'Nothing.' if status == 'ok' else 'Live health is not read by the map yet; ask the Director or the observatory.'),
        status=status, sources=[s for s in srcs if s.exists()], host=host, model=model, tools=tools, gated=off)
    link('director', f'agent:{aid}', 'runs', 'can hand work to', str(TEAM))
link('agent:javar', 'agent:javante', 'handoff', 'hands work to (only when Alex asks)', str(TEAM / 'ea'))
link('agent:setter', 'agent:hunter', 'contains', 'includes', str(TEAM / 'hunter' / 'README.md'))

# SDK engine room: the 8 parts of the build plan, graded from the plan's own dated gap list.
plan_file = SDK_PLAN_LIVE if SDK_PLAN_LIVE.exists() else SDK_PLAN_BACKUP
plan = read(plan_file)
SDK_ROOT = HOME / 'Documents' / 'Codex' / 'master-agent-operations-sdk'
SDK_ACCEPT = SDK_ROOT / 'docs' / 'evidence' / 'acceptance.json'
SDK_INTEG = SDK_ROOT / 'docs' / 'evidence' / 'integrated-v1' / 'acceptance.json'
accept = json.loads(read(SDK_ACCEPT) or '{}')
tests = accept.get('tests') or {}
sdk_verified = accept.get('state') == 'VERIFIED'
sdk_proof = f"{tilde(SDK_ACCEPT)} ({accept.get('state', '?')}, {tests.get('count', '?')} tests {tests.get('result', '?')}, {str(accept.get('accepted_at', ''))[:10]})"
SDK_STEPS = [
    ('Agent identity, profile and skills', 'partial', 'SDK derives agent profiles and enforces the strict shared-skill contract (v1.3); each target agent\'s own profile/skill baseline is still not captured.', str(SDK_ROOT / 'docs/SHARED_SKILLS.md')),
    ('Runtime and host', 'partial', 'The SDK server runs on this Mac (seen: 23 tools answer). Javar/Javante hosts are not proven; the Orgo adapter only reads metadata.', str(SDK_ROOT / 'src/master_ops/adapters/orgo.py')),
    ('Harness: controller, worker, verifier', 'proven' if sdk_verified else 'partial', 'delegate_verify links Bridge delegation to actual result acceptance; independently verified locally.', str(SDK_ACCEPT)),
    ('Ownership and handoff', 'partial', "SDK ledger rejects stale state and replays safely; Director's write guard has 291 finished writes. Javar/Javante task submission is not connected.", str(SDK_ROOT / 'src/master_ops/ledger.py')),
    ('Shared knowledge (memory)', 'partial', 'Six scoped Mem0 operations exist (memory_search/save/...); automatic capture and second-agent recall unproven.', str(SDK_ROOT / 'docs/MEMORY.md')),
    ('Checkpoints and restart recovery', 'proven' if sdk_verified else 'partial', 'Crash reconciliation and stable replay; the real parser recovery cycle is seen working (SDK README, verified acceptance).', str(SDK_ROOT / 'README.md')),
    ('Evidence and Observatory', 'partial', 'SDK has a persistent Observatory client and resolve_failure workflow; full Observatory coverage acceptance FAILED Oct 6.', str(SDK_INTEG)),
    ('Evaluation material', 'gap', 'Test packs downloaded (Petri Bloom, Meta-Harness) but not adapted or run.', ''),
]
# Is the SDK plugged into any AI app? (names only, read from each app's settings)
SDK_PLUG_FILES = {'Codex': HOME / '.codex/config.toml', 'Cursor': HOME / '.cursor/mcp.json',
                  'Claude': HOME / 'Library/Application Support/Claude/claude_desktop_config.json'}
sdk_plugged = [app for app, f in SDK_PLUG_FILES.items() if re.search(r'master-agent-operations|master-ops-mcp', read(f))]
# Claude Code keeps its servers in ~/.claude.json (the desktop app uses claude_desktop_config.json).
if re.search(r'master-agent-operations', read(HOME / '.claude.json', 2_000_000)):
    sdk_plugged.append('Claude-Code')
sdk = [{'step': i + 1, 'title': t, 'status': s, 'why': w, 'proof': tilde(p or plan_file)} for i, (t, s, w, p) in enumerate(SDK_STEPS)]
plan_note = 'current plan' if plan_file == SDK_PLAN_LIVE else 'backup copy (the live plan file is missing from ~/Documents/Codex/2026-10-06/can/outputs)'
add('sdk', 'engine', 'sdk', 'SDK engine room (Master Agent Operations SDK 1.3)',
    'Your built SDK: GHL, Google, Cloudflare and Orgo connectors, Observatory and Codex-bridge links, memory, a safety ledger and 23 tools any AI app can plug into.',
    explain('The SDK is the engine room you built: one toolbox that can inspect and safely repair your systems, with memory and a ledger of every action.',
            'yes', ('It is verified and its 23 tools answer, but NO AI app is plugged into it yet, so nothing uses it.' if not sdk_plugged
                    else f'It is plugged into {", ".join(sdk_plugged)}.') + f' Plan parts: {sum(1 for x in sdk if x["status"] == "proven")} proven, {sum(1 for x in sdk if x["status"] == "partial")} partial, {sum(1 for x in sdk if x["status"] == "gap")} gap.',
            'Plug it into Codex first (one command, see Needs me).' if not sdk_plugged else 'Nothing.'),
    status='broken' if not sdk_plugged else 'ok', sources=[SDK_ROOT / 'README.md', SDK_ACCEPT], plan_missing=plan_file != SDK_PLAN_LIVE,
    plugged_into=sdk_plugged, proof=sdk_proof)
for app in sdk_plugged:
    link(f'app:{app.lower()}', 'sdk', 'uses', 'plugged into SDK')
link('director', 'sdk', 'runs-on', 'runs on')
link('conductor', 'sdk', 'runs-on', 'runs on')

# ---------------------------------------------------------------------------------------------- 5. Missions (Director state)
skill_names = sorted((p.name for p in SKILLS.iterdir() if p.is_dir() and not p.name.startswith('.')), key=len, reverse=True)
skill_names = [s for s in skill_names if len(s) > 4 and s not in ('synced', 'image')]
AGENTS = {'Javar': 'agent:javar', 'Javante': 'agent:javante', 'Hermes': 'agent:hermes', 'Manus': 'agent:manus', 'OpenClaw': 'agent:openclaw'}
mission_skill_evidence = 0
PROJECTS = [('Dynamite Lighting / Natural Sanitation', r'dynamite|natural.?sanitation'), ('Hot Tub Launch', r'hot.?tub|\bhtl\b'),
            ('Lone Star Spas', r'lone.?star'), ('Sun Pool', r'sun.?pool'), ('Revstead', r'revstead|fenc'),
            ('PowersportsLaunch', r'powersport'), ('Increase ROAS', r'increase.?roas|tree.?service')]
parked = 0
for block in re.split(r'(?m)^## Mission: ', state_text)[1:]:
    field = lambda k: (re.search(rf'^{k}: (.*)$', block, re.M) or [None, ''])[1].strip()
    name = block.split('\n', 1)[0].strip()[:80]
    status = (field('STATUS') or '?').split()[0]
    if status in ('PARKED', 'MISSION_COMPLETE', '?'):
        parked += status == 'PARKED'
        continue
    proj_txt = (name + ' ' + field('PROJECT') + ' ' + field('MISSION_ID')).lower()
    project = next((p for p, pat in PROJECTS if re.search(pat, proj_txt)), 'Personal / system')
    mid = 'mission:' + (field('MISSION_ID') or re.sub(r'\W+', '-', name.lower()))[:80]
    q = next((x for x in quiet if x['name'][:60] == name[:60]), None)
    st = 'you' if status == 'WAITING_ON_ALEX' or (q and q['bucket'] == 'needs me') else 'stuck' if q and q['bucket'] == 'looks stuck' else 'done' if q and q['bucket'] == 'looks done' else 'ok'
    todo = {'you': 'Answer it in the Director chat.', 'stuck': 'Ask the Director why it has not moved and what unblocks it.',
            'done': 'Tell the Director to close or park it.', 'ok': 'Nothing.'}[st]
    why = q['why'] if q else ('Planned, not started.' if status == 'PLANNED' else 'It moved in the last 5 days.')
    owner = first_sentence(field('OWNER_OUTCOME'), 160)
    add(mid, 'missions', 'mission', name, owner or name,
        explain(f'A Director mission: {owner or name}', 'yes' if st in ('you', 'stuck') else 'maybe' if st == 'done' else 'no', why, todo),
        status={'you': 'you', 'stuck': 'broken', 'done': 'watch', 'ok': 'ok'}[st], sources=[DIRECTOR / 'DIRECTOR_STATE.md'],
        review=parse_review(block), project=project, mission_status=status, bucket=q['bucket'] if q else None, quiet_days=q['quiet_days'] if q else None)
    link('director', mid, 'runs', 'runs')
    if st == 'you':
        needs_me.append({'title': name, 'why': why, 'todo': todo, 'node_id': mid})
    # Which skills/agents this mission used: its own block plus its mission graph file(s).
    text = block
    for g in re.findall(r'mission-graphs/[\w.\-]+', block):
        text += read(DIRECTOR / g, 200_000)
    for s in skill_names:
        if s in ('alex-director', 'alex-workflow-conductor'):
            continue
        # Hyphenated names are distinctive; one-word names only count when written as a skill (`name` or a skills path).
        pat = (r'(?<![\w-])' + re.escape(s) + r'(?![\w-])') if '-' in s else (r'`' + re.escape(s) + r'`|skills/' + re.escape(s) + r'\b')
        if re.search(pat, text):
            sid = f'skill:{s}'
            if sid not in nodes:
                desc = skill_description(s)
                add(sid, 'skills', 'skill', s, first_sentence(desc) or f'Skill "{s}"',
                    explain(f'A how-to guide your agents follow: {first_sentence(desc) or s}', 'no', 'Nothing on it is flagged.', 'Nothing.'),
                    sources=[SKILLS / s / 'SKILL.md'])
            link(mid, sid, 'used', 'used skill', str(DIRECTOR / 'DIRECTOR_STATE.md'))
            mission_skill_evidence += 1
if parked:
    add('mission:parked', 'missions', 'mission', f'Parked missions ({parked})', 'Missions the Director parked on purpose.',
        explain(f'{parked} missions the Director paused on purpose.', 'no', 'Parked work does not move until someone restarts it.', 'Nothing.'), status='ok')
    link('director', 'mission:parked', 'runs', 'parked')

# ---------------------------------------------------------------------------------------------- 6. Connectors + 7. business systems
add('hub:composio', 'connectors', 'hub', 'Composio', 'The one door your AI apps use to reach outside apps.',
    explain('Composio is the one door your agents use to reach outside apps like GoHighLevel, Gmail or Meta.',
            'maybe', 'If it is down, every app task stops. The map does not call Composio, so it can\'t prove it is up.', 'Nothing.'))
for app in ('app:claude', 'app:claude-code', 'app:codex', 'app:cursor', 'app:chatgpt'):
    link(app, 'hub:composio', 'reaches', 'reaches apps through', str(INSTR / 'shared.md'))
for stem, kits in card_routes.items():
    cid = f'card:{stem}'
    system = nodes[cid]['meta']['system']
    registry = json.loads(read(HOME / '.agents/registry/connectors' / f'{stem}.json') or '{}')
    if registry.get('kind') == 'skill':
        if stem == 'alex-reviewer':
            link(cid, 'reviewer', 'route', 'review skill', str(CARDS / f'{stem}.md'))
        continue
    for k in kits:
        tid = f'toolkit:{k}'
        if tid not in nodes:
            add(tid, 'connectors', 'toolkit', k, f'Composio connection "{k}" (named in the {system} card).',
                explain(f'A Composio connection called "{k}". Agents use it to reach {system}.', 'no',
                        'Named in its card. The map does not log in to check it.', 'Nothing.'), status='unknown', sources=[CARDS / f'{stem}.md'])
            link('hub:composio', tid, 'contains', 'connection')
        link(cid, tid, 'route', 'route', str(CARDS / f'{stem}.md'))
        nodes[tid]['meta'].setdefault('systems', [])
        if system not in nodes[tid]['meta']['systems']:
            nodes[tid]['meta']['systems'].append(system)
    if not kits and stem != 'composio':
        local_id = f'local:{stem}'
        add(local_id, 'connectors', 'local', f'{system} (local route)', nodes[cid]['meta']['route_text'][:160],
            explain(f'{system} is reached without Composio: {nodes[cid]["meta"]["route_text"][:140]}', 'no', 'Its card says this on purpose.', 'Nothing.'),
            sources=[CARDS / f'{stem}.md'])
        link(cid, local_id, 'route', 'route', str(CARDS / f'{stem}.md'))
for lid, ln in live_nodes.items():
    if ln['kind'] == 'connector':
        cid = f'mcp:{ln["label"]}'
        add(cid, 'connectors', 'local', ln['label'], 'A local plug some apps load directly (outside Composio).',
            explain(f'"{ln["label"]}" is a local plug that runs on your Mac, outside Composio.', 'no', 'Scanned live; nothing flagged.', 'Nothing.'))
        for e in live.get('edges', []):
            if e['target'] == lid:
                link(e['source'], cid, 'uses', 'uses')
ORGO = HOME / 'Projects' / 'master-connector-repo' / 'work' / '2026-10-07_orgo-fleet-control'
if ORGO.exists():
    add('host:openclaw', 'connectors', 'local', 'OpenClaw (Orgo computer)', 'A cloud computer on Orgo that hosts some connectors.',
        explain('OpenClaw is a cloud computer you rent on Orgo. Some connectors run on it.', 'maybe',
                'The map can see its control files, not whether it is switched on.', 'Nothing.'), status='unknown', sources=[ORGO])
if 'mcp:director-observatory' in nodes and 'card:director-observatory' in nodes:
    link('card:director-observatory', 'mcp:director-observatory', 'route', 'route')

# Skill -> connector / card / other skill mentions (read each displayed SKILL.md)
card_alias: dict[str, str] = {}
for f in CARDS.glob('*.md'):
    for a in (frontmatter(read(f, 3000)).get('aliases', '') + ',' + f.stem).split(','):
        a = a.strip().lower()
        if len(a) > 3:
            card_alias[a] = f'card:{f.stem}'
for sid in [n for n in nodes if n.startswith('skill:')]:
    text = read(SKILLS / sid.split(':', 1)[1] / 'SKILL.md', 60_000)
    low = text.lower()
    for a, cid in card_alias.items():
        if re.search(r'(?<![\w-])' + re.escape(a) + r'(?![\w-])', low):
            link(sid, cid, 'mentions', 'uses card', str(SKILLS / sid.split(':', 1)[1] / 'SKILL.md'))
    for other in [n for n in nodes if n.startswith('skill:') and n != sid]:
        if re.search(r'(?<![\w-])' + re.escape(other.split(':', 1)[1]) + r'(?![\w-])', text):
            link(sid, other, 'mentions', 'uses skill', str(SKILLS / sid.split(':', 1)[1] / 'SKILL.md'))

# Which app loads each skill on the map: Codex reads ~/.agents/skills directly; Claude and Cursor need a link.
for sid in [n for n in nodes if n.startswith('skill:')]:
    name = sid.split(':', 1)[1]
    by = ['Codex'] if (SKILLS / name).exists() else []
    by += [app for app, d in (('Claude', HOME / '.claude/skills'), ('Cursor', HOME / '.cursor/skills')) if (d / name).exists()]
    nodes[sid]['meta']['loaded_by'] = by
    nodes[sid]['explain']['why'] = (f'Loaded by {", ".join(by)}. ' if by else 'No app loads it right now. ') + nodes[sid]['explain']['why']
for nid in ('director', 'conductor'):
    sk = 'alex-director' if nid == 'director' else 'alex-workflow-conductor'
    nodes[nid]['meta']['loaded_by'] = ['Codex'] + [app for app, d in (('Claude', HOME / '.claude/skills'), ('Cursor', HOME / '.cursor/skills')) if (d / sk).exists()]

# Observatory sits on the side rail
add('observatory', 'rail', 'observatory', 'Observatory', 'Read-only camera on Director: replays what ran, what got stuck and what was proven.',
    explain('The Observatory is a read-only camera on your Director: it shows what ran, what got stuck and what was proven.',
            'no', 'It only watches; it cannot change anything.', 'Nothing.'), sources=[CARDS / 'director-observatory.md'])

# ---------------------------------------------------------------------------------------------- 8. Rule audit -> red lines
verdicts = json.loads(read(VERDICTS) or '{}')
audit_files = [INSTR / 'shared.md', INSTR / 'claude.md', INSTR / 'codex.md', HOME / '.cursor/rules/agent-routing.mdc',
               HOME / '.cursor/rules/grok-bot-standing.mdc', HOME / '.cursor/rules/observatory-first.mdc', DIRECTOR / 'AGENTS.md', GATES]
audit = {'files': [], 'tool_pairs': 0, 'unreviewed': [], 'conflicts': [], 'one_agent': []}
for f in audit_files:
    pairs = None
    if RULE_AUDIT_BIN.exists() and f.exists():
        try:
            r = subprocess.run([str(RULE_AUDIT_BIN), '-f', str(f), '--format', 'json'], capture_output=True, text=True, timeout=60)
            pairs = len(json.loads(r.stdout).get('contradictions') or [])
        except Exception:
            pairs = None
    reviewed = (verdicts.get('reviewed_pairs') or {}).get(f.name, 0)
    audit['files'].append({'file': tilde(f), 'tool_pairs': pairs, 'reviewed_spurious': min(reviewed, pairs or 0)})
    if pairs:
        audit['tool_pairs'] += pairs
        if pairs > reviewed:
            audit['unreviewed'].append({'file': tilde(f), 'new_pairs': pairs - reviewed})
for c in verdicts.get('conflicts', []):
    audit['conflicts'].append(c)
    if c['a'] in nodes and c['b'] in nodes:
        edges.append({'id': c['id'], 'source': c['a'], 'target': c['b'], 'kind': 'conflict', 'label': c['title'], 'evidence': ', '.join(c['sources'])})
        for side in (c['a'], c['b']):
            if nodes[side]['status'] == 'ok':
                nodes[side]['status'] = 'conflict'
    if c['care'] == 'yes':
        needs_me.append({'title': c['title'], 'why': c['why'], 'todo': c['todo'], 'node_id': c['b']})
ONE_AGENT = [('rule:cursor-grok-bot', 'app:cursor'), ('rule:cursor-observatory', 'app:cursor')]
for line in [l.strip('- ').strip() for l in read(INSTR / 'claude.md').splitlines() if l.startswith('- ')]:
    audit['one_agent'].append({'agent': 'Claude', 'rule': line[:200], 'source': '~/.agents/instructions/claude.md'})
for line in [l.strip('- ').strip() for l in read(INSTR / 'codex.md').splitlines() if l.startswith('- ')]:
    audit['one_agent'].append({'agent': 'Codex', 'rule': line[:200], 'source': '~/.agents/instructions/codex.md'})
for rid, app in ONE_AGENT:
    if rid in nodes and app in nodes:
        edges.append({'id': f'oneagent:{rid}', 'source': app, 'target': rid, 'kind': 'one-agent', 'label': 'only Cursor sees this', 'evidence': nodes[rid]['sources'][0]})
        audit['one_agent'].append({'agent': 'Cursor', 'rule': nodes[rid]['purpose'], 'source': nodes[rid]['sources'][0]})
for p in live_problems:
    if p['severity'] in ('high', 'medium'):
        needs_me.append({'title': p['title'], 'why': p['detail'], 'todo': 'Tell me to fix it (backup first).', 'node_id': p['node_ids'][0] if p['node_ids'] else ''})
if not sdk_plugged:
    needs_me.insert(0, {'title': 'Your SDK is not plugged into any AI app', 'why': 'It is built, verified and answers with 23 tools, but Claude, Codex and Cursor do not load it.',
                        'todo': 'Run the Codex plug-in command Claude gave you, then reopen Codex.', 'node_id': 'sdk'})
if nodes.get('sdk', {}).get('meta', {}).get('plan_missing'):
    needs_me.append({'title': 'Your SDK build plan file is missing', 'why': 'outputs/ai-money-agent-harness-build.md is gone from the "can" folder; the map is grading from an Oct 8 backup.',
                     'todo': 'Tell me where it moved (Drive?) or let me restore the backup copy.', 'node_id': 'sdk'})

# ---------------------------------------------------------------------------------------------- 9. Catalog merge (counts before/after)
live_skill = {p.name.lower() for p in SKILLS.iterdir() if p.is_dir()}
for app_dir in (HOME / '.claude/skills', HOME / '.cursor/skills'):
    if app_dir.exists():
        live_skill |= {p.name.lower() for p in app_dir.iterdir()}
live_cards = {f.stem.lower(): f'card:{f.stem}' for f in CARDS.glob('*.md')}
live_card_titles = {nodes[c]['meta']['system'].lower(): c for c in live_cards.values()}
live_repo_names = {Path(n['meta'].get('path', '')).name.lower(): n for n in live_nodes.values() if n['kind'] == 'repo'}
live_names = {n['label'].lower(): nid for nid, n in nodes.items()}
live_names.update({a: c for a, c in card_alias.items()})


def norm(s: str) -> str:
    s = re.sub(r'^(AI surface|SDK|Saved skill|Tool card)\s*·\s*', '', s, flags=re.I)
    return re.sub(r'\s*\(.*?\)\s*', ' ', s).strip().lower()


matched, unmatched, hidden_hist = [], [], 0
before = {'total': len(components), 'matched': 0,
          'connected': len({x for r in cat.get('relationships', []) for x in (r['source_id'], r['target_id'])}),
          'purposed': sum(1 for c in components if not JUNK_PURPOSE.search(c.get('purpose') or ''))}
for c in components:
    name, kind = c['name'], c['kind']
    n = norm(name)
    hit = None
    if kind == 'Saved skill' and n in live_skill:
        hit = ('skill', f'skill:{n}', SKILLS / n / 'SKILL.md')
    elif kind == 'Tool card':
        cid = live_card_titles.get(n) or live_cards.get(n.replace(' ', '-')) or card_alias.get(n)
        if cid:
            hit = ('card', cid, Path(nodes[cid]['sources'][0].replace('~', str(HOME))))
    elif kind in ('app', 'AI surface', 'existing'):
        key = n.split(' / ')[0].split(' on ')[0].strip()
        nid = live_names.get(key) or card_alias.get(key) or (f'mcp:{key}' if f'mcp:{key}' in nodes else None)
        if nid:
            hit = ('app', nid, None)
    elif kind == 'asset':
        al = str(c.get('aliases') or '')
        m = re.search(r'GitHub\|Repository\|[\w.-]+/([\w.-]+)', al)
        if m and m.group(1).lower() in live_repo_names:
            hit = ('repo', live_repo_names[m.group(1).lower()]['id'], None)
    elif kind == 'Source file':
        sid = name.split(' / ')[0]
        p = sources_by_id.get(sid, {}).get('original_path')
        if p and Path(p).exists():
            hit = ('file', None, Path(p))
    if hit:
        kind_, nid, path = hit
        purpose = c.get('purpose') or ''
        better = ''
        if kind_ == 'skill':
            better = first_sentence(skill_description(n))
        elif kind_ == 'card' and nid in nodes:
            better = nodes[nid]['purpose']
        elif nid and nid in nodes:
            better = nodes[nid]['purpose']
        final = better or ('' if JUNK_PURPOSE.search(purpose) else purpose)
        connected = bool(nid and (nid in nodes) and any(e['source'] == nid or e['target'] == nid for e in edges)) or kind_ == 'skill'
        matched.append({'id': c['id'], 'name': name, 'kind': kind, 'live': nid, 'purpose': final, 'connected': connected})
        if nid in nodes:
            nodes[nid]['meta'].setdefault('catalog', []).append({'name': name, 'kind': kind, 'workbook_purpose': purpose})
            if JUNK_PURPOSE.search(nodes[nid]['purpose'] or '') and not JUNK_PURPOSE.search(purpose):
                nodes[nid]['purpose'] = purpose
    elif c.get('category') == 'historical':
        hidden_hist += 1
    else:
        cloud = kind in ('asset', 'individual asset', 'asset section', '1Password item')
        unmatched.append({'name': name, 'kind': kind, 'drawer': 'cloud' if cloud else 'gone',
                          'purpose': '' if JUNK_PURPOSE.search(c.get('purpose') or '') else c['purpose'][:160]})
after = {'total': len(components), 'matched': len(matched),
         'connected': sum(1 for m in matched if m['connected']),
         'purposed': sum(1 for m in matched if m['purpose']) + sum(1 for u in unmatched if u['purpose'])}
map_purposed = sum(1 for n in nodes.values() if n['purpose'] and not JUNK_PURPOSE.search(n['purpose']))

# ---------------------------------------------------------------------------------------------- Restructure (Alex 2026-10-11)
# Cards live ON their connector (one box = connection + its rule + login check). Rules and guards are one shared set
# shown on a side rail; each app box only lists what is different for that app.
route = json.loads(read(DATA / 'route-check.json') or '{}')
live_ids = {tk: {a.get('id') for a in accs if a.get('status') == 'active'} for tk, accs in (route.get('toolkits') or {}).items()}
login_problems = []
for cid in [n for n in list(nodes) if n.startswith('card:')]:
    card = nodes[cid]
    stem = cid.split(':', 1)[1]
    text = card['meta'].get('route_text', '') + ' ' + card['purpose']
    targets = [e['target'] for e in edges if e['source'] == cid and e['kind'] == 'route']
    if stem == 'composio':
        targets = ['hub:composio']
    for t in targets:
        if t not in nodes:
            continue
        tn = nodes[t]
        tn['meta'].update(card=stem, card_rule_lines=card['meta'].get('rule_lines', []), card_file=card['sources'][0] if card['sources'] else '',
                          system=card['meta'].get('system'))
        if t != 'reviewer':
            tn['label'] = f"{card['meta'].get('system')} · {tn['label']}" if not tn['label'].startswith(card['meta'].get('system', '~')) else tn['label']
            tn['purpose'] = '; '.join(card['meta'].get('rule_lines', [])) or tn['purpose']
        kit = t.split(':', 1)[1] if t.startswith('toolkit:') else None
        if kit and kit in live_ids:
            named = set(re.findall(rf'\b({re.escape(kit)}_[a-z]+-[a-z]+)\b', text))
            missing = sorted(x for x in named if x not in live_ids[kit])
            tn['meta'].update(route_checked=route.get('checked_at'), logins_live=sorted(live_ids[kit]), logins_card=sorted(named), logins_missing=missing)
            if missing:
                tn['status'] = 'broken'
                why = f'The {card["meta"].get("system")} card says to use login {", ".join(missing)}, but that login is not on your Composio account (live: {", ".join(sorted(live_ids[kit]))}).'
                tn['explain'] = explain(f'Your {card["meta"].get("system")} connection in Composio, with its routing card.', 'yes', why,
                                        f'Update the {card["meta"].get("system")} card to the live login, or reconnect the missing one.')
                login_problems.append({'title': f'{card["meta"].get("system")} card names a login that is gone', 'why': why,
                                       'todo': f'Fix the login name in {card["sources"][0] if card["sources"] else "the card"}.', 'node_id': t})
            else:
                tn['status'] = 'ok' if live_ids[kit] else 'broken'
                tn['explain'] = explain(f'Your {card["meta"].get("system")} connection in Composio. Card rule: ' + '; '.join(card['meta'].get('rule_lines', [])) + '.',
                                        'no', f'Connected and active (checked {str(route.get("checked_at", ""))[:16].replace("T", " ")} UTC); the card\'s login matches.', 'Nothing.')
        # skills that used the card now point at the connector itself
        for e in edges:
            if e['target'] == cid:
                e['target'] = t
        if card['meta'].get('catalog'):
            tn['meta'].setdefault('catalog', []).extend(card['meta']['catalog'])
    nodes.pop(cid)
for e in edges:
    if e['target'] == 'local:alex-reviewer':
        e['target'] = 'reviewer'
edges[:] = [e for e in edges if e['source'] in nodes and e['target'] in nodes]
needs_me[:0] = login_problems
# Per-app differences on the app box; shared rules/guards drop their per-app wires.
for aid in [n for n in nodes if n.startswith('app:')]:
    app = aid.split(':', 1)[1]
    only = [nodes[r]['label'] for r in nodes if r.startswith('rule:') and nodes[r]['meta'].get('followed_by') == [app]]
    hooks = sorted({nodes[e['target']]['label'] for e in edges if e['source'] == aid and e['kind'] == 'runs'})
    conns = nodes[aid]['meta'].get('connectors', [])
    nodes[aid]['meta'].update(only_rules=only, hooks=hooks)
    diff = []
    if only: diff.append(f'{len(only)} rule(s) only it follows')
    if hooks: diff.append(f'guards: {", ".join(hooks)}')
    if conns: diff.append(f'local plugs: {", ".join(conns)}')
    if app == 'chatgpt': diff.append('gets none of your rule files')
    if app == 'manus': diff.append('own Manus skills, not your shared rules')
    nodes[aid]['meta']['differences'] = diff
for n in nodes.values():
    if n['layer'] == 'rules':
        n['layer'] = 'rail-rules'
edges[:] = [e for e in edges if e['kind'] not in ('follows', 'enforced', 'governs') and not (e['kind'] == 'runs' and e['target'].startswith(('hook:', 'check:')))]

# ---------------------------------------------------------------------------------------------- 10. Observability (Langfuse)
# Who records what the agents do (Alex 2026-10-14). The map makes no network call: every fact comes from the receipt,
# the Langfuse card and Claude Code's settings file. A sender is "live" only when the receipt shows its traces landed.
LF_RECEIPT = ROOT / 'reviews' / 'receipts' / '2026-10-14-langfuse' / 'observability.md'
LF_CARD = CARDS / 'langfuse.md'
LF_REL = 'reviews/receipts/2026-10-14-langfuse/observability.md'  # repo-relative, so the cite survives the merge
LF_URL = 'https://us.cloud.langfuse.com/project/cmv733aoq01e7ad0mfeqexnrx'
LF_DASH = LF_URL + '/dashboards/cmv7h0unq0500ad0ey1io48r9'  # Agent fleet dashboard (receipt)
lf_receipt = read(LF_RECEIPT)
cc_settings = read(HOME / '.claude' / 'settings.json')
cc_wired = 'langfuse_otel_headers.py' in cc_settings and 'cloud.langfuse.com' in cc_settings
if lf_receipt:
    seen = set(re.findall(r'(?m)^LIVE: ([a-z0-9_-]+)$', lf_receipt))  # environments whose traces the receipt saw land
    SENDERS = [
        # node, name, state, env, how, proof (receipt row must say it)
        ('app:claude-code', 'Claude Code', 'live' if cc_wired and 'default' in seen else 'unknown', 'default',
         'OpenTelemetry, traces only; prompt and tool text redacted (Claude Code default, no OTEL_LOG_* switch set); keys from 1Password at run time',
         'traces seen 2026-10-14'),
        ('agent:javar-lab', 'JAVAR-LAB', 'live' if 'javar-lab' in seen else 'unknown', 'javar-lab',
         'Hermes langfuse plugin (env javar-lab)', 'traces seen 2026-10-14'),
        ('agent:javar', 'Javar (live)', 'live' if 'javar' in seen else 'planned', 'javar', 'Hermes langfuse plugin (env javar)',
         'traces seen 2026-10-14' if 'javar' in seen else 'no traces seen'),
        (None, 'Codex', 'not wired', '', 'nothing sends from Codex', 'not wired'),
    ]
    add('agent:javar-lab', 'agents', 'agent', 'JAVAR-LAB', 'Hermes agent whose runs reach Langfuse as environment "javar-lab".',
        explain('JAVAR-LAB is a Hermes agent that sends its runs to Langfuse under the name "javar-lab".',
                'no', 'Its traces were seen landing in Langfuse (see the receipt). Host, model and role are not checked by the map.', 'Nothing.'),
        status='ok', sources=[LF_REL], host='not checked', model='not checked', tools='not checked')
    live_n = sum(1 for s in SENDERS if s[2] == 'live')
    planned_n = sum(1 for s in SENDERS if s[2] == 'planned')
    add('obs:langfuse', 'observability', 'observability', 'Langfuse (Increase Roas)',
        f'Records runs from the senders below as traces. {live_n} live, {planned_n} planned, Codex not wired.',
        explain('Langfuse is the flight recorder for your agents: each run shows up as a trace with its steps, tools and cost.',
                'maybe', 'Only senders marked live are recorded. Codex sends nothing, and a Hermes agent whose tracing breaks goes quiet without an error.',
                'Open the Agent fleet dashboard in Langfuse for runs, spend, errors and speed per agent.'),
        status='ok', sources=[LF_REL, LF_CARD], url=LF_URL, dashboard=LF_DASH, plan='Hobby (free, 50k units/month, 30-day retention): from Alex\'s brief 2026-10-14, not checked',
        senders=[{'name': n, 'state': st, 'env': env, 'how': how, 'proof': pr, 'node': nid} for nid, n, st, env, how, pr in SENDERS])
    for nid, n, st, env, how, pr in SENDERS:
        if nid and nid in nodes and st in ('live', 'planned'):
            link(nid, 'obs:langfuse', 'traces', f'sends traces ({st})', LF_REL)
            edges[-1]['state'] = st
    if 'toolkit:custom_langfuse_mcp' in nodes:
        link('toolkit:custom_langfuse_mcp', 'obs:langfuse', 'reads', 'agents read and write it through', str(LF_CARD))

# ---------------------------------------------------------------------------------------------- Real chain + evidence rule
# Director AGENTS.md line 7: "You judge missions; controllers do the work." Controllers load the Conductor.
AG = str(DIRECTOR / 'AGENTS.md')
nodes['conductor']['layer'] = 'conductor'
for e in edges:
    if e['source'] == 'director' and e['kind'] == 'runs':
        e.update(source='conductor', id=e['id'].replace('director', 'conductor', 1), label='does the work', evidence=tilde(AG) + ' line 7 ("controllers do the work")')
for e in [e for e in edges if e['source'] == 'conductor' and e['kind'] == 'runs']:
    link('director', e['target'], 'judges', 'judges', AG + ' line 7 ("You judge missions")')
edges[:] = [e for e in edges if e['kind'] != 'runs-on']  # "Director runs on SDK" had no evidence
if sdk_plugged:
    link('conductor', 'sdk', 'can-use', f'can use (through {", ".join(sdk_plugged)})', str(HOME / '.codex/config.toml'))
EVIDENCE = {
    'talks': 'you use these apps (scanned live on this Mac)',
    'dispatches': tilde(AG) + ' line 12 (every NEXT_PLAY names alex-workflow-conductor)',
    'loads': 'alex-director skill linked in this app (scanned live)',
    'uses': 'this app\'s MCP settings (scanned live)',
    'contains': 'connection listed in its routing card',
}
for e in edges:
    if not e.get('evidence') and e['kind'] in EVIDENCE:
        e['evidence'] = EVIDENCE[e['kind']]
    e['proven'] = bool(e.get('evidence'))
unproven = [e for e in edges if not e['proven']]

# ---------------------------------------------------------------------------------------------- Observatory rail
def rail_row(layer: str, title: str) -> dict:
    xs = [n for n in nodes.values() if n['layer'] == layer]
    return {'layer': layer, 'title': title,
            'running': sum(1 for n in xs if n['status'] in ('ok',)),
            'stuck': sum(1 for n in xs if n['status'] in ('broken', 'you', 'conflict')),
            'watch': sum(1 for n in xs if n['status'] in ('watch',)),
            'unknown': sum(1 for n in xs if n['status'] == 'unknown'), 'total': len(xs)}


rail = [rail_row(l, t) for l, t in (('apps', 'AI apps'), ('rail-rules', 'Shared rules and guards'), ('director', 'Director'), ('conductor', 'Conductor'),
                                    ('observability', 'Observability'), ('missions', 'Missions'), ('skills', 'Skills'), ('connectors', 'Connectors'))]
rail.insert(3, {'layer': 'engine', 'title': 'SDK engine room' + ('' if sdk_plugged else ' (not plugged in)'), 'running': 0,
                'stuck': sum(1 for s in sdk if s['status'] == 'gap'), 'watch': sum(1 for s in sdk if s['status'] == 'partial'),
                'unknown': 0, 'total': 8, 'proven': sum(1 for s in sdk if s['status'] == 'proven')})
trace_last = dir_live.get('last_trace')

OUT.write_text(json.dumps({
    'built_at': datetime.now(timezone.utc).isoformat(),
    'scanned_at': live.get('scanned_at'),
    'layers': [['you', 'You'], ['apps', 'AI apps'], ['director', 'Director (decides)'], ['conductor', 'Conductor (does the work through the controllers)'], ['agents', 'Your agents (who does what, top-down)'], ['observability', 'Observability (who records what the agents do)'],
               ['engine', 'Engine room (SDK)'], ['missions', 'Customers and projects (click one to open its missions)'], ['skills', 'Skills those missions used'],
               ['connectors', 'Connections (each with its routing card)']],
    'nodes': list(nodes.values()), 'edges': edges, 'sdk': sdk, 'route_check': route.get('checked_at'),
    'evidence': {'lines': len(edges), 'proven': len(edges) - len(unproven), 'unproven': [{'from': nodes[e['source']]['label'], 'to': nodes[e['target']]['label'], 'kind': e['kind']} for e in unproven]}, 'sdk_plan': {'file': tilde(plan_file), 'missing_live_copy': plan_file != SDK_PLAN_LIVE},
    'rail': rail, 'last_trace': trace_last, 'needs_me': needs_me, 'rule_audit': audit,
    'catalog': {'before': before, 'after': after, 'hidden_historical': hidden_hist, 'unmatched': unmatched, 'matched_sample': matched[:50],
                'map_nodes': len(nodes), 'map_nodes_purposed': map_purposed, 'mission_skill_links': mission_skill_evidence},
}, indent=1))
print(json.dumps({'nodes': len(nodes), 'edges': len(edges), 'needs_me': len(needs_me), 'catalog_before': before, 'catalog_after': after,
                  'hidden_historical': hidden_hist, 'drawer_gone': sum(1 for u in unmatched if u['drawer'] == 'gone'),
                  'drawer_cloud': sum(1 for u in unmatched if u['drawer'] == 'cloud'), 'map_purposed': f'{map_purposed}/{len(nodes)}',
                  'rule_pairs': audit['tool_pairs'], 'unreviewed': audit['unreviewed']}, indent=1))
