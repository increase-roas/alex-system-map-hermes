#!/usr/bin/env python3
"""Bounded Hermes-native shell hook adapter. Stdlib JSON mode; optional PyYAML for general YAML. Deny by default.

Invocation: python3 -B /absolute/path/hermes_guard.py --policy /absolute/policy.json
stdin: the JSON produced by agent/shell_hooks.py::_serialize_payload:
  {"hook_event_name":"pre_tool_call", "tool_name":"read_file",
   "tool_input":{"path":"/absolute/cards/github.md"}, "session_id":"opaque",
   "cwd":"/workspace", "profile":"default",
   "extra":{"tool_call_id":"opaque", "task_id":"opaque"}}
post_tool_call uses the same envelope, with extra.result (JSON string from
read_file), extra.status, extra.error_type/error_message. pre_verify uses null
tool_name/tool_input and extra.coding/attempt/changed_paths/final_response.

Use --print-hook-config --policy ... to print an exact JSON-formatted YAML
hooks block for the active Hermes profile config.yaml. MERGE, do not replace
its other settings. Hermes hook consent remains required; no auto-accept is
set. HERMES_HOME must match policy.home, which names the active profile home.
The policy is trusted operator configuration, not tool input. routes maps exact
runtime MCP names to {server, card}; it is not discovered by guessing prefixes.
State writes use the operator-selected absolute state_dir, not tool arguments.
Only our test executions restrict state writes to hermes-fixtures.

Supported assets: only home/skills/**/SKILL.md and home/config.yaml. Without PyYAML both use
JSON-formatted YAML (valid YAML) in this narrow template; SKILL.md has ---
fences around a JSON mapping plus nonempty Markdown body. General YAML needs
PyYAML in the exact hook Python interpreter; loaded with safe parsing when
available, never installed automatically. JSON mode has no dependencies.
Custom skill policy (not Hermes caps): name equals folder, description >=20
characters includes Use when, <=500 body lines, direct local links within one
subdirectory, no chained local links. Bare/dynamic references are not resolved.
MCP env/header credentials may use ${ENV} or ${env:ENV}, and Authorization
may use Bearer ${ENV}. Plaintext credential values and URL credentials are
denied, never printed. This validates references, not their live availability.

Unsupported: skill_manage (including every operations batch), patch, terminal,
execute_code, delegation, manage_connections, connector aggregates, unknown
MCP routes, external/project/plugin skills and alternate profile configuration.
All are denied at pre_tool_call. Every nested aggregate-shaped input is denied,
even on a mapped route. Only scalar/object parameters without aggregate keys
or arrays of objects are supported. This is not a generic MCP permission engine.
No simulation or pre-write protection for terminal arbitrary edits. Post calls
observe on-disk assets; observer returns cannot stop a tool or undo its effect.
pre_verify requests continuation, not guaranteed enforcement: Hermes fires it
only for its bounded edited-code gate and may exhaust continuation attempts.
Skipped/unapproved hooks, out-of-band edits, remote filesystems, other plugins'
argument modifications, malicious same-user state/policy tampering, and MCP
server execution/startup outside tool dispatch are not covered. Not installed,
not fleet/live verified, no A-level enforcement claim.

Sources verified 2026-10-12, upstream f594424e58f18ebc2607decaa72f300e0a26a24b:
https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks
https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp
https://hermes-agent.nousresearch.com/docs/user-guide/features/skills
https://github.com/NousResearch/hermes-agent/blob/f594424e58f18ebc2607decaa72f300e0a26a24b/agent/shell_hooks.py
https://github.com/NousResearch/hermes-agent/blob/f594424e58f18ebc2607decaa72f300e0a26a24b/hermes_cli/plugins.py
https://github.com/NousResearch/hermes-agent/blob/f594424e58f18ebc2607decaa72f300e0a26a24b/tools/file_operations.py
https://github.com/NousResearch/hermes-agent/blob/f594424e58f18ebc2607decaa72f300e0a26a24b/tools/mcp_tool_schema.py
"""
import argparse
import contextlib
import fcntl
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import shlex
import sys
import time

FIXTURES = Path(__file__).resolve().parent / 'hermes-fixtures'
EVENTS = {'pre_tool_call', 'post_tool_call', 'pre_verify'}
AGGREGATE_KEYS = {'actions', 'operations', 'tools', 'tool_calls', 'requests', 'batch', 'calls', 'multi_tool_use'}


class Denied(ValueError):
    """Safe constant-text diagnostic, never echo untrusted argument values."""


