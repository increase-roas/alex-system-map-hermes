"""Codex's installed app-server owns config edits; never replace config.toml.

Only nonsecret scalar settings cross this boundary. Config versions bind the whole
user layer, while inverse writes restore changed keys and preserve later unrelated
edits. Runtime defaults are explicitly scoped to future sessions.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import selectors
import shutil
import signal
import subprocess
import tempfile
import time
from datetime import datetime, timezone

from repair_contracts import RepairError


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


ALLOWED = {
    'model': str, 'model_reasoning_effort': str, 'model_reasoning_summary': str,
    'model_verbosity': str, 'web_search': str, 'approval_policy': str,
    'sandbox_mode': str, 'service_tier': str, 'personality': str,
    'model_context_window': int, 'model_auto_compact_token_limit': int,
}
ENUMS = {
    'model_verbosity': {'low', 'medium', 'high'},
    'model_reasoning_summary': {'auto', 'concise', 'detailed', 'none'},
    'web_search': {'disabled', 'cached', 'indexed', 'live'},
    'approval_policy': {'untrusted', 'on-request', 'never'},
    'sandbox_mode': {'read-only', 'workspace-write', 'danger-full-access'},
}
STATIC_DEFAULTS = {'model', 'model_reasoning_effort', 'service_tier', 'personality'}


def safe_values(values):
    from local_files import screen
    selected = {}
    for key, kind in ALLOWED.items():
        value = values.get(key)
        if type(value) is kind and not screen(str(value))[1]:
            selected[key] = value
    return selected


class CodexClient:
    """One request per fresh native process; no credentials or raw errors emitted."""

    def __init__(self, codex_home=None, binary=None, timeout=30):
        self.home = Path(codex_home or Path.home() / '.codex').absolute()
        self.binary = binary or shutil.which('codex') or str(Path.home() / '.local/bin/codex')
        self.timeout = timeout

    def request(self, method, params):
        env = {**os.environ, 'CODEX_HOME': str(self.home)}
        try:
            child = subprocess.Popen(
                [self.binary, 'app-server', '--stdio', '-c', 'features.apps=false', '-c', 'analytics.enabled=false'],
                cwd='/tmp', env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, start_new_session=True,
            )
        except OSError:
            raise RepairError('codex_unavailable') from None
        selector = selectors.DefaultSelector()
        selector.register(child.stdout, selectors.EVENT_READ)
        buffer = bytearray()

        def send(value):
            child.stdin.write(json.dumps(value).encode() + b'\n')
            child.stdin.flush()

        def receive(request_id):
            until = time.monotonic() + self.timeout
            while time.monotonic() < until:
                while b'\n' in buffer:
                    raw, _, tail = buffer.partition(b'\n')
                    buffer[:] = tail
                    value = json.loads(raw)
                    if value.get('id') == request_id:
                        if 'error' in value:
                            raise RepairError('codex_native_rejected')
                        return value['result']
                if not selector.select(max(0, until - time.monotonic())):
                    break
                chunk = os.read(child.stdout.fileno(), 65536)
                if not chunk:
                    break
                buffer.extend(chunk)
                if len(buffer) > 4 * 1024 * 1024:
                    raise RepairError('codex_response_too_large')
            raise RepairError('codex_native_timeout')

        try:
            send({'id': 1, 'method': 'initialize', 'params': {
                'clientInfo': {'name': 'system-map-repair', 'version': '1'},
                'capabilities': {'experimentalApi': True},
            }})
            receive(1)
            send({'method': 'initialized', 'params': {}})
            send({'id': 2, 'method': method, 'params': params})
            return receive(2)
        except RepairError:
            raise
        except Exception:
            raise RepairError('codex_protocol_failed') from None
        finally:
            selector.close()
            try:
                os.killpg(child.pid, signal.SIGTERM)
                child.wait(timeout=3)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                child.wait()
            child.stdin.close()
            child.stdout.close()


class CodexAdapter:
    adapter_id = 'codex-native'
    version = '1'

    def __init__(self, codex_home=None, client=None):
        self.home = Path(codex_home or Path.home() / '.codex').absolute()
        self.path = self.home / 'config.toml'
        self.client = client or CodexClient(self.home)
        self.target_id = digest(['codex-native', str(self.path)])[:32]

    def discover(self):
        return [{
            'id': self.target_id, 'adapter_id': self.adapter_id, 'category': 'app_settings',
            'owner': 'Codex native app-server', 'scope': 'local',
            'identity': {'system': 'codex', 'path': str(self.path), 'scope': 'user settings and future-session defaults'},
            'capabilities': ['read', 'propose', 'check', 'apply', 'verify', 'undo'],
            'observed_at': now(), 'evidence': ['Installed config/read and versioned config/batchWrite protocol'],
            'limitations': ['Readback proves fresh native configuration. Existing desktop threads may retain session defaults.'],
            'allowed_patch_paths': list(ALLOWED), 'content_format': 'json',
        }]

    def _assert_target(self, target):
        if target.get('id') != self.target_id or target.get('identity') != self.discover()[0]['identity']:
            raise RepairError('native_target_changed')

    def read(self, target):
        self._assert_target(target)
        value = self.client.request('config/read', {'includeLayers': True})
        layer = next((row for row in value.get('layers', [])
                      if row.get('name', {}).get('type') == 'user'
                      and not row.get('name', {}).get('profile')
                      and Path(row['name'].get('file', '')).resolve() == self.path.resolve()), None)
        if not layer or layer.get('disabledReason') or not layer.get('version'):
            raise RepairError('codex_user_layer_unavailable')
        projection = safe_values(value.get('config', {}))
        user = safe_values(layer.get('config', {}))
        version = layer['version']
        return {'projection': projection, 'user_values': user, 'version': version,
                'fingerprint': digest({'effective': projection, 'user': user, 'version': version}),
                'context_fingerprint': digest({'version': version, 'adapter_version': self.version})}

    def prepare(self, target, snapshot, proposal):
        self._assert_target(target)
        if set(proposal) != {'patch'} or not isinstance(proposal['patch'], dict) or not proposal['patch']:
            raise RepairError('native_patch_required')
        patch = copy.deepcopy(proposal['patch'])
        from local_files import screen
        for key, value in patch.items():
            if key not in ALLOWED or type(value) is not ALLOWED[key] or screen(str(value))[1]:
                raise RepairError('native_key_or_type_rejected')
            if (key in ENUMS and value not in ENUMS[key]) or (type(value) is str and not 0 < len(value) <= 256):
                raise RepairError('native_value_rejected')
            if type(value) is int and value < 1:
                raise RepairError('native_value_rejected')
        before = {key: {'exists': key in snapshot.get('user_values', {}), 'value': snapshot.get('user_values', {}).get(key)} for key in patch}
        # Exercise the installed native parser against a nonsecret candidate in
        # a disposable Codex home. The real user file is never copied or edited.
        if isinstance(self.client, CodexClient):
            candidate_values = {**snapshot.get('user_values', {}), **patch}
            with tempfile.TemporaryDirectory(prefix='codex-repair-check-') as temporary:
                candidate_path = Path(temporary) / 'config.toml'
                candidate_path.write_text(''.join(key + ' = ' + json.dumps(value) + '\n' for key, value in candidate_values.items()))
                CodexClient(temporary, self.client.binary).request('config/read', {'includeLayers': True})
        operation = {
            'action': 'config_patch', 'selector': {'file': str(self.path)}, 'patch': patch,
            'expected_version': snapshot['version'], 'expected_fingerprint': snapshot['fingerprint'],
            'context_fingerprint': snapshot['context_fingerprint'], 'inverse': before,
            'public_diff': json.dumps({'before': {key: snapshot['projection'].get(key) for key in patch}, 'after': patch}, indent=2),
            'checks': [{
                'kind': 'native_dry_run', 'status': 'passed', 'runner_id': 'codex-native-scalar-schema-v1',
                'input_digest': digest(patch), 'output_digest': digest({'valid': True}),
                'evidence': ['Native candidate config parser in disposable home; actual versioned write occurs only after approval.'],
                'checked_at': now(), 'limitations': ['Candidate parsing, not a live write or thread reload.'],
            }],
        }
        return operation

    def prepare_bundle(self, operations, targets):
        return operations

    def preflight(self, target, operation):
        current = self.read(target)
        if current['version'] != operation['expected_version'] or current['fingerprint'] != operation['expected_fingerprint']:
            raise RepairError('native_version_changed')
        return {'ok': True, 'evidence': ['Native user version and safe effective projection match approval.']}

    def backup(self, target, operation, backup_dir):
        self.preflight(target, operation)
        before = {'inverse': operation['inverse'], 'target_id': target['id']}
        destination = Path(backup_dir) / (target['id'] + '-' + digest(operation['patch'])[:12] + '-native-inverse.json')
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if destination.is_symlink():
            raise RepairError('native_backup_invalid')
        raw = json.dumps(before, sort_keys=True).encode()
        descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        if destination.read_bytes() != raw:
            raise RepairError('native_backup_failed')
        return before

    def _write(self, version, patch):
        result = self.client.request('config/batchWrite', {
            'filePath': str(self.path), 'expectedVersion': version, 'reloadUserConfig': True,
            'edits': [{'keyPath': key, 'mergeStrategy': 'replace', 'value': value} for key, value in patch.items()],
        })
        if Path(result.get('filePath', '')).resolve() != self.path.resolve() or result.get('status') not in {'ok', 'okOverridden'}:
            raise RepairError('native_write_unconfirmed')
        return {'status': result['status'], 'version': result.get('version')}

    def apply(self, target, operation, backup):
        self.preflight(target, operation)
        return self._write(operation['expected_version'], operation['patch'])

    def verify(self, target, operation, result):
        current = self.read(target)
        written = all(current['user_values'].get(key) == value for key, value in operation['patch'].items())
        effective = written and all(current['projection'].get(key) == value for key, value in operation['patch'].items())
        limitations = []
        if not effective:
            limitations.append('Native override or readback mismatch prevents effective confirmation.')
        if STATIC_DEFAULTS.intersection(operation['patch']):
            limitations.append('These defaults apply to future sessions; existing desktop threads are not proven reloaded.')
        return {'ok': effective, 'state': 'effective' if effective else 'pending',
                'fingerprint': current['fingerprint'], 'evidence': ['Fresh native config/read effective and user-layer readback.'],
                'checks': [{'kind': 'owner_lifecycle', 'status': 'passed' if effective else 'failed',
                            'runner_id': 'codex-config-read', 'evidence': ['Native safe fields compared.'], 'limitations': limitations}],
                'limitations': limitations}

    def reconcile(self, target, operation, backup):
        current = self.read(target)
        candidate = all(current['user_values'].get(key) == value for key, value in operation['patch'].items())
        inverse = operation['inverse']
        unchanged = all((key in current['user_values']) == old['exists'] and current['user_values'].get(key) == old['value'] for key, old in inverse.items())
        if operation.get('recovery_phase') == 'undo':
            return {'outcome': 'applied' if unchanged else 'not_applied' if candidate else 'unknown',
                    'result': {'status': 'inverse_reconciled', 'version': current['version']},
                    'evidence': ['Native inverse and candidate keys compared after interrupted Undo.']}
        if candidate:
            return {'outcome': 'applied', 'result': {'status': 'reconciled', 'version': current['version']}, 'evidence': ['Native changed keys match exact candidate.']}
        return {'outcome': 'not_applied' if unchanged else 'unknown', 'evidence': ['Native changed keys compared to candidate and preimage.']}

    def undo(self, target, operation, backup, applied):
        current = self.read(target)
        if backup.get('target_id') != target['id'] or backup.get('inverse') != operation['inverse']:
            raise RepairError('native_inverse_changed')
        if not all(current['user_values'].get(key) == value for key, value in operation['patch'].items()):
            return {'ok': False, 'state': 'blocked', 'fingerprint': current['fingerprint'],
                    'evidence': ['A repaired native key changed after application; no inverse write was attempted.'],
                    'checks': [], 'limitations': ['Newer repaired-key values are preserved.']}
        inverse_patch = {key: old['value'] if old['exists'] else None for key, old in backup['inverse'].items()}
        self._write(current['version'], inverse_patch)
        readback = self.read(target)
        ok = all((key in readback['user_values']) == old['exists'] and readback['user_values'].get(key) == old['value'] for key, old in backup['inverse'].items())
        return {'ok': ok, 'state': 'undone' if ok else 'unknown', 'fingerprint': readback['fingerprint'],
                'evidence': ['Changed keys restored through native versioned inverse and read back.'], 'checks': [],
                'limitations': ['Existing desktop thread reload remains unproven.']}


def register_adapters(registry):
    registry.register(CodexAdapter())
