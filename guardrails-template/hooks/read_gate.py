#!/usr/bin/env python3
"""Claude Code read-before-MCP hook, Python stdlib, POSIX only.

Trusted launcher contract: --policy /absolute/policy.json --state-dir /absolute/state
--project /absolute/project (or READ_GATE_POLICY, READ_GATE_STATE_DIR,
READ_GATE_PROJECT, with CLAUDE_PROJECT_DIR as project fallback). stdin is the native Claude hook JSON, NOT an agent argument.
Install for PreToolUse (Read and all mcp__), PostToolUse / PostToolUseFailure (Read),
and PermissionDenied (Read). Success emits {} (does not grant tool permission);
PreToolUse denial emits hookSpecificOutput.permissionDecision=deny, exit 0.
Invalid configuration/input/state exits 2 with a generic blocking error.
Use onFailure:"block" (Claude Code >=2.1.295) to block launch/crash/timeout failures.

Runtime must pre-provision a private 0700 state directory outside the project,
owned by the hook runtime UID, and keep script, policy, launcher/environment and
state inaccessible to agent writes. This script checks owner/mode/symlink/hardlink
hygiene but IS NOT a security boundary against an agent running as the same UID.
Use an isolated runtime/service principal or trusted broker plus managed settings.
No Bash-wrapper, external process or alternative connector-route coverage claimed.

Policy v1: exact keys version, project_root, servers, direct_tools, batches. project_root is
an absolute path or the exact token ${CLAUDE_PROJECT_DIR} from trusted runtime env
(no other substitution or relative paths). servers maps exact
MCP server IDs to nonempty lists of absolute card paths. batches maps FULL MCP
names to {actions_key, action_name_key, arguments_key, optional_fields, actions}.
Action schema is EXACTLY {<action_name_key>: string, <arguments_key>: object};
input schema is exactly {<actions_key>: nonempty array} plus optional_fields typed
string/boolean/object/array/integer. Every action name must be explicitly in
'actions', mapped to a nonempty card list. Batch server cards are required too.
direct_tools is an array of exact full MCP tool names. Only those tools and
configured batches can run; a known server alone NEVER permits another tool.
Do not direct-allowlist batch/remoteexec/wrapper tools: use a verified adapter
for such routes or leave them denied. A policy author can weaken this boundary.
Unknown servers/actions/fields or malformed input fail closed; no prefix guessing.

Read evidence: primary schemas checked 2026-10-12 at
https://code.claude.com/docs/en/hooks#posttooluse-input and
https://code.claude.com/docs/en/agent-sdk/typescript#read-2 . Require native
{type:"text", file:{filePath,content,numLines,startLine,totalLines}}; reject
file_unchanged, truncatedByTokenCap, errors, partial content, and schema drift.
Exact UTF-8 bytes are required (no guessed normalization). Coverage is whole-file
single Read, never assembled pages. Syntactic completeness/hash validation does
not assess a card's semantic quality or prove model understanding.
"""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile


class GateError(Exception):
    pass


def require(ok):
    if not ok:
        raise GateError('invalid gate contract')


def unique_object(pairs):
    obj = {}
    for key, value in pairs:
        require(key not in obj)
        obj[key] = value
    return obj


def parse_json(raw):
    return json.loads(raw, object_pairs_hook=unique_object,
                      parse_constant=lambda _: require(False))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def identity(value):
    return digest(json.dumps(value, sort_keys=True, separators=(',', ':'),
                             ensure_ascii=False).encode('utf-8'))


def absolute(value):
    require(isinstance(value, str) and bool(value) and '\x00' not in value)
    path = Path(value)
    require(path.is_absolute())
    return path


def mcp_server(name):
    match = re.fullmatch(r'mcp__([A-Za-z0-9_-]+)__([A-Za-z0-9_-]+)', name)
    require(match is not None and '__' not in match[1] and '__' not in match[2])
    return match[1]


def cards(value):
    require(isinstance(value, list) and bool(value))
    paths = [str(absolute(item).resolve()) for item in value]
    require(len(set(paths)) == len(paths))
    return paths