def fail(message):
    raise Denied(message)


def object_pairs(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            fail('duplicate JSON key is unsupported')
        obj[key] = value
    return obj


def parse_json(text):
    try:
        return json.loads(text, object_pairs_hook=object_pairs)
    except (ValueError, TypeError):
        fail('invalid JSON; general YAML parser prerequisite for non-JSON YAML')


def parse_yaml(text):
    # Preserve strict JSON duplicate-key behavior; JSON is a YAML subset.
    try:
        return parse_json(text)
    except Denied:
        if text.lstrip().startswith(('{', '[')):
            raise
    try:
        yaml = importlib.import_module('yaml')
    except ImportError:
        fail('general YAML parser prerequisite: PyYAML missing from hook interpreter')
    class UniqueSafeLoader(yaml.SafeLoader):
        pass
    def mapping(loader, node, deep=False):
        loader.flatten_mapping(node)
        pairs = loader.construct_pairs(node, deep=deep)
        return object_pairs(pairs)
    UniqueSafeLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)
    try:
        return yaml.load(text, Loader=UniqueSafeLoader)
    except Denied:
        raise
    except Exception:
        fail('invalid general YAML')


def local_links(text):
    from urllib.parse import unquote
    destinations = re.findall(r"!?\[[^\]\n]*\]\(([^\n]*?)\)", text)
    destinations += re.findall(r"(?m)^\s*\[[^\]\n]+\]:\s*(\S+)", text)
    links = []
    for destination in destinations:
        target = destination.strip().split(' "', 1)[0].split(" '", 1)[0].strip('<>')
        if not target or target.startswith('#') or re.match(r'[A-Za-z][A-Za-z0-9+.-]*:', target):
            continue
        if target.startswith('//'):
            fail('protocol-relative skill reference unsupported')
        links.append(unquote(target.split('#', 1)[0]))
    return links


def digest(data):
    return hashlib.sha256(data).hexdigest()


def inside(path, root):
    return path.is_relative_to(root)


def clean_path(path, root=None):
    if not isinstance(path, str) or not path or not Path(path).is_absolute():
        fail('only absolute local paths are supported')
    p = Path(path)
    # Resolve only after inspecting the lexical path; a symlink must not escape
    # or silently redirect a protected asset/card/state location.
    for part in (p, *p.parents):
        if part.is_symlink():
            fail('symlink paths are unsupported')
    p = p.resolve()
    if root is not None and not inside(p, root):
        fail('path outside supported root')
    return p


def load_policy(path):
    policy_path = clean_path(path)
    policy_bytes = policy_path.read_bytes()
    p = parse_json(policy_bytes.decode('utf-8'))
    if not isinstance(p, dict) or set(p) != {'home', 'profile', 'cards_dir', 'state_dir', 'routes'}:
        fail('invalid policy shape')
    p['home'] = clean_path(p['home'])
    p['cards_dir'] = clean_path(p['cards_dir'])
    p['state_dir'] = clean_path(p['state_dir'])
    if not isinstance(p['profile'], str) or not p['profile'] or not isinstance(p['routes'], dict):
        fail('invalid profile or route map')
    env_home = os.environ.get('HERMES_HOME')
    if not env_home or clean_path(env_home) != p['home']:
        fail('HERMES_HOME must match active profile policy home')
    for name, route in p['routes'].items():
        if not isinstance(name, str) or not name.startswith('mcp__') or not isinstance(route, dict) or set(route) != {'server', 'card'}:
            fail('unsupported route map shape')
        if not isinstance(route['server'], str) or not re.fullmatch('[A-Za-z0-9_-]+', route['server']):
            fail('unsupported server name')
        if not isinstance(route['card'], str) or not route['card'] or Path(route['card']).is_absolute() or '..' in Path(route['card']).parts:
            fail('unsupported card path')
    p['_fingerprint'] = digest(str(policy_path).encode() + b'\0' + policy_bytes)
    return p


