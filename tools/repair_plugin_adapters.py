"""Owned Git marketplace sources, one publication, then native materialization.

Cache files are evidence only. Existing desktop runtime activation stays pending.
"""
import copy
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tomllib

from repair_contracts import RepairError
from repair_local_adapters import LocalAdapter, SOURCE_LANGUAGES, canonical, sha, target_id, safe_json_projection
from repair_local_checks import check, json_check
from repair_native_adapters import CodexClient


class ClaudePluginClient:
    def __init__(self, home, binary=None):
        self.home = Path(home)
        self.binary = binary or shutil.which('claude') or 'claude'

    def request(self, action, plugin=None):
        args = [self.binary, 'plugin', action]
        if plugin:
            args += [plugin, '--scope', 'user']
        args += ['--json']
        try:
            result = subprocess.run(args, cwd='/tmp', env={**os.environ, 'CLAUDE_CONFIG_DIR': str(self.home)},
                                    capture_output=True, text=True, timeout=45)
            if result.returncode:
                raise RepairError('claude_plugin_native_rejected')
            value = json.loads(result.stdout.strip().splitlines()[-1] if action != 'list' else result.stdout)
            if action != 'list' and value.get('outcome') != 'ok':
                raise RepairError('claude_plugin_native_rejected')
            return value
        except (OSError, ValueError, subprocess.TimeoutExpired):
            raise RepairError('claude_plugin_native_unavailable') from None