def policy_load(path, project):
    raw = path.read_bytes()
    cfg = parse_json(raw)
    require(isinstance(cfg, dict) and set(cfg) == {'version', 'project_root', 'servers', 'direct_tools', 'batches'})
    require(type(cfg['version']) is int and cfg['version'] == 1)
    configured_project = cfg['project_root']
    if configured_project == '${CLAUDE_PROJECT_DIR}':
        configured_project = os.environ.get('CLAUDE_PROJECT_DIR')
    require(absolute(configured_project).resolve() == project)
    require(isinstance(cfg['servers'], dict) and bool(cfg['servers']))
    require(isinstance(cfg['batches'], dict))
    direct = cfg['direct_tools']
    require(isinstance(direct, list) and all(isinstance(name, str) for name in direct))
    require(len(set(direct)) == len(direct))
    for name in direct:
        require(mcp_server(name) in cfg['servers'] and name not in cfg['batches'])
    routes = {}
    for server, value in cfg['servers'].items():
        require(isinstance(server, str) and re.fullmatch(r'[A-Za-z0-9_-]+', server)
                and '__' not in server)
        cfg['servers'][server] = cards(value)
        routes[identity(['server', server])] = cfg['servers'][server]
    for name, adapter in cfg['batches'].items():
        server = mcp_server(name)
        require(server in cfg['servers'])
        require(isinstance(adapter, dict) and set(adapter) == {
            'actions_key', 'action_name_key', 'arguments_key', 'optional_fields', 'actions'})
        keys = [adapter[k] for k in ('actions_key', 'action_name_key', 'arguments_key')]
        require(all(isinstance(k, str) and bool(k) for k in keys) and len(set(keys)) == 3)
        optional = adapter['optional_fields']
        require(isinstance(optional, dict) and adapter['actions_key'] not in optional)
        require(all(isinstance(k, str) and bool(k) and v in
                    ('string', 'boolean', 'object', 'array', 'integer')
                    for k, v in optional.items()))
        require(isinstance(adapter['actions'], dict) and bool(adapter['actions']))
        for slug, value in adapter['actions'].items():
            require(isinstance(slug, str) and bool(slug.strip()))
            adapter['actions'][slug] = cards(value)
            routes[identity(['batch', server, name, slug])] = adapter['actions'][slug]
    return cfg, routes, identity([str(path.resolve()), digest(raw), str(project)])


def snapshot(path):
    with open(path, 'rb') as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode))
        raw = stream.read()
        after = os.fstat(stream.fileno())
    stamp = lambda st: [st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns]
    require(stamp(before) == stamp(after) == stamp(os.stat(path)))
    text = raw.decode('utf-8')
    require(bool(text.strip()))
    return {'hash': digest(raw), 'stamp': stamp(after)}, text


def empty_state():
    return {'version': 1, 'markers': {}, 'reads': {}}


