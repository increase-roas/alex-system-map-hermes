"""Reviewed JSON-stdin remote file executor; no request contains a command.

The transport sends this exact source, followed by JSON on stdin. Registered roots
are defined here, never supplied by a browser or model. Tests inject temporary roots
in-process; the executable entry point always uses production registrations.
"""
import hashlib
import json
import os
import re
from pathlib import Path
import socket
import subprocess
import stat
import sys
import tempfile
try:
    from repair_contracts import RepairError
except ImportError:
    class RepairError(Exception):
        def __init__(self, code): self.code = code; super().__init__(code)

ROOTS = {'claude': '~/.claude', 'codex': '~/.codex', 'hermes': '~/.hermes',
         'openclaw': '~/.openclaw', 'instructions': '~/.agents/instructions'}
SECRET_WORDS = ('secret', 'password', 'token', 'credential', 'apikey', 'api_key', 'authorization', 'privatekey')


def digest(value):
    if not isinstance(value, bytes): value = json.dumps(value, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(value).hexdigest()


def sensitive(key):
    return any(word in key.lower().replace('-', '_') for word in SECRET_WORDS)


def redact(value):
    if isinstance(value, dict): return {k: '[REDACTED]' if sensitive(k) else redact(v) for k, v in value.items()}
    if isinstance(value, list): return [redact(v) for v in value]
    if isinstance(value,str):
        value=re.sub(r'(?i)(bearer\s+)[A-Za-z0-9._~+/-]{12,}',r'\1[REDACTED]',value)
        value=re.sub(r'\b(?:sk-[A-Za-z0-9_-]{12,}|ghp_[A-Za-z0-9]{12,}|github_pat_[A-Za-z0-9_]{12,}|xox[baprs]-[A-Za-z0-9-]{12,}|AIza[A-Za-z0-9_-]{20,})','[REDACTED]',value)
        value=re.sub(r'(?i)((?:api[_-]?key|password|access[_-]?token|secret)\s*[=:]\s*)[^\s,;]+',r'\1[REDACTED]',value)
        value=re.sub(r'(?i)(postgres(?:ql)?://)[^@\s]+@',r'\1[REDACTED]@',value)
    return value


def resolve(request, roots, host):
    if request.get('host') != host: raise RepairError('remote_host_mismatch')
    if request.get('root') not in roots: raise RepairError('remote_root_unregistered')
    relative = request.get('relative', '')
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute() or '..' in Path(relative).parts:
        raise RepairError('remote_path_escape')
    root = Path(roots[request['root']]).expanduser()
    path = root / relative
    # Check every existing component before resolve, including root itself.
    for item in [root, *list(path.parents)[:len(Path(relative).parts)-1], path]:
        if item.is_symlink(): raise RepairError('remote_symlink')
    if not path.resolve().is_relative_to(root.resolve()): raise RepairError('remote_path_escape')
    if not path.is_file(): raise RepairError('remote_file_missing')
    if path.suffix not in ('.json', '.md', '.yaml', '.yml', '.toml'): raise RepairError('remote_format_unsupported')
    return path


def parse(path, data):
    text = data.decode('utf-8')
    if path.suffix == '.json': return json.loads(text)
    if path.suffix in ('.yaml', '.yml'):
        try: import yaml
        except ImportError:
            try:
                result=subprocess.run(['/usr/bin/ruby','-rjson','-ryaml','-e','print JSON.generate(YAML.safe_load(STDIN.read, permitted_classes: [], aliases: false))'],input=text,capture_output=True,text=True,check=True,timeout=10)
                return json.loads(result.stdout)
            except Exception: raise RepairError('remote_yaml_native_parser_missing') from None
        return yaml.safe_load(text)
    if path.suffix == '.toml':
        import tomllib
        return tomllib.loads(text)
    return text


def serialize(path, value):
    if path.suffix == '.json': return (json.dumps(value, ensure_ascii=False, indent=2)+'\n').encode()
    if path.suffix in ('.yaml', '.yml'):
        try:
            import yaml
            return yaml.safe_dump(value, sort_keys=False).encode()
        except ImportError:
            try:
                return subprocess.run(['/usr/bin/ruby','-rjson','-ryaml','-e','print JSON.parse(STDIN.read).to_yaml'],input=json.dumps(value),capture_output=True,text=True,check=True,timeout=10).stdout.encode()
            except Exception: raise RepairError('remote_yaml_native_writer_missing') from None
    if path.suffix == '.toml': raise RepairError('remote_toml_native_writer_required')
    return value.encode()


def get_field(value, key):
    current = value
    for part in key.split('.'):
        if not isinstance(current, dict) or part not in current: return {'present': False}
        current = current[part]
    return {'present': True, 'value': current}


def set_field(value, key, item):
    parts = key.split('.')
    current = value
    for part in parts[:-1]:
        if part not in current: current[part] = {}
        if not isinstance(current[part], dict): raise RepairError('remote_field_type')
        current = current[part]
    if item['present']: current[parts[-1]] = item['value']
    else: current.pop(parts[-1], None)


def atomic_write(path, data, mode):
    fd, name = tempfile.mkstemp(prefix='.repair-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        os.chmod(name, mode)
        os.replace(name, path)
    finally:
        if os.path.exists(name): os.unlink(name)


def run_request(request, roots=None, host=None):
    host = host or socket.gethostname()
    if request.get('action') == 'inventory':
        roots = ROOTS if roots is None else roots
        files = []
        for name, directory in roots.items():
            root = Path(directory).expanduser()
            if root.is_symlink() or not root.is_dir(): continue
            for relative in ('CLAUDE.md', 'AGENTS.md', 'settings.json', 'config.yaml', 'openclaw.json'):
                item = root / relative
                if item.is_file() and not item.is_symlink(): files.append({'root':name,'relative':relative})
            if name == 'instructions':
                files.extend({'root':name,'relative':item.name} for item in sorted(root.glob('*.md')) if item.is_file() and not item.is_symlink())
        return {'host':host,'files':files}
    path = resolve(request, ROOTS if roots is None else roots, host)
    data = path.read_bytes()
    mode = stat.S_IMODE(path.stat().st_mode)
    value = parse(path, data)
    action = request.get('action')
    snapshot = {'fingerprint': digest(data), 'mode': mode, 'projection': redact(value), 'host': host,
                'version': str(path.stat().st_mtime_ns)}
    if action == 'read': return snapshot
    if action not in ('preflight', 'backup', 'apply', 'undo', 'check'): raise RepairError('remote_action_unregistered')
    patch = request.get('patch')
    candidate = request.get('candidate')
    if patch is not None:
        if not isinstance(patch, dict) or not patch or not isinstance(value, dict): raise RepairError('remote_patch_invalid')
        for key, item in patch.items():
            if not isinstance(key,str) or not key or any(sensitive(p) for p in key.split('.')):
                raise RepairError('remote_secret_field')
            if '[REDACTED]' in json.dumps(item) or redact(item) != item: raise RepairError('remote_secret_patch')
        inverse = {key: get_field(value,key) for key in patch}
        if any(redact(v) != v for v in inverse.values()): raise RepairError('remote_secret_inverse')
        changed = json.loads(json.dumps(value))
        if action == 'undo':
            inverse = request.get('inverse', {})
            if set(inverse) != set(patch): raise RepairError('remote_inverse_invalid')
            for key, item in patch.items():
                if get_field(value,key) != {'present':True,'value':item}: raise RepairError('remote_undo_conflict')
            for key,item in inverse.items(): set_field(changed,key,item)
        else:
            for key,item in patch.items(): set_field(changed,key,{'present':True,'value':item})
        new_data = serialize(path, changed)
    elif isinstance(candidate,str) and path.suffix == '.md':
        if redact(data.decode('utf-8'))!=data.decode('utf-8') or redact(candidate)!=candidate or '[REDACTED]' in candidate:raise RepairError('remote_secret_text_requires_native_preservation')
        if any(sensitive(line.split(':',1)[0]) for line in candidate.splitlines() if ':' in line):
            raise RepairError('remote_secret_text')
        inverse = {'text': data.decode('utf-8')}
        new_data = candidate.encode()
        if action == 'undo':
            if data != candidate.encode(): raise RepairError('remote_undo_conflict')
            new_data = request['inverse']['text'].encode()
    else: raise RepairError('remote_candidate_invalid')
    parse(path,new_data)  # Native parser check before any write.
    if action != 'undo' and (snapshot['fingerprint'] != request.get('expected_fingerprint') or mode != request.get('expected_mode') or (request.get('expected_version') is not None and snapshot['version'] != request['expected_version'])):
        raise RepairError('remote_stale')
    if action in ('preflight','check'): return {'ok': True, 'fingerprint':snapshot['fingerprint'], 'candidate_fingerprint':digest(new_data)}
    if action == 'backup': return {'inverse':inverse, 'before_fingerprint':snapshot['fingerprint'], 'mode':mode}
    atomic_write(path,new_data,mode)
    back = path.read_bytes()
    if back != new_data or stat.S_IMODE(path.stat().st_mode) != mode: raise RepairError('remote_readback_failed')
    return {'ok':True, 'fingerprint':digest(back), 'projection':redact(parse(path,back)), 'mode':mode, 'host':host}


def main():
    try: print(json.dumps({'ok':True,'result':run_request(json.load(sys.stdin))}))
    except Exception as error:
        print(json.dumps({'ok':False,'error':getattr(error,'code','remote_operation_failed')}))
        return 1
    return 0


if __name__ == '__main__': sys.exit(main())
