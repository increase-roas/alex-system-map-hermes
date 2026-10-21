"""Registered native local owners for immutable universal repair operations.

Only canonical sources are editable. Generated copies and Git publication are
explicit appended targets, frozen once per bundle. No model-supplied command is
run; source checks parse private temporary bytes. Runtime evidence stays pending.
"""
import copy
from datetime import datetime, timezone
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import tempfile
from urllib.parse import urlsplit

from local_file_distribution import Distribution, SOURCES, OUTPUTS, DEPENDENTS
from local_files import screen, canonical_gates_section
from repair_contracts import RepairError
from repair_local_checks import check, run_checks, load_json, python_source_projection

MAX_BYTES = 262144
SOURCE_LANGUAGES = frozenset(('py', 'sh', 'bash', 'zsh', 'js', 'cjs', 'mjs', 'go'))
EXECUTABLES = ('tools/unify/build_instructions.py', 'tools/unify/check.py', 'tools/unify/skill_lifecycle.py',
               'tools/unify/validate_docs.py', 'tools/guards/pre_tool_guard.py', 'tools/guards/commit_checked.py')
CLAUDE_KEYS = ('model', 'outputStyle', 'language', 'alwaysThinkingEnabled', 'effortLevel', 'spinnerTipsEnabled')
CURSOR_KEYS = ('model',)
JSON_OWNERS = {'.claude/settings.json': ('app_settings', 'claude', CLAUDE_KEYS + ('hooks',)),
               '.claude/settings.local.json': ('app_settings', 'claude', CLAUDE_KEYS + ('hooks',)),
               '.cursor/cli-config.json': ('cli_config', 'cursor-cli', CURSOR_KEYS),
               '.cursor/hooks.json': ('hook', 'cursor', ('hooks',)),
               '.codex/hooks.json': ('hook', 'codex', ('hooks',))}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def path_relative(target, home):
    return Path(target['identity']['path']).relative_to(home).as_posix()


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def target_id(path, kind='file'):
    return 'local-' + kind + '-' + sha(str(path).encode())[:24]


def _legacy_error(code, *_):
    return RepairError(code)


PRIVATE_KEY = re.compile(r'(?i)(?:secret|password|passwd|credential|token|api.?key|authorization|private.?key|client.?secret|access.?key|connection.?string|database.?url|dsn|cookie|headers?|^env$)')
PRIVATE_VALUE = re.compile(r'(?i)(?:-----BEGIN [^-]*(?:PRIVATE KEY|CERTIFICATE)-----|\b(?:sk-(?:proj-|ant-)?[A-Za-z0-9_-]{10,}|gh[pousr]_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+|xox[baprs]-[A-Za-z0-9-]+|AKIA[A-Z0-9]{16}|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)\b|(?:token|secret|password|api[_-]?key|authorization)\s*[:=]|--(?:token|password|api[-_]key|secret)\s+|\bBearer\s+|https?://[^\s/@:]+:[^\s/@]+@)')


def safe_json_projection(value):
    """Owner schema projection retains canonical command keys as untrusted data.

    Credential containers never enter a prompt. A hidden string remains a
    marker; proposals cannot write that marker back over its private value.
    """
    if isinstance(value, dict):
        return {key: safe_json_projection(item) for key, item in value.items() if not PRIVATE_KEY.search(key)}
    if isinstance(value, list):
        return [safe_json_projection(item) for item in value]
    if isinstance(value, str) and (PRIVATE_VALUE.search(value) or re.search(r'\b[A-Z_][A-Z0-9_]*\s*=|(?:--header|-H)\s+|[?&](?:key|token|password|secret|api[_-]?key)=', value)):
        return '[REDACTED]'
    return copy.deepcopy(value)


def get_key(value, key):
    current = value
    for piece in key.split('.'):
        if isinstance(current, dict) and piece in current:
            current = current[piece]
        elif isinstance(current, list) and piece.isdigit() and int(piece) < len(current):
            current = current[int(piece)]
        else:
            return {'exists': False}
    return {'exists': True, 'value': copy.deepcopy(current)}


def set_key(value, key, item):
    pieces = key.split('.')
    node = value
    for piece in pieces[:-1]:
        if isinstance(node, dict):
            if piece not in node:
                node[piece] = {}
            node = node[piece]
        elif isinstance(node, list) and piece.isdigit() and int(piece) < len(node):
            node = node[int(piece)]
        else:
            raise RepairError('patch_parent_type')
    leaf = pieces[-1]
    if isinstance(node, dict):
        if item['exists']:
            node[leaf] = copy.deepcopy(item['value'])
        else:
            node.pop(leaf, None)
    elif isinstance(node, list) and leaf.isdigit() and int(leaf) < len(node) and item['exists']:
        node[int(leaf)] = copy.deepcopy(item['value'])
    else:
        raise RepairError('patch_parent_type')


def editable_leaves(value, prefix=''):
    if isinstance(value, dict):
        return [path for key, item in value.items() if not PRIVATE_KEY.search(key)
                for path in editable_leaves(item, prefix + '.' + key if prefix else key)]
    if isinstance(value, list):
        return [path for index, item in enumerate(value) for path in editable_leaves(item, prefix + '.' + str(index))]
    return [] if value == '[REDACTED]' else [prefix]