def validate_skill(text, path):
    if not isinstance(text, str) or not text.startswith('---\n'):
        fail('invalid skill: required frontmatter')
    pieces = text.split('\n---\n', 1)
    if len(pieces) != 2:
        fail('invalid skill: unterminated frontmatter')
    meta = parse_yaml(pieces[0][4:])
    if not isinstance(meta, dict) or set(meta) - {'name', 'description', 'version', 'metadata', 'platforms', 'author'}:
        fail('unsupported skill metadata template')
    if not isinstance(meta.get('name'), str) or not re.fullmatch('[a-z][a-z0-9-]{0,63}', meta['name']):
        fail('invalid skill name')
    if not isinstance(meta.get('description'), str) or not meta['description'].strip():
        fail('invalid skill description')
    if 'version' in meta and not isinstance(meta['version'], str):
        fail('unsupported skill version')
    if len(meta['description'].strip()) < 20 or 'Use when' not in meta['description']:
        fail('custom skill description: >=20 characters and Use when required')
    if meta['name'] != path.parent.name:
        fail('custom skill folder must equal frontmatter name')
    body = pieces[1]
    if not body.strip():
        fail('invalid skill: missing body')
    if len(body.splitlines()) > 500:
        fail('custom skill BODY limit is 500 lines')
    for link in local_links(body):
        relative = Path(link)
        if relative.is_absolute() or '..' in relative.parts or not 1 <= len(relative.parts) <= 2 or '?' in link:
            fail('custom skill references: direct files, at most one subdirectory')
        target = clean_path(str(path.parent / relative), path.parent)
        if target == path:
            fail('self skill reference unsupported')
        if not target.is_file() or not target.read_text(encoding='utf-8').strip():
            fail('missing skill reference or empty reference')
        if local_links(target.read_text(encoding='utf-8')):
            fail('custom skill references: chained local references unsupported')


def validate_config(text):
    cfg = parse_yaml(text)
    if not isinstance(cfg, dict) or 'mcpServers' in cfg:
        fail('unsupported config: native mcp_servers required, not Claude mcpServers')
    skills = cfg.get('skills', {})
    if not isinstance(skills, dict) or set(skills) - {'write_approval'}:
        fail('external/create_dir skill configuration unsupported')
    if 'write_approval' in skills and not isinstance(skills['write_approval'], bool):
        fail('invalid skill approval configuration')
    servers = cfg.get('mcp_servers', {})
    if not isinstance(servers, dict):
        fail('invalid native mcp_servers mapping')
    for name, server in servers.items():
        if not re.fullmatch('[A-Za-z0-9_-]+', name) or not isinstance(server, dict):
            fail('unsupported MCP server shape')
        if set(server) - {'command', 'args', 'url', 'auth', 'enabled', 'env', 'headers'}:
            fail('unsupported MCP server option; narrow template only')
        for key in ('env', 'headers'):
            values = server.get(key, {})
            if not isinstance(values, dict):
                fail('unsupported MCP env/headers template')
            for field, value in values.items():
                pattern = r'\$\{(?:env:)?[A-Za-z_][A-Za-z0-9_]*\}'
                if key == 'headers' and isinstance(field, str) and field.lower() == 'authorization':
                    pattern = r'(?:Bearer )?' + pattern
                if not isinstance(field, str) or not isinstance(value, str) or not re.fullmatch(pattern, value):
                    fail('MCP plaintext env/header credentials forbidden; use environment references')
        if 'enabled' in server and not isinstance(server['enabled'], bool):
            fail('invalid MCP enabled flag')
        if server.get('auth') not in (None, 'oauth'):
            fail('unsupported MCP auth; plaintext credentials forbidden')
        if ('command' in server) == ('url' in server):
            fail('MCP requires exactly one command or url')
        if 'url' in server:
            from urllib.parse import urlsplit
            if not isinstance(server['url'], str):
                fail('invalid MCP URL')
            u = urlsplit(server['url'])
            if u.scheme != 'https' or not u.hostname or u.username or u.password or u.query or u.fragment:
                fail('MCP URL credential/plaintext or unsupported transport')
            if 'args' in server:
                fail('args unsupported on remote MCP')
        else:
            command = server['command']
            args = server.get('args', [])
            if not isinstance(command, str) or not command or re.search(r'[\s;&|`$]', command) or Path(command).name in {'sh', 'bash', 'zsh', 'fish', 'cmd', 'powershell'}:
                fail('unsupported MCP command or shell wrapper')
            if not isinstance(args, list) or any(not isinstance(a, str) for a in args):
                fail('unsupported MCP argument shape')
            if any(re.search(r'(?i)(token|secret|password|api.?key|authorization|bearer|credential)', a) for a in args):
                fail('MCP credential arguments forbidden')
            # Arbitrary positional strings could be inline secrets. This template
            # only permits flags and simple package identifiers, not scripts/code.
            if any(not re.fullmatch(r'[-@A-Za-z0-9_./:]+', a) for a in args):
                fail('unsupported MCP command arguments')
    return cfg


