"""Fixed native instruction projections for a frozen, source-scoped repair.

No broad installer, config writer, roles or remote publication is invoked here.
The native builder is loaded only from the service's fixed home, including in
private fixture homes. Candidate rendering overrides its reader in memory.
"""
import base64
from contextlib import nullcontext
import difflib
import hashlib
import importlib.util
import os
from pathlib import Path
import stat
import uuid

SOURCES = ('shared.md', 'codex.md', 'claude.md', 'codex-style.md', 'shared-style.md', 'claude-style.md')
OUTPUTS = {'codex': '.codex/AGENTS.md', 'home_agents': 'AGENTS.md',
           'cursor': '.cursor/rules/agent-routing.mdc', 'claude': '.claude/CLAUDE.md',
           'claude_style': '.claude/output-styles/alex-big-brother.md'}
DEPENDENTS = {'shared.md': ('codex', 'home_agents', 'cursor', 'claude'),
              'codex.md': ('codex',), 'claude.md': ('claude',),
              'codex-style.md': ('codex',), 'shared-style.md': ('claude_style',),
              'claude-style.md': ('claude_style',)}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(raw):
    return base64.b64encode(raw).decode()


def decode(raw):
    return base64.b64decode(raw)


class Distribution:
    def __init__(self, home, error):
        self.home, self.error = Path(home), error
        self.builder = self.home / '.agents/tools/unify/build_instructions.py'
        self.native = None
        self.allowed_builder = None

    def safe(self, path):
        path = Path(path)
        relative = path.relative_to(self.home)
        current = self.home
        for part in relative.parts:
            current /= part
            if current.is_symlink():
                raise self.error('distribution_alias', 'Native input or destination became an alias; review its owner', 409)
        return path

    def load_native(self):
        if self.native is None:
            self.safe(self.builder)
            spec = importlib.util.spec_from_file_location('_repair_native_' + uuid.uuid4().hex, self.builder)
            native = importlib.util.module_from_spec(spec)
            # Execute the fingerprinted bytes, never a timestamp-based pyc or
            # a second file read after the approval check. No cache is written.
            fd = os.open(self.builder, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, 'rb') as stream:
                st = os.fstat(stream.fileno())
                code = stream.read()
            fingerprint = {'sha256': digest(code), 'mode': stat.S_IMODE(st.st_mode)}
            if self.allowed_builder is not None and fingerprint != self.allowed_builder:
                raise self.error('stale_generator_input', 'Native builder changed immediately before loading', 409)
            exec(compile(code, str(self.builder), 'exec'), native.__dict__)
            self.loaded_builder = fingerprint
            native.H = str(self.home)
            native.SRC = str(self.home / '.agents/instructions')
            native.OUT = {**{key: str(self.home / path) for key, path in OUTPUTS.items()},
                          'codex_config': str(self.home / '.codex/config.toml')}
            self.native = native
        return self.native

    def check_builder(self, plan):
        expected = next((item['state'] for item in plan['inputs'] if item['path'] == str(self.builder)), None)
        if expected is not None:
            self.allowed_builder = expected
            path = self.safe(self.builder)
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, 'rb') as stream:
                st = os.fstat(stream.fileno())
                raw = stream.read()
            if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or expected != {'sha256': digest(raw), 'mode': stat.S_IMODE(st.st_mode)}:
                raise self.error('stale_generator_input', 'Native builder changed after preview; no source or copy writes were retried', 409)

    def locked(self, plan):
        self.check_builder(plan)
        return self.load_native().generator_lock(str(self.home)) if plan.get('inputs') else nullcontext()

    def snapshot(self, path):
        native = self.load_native()
        state = native.snapshot(self.safe(path))
        if state is None:
            return None
        if os.lstat(path).st_nlink != 1:
            raise self.error('distribution_shared', 'Native input or output has shared file links', 409)
        return {'raw': encode(state[0]), 'sha256': digest(state[0]), 'mode': state[1]}

    def fingerprint(self, path):
        state = self.snapshot(path)
        return {key: state[key] for key in ('sha256', 'mode')} if state else None

    def constraints(self, source, raw):
        """Read-only candidate ceiling from the native BEFORE document budget.

        This is a conservative proposal aid. The native candidate render still
        enforces its complete document limits before a preview can be approved.
        """
        source = Path(source)
        rules = self.home / '.agents/instructions'
        factors = {'shared.md': 2, 'codex.md': 1, 'codex-style.md': 1}
        if source.parent != rules or source.name not in factors or not self.builder.is_file():
            return None
        native = self.load_native()
        with native.generator_lock(str(self.home)):
            paths = [self.builder, self.home / '.codex/config.toml'] + [rules / n for n in SOURCES]
            inputs = [{'path': str(path), 'state': self.fingerprint(path)} for path in paths]
            if inputs[0]['state'] != self.loaded_builder:
                raise self.error('stale_generator_input', 'Native builder changed during budget analysis; reopen the proposal', 409)
            current = self.snapshot(source)
            if current is None or decode(current['raw']) != raw:
                raise self.error('stale_generator_input', 'Source changed during budget analysis; reopen the proposal', 409)
            config = native.snapshot(self.safe(self.home / '.codex/config.toml'))
            baseline = {'codex_config': config}
            projection_source = raw.decode().rstrip() + '\n'
            used_probe = False
            try:
                limit = native.doc_limit(config[0].decode() if config else '')
                try:
                    projected = native.build(baseline, rules_only=True)
                except ValueError as exc:
                    if 'exceed' not in str(exc) or 'project_doc_max_bytes=' not in str(exc):
                        raise
                    # An oversized BEFORE must still be repairable by shrinking
                    # the selected source. Render only that source's minimal
                    # valid content through the SAME native limits, in memory.
                    projection_source = ('## Voice\n\n## Delegation and model routing\n'
                                         if source.name == 'codex-style.md' else '\n')
                    reader = native.read_src
                    try:
                        native.read_src = lambda name: projection_source if name == source.name else reader(name)
                        projected = native.build(baseline, rules_only=True)
                        used_probe = True
                    finally:
                        native.read_src = reader
            except (SystemExit, ValueError) as exc:
                raise self.error('native_projection_failed', 'Native instruction projection cannot fit its configured bytes limit even with a minimal selected source, or cannot be built; shorten the other native inputs through their owner. Source is unchanged.', 422) from exc
            self.validate_inputs({'inputs': inputs})
            used = sum(len(projected[key].encode()) for key in ('codex', 'home_agents'))
            margin = max(0, (limit - used) // factors[source.name])
            # Native read_src trims trailing whitespace. Excluding that padding
            # prevents replacing padding with substantive projected instructions.
            source_size = len(projection_source.encode())
            ceiling = min(65536, source_size + margin)
            basis = 'A minimal selected-source probe' if used_probe else 'Current native'
            return {'max_candidate_bytes': ceiling, 'growth_budget_bytes': ceiling - len(raw),
                    'reason': f'{basis} Codex and home instruction projections use {used} of {limit} bytes. This source affects {factors[source.name]} projected document(s); keep the candidate within this UTF-8 byte ceiling. Native candidate validation still applies.'}

    def freeze(self, source, after):
        source = Path(source)
        rules = self.home / '.agents/instructions'
        name = source.name if source.parent == rules else None
        if name not in DEPENDENTS:
            unknown = source.parent == rules
            return {'status': 'blocked' if unknown else 'not_needed', 'targets': [], 'inputs': [],
                    'limitations': ['This instruction source has no supported native output projection; distribution remains pending.'] if unknown else []}
        if not self.builder.is_file():
            return {'status': 'blocked', 'targets': [], 'inputs': [],
                    'limitations': ['Native instruction builder is unavailable; affected copies remain pending.']}
        constraint = self.constraints(source, source.read_bytes())
        native = self.load_native()
        with native.generator_lock(str(self.home)):
            paths = [self.builder, self.home / '.codex/config.toml'] + [rules / n for n in SOURCES]
            inputs = [{'path': str(p), 'state': self.fingerprint(p)} for p in paths]
            if inputs[0]['state'] != self.loaded_builder:
                raise self.error('stale_generator_input', 'Native builder changed during preview; reopen the proposal', 409)
            baseline = {'codex_config': native.snapshot(self.safe(self.home / '.codex/config.toml'))}
            reader = native.read_src
            def candidate(filename):
                return after.decode().rstrip() + '\n' if filename == name else reader(filename)
            try:
                native.read_src = candidate
                rendered = native.build(baseline, rules_only=True)
            except (SystemExit, ValueError) as exc:
                message = 'Native rule projection could not be built; request a shorter candidate. Source is unchanged.'
                if constraint:
                    message = f'Native instruction projection exceeded or failed its configured limit; request a shorter candidate at most {constraint["max_candidate_bytes"]} UTF-8 bytes (growth budget {constraint["growth_budget_bytes"]} bytes). Source is unchanged.'
                raise self.error('native_projection_failed', message, 422) from exc
            finally:
                native.read_src = reader
            targets = []
            for key in DEPENDENTS[name]:
                path = self.home / OUTPUTS[key]
                before = self.snapshot(path)
                raw = rendered[key].encode()
                old = decode(before['raw']) if before else b''
                targets.append({'path': str(path), 'before': before, 'after': encode(raw),
                                'before_sha256': before['sha256'] if before else None,
                                'after_sha256': digest(raw), 'mode': before['mode'] if before else 0o600,
                                'diff': ''.join(difflib.unified_diff(old.decode().splitlines(keepends=True), raw.decode().splitlines(keepends=True), fromfile=str(path) + ' (before)', tofile=str(path) + ' (proposed)')),
                                'kind': 'import' if key == 'claude' else 'generated', 'requires_new_session': True})
            plan = {'status': 'ready', 'targets': targets, 'inputs': inputs, 'limitations': [],
                    'source': str(source), 'source_before_sha256': digest(source.read_bytes()), 'source_after_sha256': digest(after)}
            if name in {'codex-style.md', 'shared-style.md'}:
                plan['limitations'].append('Codex developer instructions also depend on this style source. App-owned config is excluded and remains pending in its native settings workflow.')
            self.preflight(plan)
            return plan

    def public(self, plan):
        return {'status': plan['status'], 'limitations': plan['limitations'],
                'targets': [{key: target[key] for key in ('path', 'before_sha256', 'after_sha256', 'diff', 'kind', 'requires_new_session')} for target in plan['targets']]}

    def validate_inputs(self, plan, source=None, source_sha=None):
        for item in plan['inputs']:
            current = self.fingerprint(item['path'])
            expected = item['state']
            if source and item['path'] == str(source):
                if not current or current['sha256'] != source_sha or current['mode'] != expected['mode']:
                    raise self.error('stale_generator_input', 'Canonical instruction source changed; no generated writes were retried', 409)
            elif current != expected:
                raise self.error('stale_generator_input', 'Native source, builder or app-owned config changed after preview; review a fresh repair', 409)

    def preflight(self, plan):
        self.validate_inputs(plan)
        for target in plan['targets']:
            if self.snapshot(target['path']) != target['before']:
                raise self.error('stale_destination', 'Affected instruction destination changed after preview; source is unchanged', 409)

    def backup(self, plan, folder, repair_id):
        native = self.load_native() if plan['inputs'] else None
        for index, target in enumerate(plan['targets']):
            state = target['before']
            if state is None:
                continue
            path = Path(folder) / f'{repair_id}.output-{index}.before'
            temporary = native.stage(path, decode(state['raw']), state['mode'])
            try:
                os.replace(temporary, path)
                native.fsync_dir(path.parent)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
            if native.snapshot(path)[:2] != (decode(state['raw']), state['mode']):
                raise self.error('backup_unverified', 'Generated-output undo backup failed readback; source is unchanged', 409)
            target['backup_path'] = str(path)

    def matches(self, state, target, undo=False):
        if undo:
            return state == target['before']
        return state is not None and state['sha256'] == target['after_sha256'] and state['mode'] == target['mode']

    def install(self, plan, source, source_sha, progress):
        native = self.load_native() if plan['inputs'] else None
        self.validate_inputs(plan, source, source_sha)
        for target in plan['targets']:
            current = self.snapshot(target['path'])
            if self.matches(current, target):
                target['applied'] = current
                progress()
                continue
            if current != target['before']:
                raise self.error('stale_destination', 'Generated destination has newer edits; source applied and distribution pending', 409)
            temporary = native.stage(target['path'], decode(target['after']), target['mode'])
            try:
                self.validate_inputs(plan, source, source_sha)
                if self.snapshot(target['path']) != current:
                    raise self.error('stale_destination', 'Generated destination changed before replacement', 409)
                os.replace(temporary, target['path'])
                native.fsync_dir(Path(target['path']).parent)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
            actual = self.snapshot(target['path'])
            target['applied'] = actual
            progress()
            if not self.matches(actual, target):
                raise self.error('distribution_readback', 'Generated readback failed; recovery is retained', 409)

    def observe(self, plan, undo=False, record=False):
        targets = []
        try:
            self.check_builder(plan)
            self.validate_inputs(plan, plan.get('source'), plan.get('source_before_sha256' if undo else 'source_after_sha256'))
        except (OSError, RuntimeError, self.error):
            return {'status': 'pending', 'targets': [{'path': t['path'], 'status': 'pending', 'sha256': None, 'reason': 'Native inputs changed; copies require fresh review.'} for t in plan['targets']], 'message': 'Native source, builder or app config changed after preview; recovery retained.'}
        for target in plan['targets']:
            try:
                actual = self.snapshot(target['path'])
                verified = self.matches(actual, target, undo)
                if record and verified:
                    target['applied'] = actual
                targets.append({'path': target['path'], 'status': 'verified' if verified else 'pending',
                                'sha256': actual['sha256'] if actual else None,
                                'reason': 'Exact frozen bytes and mode verified; running agents may need a new session.' if verified else 'Destination does not match the recorded replacement; recovery is retained.'})
            except (OSError, RuntimeError, self.error):
                targets.append({'path': target['path'], 'status': 'pending', 'sha256': None, 'reason': 'Destination readback unavailable; recovery is retained.'})
        pending = plan['status'] == 'blocked' or bool(plan['limitations']) or any(t['status'] == 'pending' for t in targets)
        status = 'pending' if pending else ('not_needed' if plan['status'] == 'not_needed' else 'verified')
        return {'status': status, 'targets': targets,
                'message': ' '.join(plan['limitations']) if pending and plan['limitations'] else ('Affected instruction files verified. Existing sessions were not checked for reload.' if targets else 'No dependent generated files.')}

    def preflight_undo(self, plan, source, source_sha):
        self.validate_inputs(plan, source, source_sha)
        for target in plan['targets']:
            current = self.snapshot(target['path'])
            # Interrupted installs can leave an untouched before state. Restoring
            # that state is a no-op; any other unrecorded state is a newer edit.
            expected = target.get('applied', target['before'])
            if current != expected:
                raise self.error('stale_destination', 'Affected output has newer contents or mode; Undo changed nothing', 409)
            before = target['before']
            if before is not None:
                backup = Path(target.get('backup_path', ''))
                expected_folder = (self.home / 'Backups/local-file-repairs').resolve()
                if backup.is_symlink() or backup.parent.resolve() != expected_folder:
                    raise self.error('backup_changed', 'Recorded output backup is unavailable; Undo changed nothing', 409)
                state = self.load_native().snapshot(backup)
                if state is None or state[:2] != (decode(before['raw']), before['mode']):
                    raise self.error('backup_changed', 'Recorded output backup changed; Undo changed nothing', 409)

    def restore(self, plan, source, source_sha, folder, repair_id, progress):
        native = self.load_native() if plan['inputs'] else None
        self.validate_inputs(plan, source, source_sha)
        for index, target in enumerate(plan['targets']):
            current = self.snapshot(target['path'])
            if current != target.get('applied', target['before']):
                raise self.error('stale_destination', 'Affected output changed during Undo; recovery retained', 409)
            before = target['before']
            if current == before:
                continue
            if before is None:
                # A created file is recoverable on Drive before its removal.
                recovery = Path(folder) / f'{repair_id}.output-{index}.created-recovery'
                temporary = native.stage(recovery, decode(current['raw']), current['mode'])
                os.replace(temporary, recovery)
                native.fsync_dir(recovery.parent)
                if native.snapshot(recovery)[:2] != (decode(current['raw']), current['mode']):
                    raise self.error('backup_unverified', 'Created output recovery failed; output retained', 409)
                if self.snapshot(target['path']) != current:
                    raise self.error('stale_destination', 'Created output changed before restoration', 409)
                os.unlink(target['path'])
                native.fsync_dir(Path(target['path']).parent)
            else:
                temporary = native.stage(target['path'], decode(before['raw']), before['mode'])
                try:
                    if self.snapshot(target['path']) != current:
                        raise self.error('stale_destination', 'Output changed immediately before restoration', 409)
                    os.replace(temporary, target['path'])
                    native.fsync_dir(Path(target['path']).parent)
                finally:
                    if os.path.exists(temporary):
                        os.unlink(temporary)
            target['restored'] = self.snapshot(target['path'])
            progress()
            if target['restored'] != before:
                raise self.error('distribution_readback', 'Output restoration failed readback; recovery retained', 409)