def is_hash(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def validate_state(data):
    require(isinstance(data, dict) and set(data) == {'version', 'markers', 'reads'})
    require(type(data['version']) is int and data['version'] == 1)
    require(isinstance(data['markers'], dict) and isinstance(data['reads'], dict))
    for key, value in data['markers'].items():
        require(is_hash(key) and is_hash(value))
    for key, record in data['reads'].items():
        require(is_hash(key) and isinstance(record, dict))
        require(record.get('status') in ('pending', 'invalid', 'completed'))
        if record['status'] == 'pending':
            require(set(record) == {'status', 'context', 'path', 'snapshot', 'input_hash', 'routes'})
            require(is_hash(record['context']))
            absolute(record['path'])
            snap = record['snapshot']
            require(isinstance(snap, dict) and set(snap) == {'hash', 'stamp'})
            require(is_hash(snap['hash']) and isinstance(snap['stamp'], list)
                    and len(snap['stamp']) == 5 and all(type(i) is int for i in snap['stamp']))
            require(is_hash(record['input_hash']) and isinstance(record['routes'], list)
                    and bool(record['routes']) and all(is_hash(i) for i in record['routes']))
        else:
            require(set(record) == {'status'})


def secure_file(fd):
    st = os.fstat(fd)
    require(stat.S_ISREG(st.st_mode) and st.st_uid == os.geteuid()
            and stat.S_IMODE(st.st_mode) == 0o600 and st.st_nlink == 1)


@contextmanager
def locked_state(directory, project):
    # Must exist: never silently create an agent-owned runtime directory.
    require(directory == directory.resolve() and not directory.is_relative_to(project))
    st = directory.lstat()
    require(stat.S_ISDIR(st.st_mode) and st.st_uid == os.geteuid()
            and stat.S_IMODE(st.st_mode) == 0o700)
    dfd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    lockfd = None
    try:
        lockfd = os.open('gate.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600, dir_fd=dfd)
        secure_file(lockfd)
        fcntl.flock(lockfd, fcntl.LOCK_EX)
        try:
            statefd = os.open('state.json', os.O_RDONLY | os.O_NOFOLLOW, dir_fd=dfd)
        except FileNotFoundError:
            state = empty_state()
        else:
            with os.fdopen(statefd, 'r', encoding='utf-8') as stream:
                secure_file(stream.fileno())
                state = parse_json(stream.read())
            validate_state(state)
        before = identity(state)
        yield state
        if identity(state) != before:
            fd, temporary = tempfile.mkstemp(prefix='.state-', dir=directory)
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                    os.fchmod(stream.fileno(), 0o600)
                    json.dump(state, stream, sort_keys=True, separators=(',', ':'))
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, directory / 'state.json')
                os.fsync(dfd)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
    finally:
        if lockfd is not None:
            os.close(lockfd)
        os.close(dfd)


def whole_input(inp, text):
    require(set(inp).issubset({'file_path', 'offset', 'limit'}))
    if 'offset' in inp:
        require(type(inp['offset']) is int and inp['offset'] == 1)
    if 'limit' in inp:
        require(type(inp['limit']) is int and inp['limit'] >= len(text.split('\n')))


def complete_response(response, path, text):
    require(isinstance(response, dict) and set(response).issubset({'type', 'file'}))
    require(response.get('type') == 'text' and isinstance(response.get('file'), dict))
    file = response['file']
    require(set(file).issubset({'filePath', 'content', 'numLines', 'startLine',
                              'totalLines', 'truncatedByTokenCap'}))
    require(absolute(file.get('filePath')).resolve() == Path(path))
    require(file.get('content') == text)
    require(type(file.get('startLine')) is int and file['startLine'] == 1)
    require(type(file.get('numLines')) is int and type(file.get('totalLines')) is int)
    require(file['numLines'] == file['totalLines'] and file['numLines'] in
            {len(text.splitlines()), len(text.split('\n'))})
    require('truncatedByTokenCap' not in file or file['truncatedByTokenCap'] is False)


def requirements(name, inp, cfg):
    server = mcp_server(name)
    require(server in cfg['servers'])
    require(name in cfg['direct_tools'] or name in cfg['batches'])
    needed = [(identity(['server', server]), cfg['servers'][server])]
    if name in cfg['batches']:
        adapter = cfg['batches'][name]
        ak, nk, pk = (adapter[k] for k in ('actions_key', 'action_name_key', 'arguments_key'))
        optional = adapter['optional_fields']
        require(ak in inp and set(inp).issubset({ak, *optional}))
        types = {'string': str, 'boolean': bool, 'object': dict, 'array': list, 'integer': int}
        for field in set(inp) - {ak}:
            require(type(inp[field]) is types[optional[field]])
        actions = inp[ak]
        require(isinstance(actions, list) and bool(actions))
        for action in actions:
            require(isinstance(action, dict) and set(action) == {nk, pk})
            require(isinstance(action[nk], str) and action[nk] in adapter['actions'])
            require(isinstance(action[pk], dict))
            slug = action[nk]
            needed.append((identity(['batch', server, name, slug]), adapter['actions'][slug]))
    return needed


def handle(event, cfg, routes, binding, project, state):
    require(isinstance(event, dict))
    kind = event.get('hook_event_name')
    require(kind in ('PreToolUse', 'PostToolUse', 'PostToolUseFailure', 'PermissionDenied'))
    name = event.get('tool_name')
    inp = event.get('tool_input')
    require(isinstance(name, str) and isinstance(inp, dict))
    session = event.get('session_id')
    require(isinstance(session, str) and bool(session.strip()))
    cwd = absolute(event.get('cwd')).resolve()
    require(cwd.is_relative_to(project))
    agent = event.get('agent_id', '')
    require(isinstance(agent, str))
    context = identity([binding, session, str(project), agent])
    marker_key = lambda route, path: identity([context, route, path])
    if name == 'Read':
        uid = event.get('tool_use_id')
        # PermissionDenied does not have a documented tool_use_id. Invalidate all
        # pending reads for this context instead of guessing which call was denied.
        if kind == 'PermissionDenied' and not uid:
            for key, record in state['reads'].items():
                if record['status'] == 'pending' and record['context'] == context:
                    record.clear()
                    record['status'] = 'invalid'
            return {}
        require(isinstance(uid, str) and bool(uid))
        read_key = identity([context, uid])
        if kind == 'PermissionDenied':
            state['reads'][read_key] = {'status': 'invalid'}
            return {}
        if kind == 'PreToolUse':
            if read_key in state['reads']:
                state['reads'][read_key] = {'status': 'invalid'}
                return {}
            state['reads'][read_key] = {'status': 'invalid'}
            try:
                path = str(absolute(inp.get('file_path')).resolve())
                matching = [route for route, paths in routes.items() if path in paths]
                if not matching:
                    return {}
                snap, text = snapshot(path)
                whole_input(inp, text)
                state['reads'][read_key] = {'status': 'pending', 'context': context, 'path': path,
                                          'snapshot': snap, 'input_hash': identity(inp),
                                          'routes': matching}
            except (GateError, OSError, UnicodeError):
                pass
            return {}
        pending = state['reads'].get(read_key)
        if not pending or pending['status'] != 'pending':
            return {}
        state['reads'][read_key] = {'status': 'invalid'}
        if kind != 'PostToolUse':
            return {}
        try:
            require(not any(event.get(k) for k in ('error', 'is_error', 'isError', 'interrupted')))
            require(identity(inp) == pending['input_hash'])
            path = str(absolute(inp.get('file_path')).resolve())
            require(path == pending['path'])
            snap, text = snapshot(path)
            require(snap == pending['snapshot'])
            complete_response(event.get('tool_response'), path, text)
            # Recheck after response validation; marker hash still checked on use.
            require(snapshot(path)[0] == snap)
            for route in pending['routes']:
                require(route in routes and path in routes[route])
            for route in pending['routes']:
                state['markers'][marker_key(route, path)] = snap['hash']
            state['reads'][read_key] = {'status': 'completed'}
        except (GateError, OSError, UnicodeError):
            pass
        return {}
    if kind == 'PreToolUse' and name.startswith('mcp__'):
        try:
            for route, paths in requirements(name, inp, cfg):
                for path in paths:
                    snap, _ = snapshot(path)
                    require(state['markers'].get(marker_key(route, path)) == snap['hash'])
        except (GateError, OSError, UnicodeError):
            return {'hookSpecificOutput': {'hookEventName': 'PreToolUse',
                    'permissionDecision': 'deny', 'permissionDecisionReason':
                    'Read gate: missing current full-card Read, unknown route, or malformed batch. '
                    'Read every configured card in this session/project, then retry with a new tool ID.'}}
    return {}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--policy', default=os.environ.get('READ_GATE_POLICY'))
    parser.add_argument('--state-dir', default=os.environ.get('READ_GATE_STATE_DIR'))
    parser.add_argument('--project', default=os.environ.get('READ_GATE_PROJECT') or os.environ.get('CLAUDE_PROJECT_DIR'))
    # argparse's usual exit 2 is blocking in PreToolUse.
    args = parser.parse_args()
    try:
        project = absolute(args.project).resolve(strict=True)
        require(project.is_dir())
        cfg, routes, binding = policy_load(absolute(args.policy), project)
        event = parse_json(sys.stdin.read())
        with locked_state(absolute(args.state_dir), project) as state:
            result = handle(event, cfg, routes, binding, project, state)
        print(json.dumps(result, separators=(',', ':')))
        return 0
    except Exception:
        # Never echo tool input, card content, paths containing secrets or raw errors.
        print('Read gate blocked: invalid input, trusted configuration, card or runtime state.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