def scan_assets(policy, replacement=None):
    home = policy['home']
    config = clean_path(str(home / 'config.yaml'), home)
    if not config.is_file() and (not replacement or replacement[0] != config):
        fail('missing native profile config.yaml')
    cfg = validate_config(replacement[1] if replacement and replacement[0] == config else config.read_text(encoding='utf-8'))
    root = clean_path(str(home / 'skills'), home)
    paths = list(root.rglob('SKILL.md')) if root.exists() else []
    # Directory symlinks may be omitted by rglob, so inspect them explicitly.
    if root.exists() and any(p.is_symlink() for p in root.rglob('*')):
        fail('symlink skills unsupported')
    if replacement and replacement[0].name == 'SKILL.md' and replacement[0] not in paths:
        paths.append(replacement[0])
    for path in paths:
        clean_path(str(path), root)
        validate_skill(replacement[1] if replacement and replacement[0] == path else path.read_text(encoding='utf-8'), path)
    return cfg


def atomic_json(path, value):
    clean_path(str(path))
    temporary = path.with_suffix(path.suffix + '.tmp')
    clean_path(str(temporary))
    with open(temporary, 'w', encoding='utf-8') as handle:
        os.chmod(temporary, 0o600)
        json.dump(value, handle, sort_keys=True)
        handle.write('\n')
    os.replace(temporary, path)


@contextlib.contextmanager
def locked_state(policy):
    root = policy['state_dir']
    root.mkdir(parents=True, exist_ok=True)
    lock_path = clean_path(str(root / 'state.lock'))
    with open(lock_path, 'a', encoding='utf-8') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state_path = clean_path(str(root / 'state.json'))
        state = parse_json(state_path.read_text()) if state_path.exists() else {'pending': {}, 'reads': {}}
        if not isinstance(state, dict) or set(state) != {'pending', 'reads'} or any(not isinstance(v, dict) for v in state.values()):
            fail('invalid state')
        before = json.dumps(state, sort_keys=True, separators=(',', ':'))
        existed = state_path.exists()
        try:
            yield state
        finally:
            if not existed or json.dumps(state, sort_keys=True, separators=(',', ':')) != before:
                atomic_json(state_path, state)
            fcntl.flock(lock, fcntl.LOCK_UN)


def aggregate(value):
    if isinstance(value, dict):
        return any(key.lower() in AGGREGATE_KEYS or aggregate(v) for key, v in value.items())
    if isinstance(value, list):
        return any(isinstance(v, (dict, list)) for v in value)
    return False


def card_path(policy, route):
    path = clean_path(str(policy['cards_dir'] / route['card']), policy['cards_dir'])
    if not path.is_file() or not path.read_bytes():
        fail('missing card or empty card')
    return path


def scope_key(policy, payload, path):
    return digest(json.dumps([policy['_fingerprint'], str(policy['home']), policy['profile'], payload['session_id'], str(path)]).encode())


def pending_key(policy, payload, path):
    # Hermes sends tool_call_id under extra; tool_use_id is NOT assumed.
    call_id = payload['extra'].get('tool_call_id')
    if call_id is not None and not isinstance(call_id, str):
        fail('invalid call ID')
    return scope_key(policy, payload, path) + ':' + digest((call_id or 'no-id').encode())


def full_read_result(payload, args, text):
    extra = payload['extra']
    if extra.get('status') not in (None, 'success') or extra.get('error_type') or extra.get('error_message'):
        return False
    result = extra.get('result')
    if isinstance(result, str):
        try:
            result = parse_json(result)
        except Denied:
            return False
    if not isinstance(result, dict) or result.get('error') or result.get('success') is False or result.get('isError'):
        return False
    if args.get('offset', 1) != 1 or result.get('truncated') is not False or result.get('truncated_lines') or result.get('truncated_by') or result.get('unchanged'):
        return False
    expected = '\n'.join(f'{i}|{line}' for i, line in enumerate(text.removesuffix('\n').split('\n'), 1))
    return result.get('total_lines') == len(text.splitlines()) and result.get('content') == expected


def observe(policy, payload):
    violations = []
    try:
        scan_assets(policy)
    except Denied as exc:
        violations.append(str(exc))
    atomic_json(policy['state_dir'] / 'findings.json', {'observer_only': True, 'event': 'post_tool_call', 'session_hash': digest(payload['session_id'].encode()), 'violations': violations})
    # Observer returns are ignored by Hermes. Never emit a fake post-call veto.
    return {}


