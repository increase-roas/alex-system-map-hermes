#!/usr/bin/env python3
"""Explicit reviewed local-source repairs. No mutation on source/preview reads."""
import argparse
import base64
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import difflib
import fcntl
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import stat
import socket
import subprocess
import sys
import tempfile
import uuid
from urllib.parse import urlsplit

from local_files import read_source, screen

MAX_SOURCE = 65536
MAX_BODY = 192 * 1024


class RepairError(Exception):
    def __init__(self, code, message, status=400):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def sync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def private_write(path, raw):
    if path.is_symlink():
        raise RepairError('unsafe_state', 'Repair state must be a regular private file', 409)
    fd, temporary = tempfile.mkstemp(prefix='.repair-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        sync_dir(path.parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class RepairService:
    def __init__(self, home, index_path, state_dir):
        self.home = Path(home).absolute()
        self.index_path = Path(index_path)
        self.state = Path(state_dir) / 'local-file-repairs'
        fixture = os.environ.get('LOCAL_FILE_REPAIR_FIXTURE_HOME', '')
        self.fixture = bool(fixture)
        if self.fixture:
            temp_roots = [Path(tempfile.gettempdir()).resolve(), Path('/tmp').resolve()]
            actual = self.home.resolve()
            if Path(fixture).absolute() != self.home or not any(actual != root and root in actual.parents for root in temp_roots):
                raise RepairError('fixture_boundary', 'Fixture home must be an exact private temporary home', 400)
            if not all(actual in p.resolve().parents for p in [self.index_path, self.state]):
                raise RepairError('fixture_boundary', 'Fixture state must remain inside its temporary home', 400)
        self.state.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.state.is_symlink():
            raise RepairError('unsafe_state', 'Repair state directory cannot be an alias', 409)
        os.chmod(self.state, 0o700)

    def index(self):
        try:
            index = json.loads(self.index_path.read_text())
        except (OSError, ValueError):
            raise RepairError('index_unavailable', 'Refresh the local-file inventory before reviewing a repair', 409)
        if Path(index.get('home', '')).absolute() != self.home:
            raise RepairError('index_home_mismatch', 'Local-file inventory belongs to a different home; refresh it', 409)
        return index

    def owned_path(self, path):
        lexical = Path(path).absolute()
        folders = [self.home / p for p in ['.agents/instructions', '.claude/rules', '.cursor/rules', 'Alex-Director/rules']]
        singles = [self.home / p for p in ['AGENTS.md', 'AGENT-CONTEXT.md', 'Alex-Director/AGENTS.md']]
        return lexical.suffix.lower() in {'.md', '.mdc', '.txt'} and (lexical in singles or any(root in lexical.parents for root in folders))

    def canonical_path(self, path):
        p = Path(path)
        if not self.owned_path(p):
            raise RepairError('unsupported_source', 'Only indexed handwritten rule sources in the listed editable locations can be repaired', 400)
        relative = p.relative_to(self.home)
        current = self.home
        for component in relative.parts:
            current = current / component
            if current.is_symlink():
                raise RepairError('shared_link', 'This is a shared link; open its indexed canonical source instead', 400)
        if self.fixture and self.home.resolve() not in p.resolve().parents:
            raise RepairError('fixture_boundary', 'Fixture source escaped its temporary home', 400)
        return p

    def inspected(self, file_id):
        idx = self.index()
        row = next((r for r in idx['files'] if r['id'] == file_id), None)
        if row is None:
            raise RepairError('unknown_file', 'Select an existing indexed file', 400)
        path = self.canonical_path(row['path'])
        if row['state'] != 'readable' or row['generated'] or row['kind'] in {'config', 'script', 'hook', 'skill'}:
            raise RepairError('managed_source', 'Generated, managed, skill and executable sources require their owning workflow', 400)
        if str(path.resolve(strict=True)) != row['real_path']:
            raise RepairError('source_target_changed', 'The indexed source target changed; refresh the inventory', 409)
        try:
            raw, st, _ = read_source(path, [Path(r['path']).resolve() for r in idx['coverage']['roots']], MAX_SOURCE)
            text = raw.decode('utf-8')
        except (OSError, OverflowError, RuntimeError, UnicodeError):
            raise RepairError('source_unavailable', 'Source must be readable UTF-8 and at most 64 KiB; refresh or open its owner', 400)
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
            raise RepairError('shared_file', 'Only a regular source with one native file link can be repaired here', 400)
        if re.search(r'(?i)\bgenerated\b|auto.generated|do not edit', text[:6000]):
            raise RepairError('managed_source', 'This source declares generated or managed ownership; use its owner', 400)
        if screen(text)[1]:
            raise RepairError('redacted_source', 'This source contains screened material and cannot be edited in the generic repair editor', 400)
        return idx, row, path, raw, st

    def owner_ids(self, idx, row):
        ids = [r['target_id'] for r in idx['references'] if r['source_id'] == row['id'] and r['kind'] in {'generated_from', 'symlink'}]
        candidates = [r for r in idx['files'] if r['id'] != row['id'] and r['real_path'] == row['real_path']]
        for reference in row.get('generated_sources', []):
            # Native unify headers are relative to ~/.agents, even when their
            # generated distribution lives in ~/.codex or another harness.
            relative = re.sub(r'\s+\([^)]*\)\s*$', '', reference).strip()
            target = self.home / '.agents' / relative
            candidates += [r for r in idx['files'] if Path(r['path']) == target]
        for candidate in candidates:
            try:
                if not candidate['generated']:
                    self.canonical_path(candidate['path'])
                    ids.append(candidate['id'])
            except (RepairError, OSError, ValueError):
                pass
        # Return existing indexed, canonical editable owners only. No caller path
        # or generated-header text can cause a file outside the index to be read.
        result = []
        for file_id in ids:
            candidate = next((r for r in idx['files'] if r['id'] == file_id), None)
            try:
                if candidate and not candidate['generated']:
                    self.canonical_path(candidate['path'])
                    result.append(file_id)
            except (RepairError, OSError, ValueError):
                pass
        return list(dict.fromkeys(result))

    def source(self, file_id):
        idx = self.index()
        row = next((r for r in idx['files'] if r['id'] == file_id), None)
        owner_ids = self.owner_ids(idx, row) if row else []
        result = {'file_id': file_id, 'path': row['path'] if row else '', 'sha256': None, 'content': '', 'editable': False, 'reason': '', 'source_file_ids': list(dict.fromkeys(owner_ids))}
        try:
            _, _, _, raw, _ = self.inspected(file_id)
            result.update(sha256=sha(raw), content=raw.decode(), editable=True, reason='Handwritten canonical source. Preview an exact edit before applying it.')
        except (RepairError, OSError) as exc:
            result['reason'] = exc.message if isinstance(exc, RepairError) else 'Source unavailable; refresh the inventory'
        return result

    def git(self, repo, *args, binary=False):
        try:
            run = subprocess.run(['git', '-C', str(repo), *args], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=30, env={**os.environ, 'GIT_TERMINAL_PROMPT': '0', 'GIT_OPTIONAL_LOCKS': '0'})
        except (OSError, subprocess.TimeoutExpired):
            raise RepairError('git_unavailable', 'Native Git did not finish; source publication requires manual inspection', 409)
        if run.returncode:
            raise RepairError('git_failed', 'Native Git check or publication failed; inspect this source repository before retrying', 409)
        return run.stdout if binary else run.stdout.decode('utf-8').strip()

    def git_blob(self, repo, revision, relative):
        key = revision + ':' + relative
        size = self.git(repo, 'cat-file', '-s', key)
        if not size.isdigit() or int(size) > MAX_SOURCE:
            raise RepairError('git_preimage', 'Tracked source preimage is unavailable or too large', 409)
        return self.git(repo, 'show', key, binary=True)

    def repo_info(self, path):
        repo = Path(self.git(path.parent, 'rev-parse', '--show-toplevel'))
        if self.fixture and self.home.resolve() not in repo.resolve().parents:
            raise RepairError('fixture_boundary', 'Fixture Git repository must be inside fixture home', 400)
        relative = path.relative_to(repo).as_posix()
        branch = self.git(repo, 'symbolic-ref', '--quiet', '--short', 'HEAD')
        if not branch or branch.startswith('-'):
            raise RepairError('git_branch', 'Source needs an attached current branch', 409)
        head = self.git(repo, 'rev-parse', 'HEAD')
        origin = self.git(repo, 'remote', 'get-url', 'origin')
        if self.git(repo, 'remote', 'get-url', '--push', 'origin') != origin:
            raise RepairError('remote_mismatch', 'Origin fetch and push destinations differ; inspect source repository publication first', 409)
        host = urlsplit(origin).hostname if '://' in origin else (origin.split('@', 1)[-1].split(':', 1)[0] if re.match(r'^[^/@:]+@[^:]+:', origin) else None)
        if host:
            lowered = host.lower().rstrip('.')
            local_host = lowered in {'localhost', 'localhost.localdomain', socket.gethostname().lower().rstrip('.'), socket.getfqdn().lower().rstrip('.')}
            try:
                address = ipaddress.ip_address(lowered)
                mapped = getattr(address, 'ipv4_mapped', None)
                local_host = local_host or address.is_loopback or address.is_unspecified or bool(mapped and mapped.is_loopback)
            except ValueError:
                pass
            if local_host:
                raise RepairError('remote_not_durable', 'Loopback or this-machine origin cannot prove off-machine durability', 409)
        local = not (origin.startswith(('https://', 'ssh://', 'git://')) or re.match(r'^[^/@:]+@[^:]+:', origin))
        if local:
            local_path = Path(origin.removeprefix('file://'))
            if not local_path.is_absolute():
                local_path = repo / local_path
            if not self.fixture or self.home.resolve() not in local_path.resolve().parents:
                raise RepairError('remote_not_durable', 'Origin must be off this machine before a live source repair; push the exact preimage first', 409)
            if self.git(local_path, 'rev-parse', '--is-bare-repository') != 'true':
                raise RepairError('fixture_boundary', 'Fixture origin must be its private bare repository', 400)
        return {'repo': str(repo), 'relative': relative, 'branch': branch, 'head': head, 'origin_sha256': sha(origin.encode())}

    def remote_head(self, info):
        value = self.git(Path(info['repo']), 'ls-remote', '--exit-code', 'origin', 'refs/heads/' + info['branch'])
        rows = value.splitlines()
        if len(rows) != 1 or not re.fullmatch(r'[a-f0-9]{40,64}', rows[0].split()[0]):
            raise RepairError('remote_preimage', 'Origin current branch could not be verified exactly', 409)
        return rows[0].split()[0]

    def backed_preimage(self, path, raw):
        info = self.repo_info(path)
        repo, rel = Path(info['repo']), info['relative']
        if self.git_blob(repo, 'HEAD', rel) != raw or self.git_blob(repo, '', rel) != raw:
            raise RepairError('git_preimage', 'Source exact bytes must already match both Git HEAD and index; commit and push existing source edits first', 409)
        self.git(repo, 'diff', '--quiet', '--', ':(literal)' + rel)
        self.git(repo, 'diff', '--cached', '--quiet', 'HEAD', '--', ':(literal)' + rel)
        if self.remote_head(info) != info['head']:
            raise RepairError('remote_preimage', 'Push the exact current source branch before applying a repair', 409)
        return info

    @contextmanager
    def locked(self):
        fd = os.open(self.state / 'operation.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            os.close(fd)

    def save(self, repair_id, value):
        private_write(self.state / (repair_id + '.json'), canonical(value))

    def load(self, repair_id):
        if not isinstance(repair_id, str) or not re.fullmatch(r'[a-f0-9]{32}', repair_id):
            raise RepairError('invalid_repair', 'Select a frozen preview before applying or undoing', 400)
        path = self.state / (repair_id + '.json')
        try:
            if path.is_symlink():
                raise ValueError()
            value = json.loads(path.read_text())
        except (OSError, ValueError):
            raise RepairError('unknown_repair', 'Repair preview or receipt is unavailable; create a fresh preview', 400)
        if sha(canonical(value['proposal'])) != value['proposal_sha256']:
            raise RepairError('proposal_changed', 'Frozen proposal no longer matches its fingerprint', 409)
        return value

    def preview(self, file_id, expected_sha256, new_content):
        if not isinstance(new_content, str) or len(new_content.encode()) > MAX_SOURCE or '\x00' in new_content:
            raise RepairError('invalid_content', 'Proposed source must be UTF-8 text at most 64 KiB without NUL bytes', 400)
        if screen(new_content)[1]:
            raise RepairError('secret_proposal', 'Proposed text contains screened credential or command material; use the source owning workflow', 400)
        with self.locked():
            idx, row, path, before, st = self.inspected(file_id)
            if sha(before) != expected_sha256:
                raise RepairError('stale_source', 'Source changed after it was displayed; reopen it before previewing', 409)
            after = new_content.encode()
            if before == after:
                raise RepairError('no_change', 'Change the proposed text before creating a preview', 400)
            info = self.backed_preimage(path, before)
            repair_id = uuid.uuid4().hex
            created = timestamp()
            expires = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
            generated = (self.home / '.agents' / 'instructions') in path.parents or any(r['target_id'] == file_id and r['kind'] == 'generated_from' for r in idx['references'])
            proposal = {'repair_id': repair_id, 'file_id': file_id, 'path': str(path), 'real_path': str(path.resolve()), 'before': base64.b64encode(before).decode(), 'after': base64.b64encode(after).decode(), 'before_sha256': sha(before), 'after_sha256': sha(after), 'mode': stat.S_IMODE(st.st_mode), 'created_at': created, 'expires_at': expires, 'git': info, 'generated_follow_up': generated}
            digest = sha(canonical(proposal))
            self.save(repair_id, {'proposal': proposal, 'proposal_sha256': digest, 'phase': 'preview'})
            return {'repair_id': repair_id, 'file_id': file_id, 'path': str(path), 'before_sha256': sha(before), 'after_sha256': sha(after), 'proposal_sha256': digest, 'diff': ''.join(difflib.unified_diff(before.decode().splitlines(keepends=True), new_content.splitlines(keepends=True), fromfile=str(path) + ' (before)', tofile=str(path) + ' (proposed)')), 'created_at': created, 'expires_at': expires, 'generated_follow_up': generated}

    def backup(self, proposal):
        base = self.home / 'Backups'
        if not base.is_dir():
            raise RepairError('backup_unavailable', 'Existing ~/Backups Drive location is unavailable; source is unchanged', 409)
        if self.fixture and self.home.resolve() not in base.resolve().parents:
            raise RepairError('fixture_boundary', 'Fixture backup escaped its temporary home', 400)
        folder = base / 'local-file-repairs'
        folder.mkdir(mode=0o700, exist_ok=True)
        if folder.is_symlink():
            raise RepairError('backup_unavailable', 'Undo-copy folder must not be an unexpected alias', 409)
        path = folder / (proposal['repair_id'] + '.before')
        raw = base64.b64decode(proposal['before'])
        private_write(path, raw)
        os.chmod(path, proposal['mode'])
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        metadata = folder / (proposal['repair_id'] + '.json')
        private_write(metadata, canonical({'path': proposal['path'], 'sha256': proposal['before_sha256'], 'mode': proposal['mode']}))
        sync_dir(folder)
        if path.read_bytes() != raw or stat.S_IMODE(path.stat().st_mode) != proposal['mode']:
            raise RepairError('backup_unverified', 'Undo copy readback failed; source is unchanged', 409)
        return str(path)

    def replace(self, proposal, expected, replacement):
        path = self.canonical_path(proposal['path'])
        if str(path.resolve()) != proposal['real_path']:
            raise RepairError('source_target_changed', 'Source target changed after preview', 409)
        raw, st, actual = read_source(path, [self.home.resolve()], MAX_SOURCE)
        if str(actual) != proposal['real_path']:
            raise RepairError('source_target_changed', 'Source target changed after preview', 409)
        if sha(raw) != expected or stat.S_IMODE(st.st_mode) != proposal['mode'] or st.st_nlink != 1:
            raise RepairError('stale_source', 'Source contents or mode changed; source is unchanged by this request', 409)
        # Parent descriptors refuse link swaps; CAS is checked again immediately
        # before the same-directory atomic replacement.
        fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
        temporary = '.local-repair-' + uuid.uuid4().hex
        try:
            for part in Path(proposal['real_path']).parts[1:-1]:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = child
            out = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, proposal['mode'], dir_fd=fd)
            with os.fdopen(out, 'wb') as stream:
                stream.write(replacement)
                stream.flush()
                os.fchmod(stream.fileno(), proposal['mode'])
                os.fsync(stream.fileno())
            current, current_st, current_real = read_source(path, [self.home.resolve()], MAX_SOURCE)
            self.canonical_path(proposal['path'])
            native = os.stat(path.name, dir_fd=fd, follow_symlinks=False)
            if str(current_real) != proposal['real_path'] or str(path.resolve()) != proposal['real_path'] or sha(current) != expected or (native.st_dev, native.st_ino) != (st.st_dev, st.st_ino) or stat.S_IMODE(current_st.st_mode) != proposal['mode']:
                raise RepairError('stale_source', 'Source changed immediately before replacement', 409)
            os.replace(temporary, path.name, src_dir_fd=fd, dst_dir_fd=fd)
            os.fsync(fd)
        finally:
            try:
                os.unlink(temporary, dir_fd=fd)
            except FileNotFoundError:
                pass
            os.close(fd)
        check, _, _ = read_source(path, [self.home.resolve()], MAX_SOURCE)
        if check != replacement:
            raise RepairError('source_readback', 'Replacement needs manual inspection; recovery data is retained', 409)

    def known_index(self, proposal, info):
        repo, rel = Path(info['repo']), info['relative']
        staged_hash = sha(self.git_blob(repo, '', rel))
        entry = self.git(repo, 'ls-files', '--stage', '--', ':(literal)' + rel).split()
        expected_mode = '100755' if proposal['mode'] & 0o111 else '100644'
        if staged_hash not in {proposal['before_sha256'], proposal['after_sha256']} or len(entry) < 3 or entry[0] != expected_mode or entry[2] != '0':
            raise RepairError('git_index_changed', 'Source index has newer staged contents or mode; inspect it before publication or Undo', 409)

    def publish(self, proposal, value, undo=False):
        info = self.repo_info(Path(proposal['path']))
        if any(info[key] != proposal['git'][key] for key in ['repo', 'branch', 'origin_sha256']):
            raise RepairError('git_branch_changed', 'Source repository or branch changed; inspect publication manually', 409)
        expected_parent = value.get('undo_parent_head') if undo else proposal['git']['head']
        if info['head'] != expected_parent:
            raise RepairError('git_head_changed', 'Git HEAD changed during repair; inspect one-path publication manually', 409)
        expected = proposal['before_sha256'] if undo else proposal['after_sha256']
        repo, rel = Path(info['repo']), info['relative']
        self.known_index(proposal, info)
        path = self.canonical_path(proposal['path'])
        raw, current_st, real = read_source(path, [self.home.resolve()], MAX_SOURCE)
        if sha(raw) != expected or str(real) != proposal['real_path'] or stat.S_IMODE(current_st.st_mode) != proposal['mode']:
            raise RepairError('stale_source', 'Source changed before commit; publication is pending', 409)
        value['phase'] = 'undo_commit_started' if undo else 'commit_started'
        self.save(proposal['repair_id'], value)
        if sha(self.git_blob(repo, 'HEAD', rel)) != expected:
            self.git(repo, 'commit', '--only', '-m', 'Restore reviewed local instruction' if undo else 'Repair reviewed local instruction', '--', ':(literal)' + rel)
        commit = self.git(repo, 'rev-parse', 'HEAD')
        if commit != expected_parent:
            parents = self.git(repo, 'rev-list', '--parents', '-n', '1', commit).split()
            changed = self.git(repo, 'diff-tree', '--no-commit-id', '--name-only', '-r', commit).splitlines()
            if parents != [commit, expected_parent] or changed != [rel]:
                raise RepairError('commit_scope', 'Commit scope or parent changed; inspect publication before pushing', 409)
        if sha(self.git_blob(repo, 'HEAD', rel)) != expected:
            raise RepairError('commit_readback', 'Source commit readback did not match the reviewed bytes', 409)
        value['commit'] = commit
        value['phase'] = 'undo_push_started' if undo else 'push_started'
        self.save(proposal['repair_id'], value)
        self.git(repo, 'push', '--porcelain', 'origin', commit + ':refs/heads/' + info['branch'])
        if self.remote_head(info) != commit:
            raise RepairError('push_readback', 'Remote commit could not be confirmed; publication remains pending', 409)
        return commit

    def result(self, value, undo, pushed, message):
        p = value['proposal']
        current_hash = p['before_sha256'] if undo else p['after_sha256']
        try:
            path = self.canonical_path(p['path'])
            current, _, real = read_source(path, [self.home.resolve()], MAX_SOURCE)
            if str(real) != p['real_path']:
                raise OSError()
            current_hash = sha(current)
            if current_hash != (p['before_sha256'] if undo else p['after_sha256']):
                message += ' Current source changed after replacement; publication stopped.'
        except (RepairError, OSError, RuntimeError, OverflowError):
            message += ' Current source readback is unavailable; fingerprint describes the recorded replacement.'
        return {'repair_id': p['repair_id'], 'file_id': p['file_id'], 'path': p['path'], 'state': ('undone' if undo else 'applied') + ('' if pushed else '_publish_pending'), 'current_sha256': current_hash, 'backup_path': value.get('backup_path', ''), 'commit': value.get('commit'), 'pushed': pushed, 'generated_follow_up': p['generated_follow_up'], 'message': message + (' Generated-publication verification remains pending; existing repository hooks may run. This app did not directly invoke an app-settings builder.' if p['generated_follow_up'] else '') + ' Undo copy verified locally; Drive cloud upload was not verified.'}

    def reconcile(self, value, undo=False):
        if not undo and 'undo_result' in value:
            undo = True
        key = 'undo_result' if undo else 'result'
        p = value['proposal']
        expected = p['before_sha256'] if undo else p['after_sha256']
        try:
            path = self.canonical_path(p['path'])
            raw, st, real = read_source(path, [self.home.resolve()], MAX_SOURCE)
        except (RepairError, OSError, RuntimeError, OverflowError):
            raise RepairError('repair_recovery', 'Earlier repair source is unavailable or changed; no side effect was retried', 409)
        if sha(raw) != expected or str(real) != p['real_path'] or stat.S_IMODE(st.st_mode) != p['mode']:
            raise RepairError('stale_source', 'Recorded repair source now has newer contents, target or mode; no side effect was retried', 409)
        if key in value:
            return value[key]
        result = self.result(value, undo, False, 'Recorded source operation reconciled; publication needs manual inspection. No side effect was retried.')
        value[key] = result
        self.save(p['repair_id'], value)
        return result

    def apply(self, repair_id, proposal_sha256):
        with self.locked():
            value = self.load(repair_id)
            if value['proposal_sha256'] != proposal_sha256:
                raise RepairError('proposal_changed', 'Apply must name the exact reviewed proposal fingerprint', 409)
            if value['phase'] != 'preview':
                return self.reconcile(value)
            p = value['proposal']
            if datetime.now(timezone.utc) > datetime.fromisoformat(p['expires_at']):
                raise RepairError('proposal_expired', 'Preview expired; reopen and review a fresh proposal', 409)
            _, row, path, before, st = self.inspected(p['file_id'])
            if str(path) != p['path'] or sha(before) != p['before_sha256'] or stat.S_IMODE(st.st_mode) != p['mode']:
                raise RepairError('stale_source', 'Source changed after preview; review a fresh proposal', 409)
            if self.backed_preimage(path, before) != p['git']:
                raise RepairError('git_changed', 'Source repository changed after preview; review a fresh proposal', 409)
            value['backup_path'] = self.backup(p)
            value['phase'] = 'replacing'
            self.save(repair_id, value)
            try:
                self.replace(p, p['before_sha256'], base64.b64decode(p['after']))
            except RepairError as exc:
                if exc.code in {'stale_source', 'source_target_changed', 'shared_link'}:
                    value['phase'] = 'preview'
                    self.save(repair_id, value)
                raise
            value['phase'] = 'source_applied'
            self.save(repair_id, value)
            try:
                value['commit'] = self.publish(p, value)
                result = self.result(value, False, True, 'Source updated, exact readback verified, one-path commit pushed.')
            except (RepairError, OSError):
                result = self.result(value, False, False, 'Source updated; commit or push is pending. Recovery is retained; inspect the repository before any manual publication.')
            value['result'] = result
            value['phase'] = 'applied'
            self.save(repair_id, value)
            return result

    def undo(self, repair_id):
        with self.locked():
            value = self.load(repair_id)
            if 'undo_result' in value or value['phase'].startswith('undo_'):
                return self.reconcile(value, True)
            if 'result' not in value:
                raise RepairError('not_applied', 'This repair has no recorded applied source to undo', 409)
            p = value['proposal']
            backup = Path(value['backup_path'])
            expected_folder = (self.home / 'Backups' / 'local-file-repairs').resolve()
            if backup.is_symlink() or backup.parent.resolve() != expected_folder or sha(backup.read_bytes()) != p['before_sha256']:
                raise RepairError('backup_changed', 'Exact recorded undo copy is unavailable; source is unchanged', 409)
            path = self.canonical_path(p['path'])
            current, _, _ = read_source(path, [self.home.resolve()], MAX_SOURCE)
            if sha(current) != p['after_sha256']:
                raise RepairError('stale_source', 'Source has newer edits; conditional Undo will not overwrite them', 409)
            info = self.repo_info(path)
            if any(info[key] != p['git'][key] for key in ['repo', 'branch', 'origin_sha256']):
                raise RepairError('git_changed', 'Source repository changed; inspect the restoration manually', 409)
            self.known_index(p, info)
            value['undo_parent_head'] = info['head']
            value['phase'] = 'undo_replacing'
            self.save(repair_id, value)
            self.replace(p, p['after_sha256'], backup.read_bytes())
            value['phase'] = 'undo_source_restored'
            value['commit'] = None
            self.save(repair_id, value)
            try:
                value['commit'] = self.publish(p, value, True)
                result = self.result(value, True, True, 'Exact preimage restored, read back, and restoration pushed.')
            except (RepairError, OSError):
                result = self.result(value, True, False, 'Exact preimage restored; restoration commit or push remains pending. No publication will retry automatically.')
            value['undo_result'] = result
            value['phase'] = 'undone'
            self.save(repair_id, value)
            return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--index', required=True)
    parser.add_argument('--state', required=True)
    args = parser.parse_args()
    try:
        raw = sys.stdin.buffer.read(MAX_BODY + 1)
        if len(raw) > MAX_BODY:
            raise RepairError('body_too_large', 'Repair request exceeds 192 KiB', 400)
        request = json.loads(raw)
        service = RepairService(Path.home(), Path(args.index), Path(args.state))
        action = request.get('action')
        allowed = {'source': {'action', 'file_id'}, 'preview': {'action', 'file_id', 'expected_sha256', 'new_content'}, 'apply': {'action', 'repair_id', 'proposal_sha256'}, 'undo': {'action', 'repair_id'}}
        if action not in allowed or set(request) != allowed[action] or not all(isinstance(v, str) for v in request.values()):
            raise RepairError('invalid_request', 'Use a supported action with its exact named text fields', 400)
        if action == 'source':
            result = service.source(request['file_id'])
        elif action == 'preview':
            result = service.preview(request['file_id'], request['expected_sha256'], request['new_content'])
        elif action == 'apply':
            result = service.apply(request['repair_id'], request['proposal_sha256'])
        else:
            result = service.undo(request['repair_id'])
        print(json.dumps({'status': 200, 'data': result}))
    except RepairError as exc:
        print(json.dumps({'status': exc.status, 'error': exc.message, 'code': exc.code}))
    except (OSError, ValueError, KeyError, TypeError, OverflowError, RuntimeError):
        print(json.dumps({'status': 409, 'error': 'Local source repair could not finish safely; source or private recovery state needs inspection', 'code': 'repair_unavailable'}))


if __name__ == '__main__':
    main()