class LocalAdapter:
    adapter_id = 'local-owner'
    version = '1'

    def __init__(self, home=None):
        self.home = Path(home or Path.home()).absolute()
        self.fixture = self.home.resolve() != Path.home().resolve() and any(p == self.home.resolve() or p in self.home.resolve().parents for p in (Path('/tmp').resolve(), Path(tempfile.gettempdir()).resolve()))
        self.distribution = Distribution(self.home, _legacy_error)
        self._targets = {}

    def safe(self, path, missing=False):
        path = Path(path).absolute()
        try:
            relative = path.relative_to(self.home)
        except ValueError:
            raise RepairError('path_outside_owner')
        current = self.home
        if current.is_symlink():
            raise RepairError('owner_alias')
        for component in relative.parts:
            current /= component
            if current.is_symlink():
                raise RepairError('owner_alias')
        if not missing and not path.is_file():
            raise RepairError('source_missing')
        if path.exists() and (not path.is_file() or path.stat().st_nlink != 1):
            raise RepairError('shared_file')
        return path

    def state(self, path, missing=False):
        path = self.safe(path, missing)
        try:
            # Open every ancestor with O_NOFOLLOW, not just the leaf. Atomic
            # replacements use that same anchored parent descriptor below.
            parent = self.parent_fd(path)
            try:
                fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
            finally:
                os.close(parent)
        except FileNotFoundError:
            if missing:
                return None, {'exists': False}
            raise RepairError('source_missing')
        try:
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > MAX_BYTES:
                raise RepairError('source_shape')
            with os.fdopen(fd, 'rb', closefd=False) as stream:
                raw = stream.read(MAX_BYTES + 1)
            after = os.fstat(fd)
            current = os.stat(path, follow_symlinks=False)
            values = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_size, s.st_mtime_ns)
            if values(before) != values(after) or values(current) != values(after) or len(raw) != after.st_size:
                raise RepairError('source_raced')
            state = {'exists': True, 'sha256': sha(raw), 'mode': stat.S_IMODE(after.st_mode), 'inode': after.st_ino, 'device': after.st_dev}
            return raw, state
        finally:
            os.close(fd)

    def parent_fd(self, path):
        fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
        try:
            for component in Path(path).parts[1:-1]:
                nxt = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = nxt
            return fd
        except BaseException:
            os.close(fd)
            raise

    def replace(self, path, raw, expected, mode):
        path = self.safe(path, True)
        parent = self.parent_fd(path)
        name = '.repair-' + os.urandom(12).hex()
        try:
            fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode, dir_fd=parent)
            with os.fdopen(fd, 'wb') as stream:
                os.fchmod(stream.fileno(), mode)
                stream.write(raw); stream.flush(); os.fsync(stream.fileno())
            if self.state(path, True)[1] != expected:
                raise RepairError('stale_source')
            # Confirm the visible parent is the descriptor we anchored. Never
            # install into a directory exchanged during preflight.
            visible = self.parent_fd(path)
            try:
                if (os.fstat(visible).st_dev, os.fstat(visible).st_ino) != (os.fstat(parent).st_dev, os.fstat(parent).st_ino):
                    raise RepairError('parent_raced')
            finally:
                os.close(visible)
            os.replace(name, path.name, src_dir_fd=parent, dst_dir_fd=parent)
            os.fsync(parent)
        finally:
            try:
                os.unlink(name, dir_fd=parent)
            except FileNotFoundError:
                pass
            os.close(parent)
        return self.state(path)[1]

    def provider_skills(self):
        lock = self.home / '.agents/.skill-lock.json'
        if not lock.exists():
            return set()
        try:
            raw, _ = self.state(lock)
            value = load_json(raw)
            if value.get('version') != 3 or not isinstance(value.get('skills'), dict):
                raise RepairError('provider_registry_invalid')
            return set(value['skills'])
        except (ValueError, OSError):
            raise RepairError('provider_registry_invalid')

    def context(self, target=None):
        inputs = {}
        for relative in ('.agents/.skill-lock.json', '.agents/tools/unify/skill-routes.json'):
            path = self.home / relative
            if path.exists():
                inputs[relative] = self.state(path)[1]
        if target and target['category'] == 'skill':
            folder = Path(target['identity']['path']).parent
            for runtime in ('.claude', '.cursor'):
                link = self.home / runtime / 'skills' / folder.name
                inputs[str(link)] = {'exists': link.exists() or link.is_symlink(), 'link': os.readlink(link) if link.is_symlink() else None}
        return sha(canonical({'version': self.version, 'home': str(self.home), 'inputs': inputs}))

    def row(self, path, category, owner, **extra):
        if category == 'executable':
            extra.update(content_language=Path(path).suffix.lstrip('.'), source_language=Path(path).suffix.lstrip('.'))
        return {'id': target_id(path, 'repo' if category == 'publication' else 'file'), 'adapter_id': self.adapter_id,
                'category': category, 'owner': owner, 'scope': 'local', 'identity': {'path': str(path), 'home': str(self.home)},
                'capabilities': ['read', 'prepare', 'preflight', 'backup', 'apply', 'verify', 'reconcile', 'undo'],
                'observed_at': timestamp(), 'evidence': [str(path)], 'limitations': ['Runtime discovery, effective precedence and reload are not inferred from file bytes.'], **extra}

    def source_files(self, root, executable_only=False):
        """Bounded canonical traversal; no aliases, caches or generated trees."""
        root = Path(root)
        if not root.is_dir() or root.is_symlink():
            return []
        found = []
        for directory, dirs, files in os.walk(root, followlinks=False):
            current = Path(directory)
            dirs[:] = sorted(d for d in dirs if not d.startswith('.') and d not in ('__pycache__', 'node_modules', 'vendor', 'generated', 'dist', 'build') and not (current / d).is_symlink() and len((current / d).relative_to(root).parts) <= 4)
            for name in sorted(files):
                path = current / name
                suffix = path.suffix.lstrip('.')
                if path.is_symlink() or suffix not in SOURCE_LANGUAGES | ({'md', 'txt', 'json', 'toml', 'yaml', 'yml'} if not executable_only else set()):
                    continue
                try:
                    self.safe(path)
                    if re.search(r'(?i)generated by|do not edit', self.state(path)[0].decode('utf-8')[:6000]):
                        continue
                except (RepairError, OSError, UnicodeError):
                    continue
                found.append(path)
                if len(found) >= 256:
                    return found
        return found

    def discover(self):
        rows = []
        rules = self.home / '.agents/instructions'
        for name in SOURCES:
            path = rules / name
            if path.is_file() and not path.is_symlink():
                rows.append(self.row(path, 'rule', 'native-instruction-builder', content_format='text'))
        providers = self.provider_skills()
        root = self.home / '.agents/skills'
        if root.is_dir() and not root.is_symlink():
            for folder in sorted(root.iterdir()):
                if folder.name in providers or folder.is_symlink() or not folder.is_dir() or folder.name.startswith('.'):
                    continue
                path = folder / 'SKILL.md'
                if path.is_file() and not path.is_symlink():
                    rows.append(self.row(path, 'skill', 'shared-skill-lifecycle', content_format='text'))
                    for subdir in ('scripts', 'references', 'assets'):
                        source_root = folder / subdir
                        for script in self.source_files(source_root):
                            category = 'executable' if script.suffix.lstrip('.') in SOURCE_LANGUAGES else 'skill_reference'
                            row = self.row(script, category, 'shared-skill-lifecycle', content_format='text')
                            if script == root / 'alex-director/references/gates.md':
                                row.update(context_only=True, capabilities=['read'], missing_capability='context_only_policy')
                            rows.append(row)
        for relative, (category, runtime, keys) in JSON_OWNERS.items():
            path = self.home / relative
            if path.is_file() and not path.is_symlink():
                allowed = list(keys)
                try:
                    value = load_json(self.state(path)[0])
                    if isinstance(value, dict) and isinstance(value.get('hooks'), dict):
                        allowed.extend(editable_leaves(safe_json_projection(value['hooks']), 'hooks'))
                except (RepairError, OSError, ValueError):
                    pass
                rows.append(self.row(path, category, runtime, content_format='json', allowed_patch_paths=allowed))
        executable_paths = {self.home / '.agents' / relative for relative in EXECUTABLES}
        executable_paths.update(self.source_files(self.home / '.agents/tools/guards', executable_only=True))
        for path in sorted(executable_paths):
            if path.is_file() and not path.is_symlink():
                rows.append(self.row(path, 'executable', 'registered-agent-tools', content_format='text', **({'source_language': 'py'} if path.suffix == '.py' else {})))
        if any(row['category'] == 'rule' for row in rows):
            for key, relative in OUTPUTS.items():
                path = self.home / relative
                rows.append(self.row(path, 'distribution', 'native-instruction-builder', content_format='text', generated_key=key))
        repos = set()
        # Resolve each native checkout once per inventory. Calling Git for each
        # reference adds seconds per owned skill on a real home. Nested native
        # repositories still receive their own exact discovery/publication owner.
        repo_cache = {}
        def discovered_repo(path):
            parent = path if path.is_dir() else path.parent
            nearest = parent
            while nearest != self.home and not (nearest / '.git').exists():
                nearest = nearest.parent
            key = nearest if nearest != self.home else self.home / path.relative_to(self.home).parts[0]
            if key not in repo_cache:
                repo_cache[key] = self.repo_path(parent)
            return repo_cache[key]
        for row in rows:
            try:
                self.safe(row['identity']['path'], row['category'] == 'distribution')
                repo = discovered_repo(Path(row['identity']['path']))
                if repo:
                    repos.add(repo)
            except (RepairError, OSError):
                continue
        for repo in sorted(repos):
            rows.append(self.row(repo, 'publication', 'git', content_format='json'))
        for row in rows:
            if row.get('content_format') == 'text' and row['category'] != 'distribution':
                try:
                    text = self.state(row['identity']['path'])[0].decode('utf-8')
                    if self.canonical_gates_target(row) and canonical_gates_section(text)[1]:
                        row['limitations'].append("Only the canonical section Alex's gates (the one list) is supplied; other sections are not reviewed. Omitted lines are blank-padded to preserve original citation line numbers. The fingerprint binds the whole file.")
                    if self.text_projection(row, text)[1]:
                        row['missing_capability'] = 'safe_text_projection'
                        row['limitations'].append('Screened text cannot be replaced wholesale without losing private material; this target requires a safe partial native operation.')
                    elif re.search(r'(?i)generated by|do not edit', text[:6000]):
                        row['missing_capability'] = 'canonical_source_owner'
                        row['limitations'].append('Managed text must be repaired through its canonical source owner.')
                except (RepairError, OSError, UnicodeError):
                    row['missing_capability'] = 'readable_source'
            if row['category'] in ('hook', 'app_settings'):
                try:
                    value = load_json(self.state(row['identity']['path'])[0])
                    scripts = self.hook_scripts(value, rows)
                    row['related_target_ids'] = [target_id(path) for path in scripts]
                    row['limitations'].append('External or shell-expanded hook programs require separate runtime evidence.')
                except (RepairError, OSError, ValueError):
                    row['related_target_ids'] = []
        self._targets = {row['id']: row for row in rows}
        return rows

    def hook_scripts(self, value, rows=None):
        known = {row['identity']['path']: row['id'] for row in (rows or self._targets.values()) if row['category'] == 'executable'}
        found = set()
        def visit(item):
            if isinstance(item, dict):
                for key, child in item.items():
                    if key == 'command' and isinstance(child, str) and not self.sensitive_value(child):
                        try:
                            tokens = shlex.split(child)
                        except ValueError:
                            tokens = []
                        for token in tokens:
                            path = str(self.home / token[2:]) if token.startswith('~/') else token
                            if path in known:
                                found.add(path)
                    elif not PRIVATE_KEY.search(key):
                        visit(child)
            elif isinstance(item, list):
                for child in item:
                    visit(child)
        visit(value)
        return sorted(found)

    def canonical_gates_target(self, target):
        return (Path(target['identity']['path']) == self.home / '.agents/skills/alex-director/references/gates.md'
                and target['category'] == 'skill_reference' and target['owner'] == 'shared-skill-lifecycle'
                and target.get('context_only') is True and target.get('capabilities') == ['read'])

    def text_projection(self, target, text):
        if self.canonical_gates_target(target):
            text, _ = canonical_gates_section(text)
        if target['category'] == 'executable' and target.get('source_language') == 'py':
            return python_source_projection(text)
        return screen(text)

    def registered(self, target):
        if target['id'] not in self._targets:
            self.discover()
        row = self._targets.get(target['id'])
        if row is None or row['identity'] != target['identity'] or row['category'] != target['category']:
            raise RepairError('unregistered_target')
        return row

    def read(self, target):
        target = self.registered(target)
        if target['category'] == 'publication':
            info = self.repo_info(Path(target['identity']['path']))
            return {'fingerprint': sha(canonical(info)), 'version': 'git.v1', 'projection': {'branch': info['branch']}, 'context_fingerprint': self.context(target)}
        raw, state = self.state(target['identity']['path'], target['category'] == 'distribution')
        if target.get('content_format') == 'json':
            try:
                value = load_json(raw)
            except (ValueError, TypeError):
                raise RepairError('invalid_native_config') from None
            if not isinstance(value, dict):
                raise RepairError('invalid_native_config')
            projection = {}
            for key in JSON_OWNERS[path_relative(target, self.home)][2]:
                entry = get_key(value, key)
                if entry['exists']:
                    projection[key] = safe_json_projection(entry['value'])
            projection = safe_json_projection(projection)
        else:
            text = (raw or b'').decode('utf-8')
            projection = {'content': self.text_projection(target, text)[0]}
        snapshot = {'fingerprint': sha(canonical(state)), 'version': self.version, 'projection': projection, 'context_fingerprint': self.context(target)}
        if self.canonical_gates_target(target):
            snapshot.update(whole_file_sha256=sha(raw), limitations=list(target['limitations']))
        return snapshot

    def prepare(self, target, snapshot, proposal):
        target = self.registered(target)
        if target.get('context_only'):
            raise RepairError('context_only_policy')
        if target['category'] in ('publication', 'distribution'):
            raise RepairError('owner_generated_operation')
        actual = self.read(target)
        if snapshot != actual:
            raise RepairError('stale_snapshot')
        path = Path(target['identity']['path'])
        raw, state = self.state(path)
        op = {'action': 'patch' if target.get('content_format') == 'json' else 'replace', 'selector': {'path': str(path)},
              'expected_fingerprint': snapshot['fingerprint'], 'expected_version': snapshot['version'],
              'context_fingerprint': snapshot['context_fingerprint'], 'before_state': state}
        if op['action'] == 'patch':
            patch = proposal.get('patch')
            if not isinstance(patch, dict) or not patch:
                raise RepairError('invalid_patch')
            keys = sorted(patch)
            allowed = target['allowed_patch_paths']
            if any(not isinstance(k, str) or not k or not any(k == a or (a == 'hooks' and k.startswith('hooks.')) for a in allowed) for k in keys):
                raise RepairError('unsupported_key')
            if any(b.startswith(a + '.') for a in keys for b in keys if a != b):
                raise RepairError('overlapping_patch')
            if any(re.search(r'(?i)(secret|password|credential|token|api.?key|headers?|env)', key) for key in keys):
                raise RepairError('secret_key')
            before = load_json(raw)
            after = copy.deepcopy(before)
            inverse, public_before, created_parents = {}, {}, []
            for key in keys:
                item = get_key(before, key)
                if item['exists'] and self.sensitive_value(item['value']):
                    raise RepairError('secret_inverse')
                if self.sensitive_value(patch[key]):
                    raise RepairError('secret_candidate')
                inverse[key] = item
                for length in range(1, len(key.split('.'))):
                    parent = '.'.join(key.split('.')[:length])
                    if not get_key(before, parent)['exists'] and parent not in created_parents:
                        created_parents.append(parent)
                public_before[key] = item.get('value') if item['exists'] else None
                set_key(after, key, {'exists': True, 'value': patch[key]})
            op.update(patch=copy.deepcopy(patch), inverse=inverse, created_parents=created_parents, public_diff=json.dumps({'before': public_before, 'after': patch}, sort_keys=True))
            candidate = after
        else:
            candidate = proposal.get('candidate')
            if not isinstance(candidate, str) or not candidate.strip() or len(candidate.encode()) > MAX_BYTES:
                raise RepairError('invalid_candidate')
            before = raw.decode()
            if self.text_projection(target, before)[1] or self.text_projection(target, candidate)[1]:
                raise RepairError('screened_text_source')
            if re.search(r'(?i)generated by|do not edit', before[:6000]):
                raise RepairError('provider_owned')
            op.update(candidate=candidate, inverse={'content': before}, public_diff=''.join(difflib.unified_diff(before.splitlines(True), candidate.splitlines(True), fromfile='before', tofile='candidate')))
        if target['category'] in ('hook', 'app_settings') and isinstance(candidate, dict):
            op['related_inputs'] = [{'path': script, 'state': self.state(script)[1]} for script in self.hook_scripts(candidate)]
        op['checks'] = run_checks(candidate, target['category'], path, self.home, target['owner'])
        if target['category'] == 'skill':
            references = set(re.findall(r'\]\(((?:references|scripts|assets)/[^)#\s]+)', candidate))
            references.update(re.findall(r'`((?:references|scripts|assets)/[^`\s]+)`', candidate))
            op['resource_inputs'] = [{'path': str(path.parent / reference), 'state': self.state(path.parent / reference)[1]} for reference in sorted(references)]
        if any(c['status'] != 'passed' for c in op['checks']):
            raise RepairError('candidate_check_failed')
        return op

    def sensitive_value(self, value):
        if safe_json_projection(value) != value:
            return True
        if isinstance(value, str):
            return '[REDACTED' in value
        if isinstance(value, dict):
            return any(self.sensitive_value(v) for v in value.values())
        if isinstance(value, list):
            return any(self.sensitive_value(v) for v in value)
        return False

    def bind(self, target, op, index):
        op.update(target_id=target['id'], adapter_id=self.adapter_id, adapter_version=self.version,
                  target_identity=target['identity'], step_id='local-' + str(index) + '-' + target['id'])
        return op

    def prepare_bundle(self, operations, targets):
        own = copy.deepcopy(operations)
        if not own:
            return own
        rule_ops = [op for op in own if targets[op['target_id']]['category'] == 'rule']
        if rule_ops:
            self.freeze_rules(rule_ops, own, targets)
        groups = {}
        for op in own:
            path = Path(op['selector']['path'])
            repo = self.repo_path(path)
            if repo and not self.matches_after(op):
                groups.setdefault(repo, []).append(op)
        for repo, members in sorted(groups.items()):
            target = targets.get(target_id(repo, 'repo'))
            if not target:
                raise RepairError('unregistered_publication')
            info = self.repo_info(repo)
            paths = sorted(str(Path(op['selector']['path']).relative_to(repo)) for op in members)
            for op in members:
                path = Path(op['selector']['path'])
                raw, _ = self.state(path, True)
                rel = path.relative_to(repo).as_posix()
                if raw is None or self.git(repo, 'show', 'HEAD:' + rel, binary=True) != raw or self.git(repo, 'show', ':' + rel, binary=True) != raw:
                    raise RepairError('git_preimage')
            if self.remote_head(info) != info['head']:
                raise RepairError('remote_preimage')
            snap = self.read(target)
            op = {'action': 'publish', 'selector': {'path': str(repo)}, 'repo': info, 'paths': paths,
                  'members': copy.deepcopy(members), 'expected_fingerprint': snap['fingerprint'], 'expected_version': snap['version'],
                  'context_fingerprint': snap['context_fingerprint'], 'inverse': {'head': info['head']},
                  'public_diff': 'Publish exactly: ' + ', '.join(paths),
                  'checks': [check('owner_lifecycle', 'passed', 'git.exact-pathset.v1', [info, paths], ['Tracked source/index and remote preimages match.'])]}
            own.append(self.bind(target, op, len(own)))
        return own

    def freeze_rules(self, rule_ops, output, targets):
        dist = self.distribution
        native = dist.load_native()
        rules = self.home / '.agents/instructions'
        candidates = {Path(op['selector']['path']).name: op['candidate'] for op in rule_ops}
        needed = set(key for name in candidates for key in DEPENDENTS[name])
        with native.generator_lock(str(self.home)):
            paths = [dist.builder, self.home / '.codex/config.toml'] + [rules / name for name in SOURCES]
            inputs = [{'path': str(path), 'state': self.state(path, True)[1]} for path in paths]
            baseline = {'codex_config': native.snapshot(dist.safe(self.home / '.codex/config.toml'))}
            reader = native.read_src
            try:
                native.read_src = lambda name: candidates[name].rstrip() + '\n' if name in candidates else reader(name)
                rendered = native.build(baseline, rules_only=True)
            except (SystemExit, ValueError, OSError):
                raise RepairError('native_projection_failed')
            finally:
                native.read_src = reader
            for op in rule_ops:
                op['native_inputs'] = inputs
                op['native_candidates'] = {str(rules / name): sha(value.encode()) for name, value in candidates.items()}
                op['checks'].append(check('owner_lifecycle', 'passed', 'native-instruction-builder.rules-only.v1', candidates, ['All canonical proposals projected together through existing builder.']))
            for key in sorted(needed):
                path = self.home / OUTPUTS[key]
                target = targets.get(target_id(path))
                if not target:
                    raise RepairError('unregistered_distribution')
                raw, state = self.state(path, True)
                candidate = rendered[key]
                # Native output projection can carry no opaque secrets to its
                # public diff, backup or model context.
                if screen(candidate)[1] or (raw and screen(raw.decode())[1]):
                    raise RepairError('screened_distribution')
                snap = self.read(target)
                op = {'action': 'replace', 'selector': {'path': str(path)}, 'candidate': candidate,
                      'before_state': state, 'inverse': {'content': raw.decode() if raw else None},
                      'expected_fingerprint': snap['fingerprint'], 'expected_version': snap['version'],
                      'context_fingerprint': snap['context_fingerprint'],
                      'public_diff': ''.join(difflib.unified_diff((raw or b'').decode().splitlines(True), candidate.splitlines(True), fromfile='before', tofile='candidate')),
                      'checks': [check('owner_lifecycle', 'passed', 'native-instruction-builder.rules-only.v1', candidate, ['Frozen combined native output.'])]}
                output.append(self.bind(target, op, len(output)))

    def preflight(self, target, operation):
        try:
            target = self.registered(target)
            if operation['context_fingerprint'] != self.context(target):
                return {'ok': False, 'evidence': ['Owner registration changed.']}
            if operation['action'] == 'publish':
                ok = self.repo_info(Path(operation['selector']['path'])) == operation['repo'] and self.remote_head(operation['repo']) == operation['repo']['head']
            else:
                ok = self.state(operation['selector']['path'], True)[1] == operation['before_state']
                for item in operation.get('native_inputs', []) + operation.get('resource_inputs', []) + operation.get('related_inputs', []):
                    ok = ok and self.state(item['path'], True)[1] == item['state']
            return {'ok': bool(ok), 'evidence': ['Hash, mode, inode, native inputs and owner context compared.']}
        except (RepairError, OSError, ValueError):
            return {'ok': False, 'evidence': ['Native source is stale or unavailable.']}

    def backup_root(self):
        root = self.home / 'Backups'
        if not root.is_dir():
            raise RepairError('drive_backup_unavailable')
        # ~/Backups is the existing Drive link. No other alias is allowed.
        real = root.resolve(strict=True)
        if self.fixture and self.home.resolve() not in real.parents:
            raise RepairError('fixture_backup_escape')
        folder = real / 'universal-repairs'
        folder.mkdir(mode=0o700, exist_ok=True)
        if folder.is_symlink():
            raise RepairError('backup_alias')
        return folder

    def backup(self, target, operation, backup_dir):
        if not self.preflight(target, operation)['ok']:
            raise RepairError('stale_backup_source')
        if operation['action'] == 'publish':
            return {'repo': operation['repo'], 'members': [self.backup(self._targets[member['target_id']], member, backup_dir) for member in operation['members']]}
        folder = self.backup_root()
        # JSON backups contain changed safe fields only; never entire config.
        raw = canonical(operation['inverse']) if operation['action'] == 'patch' else (operation['inverse']['content'] or '').encode()
        path = folder / (sha(canonical(operation)) + '.before')
        if path.is_symlink():
            raise RepairError('backup_alias')
        if path.exists():
            if path.read_bytes() != raw:
                raise RepairError('backup_changed')
        else:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'wb') as stream:
                stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        if path.read_bytes() != raw:
            raise RepairError('backup_unverified')
        return {'path': str(path), 'sha256': sha(raw), 'inverse': operation['inverse'], 'before_state': operation['before_state'], 'cloud_upload': 'unverified'}

    def candidate_bytes(self, operation, current):
        if operation['action'] != 'patch':
            return operation['candidate'].encode()
        value = load_json(current)
        for key, replacement in operation['patch'].items():
            set_key(value, key, {'exists': True, 'value': replacement})
        return json.dumps(value, ensure_ascii=False, indent=2).encode() + b'\n'

    def matches_after(self, operation):
        raw, state = self.state(operation['selector']['path'], True)
        if raw is None or state['mode'] != operation['before_state'].get('mode', 0o600):
            return False
        if operation['action'] == 'patch':
            value = load_json(raw)
            return all(get_key(value, key) == {'exists': True, 'value': replacement} for key, replacement in operation['patch'].items())
        return raw == operation['candidate'].encode()

    def apply(self, target, operation, backup):
        self.registered(target)
        if operation['action'] == 'publish':
            observed = self.reconcile(target, operation, backup)
            if observed['outcome'] == 'applied':
                return observed['result']
            return self.publish(operation)
        self.validate_backup(backup)
        if self.matches_after(operation):
            raw, state = self.state(operation['selector']['path'])
            return {'after_state': state, 'after_sha256': sha(raw)}
        if operation['context_fingerprint'] != self.context(target) or self.state(operation['selector']['path'], True)[1] != operation['before_state']:
            raise RepairError('stale_source')
        for item in operation.get('native_inputs', []) + operation.get('resource_inputs', []) + operation.get('related_inputs', []):
            actual = self.state(item['path'], True)[1]
            candidate_hash = operation.get('native_candidates', {}).get(item['path'])
            if actual != item['state'] and not (candidate_hash and actual.get('sha256') == candidate_hash and actual.get('mode') == item['state'].get('mode')):
                raise RepairError('stale_native_input')
        self.validate_backup(backup)
        raw, state = self.state(operation['selector']['path'], True)
        after = self.candidate_bytes(operation, raw)
        new_state = self.replace(operation['selector']['path'], after, state, state.get('mode', 0o600))
        return {'after_state': new_state, 'after_sha256': sha(after)}

    def receipt(self, ok, state, evidence, limitations=None, checks=None, fingerprint=None):
        return {'ok': bool(ok), 'state': state, 'evidence': evidence, 'limitations': limitations or [], 'checks': checks or [], **({'fingerprint': fingerprint} if fingerprint else {})}

    def verify(self, target, operation, result):
        try:
            if operation['action'] == 'publish':
                head = result.get('commit')
                ok = bool(head and self.git(Path(operation['repo']['repo']), 'rev-parse', 'HEAD') == head and self.remote_head(operation['repo']) == head)
                return self.receipt(ok, 'effective' if ok else 'pending', ['Exact Git path set and remote branch read back.'], fingerprint=head)
            ok = self.matches_after(operation)
            raw, state = self.state(operation['selector']['path'])
            return self.receipt(ok, 'byte_verified' if ok else 'pending', ['Exact configured values and mode read back.'],
                                ['Runtime discovery, effective precedence, trust and reload remain unobserved.', 'Drive cloud upload was not verified.'], operation.get('checks', []), sha(canonical(state)))
        except (RepairError, OSError, ValueError):
            return self.receipt(False, 'pending', ['Readback unavailable.'])

    def reconcile(self, target, operation, backup):
        if operation.get('recovery_phase') == 'undo':
            return self.reconcile_undo(target, operation, backup)
        try:
            if operation['action'] == 'publish':
                repo = Path(operation['repo']['repo']); head = self.git(repo, 'rev-parse', 'HEAD')
                if head == operation['repo']['head']:
                    return {'outcome': 'not_applied', 'evidence': ['Git parent remains current.']}
                remote = self.remote_head(operation['repo'])
                own = self.commit_matches(operation, head) and self.committed_members_match(operation, head) and all(self.matches_after(m) for m in operation['members'])
                ok = own and remote == head
                retry = own and remote == operation['repo']['head']
                return {'outcome': 'applied' if ok else 'not_applied' if retry else 'unknown', 'result': {'commit': head}, 'evidence': ['Git commit and exact remote branch read back.']}
            if self.matches_after(operation):
                _, state = self.state(operation['selector']['path'])
                return {'outcome': 'applied', 'result': {'after_state': state}, 'evidence': ['Candidate values observed.']}
            raw, state = self.state(operation['selector']['path'], True)
            if operation['action'] == 'patch' and raw:
                value = load_json(raw)
                before = all(get_key(value, key) == entry for key, entry in operation['inverse'].items())
            else:
                before = (raw.decode() if raw else None) == operation['inverse']['content']
            return {'outcome': 'not_applied' if before else 'unknown', 'evidence': ['Changed values read back.']}
        except (RepairError, OSError, ValueError):
            return {'outcome': 'unknown', 'evidence': ['Readback unavailable.']}

    def reconcile_undo(self, target, operation, backup):
        try:
            if operation['action'] == 'publish':
                repo = Path(operation['repo']['repo'])
                head = self.git(repo, 'rev-parse', 'HEAD')
                parent = self.git(repo, 'rev-list', '--parents', '-n', '1', head).split()
                paths = self.git(repo, 'diff-tree', '--no-commit-id', '--name-only', '-r', head).splitlines()
                members = [self.reconcile_undo(self._targets[m['target_id']], m, b)['outcome'] for m, b in zip(operation['members'], backup['members'])]
                before = all(outcome == 'applied' for outcome in members)
                applied = before and self.committed_members_match(operation, head, undo=True) and self.remote_head(operation['repo']) == head and len(parent) == 2 and self.commit_matches(operation, parent[1]) and self.committed_members_match(operation, parent[1]) and sorted(paths) == sorted(operation['paths'])
                if applied:
                    return {'outcome': 'applied', 'result': {'commit': head}, 'evidence': ['Restoration commit, inverse fields and remote branch read back.']}
                retry = before and len(parent) == 2 and self.commit_matches(operation, parent[1]) and self.committed_members_match(operation, parent[1]) and sorted(paths) == sorted(operation['paths']) and self.committed_members_match(operation, head, undo=True) and self.remote_head(operation['repo']) == parent[1]
                # An interrupted member loop may have restored any prefix of
                # the inverse without writing its receipt. Resume only under
                # the exact published forward commit, when every member is
                # independently proven to be its original or candidate value.
                # A third value/mode remains unknown and is never overwritten.
                partial = (self.commit_matches(operation, head) and self.committed_members_match(operation, head)
                           and self.remote_head(operation['repo']) == head
                           and len(members) == len(operation['members'])
                           and all(outcome in ('applied', 'not_applied') for outcome in members))
                original = retry or partial
                return {'outcome': 'not_applied' if original else 'unknown', 'evidence': ['Publication restoration state observed.']}
            raw, state = self.state(operation['selector']['path'], True)
            if operation['action'] == 'patch':
                value = load_json(raw)
                before = all(get_key(value, key) == entry for key, entry in operation['inverse'].items())
            else:
                before = (raw.decode() if raw is not None else None) == operation['inverse']['content']
            before = before and (not state.get('exists') or state['mode'] == operation['before_state'].get('mode', 0o600))
            return {'outcome': 'applied' if before else 'not_applied' if self.matches_after(operation) else 'unknown', 'evidence': ['Conditional inverse fields observed without writing.']}
        except (RepairError, OSError, ValueError):
            return {'outcome': 'unknown', 'evidence': ['Restoration readback unavailable.']}

    def validate_backup(self, backup):
        path = Path(backup['path'])
        if path.is_symlink() or path.parent != self.backup_root() or sha(path.read_bytes()) != backup['sha256']:
            raise RepairError('backup_changed')

    def restore_one(self, target, operation, backup, applied):
        self.validate_backup(backup)
        path = Path(operation['selector']['path'])
        raw, state = self.state(path, True)
        mode = operation['before_state'].get('mode', 0o600)
        if raw is None:
            return operation['before_state'] == {'exists': False}
        if state['mode'] != mode:
            return False
        if operation['action'] == 'patch':
            value = load_json(raw)
            if all(get_key(value, key) == entry for key, entry in operation['inverse'].items()):
                return True
            if not self.matches_after(operation):
                return False
            for key, entry in operation['inverse'].items():
                set_key(value, key, entry)
            for parent in sorted(operation.get('created_parents', []), key=lambda key: key.count('.'), reverse=True):
                if get_key(value, parent) == {'exists': True, 'value': {}}:
                    set_key(value, parent, {'exists': False})
            before = json.dumps(value, ensure_ascii=False, indent=2).encode() + b'\n'
        else:
            before = operation['inverse']['content']
            if raw.decode() == before:
                return True
            if not self.matches_after(operation):
                return False
            if before is None:
                # Recovery of the created bytes is saved before unlink.
                recovery = self.backup_root() / (sha(raw) + '.created')
                if not recovery.exists():
                    fd = os.open(recovery, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                    with os.fdopen(fd, 'wb') as stream:
                        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
                if recovery.is_symlink() or recovery.read_bytes() != raw:
                    raise RepairError('backup_changed')
                parent = self.parent_fd(path)
                try:
                    if self.state(path)[1] != state:
                        raise RepairError('stale_source')
                    os.unlink(path.name, dir_fd=parent); os.fsync(parent)
                finally:
                    os.close(parent)
                return not path.exists()
            before = before.encode()
        self.replace(path, before, state, mode)
        return True

    def undo(self, target, operation, backup, applied):
        # Only known conflicts before the first effect are blocked. Once a
        # restoration starts, failures must remain uncertain for reconciliation.
        if operation['action'] == 'publish':
            repo = Path(operation['repo']['repo'])
            head = self.git(repo, 'rev-parse', 'HEAD')
            parents = self.git(repo, 'rev-list', '--parents', '-n', '1', head).split()
            if len(parents) == 2 and self.commit_matches(operation, parents[1]) and self.committed_members_match(operation, parents[1]) and self.committed_members_match(operation, head, undo=True):
                reverse = copy.deepcopy(operation); reverse['repo']['head'] = parents[1]
                result = self.publish(reverse, undo=True)
                return self.receipt(True, 'undone', ['Existing restoration commit pushed and read back.'], fingerprint=result['commit'])
            if not self.commit_matches(operation, head) or not self.committed_members_match(operation, head) or self.remote_head(operation['repo']) != head:
                return self.receipt(False, 'blocked', ['Publication has newer commits.'])
            for member, saved in zip(operation['members'], backup['members']):
                try:
                    self.validate_backup(saved)
                except (RepairError, OSError, ValueError):
                    return self.receipt(False, 'blocked', ['Backup is unavailable or changed before restoration.'])
                observed = self.reconcile_undo(self._targets[member['target_id']], member, saved)
                if not self.matches_after(member) and observed['outcome'] != 'applied':
                    return self.receipt(False, 'blocked', ['A published target changed after repair.'])
            for member, saved in reversed(list(zip(operation['members'], backup['members']))):
                if not self.restore_one(self._targets[member['target_id']], member, saved, {}):
                    raise RepairError('inverse_restore_uncertain')
            reverse = copy.deepcopy(operation); reverse['repo']['head'] = head
            self.publish(reverse, undo=True)
            return self.receipt(True, 'undone', ['Exact approved path set restored and restoration commit pushed.'])
        try:
            self.validate_backup(backup)
        except (RepairError, OSError, ValueError):
            return self.receipt(False, 'blocked', ['Backup is unavailable or changed before restoration.'])
        ok = self.restore_one(target, operation, backup, applied)
        return self.receipt(ok, 'undone' if ok else 'blocked', ['Conditional changed-field inverse compared and read back.'], ['Unrelated newer JSON keys preserved; runtime reload unobserved.'])

    def git(self, repo, *args, binary=False):
        try:
            result = subprocess.run(['git', '-C', str(repo), *args], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                    stderr=subprocess.DEVNULL, timeout=45,
                                    env={**os.environ, 'GIT_TERMINAL_PROMPT': '0', 'GIT_OPTIONAL_LOCKS': '0'})
            if result.returncode:
                raise RepairError('git_failed')
            return result.stdout if binary else result.stdout.decode().strip()
        except (OSError, subprocess.TimeoutExpired):
            raise RepairError('git_unavailable')

    def repo_path(self, path):
        parent = path if path.is_dir() else path.parent
        while not parent.is_dir() and parent != self.home:
            parent = parent.parent
        try:
            repo = Path(self.git(parent, 'rev-parse', '--show-toplevel'))
            if repo != self.home and self.home not in repo.parents:
                raise RepairError('repo_outside_owner')
            return str(repo)
        except RepairError:
            return None

    def repo_info(self, repo):
        repo = Path(repo)
        branch = self.git(repo, 'symbolic-ref', '--quiet', '--short', 'HEAD')
        if not branch or branch.startswith('-'):
            raise RepairError('detached_repo')
        origin = self.git(repo, 'remote', 'get-url', 'origin')
        if origin != self.git(repo, 'remote', 'get-url', '--push', 'origin'):
            raise RepairError('remote_mismatch')
        if self.fixture:
            remote = Path(origin.removeprefix('file://'))
            if not remote.is_absolute():
                remote = repo / remote
            if self.home.resolve() not in remote.resolve().parents or self.git(remote, 'rev-parse', '--is-bare-repository') != 'true':
                raise RepairError('fixture_remote_escape')
        else:
            host = urlsplit(origin).hostname if '://' in origin else (origin.split('@')[-1].split(':')[0] if re.match(r'[^/@:]+@[^:]+:', origin) else '')
            if not host or host.lower() in ('localhost', '127.0.0.1', '::1'):
                raise RepairError('remote_not_durable')
        return {'repo': str(repo), 'branch': branch, 'head': self.git(repo, 'rev-parse', 'HEAD'), 'origin_fingerprint': sha(origin.encode())}

    def remote_head(self, info):
        rows = self.git(Path(info['repo']), 'ls-remote', '--exit-code', 'origin', 'refs/heads/' + info['branch']).splitlines()
        if len(rows) != 1:
            raise RepairError('remote_head_unknown')
        return rows[0].split()[0]

    def commit_matches(self, operation, head):
        repo = Path(operation['repo']['repo'])
        parents = self.git(repo, 'rev-list', '--parents', '-n', '1', head).split()
        paths = self.git(repo, 'diff-tree', '--no-commit-id', '--name-only', '-r', head).splitlines()
        return parents == [head, operation['repo']['head']] and sorted(paths) == sorted(operation['paths'])

    def committed_members_match(self, operation, head, undo=False):
        repo = Path(operation['repo']['repo'])
        for member in operation['members']:
            relative = Path(member['selector']['path']).relative_to(repo).as_posix()
            raw = self.git(repo, 'show', head + ':' + relative, binary=True)
            if member['action'] == 'patch':
                value = load_json(raw)
                entries = member['inverse'] if undo else {key: {'exists': True, 'value': val} for key, val in member['patch'].items()}
                if not all(get_key(value, key) == entry for key, entry in entries.items()):
                    return False
            elif raw != (member['inverse']['content'] if undo else member['candidate']).encode():
                return False
        return True

    def publish(self, operation, undo=False):
        info = operation['repo']; repo = Path(info['repo'])
        current = self.repo_info(repo)
        if {k: v for k, v in current.items() if k != 'head'} != {k: v for k, v in info.items() if k != 'head'}:
            raise RepairError('stale_publication')
        head = current['head']; remote = self.remote_head(info)
        if head != info['head']:
            # The exact frozen-parent commit already exists locally. Retry only
            # its push, never mint a second commit after a lost response.
            if not self.commit_matches(operation, head) or not self.committed_members_match(operation, head, undo):
                raise RepairError('stale_publication')
            if remote not in (info['head'], head):
                raise RepairError('stale_publication')
        else:
            if remote != info['head']:
                raise RepairError('stale_publication')
            for member in operation['members']:
                if not undo and not self.matches_after(member):
                    raise RepairError('publication_readback')
            self.git(repo, 'commit', '--only', '-m', 'Restore reviewed local repair' if undo else 'Apply reviewed local repair', '--', *(':(literal)' + p for p in operation['paths']))
            head = self.git(repo, 'rev-parse', 'HEAD')
            if not self.commit_matches(operation, head) or not self.committed_members_match(operation, head, undo):
                raise RepairError('commit_pathset_mismatch')
        for member in operation['members']:
            path = Path(member['selector']['path']); relative = path.relative_to(repo).as_posix()
            raw, _ = self.state(path)
            if self.git(repo, 'show', head + ':' + relative, binary=True) != raw:
                raise RepairError('commit_readback_mismatch')
        if remote != head:
            self.git(repo, 'push', '--porcelain', 'origin', head + ':refs/heads/' + info['branch'])
        if self.remote_head(info) != head:
            raise RepairError('push_unconfirmed')
        return {'commit': head, 'paths': operation['paths']}


def register_adapters(registry, home=None):
    registry.register(LocalAdapter(home))