def handle(policy, payload, state):
    if not isinstance(payload, dict) or payload.get('hook_event_name') not in EVENTS:
        fail('unsupported Hermes hook event/envelope')
    event = payload['hook_event_name']
    if not isinstance(payload.get('session_id'), str) or not payload['session_id']:
        fail('missing session ID')
    if payload.get('profile') != policy['profile']:
        fail('profile mismatch')
    if not isinstance(payload.get('extra'), dict):
        fail('missing native extra payload')
    if event == 'pre_verify':
        scan_assets(policy)
        return {}
    args = payload.get('tool_input')
    tool = payload.get('tool_name')
    if not isinstance(args, dict) or not isinstance(tool, str):
        fail('unsupported native tool payload')
    if event == 'post_tool_call':
        if tool == 'read_file' and isinstance(args.get('path'), str):
            path = clean_path(args['path'])
            key = pending_key(policy, payload, path)
            pending = state['pending'].pop(key, None)
            if pending and path.is_file() and pending['args_hash'] == digest(json.dumps(args, sort_keys=True).encode()):
                data = path.read_bytes()
                if time.time() - pending['time'] <= 300 and pending['hash'] == digest(data) and full_read_result(payload, args, data.decode('utf-8')):
                    state['reads'][scope_key(policy, payload, path)] = digest(data)
        return observe(policy, payload)
    if aggregate(args):
        fail('unsupported aggregate/batch route: every action must be checked; this adapter denies the whole batch')
    if tool == 'read_file':
        path = clean_path(args.get('path'))
        # Noncard local reads are allowed, but cannot create card-read evidence.
        if inside(path, policy['cards_dir']):
            if not path.is_file():
                fail('missing card')
            key = pending_key(policy, payload, path)
            if key in state['pending']:
                fail('ambiguous pending card read; finish outstanding read before retry')
            state['pending'][key] = {'hash': digest(path.read_bytes()), 'time': time.time(), 'args_hash': digest(json.dumps(args, sort_keys=True).encode())}
        return {}
    if tool == 'write_file':
        path = clean_path(args.get('path'))
        if args.get('append') or set(args) - {'path', 'content', 'append'}:
            fail('unsupported append or write option')
        if path != policy['home'] / 'config.yaml' and not (inside(path, policy['home'] / 'skills') and path.name == 'SKILL.md'):
            fail('unsupported write outside native skill/config assets')
        if not isinstance(args.get('content'), str):
            fail('unsupported write content')
        scan_assets(policy, (path, args['content']))
        return {}
    route = policy['routes'].get(tool)
    if route is None:
        fail('unsupported tool route (including skill_manage aggregate/terminal/patch/delegation)')
    cfg = scan_assets(policy)
    server = cfg.get('mcp_servers', {}).get(route['server'])
    if not server:
        fail('missing native MCP server configuration')
    if server.get('enabled') is False:
        fail('disabled MCP server')
    path = card_path(policy, route)
    if state['reads'].get(scope_key(policy, payload, path)) != digest(path.read_bytes()):
        fail('connector requires successful full read_file of current card in this session')
    return {}


def hook_config(policy_path):
    command = shlex.join(['python3', '-B', str(Path(__file__).resolve()), '--policy', str(Path(policy_path).resolve())])
    return {'hooks': {'pre_tool_call': [{'command': command, 'timeout': 10, 'fail_closed': True}], 'post_tool_call': [{'command': command, 'timeout': 10}], 'pre_verify': [{'command': command, 'timeout': 10}]}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--policy', required=True)
    parser.add_argument('--print-hook-config', action='store_true')
    options = parser.parse_args()
    if options.print_hook_config:
        print(json.dumps(hook_config(options.policy), indent=2))
        return 0
    payload = {}
    try:
        payload = parse_json(sys.stdin.read())
        policy = load_policy(options.policy)
        with locked_state(policy) as state:
            result = handle(policy, payload, state)
    except (Denied, OSError, UnicodeError, KeyError, TypeError, AttributeError, ValueError):
        # Never print exception details from I/O or untrusted secrets. Denied
        # messages are fixed text only; no card/result/command bytes are logged.
        exc = sys.exc_info()[1]
        message = str(exc) if isinstance(exc, Denied) else 'guard input/state/asset read failed'
        event = payload.get('hook_event_name') if isinstance(payload, dict) else None
        if event == 'post_tool_call':
            # Return ignored; don't lie about blocking an already executed call.
            print('{}')
            return 1
        if event == 'pre_verify':
            print(json.dumps({'action': 'continue', 'message': message}))
            return 0
        print(json.dumps({'action': 'block', 'message': message}))
        return 2
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    sys.exit(main())
