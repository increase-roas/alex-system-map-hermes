#!/usr/bin/env python3
"""Frozen repair transactions. All effects belong to fixed registered native adapters."""
import argparse
import copy
from datetime import datetime, timedelta, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid
from contextlib import contextmanager
from repair_contracts import RepairError, SCHEMA_VERSION
from repair_registry import default_registry


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def opaque(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-f0-9]{32}', value):
        raise RepairError('invalid_id')
    return value


class Coordinator:
    def __init__(self, state_dir, registry, proposer=None):
        self.root = Path(state_dir)
        self.registry = registry
        self.proposer = proposer
        for folder in (self.root, self.root / 'plans', self.root / 'jobs', self.root / 'backups'):
            folder.mkdir(parents=True, exist_ok=True, mode=0o700)
            folder.chmod(0o700)

    @contextmanager
    def lock(self, name):
        file = self.root / (name + '.lock')
        fd = os.open(file, os.O_CREAT | os.O_RDWR, 0o600)
        with os.fdopen(fd, 'w') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            yield

    def save(self, folder, identifier, value):
        path = self.root / folder / (opaque(identifier) + '.json')
        temp = path.with_suffix('.' + uuid.uuid4().hex + '.tmp')
        fd = os.open(temp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'w') as handle:
            json.dump(value, handle, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def load(self, folder, identifier):
        try:
            return json.loads((self.root / folder / (opaque(identifier) + '.json')).read_text())
        except (OSError, ValueError):
            raise RepairError('record_unavailable') from None

    def discover(self):
        targets = list(self.registry.discover().values())
        return {'schema_version': SCHEMA_VERSION, 'targets': targets, 'limitations': list(self.registry.limitations)}

    def source(self, target_id):
        return self._source_from_targets(target_id, self.registry.discover())

    def _source_from_targets(self, target_id, targets, context_only=False):
        if target_id not in targets:
            raise RepairError('unknown_target')
        target = targets[target_id]
        if target.get('missing_capability') and not (context_only and self.readonly_policy(target)):
            raise RepairError('target_unavailable')
        snapshot = self.registry.adapter(target['adapter_id']).read(target)
        return {'target': target, 'snapshot': {key: snapshot[key] for key in ('fingerprint', 'version', 'context_fingerprint', 'projection') if key in snapshot}}

    def propose(self, target_ids, intent):
        if not target_ids or len(set(target_ids)) != len(target_ids) or not isinstance(intent, str) or not intent.strip():
            raise RepairError('invalid_request')
        targets = self.registry.discover()
        sources = [self._source_from_targets(identifier, targets) for identifier in target_ids]
        # Native registrations alone establish these canonical paths. Context
        # can explain the standing gates but never expands the editable scope.
        homes = {source['target'].get('identity', {}).get('home')
                  for source in sources if source['target'].get('scope') == 'local'
                  and source['target'].get('category') in ('rule', 'skill', 'skill_reference', 'hook', 'executable')}
        canonical = ('.agents/instructions/shared.md', '.agents/skills/alex-director/references/gates.md')
        for relative in canonical:
            for target in targets.values():
                identity = target.get('identity', {})
                home = identity.get('home')
                if home and home in homes and target.get('scope') == 'local' and identity.get('path') == str(Path(home) / relative) and target['id'] not in target_ids and (not target.get('missing_capability') or self.readonly_policy(target)):
                    source = self._source_from_targets(target['id'], targets, context_only=True)
                    source['context_only'] = True
                    sources.append(source)
        if self.proposer is None:
            raise RepairError('ai_unavailable')
        proposal = self.proposer(intent, sources)
        proposals = proposal['proposals']
        if not proposals:
            diagnostics = proposal.get('diagnostics', {})
            stages = {'source', 'proposal', 'scenario', 'before', 'candidate', 'validation'}
            reasons = {'source_boundary', 'provider_unavailable', 'schema', 'citation', 'coverage', 'bounds', 'simulation'}
            error = RepairError('ai_no_proposals')
            error.details = {
                'code': error.code, 'error': 'No approvable proposal was produced.',
                'diagnostics': {'stage': diagnostics.get('stage') if diagnostics.get('stage') in stages else 'validation',
                                'reason': diagnostics.get('reason') if diagnostics.get('reason') in reasons else 'schema'},
                'checks': proposal.get('checks', []), 'limitations': proposal.get('limitations', []),
            }
            raise error
        if any(item['target_id'] not in target_ids for item in proposals):
            raise RepairError('proposal_scope_changed')
        return self.freeze(intent, proposals, proposal.get('checks', []), proposal.get('limitations', []), {source['target']['id']: source for source in sources})

    def freeze(self, intent, proposals, checks=None, limitations=None, reviewed_sources=None):
        targets = self.registry.discover()
        groups = {}
        reviewed_context = {}
        snapshots = {}
        for target_id, reviewed in (reviewed_sources or {}).items():
            if target_id not in targets or (targets[target_id].get('missing_capability') and not (reviewed.get('context_only') and self.readonly_policy(targets[target_id]))):
                raise RepairError('analysis_context_changed')
            target = targets[target_id]
            adapter = self.registry.adapter(target['adapter_id'])
            snapshot = adapter.read(target)
            if self.stable_target(reviewed['target']) != self.stable_target(target) or self.context_snapshot(snapshot) != self.context_snapshot(reviewed['snapshot']):
                raise RepairError('analysis_context_changed')
            snapshots[target_id] = snapshot
            reviewed_context[target_id] = {'target': self.stable_target(target), 'adapter_version': adapter.version,
                                           'snapshot_digest': digest(self.context_snapshot(snapshot))}
        for item in proposals:
            target_id = item['target_id']
            if target_id not in targets:
                raise RepairError('unknown_target')
            target = targets[target_id]
            if target.get('missing_capability'):
                raise RepairError('target_unavailable')
            adapter = self.registry.adapter(target['adapter_id'])
            snapshot = snapshots[target_id] if target_id in snapshots else adapter.read(target)
            operation = adapter.prepare(target, snapshot, item['proposal'])
            operation['target_id'] = target_id
            groups.setdefault(adapter.adapter_id, []).append(operation)
        operations = []
        for adapter_id, group in groups.items():
            adapter = self.registry.adapter(adapter_id)
            bundle = adapter.prepare_bundle(group, targets)
            for operation in bundle:
                target_id = operation['target_id']
                if target_id not in targets or targets[target_id]['adapter_id'] != adapter_id:
                    raise RepairError('unregistered_bundle_target')
                operation = copy.deepcopy(operation)
                operation.update(step_id=uuid.uuid4().hex, adapter_id=adapter_id, adapter_version=adapter.version, target_identity=targets[target_id]['identity'])
                operations.append(operation)
        if not operations:
            raise RepairError('empty_plan')
        selected = {op['target_id']: targets[op['target_id']] for op in operations}
        plan = dict(schema_version=SCHEMA_VERSION, plan_id=uuid.uuid4().hex, created_at=now(), expires_at=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(), intent=intent, targets=selected, operations=operations, checks=checks or [], limitations=limitations or [])
        plan['reviewed_context'] = reviewed_context
        plan['digest'] = digest(plan)
        self.save('plans', plan['plan_id'], plan)
        return self.public_plan(plan)

    def checked_plan(self, plan_id, expected_digest=None):
        plan = self.load('plans', plan_id)
        stored = plan.pop('digest')
        actual = digest(plan)
        plan['digest'] = stored
        if actual != stored or (expected_digest is not None and expected_digest != stored):
            raise RepairError('plan_digest_changed')
        return plan

    def public_plan(self, plan):
        fields = ('step_id', 'target_id', 'adapter_id', 'adapter_version', 'action', 'public_diff', 'checks', 'expected_fingerprint', 'expected_version')
        return {**{k: plan[k] for k in ('schema_version', 'plan_id', 'digest', 'created_at', 'expires_at', 'intent', 'checks', 'limitations')}, 'targets': list(plan['targets'].values()), 'operations': [{k: op[k] for k in fields if k in op} for op in plan['operations']]}

    def get_plan(self, plan_id):
        return self.public_plan(self.checked_plan(plan_id))

    def approve(self, plan_id, expected_digest):
        with self.lock('approval'):
            plan = self.checked_plan(plan_id, expected_digest)
            path = self.root / 'jobs' / (opaque(plan_id) + '.json')
            if path.exists():
                return self.get_job(plan_id)
            if datetime.fromisoformat(plan['expires_at']) < datetime.now(timezone.utc):
                raise RepairError('plan_expired')
            if any(check.get('status') != 'passed' for check in plan['checks']) or any(check.get('status') != 'passed' for op in plan['operations'] for check in op.get('checks', [])):
                raise RepairError('checks_not_passed')
            job = dict(schema_version=SCHEMA_VERSION, job_id=plan_id, plan_id=plan_id, digest=expected_digest, approval={'at': now(), 'digest': expected_digest}, status='queued', direction='forward', next_step=0, steps=[dict(step_id=op['step_id'], target_id=op['target_id'], phase='pending') for op in plan['operations']], events=[], unknown_effect=None, created_at=now(), updated_at=now(), barrier=False)
            self.save('jobs', plan_id, job)
            return self.public_job(job)

    def public_job(self, job):
        result = {k: job[k] for k in ('schema_version', 'job_id', 'plan_id', 'digest', 'status', 'next_step', 'unknown_effect', 'created_at', 'updated_at')}
        result['steps'] = [{k: step[k] for k in ('step_id', 'target_id', 'phase', 'outcome', 'receipt') if k in step} for step in job['steps']]
        result['events'] = job['events'][-200:]
        if 'error' in job:
            result['error'] = job['error']
        return result

    def get_job(self, job_id):
        return self.public_job(self.load('jobs', job_id))

    def event(self, job, phase, step=None):
        event = {'at': now(), 'phase': phase}
        if step:
            event['step_id'] = step['step_id']
        job['events'] = (job['events'] + [event])[-200:]
        job['updated_at'] = event['at']
        self.save('jobs', job['job_id'], job)

    @staticmethod
    def stable_target(target):
        # These two fields are discoveries from the current safe projection,
        # so a legitimate repair can change them. Owner/path/account identity
        # remains bound; adapters retain fingerprint/version CAS and field scope.
        return {key: value for key, value in target.items() if key not in ('observed_at', 'evidence', 'limitations', 'allowed_patch_paths', 'related_target_ids')}

    @staticmethod
    def readonly_policy(target):
        return target.get('context_only') is True and target.get('missing_capability') == 'context_only_policy' and target.get('capabilities') == ['read']

    @staticmethod
    def context_snapshot(snapshot):
        return {key: snapshot.get(key) for key in ('fingerprint', 'version', 'context_fingerprint', 'projection')}

    def check_reviewed_context(self, plan, current, job):
        changed = {step['target_id'] for step in job['steps'] if step['phase'] in ('applied', 'verified', 'undone')}
        for target_id, reviewed in plan.get('reviewed_context', {}).items():
            if target_id in changed:
                continue
            target = current.get(target_id)
            if target is None or self.stable_target(target) != reviewed['target']:
                raise RepairError('analysis_context_changed')
            adapter = self.registry.adapter(target['adapter_id'])
            if adapter.version != reviewed['adapter_version'] or digest(self.context_snapshot(adapter.read(target))) != reviewed['snapshot_digest']:
                raise RepairError('analysis_context_changed')

    def binding(self, plan, op, current):
        target = plan['targets'][op['target_id']]
        adapter = self.registry.adapter(op['adapter_id'])
        if op['target_id'] not in current or self.stable_target(current[op['target_id']]) != self.stable_target(target) or current[op['target_id']]['adapter_id'] != op['adapter_id'] or adapter.version != op['adapter_version']:
            raise RepairError('target_binding_changed')
        return target, adapter

    def run_job(self, job_id):
        saved = self.load('jobs', job_id)
        if saved.get('direction') == 'inverse' and saved['status'] == 'undoing':
            return self.undo(job_id)
        with self.lock(opaque(job_id)):
            job = self.load('jobs', job_id)
            plan = self.checked_plan(job['plan_id'], job['digest'])
            if job['status'] in ('completed', 'undone', 'unknown', 'blocked'):
                return self.public_job(job)
            # Intent without receipt after process loss is uncertain. Never replay it.
            for step in job['steps']:
                if step['phase'] in ('applying', 'undoing'):
                    job.update(status='unknown', unknown_effect=step['step_id'])
                    self.event(job, 'unknown', step)
                    return self.public_job(job)
            try:
                current = self.registry.discover()
                continuing = job['barrier']
                if not job['barrier']:
                    job['status'] = 'preflight'
                    self.event(job, 'preflight')
                    for op in plan['operations']:
                        target, adapter = self.binding(plan, op, current)
                        if not adapter.preflight(target, op).get('ok'):
                            raise RepairError('stale_preflight')
                    backup_dir = self.root / 'backups' / job_id
                    backup_dir.mkdir(mode=0o700, exist_ok=True)
                    for op, step in zip(plan['operations'], job['steps']):
                        target, adapter = self.binding(plan, op, current)
                        if 'backup' not in step:
                            step['backup'] = adapter.backup(target, op, str(backup_dir))
                        step['phase'] = 'ready'
                        self.event(job, 'backed_up', step)
                    job['barrier'] = True
                    self.event(job, 'barrier_complete')
                # On continuation validate every not-yet-applied target before the
                # first remaining effect; completed writes keep their original receipt.
                for op, step in zip(plan['operations'], job['steps']):
                    if continuing and step['phase'] == 'ready':
                        target, adapter = self.binding(plan, op, current)
                        if not adapter.preflight(target, dict(op, recovery_phase='forward')).get('ok'):
                            raise RepairError('stale_preflight')
                self.check_reviewed_context(plan, current, job)
                job['status'] = 'applying'
                for index, (op, step) in enumerate(zip(plan['operations'], job['steps'])):
                    if step['phase'] == 'verified':
                        continue
                    target, adapter = self.binding(plan, op, current)
                    job['next_step'] = index
                    if step['phase'] != 'applied':
                        step['phase'] = 'applying'
                        self.event(job, 'intent', step)
                        try:
                            step['result'] = adapter.apply(target, op, step['backup'])
                        except Exception:
                            job.update(status='unknown', unknown_effect=step['step_id'], error='effect_uncertain')
                            self.event(job, 'unknown', step)
                            return self.public_job(job)
                        step['phase'] = 'applied'
                        self.event(job, 'applied', step)
                    step['receipt'] = adapter.verify(target, op, step['result'])
                    if not step['receipt'].get('ok'):
                        raise RepairError('verification_incomplete')
                    step['phase'] = 'verified'
                    self.event(job, 'verified', step)
                job.update(status='completed', next_step=len(job['steps']))
                self.event(job, 'completed')
            except Exception as error:
                job.update(status='blocked', error=error.code if isinstance(error, RepairError) else 'repair_failed')
                self.event(job, 'blocked')
            return self.public_job(job)

    def reconcile(self, job_id):
        with self.lock(opaque(job_id)):
            job = self.load('jobs', job_id)
            plan = self.checked_plan(job['plan_id'], job['digest'])
            current = self.registry.discover()
            recovering_undo = job.get('direction') == 'inverse' or job.get('error') in ('undo_conflict', 'undo_uncertain') or any(step['phase'] in ('undoing', 'undone') for step in job['steps'])
            job['direction'] = 'inverse' if recovering_undo else 'forward'
            for op, step in zip(plan['operations'], job['steps']):
                if step['phase'] not in ('applying', 'undoing'):
                    continue
                is_undo = step['phase'] == 'undoing'
                target, adapter = self.binding(plan, op, current)
                observed = adapter.reconcile(target, dict(op, recovery_phase='undo') if is_undo else op, step['backup'])
                step['reconciliation'] = observed
                if observed.get('outcome') == 'applied':
                    if is_undo:
                        step['phase'] = 'undone'
                        step['receipt'] = {'ok': True, 'state': 'undone', 'evidence': observed.get('evidence', []), 'checks': [], 'limitations': []}
                    else:
                        step['result'] = observed.get('result', {})
                        step['phase'] = 'applied'
                elif observed.get('outcome') == 'not_applied':
                    step['phase'] = 'applied' if is_undo else 'ready'
                else:
                    job.update(status='unknown', unknown_effect=step['step_id'])
                    self.event(job, 'reconciliation_unknown', step)
                    return self.public_job(job)
                self.event(job, 'reconciled', step)
            job.update(status='undoing' if recovering_undo else 'queued', unknown_effect=None)
            job.pop('error', None)
            self.event(job, 'queued')
            return self.public_job(job)

    def resume(self, job_id):
        with self.lock(opaque(job_id)):
            job = self.load('jobs', job_id)
            self.checked_plan(job['plan_id'], job['digest'])
            if job['unknown_effect'] or any(step['phase'] in ('applying', 'undoing') for step in job['steps']):
                job.update(status='unknown', unknown_effect=job['unknown_effect'] or next(step['step_id'] for step in job['steps'] if step['phase'] in ('applying', 'undoing')))
                self.event(job, 'reconcile_required')
                return self.public_job(job)
            if job['status'] == 'blocked':
                inverse = job.get('direction') == 'inverse' or job.get('error') == 'undo_conflict' or any(step['phase'] == 'undone' for step in job['steps'])
                job['status'] = 'undoing' if inverse else 'queued'
                job.pop('error', None)
                self.event(job, 'resume_queued')
            return self.public_job(job)

    def queue_undo(self, job_id):
        with self.lock(opaque(job_id)):
            job = self.load('jobs', job_id)
            if job['unknown_effect']:
                raise RepairError('reconcile_required')
            if job['status'] == 'undone':
                return self.public_job(job)
            job.update(status='undoing', direction='inverse')
            self.event(job, 'undo_queued')
            return self.public_job(job)

    def undo(self, job_id):
        with self.lock(opaque(job_id)):
            job = self.load('jobs', job_id)
            plan = self.checked_plan(job['plan_id'], job['digest'])
            if job['unknown_effect']:
                raise RepairError('reconcile_required')
            current = self.registry.discover()
            for step in job['steps']:
                if step['phase'] == 'undoing':
                    job.update(status='unknown', unknown_effect=step['step_id'], error='undo_uncertain')
                    self.event(job, 'undo_unknown', step)
                    return self.public_job(job)
            job.update(status='undoing', direction='inverse')
            for op, step in reversed(list(zip(plan['operations'], job['steps']))):
                if step['phase'] not in ('verified', 'applied'):
                    continue
                target, adapter = self.binding(plan, op, current)
                step['phase'] = 'undoing'
                self.event(job, 'undo_intent', step)
                try:
                    receipt = adapter.undo(target, op, step['backup'], step['result'])
                except Exception:
                    job.update(status='unknown', unknown_effect=step['step_id'], error='undo_uncertain')
                    self.event(job, 'undo_unknown', step)
                    return self.public_job(job)
                step['receipt'] = receipt
                if not receipt.get('ok'):
                    step['phase'] = 'applied'
                    job.update(status='blocked', error='undo_conflict')
                    self.event(job, 'undo_blocked', step)
                    return self.public_job(job)
                step['phase'] = 'undone'
                self.event(job, 'undone', step)
            job['status'] = 'undone'
            self.event(job, 'undone')
            return self.public_job(job)


def service(state):
    from repair_ai import propose_repair
    return Coordinator(state, default_registry(), propose_repair)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--state', required=True)
    parser.add_argument('--worker')
    parser.add_argument('--worker-action', choices=('run', 'undo'), default='run')
    args = parser.parse_args()
    try:
        coordinator = service(args.state)
        if args.worker:
            (coordinator.undo if args.worker_action == 'undo' else coordinator.run_job)(args.worker)
            return
        request = json.load(sys.stdin)
        action = request.get('action')
        keys = {'discover': {'action'}, 'source': {'action', 'target_id'}, 'plan': {'action', 'plan_id'}, 'propose': {'action', 'target_ids', 'intent'}, 'apply': {'action', 'plan_id', 'digest'}, 'job': {'action', 'job_id'}, 'resume': {'action', 'job_id'}, 'reconcile': {'action', 'job_id'}, 'undo': {'action', 'job_id'}}
        if action not in keys or set(request) != keys[action]:
            raise RepairError('invalid_request')
        if action == 'discover':
            result = coordinator.discover()
        elif action == 'source':
            result = coordinator.source(request['target_id'])
        elif action == 'plan':
            result = coordinator.get_plan(request['plan_id'])
        elif action == 'propose':
            result = coordinator.propose(request['target_ids'], request['intent'])
        elif action == 'job':
            result = coordinator.get_job(request['job_id'])
        elif action in ('apply', 'resume', 'undo', 'reconcile'):
            result = coordinator.approve(request['plan_id'], request['digest']) if action == 'apply' else coordinator.queue_undo(request['job_id']) if action == 'undo' else coordinator.reconcile(request['job_id']) if action == 'reconcile' else coordinator.resume(request['job_id'])
            worker_action = 'undo' if result['status'] == 'undoing' else 'run'
            child = None
            if result['status'] in ('queued', 'preflight', 'applying', 'undoing'):
                child = subprocess.Popen([sys.executable, '-B', str(Path(__file__).resolve()), '--state', str(coordinator.root.resolve()), '--worker', result['job_id'], '--worker-action', worker_action], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True, close_fds=True)
            result['worker_started'] = bool(child and child.pid)
        print(json.dumps({'status': 200, 'data': result}))
    except Exception as error:
        code = error.code if isinstance(error, RepairError) else 'repair_unavailable'
        status = 404 if code == 'record_unavailable' else 422 if code == 'ai_no_proposals' else 409
        result = {'status': status, 'code': code, 'error': 'Repair operation unavailable; inspect the recorded safe status.'}
        if code == 'ai_no_proposals':
            result['data'] = error.details
        print(json.dumps(result))


if __name__ == '__main__':
    main()