class PluginAdapter(LocalAdapter):
    adapter_id = 'owned-plugin'
    category = 'skill'
    version = '1'

    def __init__(self, home=None, codex=None, claude=None):
        super().__init__(home)
        self.codex = codex or CodexClient(self.home / '.codex')
        self.claude = claude or ClaudePluginClient(self.home / '.claude')
        self.packages = {}

    def registry(self):
        path = self.home / '.claude/plugins/known_marketplaces.json'
        return json.loads(self.state(path)[0]) if path.exists() else {}

    def context(self, target=None):
        path = self.home / '.claude/plugins/known_marketplaces.json'
        return sha(canonical({'registry': self.state(path)[1] if path.exists() else None, 'version': self.version}))

    def discover(self):
        rows = []
        self.packages = {}
        for name, record in sorted(self.registry().items()):
            source = record.get('source', {})
            if source.get('source') != 'directory':
                continue
            root = Path(source.get('path', '')).absolute()
            try:
                marketplace = self.safe(root / '.claude-plugin/marketplace.json')
                repo = self.repo_path(marketplace)
                if not repo or any(part in ('cache', 'marketplaces') for part in root.relative_to(self.home).parts):
                    continue
                document = json.loads(self.state(marketplace)[0])
                if document.get('name') != name:
                    continue
                for plugin in document.get('plugins', []):
                    relative = plugin.get('source')
                    if not isinstance(relative, str) or not relative.startswith('./') or '..' in Path(relative).parts:
                        continue
                    folder = root / relative
                    manifest = self.safe(folder / '.claude-plugin/plugin.json')
                    meta = json.loads(self.state(manifest)[0])
                    if meta.get('name') != plugin.get('name') or not re.fullmatch(r'[A-Za-z0-9_-]+', meta['name']):
                        continue
                    key = meta['name'] + '@' + name
                    package = dict(key=key, name=meta['name'], marketplace=name, marketplace_path=str(marketplace),
                                   root=str(folder), manifest=str(manifest), repo=repo)
                    self.packages[key] = package
                    if not any(r['identity']['path'] == str(marketplace) for r in rows):
                        rows.append(self.row(marketplace, 'plugin_metadata', 'owned-plugin-source', content_format='text', plugin_key=key))
                    host_manifest = folder / '.codex-plugin/plugin.json'
                    paths = set(self.source_files(folder)) | {manifest}
                    if host_manifest.is_file():
                        self.safe(host_manifest)
                        paths.add(host_manifest)
                    for path in sorted(paths):
                        rel = path.relative_to(folder)
                        if path in (manifest, host_manifest):
                            category = 'plugin_metadata'
                        elif path.name == 'SKILL.md':
                            category = 'skill'
                        elif rel.parts[0] == 'hooks' and path.suffix == '.json':
                            category = 'hook'
                        elif path.suffix.lstrip('.') in SOURCE_LANGUAGES:
                            category = 'executable'
                        elif rel.parts[0] in ('skills', 'references', 'scripts'):
                            category = 'skill_reference'
                        else:
                            continue
                        rows.append(self.row(path, category, 'owned-plugin-source', content_format='text', plugin_key=key))
                    sync = self.row(folder / '.native-materialization', 'plugin_sync', 'native-plugin-install', content_format='json', plugin_key=key)
                    sync['identity']['package'] = copy.deepcopy(package)
                    rows.append(sync)
            except (RepairError, OSError, ValueError, KeyError):
                continue
        for repo in sorted({p['repo'] for p in self.packages.values()}):
            rows.append(self.row(repo, 'publication', 'git', content_format='json'))
        # Source text containing private material is never sent to a model or replaced.
        for row in rows:
            if row.get('content_format') == 'text':
                try:
                    if self.text_projection(row, self.state(row['identity']['path'])[0].decode())[1]:
                        row['missing_capability'] = 'safe_text_projection'
                except (RepairError, UnicodeError):
                    row['missing_capability'] = 'readable_source'
        self._targets = {r['id']: r for r in rows}
        return rows

    def inventory(self, package):
        """Read native persisted records only; native discovery may materialize.

        Codex persists installation enablement/source in config.toml and one
        materialized version directory, not a separate installed JSON registry.
        Claude persists the installed version/path in installed_plugins.json.
        No process, app-server request or CLI invocation belongs in this method.
        """
        copies = []
        config = self.home / '.codex/config.toml'
        if config.exists():
            document = tomllib.loads(self.state(config)[0].decode())
            if package['key'] in document.get('plugins', {}):
                market = document.get('marketplaces', {}).get(package['marketplace'], {})
                source = Path(market.get('source', '')).absolute()
                expected = Path(package['marketplace_path']).parent.parent
                if market.get('source_type') != 'local' or source != expected:
                    raise RepairError('plugin_codex_registered_source_changed')
                if not document['plugins'][package['key']].get('enabled', False):
                    raise RepairError('plugin_disabled_copy_native_sync_unavailable')
                cache = self.home / '.codex/plugins/cache' / package['marketplace'] / package['name']
                candidates = []
                if cache.is_dir() and not cache.is_symlink():
                    for version in sorted(cache.iterdir()):
                        if not version.is_dir() or version.is_symlink():
                            raise RepairError('plugin_cache_identity_changed')
                        manifests = [version / kind / 'plugin.json' for kind in ('.codex-plugin', '.claude-plugin')]
                        manifest = next((p for p in manifests if p.is_file()), None)
                        if manifest is None:
                            raise RepairError('plugin_cache_identity_changed')
                        meta = json.loads(self.state(manifest)[0])
                        if meta.get('name') != package['name'] or meta.get('version') != version.name:
                            raise RepairError('plugin_cache_identity_changed')
                        candidates.append(version)
                if len(candidates) != 1:
                    raise RepairError('plugin_codex_installed_version_ambiguous')
                version = candidates[0]
                copies.append({'system': 'codex', 'id': package['key'], 'version': version.name, 'path': str(version)})
        installed = self.home / '.claude/plugins/installed_plugins.json'
        if installed.exists():
            value = json.loads(self.state(installed)[0])
            if value.get('version') != 2 or not isinstance(value.get('plugins'), dict):
                raise RepairError('plugin_claude_installed_registry_invalid')
            rows = [r for r in value['plugins'].get(package['key'], []) if r.get('scope') == 'user']
            if len(rows) > 1:
                raise RepairError('plugin_claude_installed_version_ambiguous')
            for row in rows:
                expected = self.home / '.claude/plugins/cache' / package['marketplace'] / package['name'] / row['version']
                if Path(row.get('installPath', '')).absolute() != expected:
                    raise RepairError('plugin_cache_identity_changed')
                copies.append({'system': 'claude', 'id': package['key'], 'version': row['version'], 'path': str(expected)})
        if not copies:
            raise RepairError('plugin_installed_copy_unavailable')
        return copies

    def file_hashes(self, root):
        root = Path(root)
        hashes = {}
        # Bound the package, reject aliases, and never follow provider cache links.
        for directory, dirs, files in os.walk(root, followlinks=False):
            dirs[:] = sorted(d for d in dirs if d != '.git')
            for name in files:
                path = self.safe(Path(directory) / name)
                rel = path.relative_to(root).as_posix()
                hashes[rel] = sha(self.state(path)[0])
                if len(hashes) > 2048:
                    raise RepairError('plugin_package_too_large')
            if any((Path(directory) / d).is_symlink() for d in dirs):
                raise RepairError('plugin_package_alias')
        if not hashes:
            raise RepairError('plugin_package_empty')
        return hashes

    def cache_state(self, package):
        return [{**item, 'hashes': self.file_hashes(item['path'])} for item in self.inventory(package)]

    def read(self, target):
        if target['category'] != 'plugin_sync':
            return super().read(target)
        self.registered(target)
        state = self.cache_state(target['identity']['package'])
        return {'version': self.version, 'fingerprint': sha(canonical(state)), 'projection': {'copies': state}, 'context_fingerprint': self.context(target)}

    def prepare(self, target, snapshot, proposal):
        if target['category'] == 'plugin_sync' or (target['category'] == 'plugin_metadata' and not getattr(self, '_metadata_preparing', False)):
            raise RepairError('owner_generated_operation')
        if target['category'] in ('hook', 'plugin_metadata'):
            # Reuse canonical CAS/secret checks; parse JSON without executing hooks.
            original = self._targets[target['id']]
            surrogate = {**original, 'category': 'skill_reference'}
            self._targets[target['id']] = surrogate
            try:
                op = super().prepare(surrogate, snapshot, proposal)
            finally:
                self._targets[target['id']] = original
            value = json.loads(op['candidate'])
            if not isinstance(value, dict):
                raise RepairError('plugin_json_object_required')
            if target['category'] == 'hook':
                parsed = json_check(value, 'hook', 'claude')
                if parsed['status'] != 'passed':
                    raise RepairError('candidate_check_failed')
                op['checks'].append(parsed)
            return op
        return super().prepare(target, snapshot, proposal)

    def prepare_metadata(self, target, candidate):
        self._metadata_preparing = True
        try:
            return self.prepare(target, self.read(target), {'candidate': candidate})
        finally:
            self._metadata_preparing = False

    def stale_inputs(self, copies, source_hashes):
        inputs = []
        for item in copies:
            for relative, fingerprint in item['hashes'].items():
                if source_hashes.get(relative) == fingerprint:
                    continue
                path = Path(item['path']) / relative
                raw, state = self.state(path)
                try:
                    text = raw.decode('utf-8')
                    if path.suffix == '.json':
                        value = json.loads(text)
                        private = safe_json_projection(value) != value or self.sensitive_value(value)
                    else:
                        target = {'category': 'executable' if path.suffix.lstrip('.') in SOURCE_LANGUAGES else 'skill_reference',
                                  'identity': {'path': str(path)}, 'source_language': path.suffix.lstrip('.')}
                        private = self.text_projection(target, text)[1]
                    if private:
                        raise RepairError('plugin_private_cache_preimage')
                except (ValueError, UnicodeError):
                    raise RepairError('plugin_opaque_cache_preimage') from None
                inputs.append({'path': str(path), 'state': state})
        return inputs

    def prepare_bundle(self, operations, targets):
        own = copy.deepcopy(operations)
        selected = sorted({targets[op['target_id']]['plugin_key'] for op in own})
        frozen = []
        for key in selected:
            package = copy.deepcopy(self.packages[key])
            before = self.cache_state(package)
            expected = self.file_hashes(package['root'])
            before_source_hashes = copy.deepcopy(expected)
            before_version = json.loads(self.state(package['manifest'])[0])['version']
            canonical_before = [{**c, 'hashes': before_source_hashes, 'version': before_version,
                                 'path': str(Path(c['path']).parent / before_version)} for c in before]
            members = [op for op in own if targets[op['target_id']].get('plugin_key') == key
                       and Path(package['root']) in Path(op['selector']['path']).parents]
            if any(c['system'] == 'claude' for c in before):
                manifest = Path(package['manifest'])
                document = json.loads(self.state(manifest)[0])
                if any(op['selector']['path'] == str(manifest) for op in members):
                    raise RepairError('plugin_version_owned_by_bundle')
                match = re.fullmatch(r'(\d+)\.(\d+)\.(\d+)', document.get('version', ''))
                if not match:
                    raise RepairError('plugin_semver_required')
                document['version'] = '.'.join([match[1], match[2], str(int(match[3]) + 1)])
                target = targets[target_id(manifest)]
                op = self.prepare_metadata(target, json.dumps(document, indent=2) + '\n')
                own.append(self.bind(target, op, len(own))); members.append(own[-1])
                host_manifest = Path(package['root']) / '.codex-plugin/plugin.json'
                if host_manifest.is_file():
                    meta = json.loads(self.state(host_manifest)[0])
                    if meta.get('name') != package['name']:
                        raise RepairError('plugin_host_manifest_identity_changed')
                    meta['version'] = document['version']
                    host_target = targets[target_id(host_manifest)]
                    op = self.prepare_metadata(host_target, json.dumps(meta, indent=2) + '\n')
                    own.append(self.bind(host_target, op, len(own))); members.append(own[-1])
                # Marketplace metadata is a source target frozen alongside manifest.
                market_path = Path(package['marketplace_path'])
                market = json.loads(self.state(market_path)[0])
                for entry in market['plugins']:
                    if entry.get('name') == package['name']:
                        entry['version'] = document['version']
                market_target = targets.get(target_id(market_path))
                if not market_target:
                    raise RepairError('plugin_marketplace_target_missing')
                existing = next((o for o in own if o['selector']['path'] == str(market_path)), None)
                if existing:
                    # Freeze one combined marketplace diff across all selected plugins.
                    market = json.loads(existing['candidate'])
                    for entry in market['plugins']:
                        if entry.get('name') == package['name']:
                            entry['version'] = document['version']
                    updated = self.prepare_metadata(market_target, json.dumps(market, indent=2) + '\n')
                    updated = self.bind(market_target, updated, len(own))
                    existing.clear(); existing.update(updated)
                else:
                    op = self.prepare_metadata(market_target, json.dumps(market, indent=2) + '\n')
                    own.append(self.bind(market_target, op, len(own)))
                package['after_version'] = document['version']
            else:
                package['after_version'] = json.loads(self.state(package['manifest'])[0])['version']
            for op in members:
                rel = Path(op['selector']['path']).relative_to(package['root']).as_posix()
                expected[rel] = sha(op['candidate'].encode())
            frozen.append((package, before, expected, canonical_before, before_source_hashes))
        own = super().prepare_bundle(own, targets)
        for package, before, expected, canonical_before, before_source_hashes in frozen:
            sync = next(t for t in targets.values() if t['category'] == 'plugin_sync' and t['plugin_key'] == package['key'])
            publication = next(o for o in own if o['action'] == 'publish' and o['repo']['repo'] == package['repo'])
            op = {'action': 'plugin_materialize', 'selector': {'path': package['root']}, 'package': package,
                  'stale_cache_inputs': self.stale_inputs(before, before_source_hashes), 'before_copies': before, 'canonical_before_copies': canonical_before, 'before_source_hashes': before_source_hashes, 'expected_hashes': expected, 'publication': copy.deepcopy(publication),
                  'context_fingerprint': self.context(sync), 'expected_version': self.version,
                  'expected_fingerprint': sha(canonical(before)), 'inverse': {'copies': before},
                  'public_diff': json.dumps({'native_materialization': package, 'before_copies': before, 'after_hashes': expected, 'undo': 'Undo restores previous canonical source and refreshes copies; pre-existing stale copies are not recreated.'}, sort_keys=True),
                  'checks': [check('owner_lifecycle', 'passed', 'native-plugin-materialization.v1', expected,
                                    ['Frozen source, version metadata, exact publication, native calls and installed-copy preimages.'],
                                    ['Desktop runtime activation remains pending.'])]}
            own.append(self.bind(sync, op, len(own)))
        return own

    def preflight(self, target, operation):
        if operation['action'] != 'plugin_materialize':
            return super().preflight(target, operation)
        try:
            # Before the barrier every package file must remain the frozen
            # preimage, including files outside the selected patch set. Approved
            # candidate bytes are accepted after source steps by apply() or an
            # explicitly marked continuation with exact publication proof.
            source = self.file_hashes(operation['package']['root'])
            copies = self.cache_state(operation['package'])
            ok = (self.context(target) == operation['context_fingerprint']
                  and source == operation['before_source_hashes']
                  and copies == operation['before_copies'])
            if operation.get('recovery_phase') == 'forward':
                publication = operation['publication']
                published = super().reconcile(self._targets[publication['target_id']], publication, {})['outcome'] == 'applied'
                ok = ok or (self.context(target) == operation['context_fingerprint']
                            and source == operation['expected_hashes'] and self.caches_known(operation, copies) and published)
            return {'ok': ok, 'evidence': ['Whole canonical package preimage, installed identities, versions and cache bytes compared.']}
        except (RepairError, OSError, ValueError):
            return {'ok': False, 'evidence': ['Native installed copy unavailable.']}

    def backup(self, target, operation, backup_dir):
        if operation['action'] != 'plugin_materialize':
            return super().backup(target, operation, backup_dir)
        if not self.preflight(target, operation)['ok']:
            raise RepairError('stale_plugin_backup_source')
        publication = operation['publication']
        saved = []
        for item in operation['stale_cache_inputs']:
            raw, state = self.state(item['path'])
            if state != item['state']:
                raise RepairError('plugin_cache_changed')
            path = self.backup_root() / (sha(canonical(item)) + '.plugin-cache-before')
            if path.is_symlink():
                raise RepairError('backup_alias')
            if not path.exists():
                descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                with os.fdopen(descriptor, 'wb') as stream:
                    stream.write(raw); stream.flush(); os.fsync(stream.fileno())
            if path.read_bytes() != raw:
                raise RepairError('backup_changed')
            saved.append({'path': str(path), 'sha256': sha(raw), 'source_path': item['path'], 'cloud_upload': 'unverified'})
        return {'publication': super().backup(self._targets[publication['target_id']], publication, backup_dir),
                'copies': operation['before_copies'], 'stale_cache_backups': saved}

    def refresh(self, package, copies):
        desired_hashes = self.file_hashes(package['root'])
        desired_version = json.loads(self.state(package['manifest'])[0])['version']
        for item in copies:
            # Read persisted native registration and exact package bytes afresh.
            # A completed copy is never reinstalled merely because its receipt
            # was lost while another copy was still pending.
            observed = next((c for c in self.cache_state(package) if (c['system'], c['id']) == (item['system'], item['id'])), None)
            if observed and observed['hashes'] == desired_hashes and observed['version'] == desired_version:
                continue
            if item['system'] == 'codex':
                params = {'pluginName': package['name'], 'marketplacePath': package['marketplace_path']}
                self.codex.request('plugin/install', params)
                row = self.codex.request('plugin/read', params).get('plugin', {})
                if row.get('summary', {}).get('id') != item['id'] or not row.get('summary', {}).get('installed'):
                    raise RepairError('plugin_native_readback_failed')
            else:
                self.claude.request('update', package['key'])
                rows = self.claude.request('list')
                if not any(r.get('id') == item['id'] and r.get('scope') == 'user' for r in rows):
                    raise RepairError('plugin_native_readback_failed')
        return self.cache_state(package)

    def apply(self, target, operation, backup):
        if operation['action'] != 'plugin_materialize':
            return super().apply(target, operation, backup)
        if self.context(target) != operation['context_fingerprint'] or self.file_hashes(operation['package']['root']) != operation['expected_hashes']:
            raise RepairError('plugin_source_changed')
        pub = operation['publication']
        observed = super().reconcile(self._targets[pub['target_id']], pub, backup['publication'])
        if observed['outcome'] != 'applied':
            raise RepairError('plugin_publication_unconfirmed')
        current = self.cache_state(operation['package'])
        if not self.caches_known(operation, current):
            raise RepairError('plugin_cache_changed')
        return {'copies': self.refresh(operation['package'], operation['before_copies'])}

    def caches_known(self, operation, copies):
        before = {(c['system'], c['id']): c for c in operation['before_copies']}
        # Native list can materialize a version change while reporting inventory.
        # Each copy must still be an exact frozen preimage or approved candidate.
        return {(c['system'], c['id']) for c in copies} == set(before) and all(
            c == before[(c['system'], c['id'])] or
            (c['hashes'] == operation['expected_hashes'] and c['version'] == operation['package']['after_version'])
            for c in copies)

    def caches_match(self, operation, copies):
        identities = {(c['system'], c['id']) for c in operation['before_copies']}
        return {(c['system'], c['id']) for c in copies} == identities and all(c['hashes'] == operation['expected_hashes'] and c['version'] == operation['package']['after_version'] for c in copies)

    def verify(self, target, operation, result):
        if operation['action'] != 'plugin_materialize':
            return super().verify(target, operation, result)
        copies = self.cache_state(operation['package'])
        ok = self.caches_match(operation, copies)
        return self.receipt(ok, 'byte_verified' if ok else 'pending', ['Fresh native inventory and installed package bytes compared.'],
                            ['Existing desktop runtime activation remains pending.'], operation['checks'], sha(canonical(copies)))

    def inverse_caches_known(self, operation, copies):
        originals = {(c['system'], c['id']): c for c in operation['canonical_before_copies']}
        return {(c['system'], c['id']) for c in copies} == set(originals) and all(
            c == originals[(c['system'], c['id'])] or
            (c['hashes'] == operation['expected_hashes'] and c['version'] == operation['package']['after_version'])
            for c in copies)

    def inverse_publication(self, operation, backup):
        publication = operation['publication']
        return super().reconcile_undo(self._targets[publication['target_id']], publication, backup['publication'])

    def reconcile(self, target, operation, backup):
        if operation['action'] != 'plugin_materialize':
            return super().reconcile(target, operation, backup)
        copies = self.cache_state(operation['package'])
        source = self.file_hashes(operation['package']['root'])
        after = self.caches_match(operation, copies)
        if operation.get('recovery_phase') == 'undo':
            restored = source == operation['before_source_hashes'] and self.inverse_publication(operation, backup)['outcome'] == 'applied'
            if restored and self.inverse_caches_known(operation, copies):
                outcome = 'applied' if copies == operation['canonical_before_copies'] else 'not_applied'
            elif source == operation['expected_hashes'] and after:
                outcome = 'not_applied'
            else:
                outcome = 'unknown'
        else:
            before = copies == operation['before_copies'] and source == operation['before_source_hashes']
            publication = operation['publication']
            published = super().reconcile(self._targets[publication['target_id']], publication, backup['publication'])['outcome'] == 'applied'
            ready = source == operation['expected_hashes'] and self.caches_known(operation, copies) and published
            outcome = 'applied' if ready and after else 'not_applied' if before or ready else 'unknown'
        return {'outcome': outcome, 'result': {'copies': copies},
                'evidence': ['Canonical source, exact cache fingerprints and inverse publication observed without native commands.']}

    def undo(self, target, operation, backup, applied):
        if operation['action'] != 'plugin_materialize':
            return super().undo(target, operation, backup, applied)
        copies = self.cache_state(operation['package'])
        source = self.file_hashes(operation['package']['root'])
        if source == operation['before_source_hashes']:
            # Another package in this same approved publication may already have
            # restored every source. Prove that exact inverse commit and remote;
            # refresh only this package, without publishing another inverse.
            if self.inverse_publication(operation, backup)['outcome'] != 'applied' or not self.inverse_caches_known(operation, copies):
                return self.receipt(False, 'blocked', ['Canonical inverse publication or installed-copy state is not proven; newer values preserved.'])
            if copies == operation['canonical_before_copies']:
                return self.receipt(True, 'undone', ['Exact inverse publication, original source and installed bytes already observed.'])
        else:
            if source != operation['expected_hashes'] or not self.caches_match(operation, copies):
                return self.receipt(False, 'blocked', ['A repaired source or cache changed; newer bytes preserved.'])
            pub = operation['publication']
            observed = super().reconcile(self._targets[pub['target_id']], pub, backup['publication'])
            if observed['outcome'] != 'applied':
                raise RepairError('plugin_publication_unconfirmed')
            restored = super().undo(self._targets[pub['target_id']], pub, backup['publication'], observed['result'])
            if not restored['ok']:
                return restored
        if self.file_hashes(operation['package']['root']) != operation['before_source_hashes']:
            raise RepairError('plugin_inverse_source_changed')
        actual = self.refresh(operation['package'], operation['before_copies'])
        ok = actual == operation['canonical_before_copies']
        return self.receipt(ok, 'undone' if ok else 'pending', ['Conditional source inverse published once, native installed copies restored and read back.'], ['Existing desktop runtime activation remains pending.'])


def register_adapters(registry, home=None):
    registry.register(PluginAdapter(home))
