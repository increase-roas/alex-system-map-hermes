#!/usr/bin/env python3
"""Synthetic/local workflow contract. Never dispatches work or certifies external jobs."""
import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

class ContractError(ValueError):
    pass

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))

def nonempty(value, field, placeholders=False):
    if not isinstance(value, str) or not value.strip(): raise ContractError(field + ' must be a nonempty string')
    if placeholders and any(marker in value for marker in ('REQUIRED', 'JOB_ID', 'TASK_ID')):
        raise ContractError(field + ' contains template placeholder')

def strings(value, field, required=False, placeholders=False):
    if not isinstance(value, list): raise ContractError(field + ' must be a string list')
    if required and not value: raise ContractError(field + ' must not be empty')
    for item in value: nonempty(item, field, placeholders)
    if len(value) != len(set(value)): raise ContractError(field + ' must contain unique values')

def validate_request(job_id, expected_revision, operation_id, action, payload):
    nonempty(job_id, 'job_id', True); nonempty(operation_id, 'operation_id', True)
    if type(expected_revision) is not int or expected_revision < 0: raise ContractError('expected_revision must be a nonnegative integer')
    fields = {
        'create': ({'goal','scope','constraints','owner','acceptance'}, {'account_or_local_only'}),
        'add_task': ({'id','goal','owner','acceptance','deps'}, {'next_action', 'declared_outcomes'}),
        'update': ({'task_id'}, {'checkpoint_id','status','attempt','outputs','evidence','blockers','next_action', 'declared_outcomes'}),
        'dependencies': ({'task_id','deps'}, set()),
        'correct': ({'id','task_id','reason'}, set()),
        'verify': ({'id','task_id','verifier','evidence','checks'}, {'requirement_claims'}),
        'checkpoint': ({'id','task_id','verifier','evidence','checks'}, {'requirement_claims'}),
    }
    if not isinstance(action, str) or action not in fields: raise ContractError('unknown action')
    if not isinstance(payload, dict): raise ContractError('payload must be an object')
    required, optional = fields[action]
    if not required <= payload.keys(): raise ContractError('missing required fields: ' + ','.join(sorted(required - payload.keys())))
    if payload.keys() - required - optional: raise ContractError('unknown payload fields')
    for field in ('id','task_id','checkpoint_id','verifier','goal','owner','reason','account_or_local_only','attempt'):
        if field in payload: nonempty(payload[field], field, action in ('create','add_task'))
    for field in ('scope','constraints','deps','acceptance','outputs','evidence','blockers'):
        if field in payload:
            strings(payload[field],field,required=(field == 'acceptance' or field == 'evidence' and action in ('verify','checkpoint')),placeholders=action in ('create','add_task'))
    if 'declared_outcomes' in payload:
        strings(payload['declared_outcomes'], 'declared_outcomes', required=False, placeholders=False)
    if 'next_action' in payload and payload['next_action'] is not None: nonempty(payload['next_action'],'next_action',action == 'add_task')
    if 'status' in payload and payload['status'] not in ('pending','in_progress','blocked','needs_rechecking'): raise ContractError('completion requires independent verification')
    if 'checks' in payload:
        if not isinstance(payload['checks'],dict): raise ContractError('checks must be an object')
        for key,value in payload['checks'].items():
            nonempty(key,'checks key')
            if type(value) is not bool: raise ContractError('checks values must be Boolean')

class Engine:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, revision INTEGER NOT NULL, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, job_id TEXT NOT NULL, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS checkpoints(id TEXT PRIMARY KEY, job_id TEXT NOT NULL, task_id TEXT NOT NULL, revision INTEGER NOT NULL, valid INTEGER NOT NULL, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS corrections(id TEXT PRIMARY KEY, job_id TEXT NOT NULL, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS events(sequence INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL, revision INTEGER NOT NULL, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS operations(id TEXT PRIMARY KEY, digest TEXT NOT NULL, result TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS controlled_producer_receipts(
            receipt_id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL,
            task_id TEXT NOT NULL,
            producer_operation_id TEXT NOT NULL,
            job_revision_at_production INTEGER NOT NULL,
            declared_contract_revision INTEGER NOT NULL,
            declared_contract_sha256 TEXT NOT NULL,
            relative_path TEXT NOT NULL,
            artifact_sha256 TEXT NOT NULL,
            byte_length INTEGER NOT NULL,
            production_kind TEXT NOT NULL,
            consumed_by_operation_id TEXT,
            created_at TEXT NOT NULL
        );
        ''')
    def close(self):
        self.db.close()
    def job(self, job_id):
        row = self.db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
        if not row: raise ContractError('unknown job')
        return dict(row)
    def tasks(self, job_id):
        return {r['id']: json.loads(r['payload']) for r in self.db.execute('SELECT * FROM tasks WHERE job_id=?', (job_id,))}
    def _save(self, task):
        self.db.execute('UPDATE tasks SET payload=? WHERE id=?', (canonical(task), task['id']))
    def _unique(self, identity):
        if not isinstance(identity, str) or not identity.strip(): raise ContractError('nonempty ID required')
        for table in ('jobs', 'tasks', 'checkpoints', 'corrections', 'operations'):
            if self.db.execute(f'SELECT 1 FROM {table} WHERE id=?', (identity,)).fetchone():
                raise ContractError('ID already exists')
    def _dag(self, tasks):
        visiting, visited = set(), set()
        def visit(key):
            if key in visiting: raise ContractError('dependency cycle')
            if key in visited: return
            if key not in tasks: raise ContractError('unknown dependency')
            visiting.add(key)
            for dep in tasks[key]['deps']: visit(dep)
            visiting.remove(key); visited.add(key)
        for key in tasks: visit(key)
    def lookup_operation(self, operation_id: str) -> tuple[str, dict] | None:
        row = self.db.execute('SELECT digest, result FROM operations WHERE id=?', (operation_id,)).fetchone()
        if not row:
            return None
        return row['digest'], json.loads(row['result'])

    def apply(self, job_id, expected_revision, operation_id, action, payload, actor_owner=None, *, manage_tx: bool = True):
        validate_request(job_id, expected_revision, operation_id, action, payload)
        actor = (actor_owner or '').strip()
        if not actor:
            raise ContractError('actor_owner required')
        request = dict(
            job_id=job_id,
            expected_revision=expected_revision,
            operation_id=operation_id,
            action=action,
            payload=payload,
            actor_owner=actor,
        )
        digest = hashlib.sha256(canonical(request).encode()).hexdigest()
        if manage_tx:
            self.db.execute('BEGIN IMMEDIATE')
        try:
            old = self.db.execute('SELECT * FROM operations WHERE id=?', (operation_id,)).fetchone()
            if old:
                if old['digest'] != digest:
                    raise ContractError('operation payload conflict')
                if manage_tx:
                    self.db.rollback()
                return json.loads(old['result'])
            self._unique(operation_id)
            if operation_id in (job_id, payload.get('id')): raise ContractError('operation ID must be distinct from record IDs')
            if action == 'create':
                self._unique(job_id)
                if expected_revision != 0: raise ContractError('new job expects revision 0')
                for field in ('goal', 'scope', 'constraints', 'owner', 'acceptance'):
                    if field not in payload: raise ContractError('missing job field: ' + field)
                revision = 1
                self.db.execute('INSERT INTO jobs VALUES(?,?,?)', (job_id, revision, canonical(payload)))
            else:
                job = self.job(job_id)
                if expected_revision != job['revision']: raise ContractError('revision conflict')
                revision = expected_revision + 1
                tasks = self.tasks(job_id)
                if action == 'add_task':
                    self._unique(payload['id'])
                    for field in ('goal', 'owner', 'acceptance', 'deps'):
                        if field not in payload: raise ContractError('missing task field: ' + field)
                    from bounded_acceptance import validate_task_declared_outcomes

                    ok_decl, decl_reason = validate_task_declared_outcomes(
                        payload['acceptance'], payload.get('declared_outcomes')
                    )
                    if not ok_decl:
                        raise ContractError(decl_reason)
                    task = dict(
                        payload,
                        status='pending',
                        attempts=[],
                        outputs=[],
                        evidence=[],
                        blockers=[],
                        declaration_history=[],
                        production_history=[],
                        output_history=[],
                        next_action=payload.get('next_action', 'perform task'),
                    )
                    tasks[task['id']] = task; self._dag(tasks)
                    self.db.execute('INSERT INTO tasks VALUES(?,?,?)', (task['id'], job_id, canonical(task)))
                    for row in self.db.execute('SELECT payload FROM corrections WHERE job_id=?', (job_id,)).fetchall():
                        correction = json.loads(row['payload'])
                        if correction['active'] and task['id'] in self._descendants(tasks, correction['task_id']):
                            self._invalidate(job_id, tasks, task['id'])
                            break
                elif action in ('update', 'checkpoint', 'verify', 'correct', 'dependencies'):
                    task_id = payload['task_id']
                    if task_id not in tasks: raise ContractError('unknown task')
                    task = tasks[task_id]
                    if action == 'dependencies':
                        task['deps'] = payload['deps']; self._dag(tasks)
                        # Changing prerequisites invalidates prior downstream proof.
                        self._invalidate(job_id, tasks, task_id)
                    elif action == 'correct':
                        self._unique(payload['id'])
                        if not payload.get('reason'): raise ContractError('correction reason required')
                        correction = dict(
                            payload,
                            active=True,
                            revision=revision,
                            affected_task_ids=sorted(self._descendants(tasks, task_id)),
                            superseded_next_action=task.get('next_action'),
                            preserved_attempts=list(task.get('attempts') or []),
                            preserved_outputs=list(task.get('outputs') or []),
                        )
                        self.db.execute('INSERT INTO corrections VALUES(?,?,?)', (payload['id'], job_id, canonical(correction)))
                        self._invalidate(job_id, tasks, task_id)
                    elif action == 'update':
                        if 'checkpoint_id' in payload:
                            cp = self.db.execute('SELECT * FROM checkpoints WHERE id=? AND job_id=? AND task_id=?', (payload['checkpoint_id'], job_id, task_id)).fetchone()
                            if not cp or not cp['valid'] or cp['revision'] != expected_revision:
                                raise ContractError('stale checkpoint cannot drive next step')
                        if payload.get('status', 'in_progress') not in (
                            'pending',
                            'in_progress',
                            'blocked',
                            'needs_rechecking',
                        ):
                            raise ContractError('completion requires independent verification')
                        if any(tasks[d]['status'] != 'verified' for d in task['deps']): raise ContractError('unmet dependencies')
                        has_outputs = 'outputs' in payload
                        has_decl = 'declared_outcomes' in payload
                        if has_outputs and has_decl:
                            raise ContractError('declaration_and_production_same_operation_forbidden')
                        if task['status'] == 'verified':
                            self._invalidate(job_id, tasks, task_id)
                        task['attempts'].append(dict(revision=revision, details=payload.get('attempt', 'local attempt')))
                        if has_decl:
                            from bounded_acceptance import (
                                archive_superseded_declarations,
                                contract_change_allowed,
                                declared_outcomes_index,
                                validate_task_declared_outcomes,
                            )

                            ok_decl, decl_reason = validate_task_declared_outcomes(
                                task['acceptance'], payload['declared_outcomes']
                            )
                            if not ok_decl:
                                raise ContractError(decl_reason)
                            old_index = declared_outcomes_index(task)
                            new_index = declared_outcomes_index({'declared_outcomes': payload['declared_outcomes']})
                            had_outputs = bool(task.get('outputs'))
                            ok_change, change_reason = contract_change_allowed(
                                old_index, new_index, had_outputs=had_outputs
                            )
                            if not ok_change:
                                raise ContractError(change_reason)
                            archived = archive_superseded_declarations(
                                old_index, new_index, superseded_at_job_revision=revision
                            )
                            if archived:
                                history = list(task.get('declaration_history') or [])
                                history.extend(archived)
                                task['declaration_history'] = history
                                task['outputs'] = []
                                task['evidence'] = []
                                task['status'] = 'needs_rechecking'
                                task['next_action'] = 'reproduce output under revised declaration'
                            task['declared_outcomes'] = payload['declared_outcomes']
                        if has_outputs:
                            from bounded_acceptance import seal_production_outputs, validate_output_descriptors_for_task

                            ok_out, out_reason = validate_output_descriptors_for_task(task, payload['outputs'])
                            if not ok_out:
                                raise ContractError(out_reason)
                            from bounded_acceptance import task_requires_declaration_binding

                            if task_requires_declaration_binding(task):
                                sealed, prod_records, seal_reason = seal_production_outputs(
                                    job_id,
                                    task_id,
                                    revision,
                                    operation_id,
                                    task,
                                    payload['outputs'],
                                    self.db,
                                )
                                if seal_reason:
                                    raise ContractError(seal_reason)
                                history = list(task.get('production_history') or [])
                                history.extend(prod_records)
                                task['production_history'] = history
                                out_hist = list(task.get('output_history') or [])
                                out_hist.append(
                                    {
                                        'job_revision': revision,
                                        'operation_id': operation_id,
                                        'outputs': sealed,
                                    }
                                )
                                task['output_history'] = out_hist
                                task['outputs'] = sealed
                            else:
                                task['outputs'] = payload['outputs']
                            if task['status'] == 'needs_rechecking':
                                task['status'] = 'in_progress'
                                task['next_action'] = payload.get('next_action') or 'await verification'
                            else:
                                task['status'] = payload.get('status', 'in_progress')
                        elif not has_decl:
                            task['status'] = payload.get('status', task.get('status', 'in_progress'))
                        for field in ('evidence', 'blockers', 'next_action'):
                            if field in payload and not (field == 'next_action' and has_decl and not has_outputs):
                                task[field] = payload[field]
                    else:
                        self._unique(payload['id'])
                        if any(tasks[d]['status'] != 'verified' for d in task['deps']): raise ContractError('unmet dependencies')
                        if not payload.get('verifier') or payload['verifier'] == task['owner']: raise ContractError('independent verifier required')
                        if not payload.get('evidence'): raise ContractError('verification evidence required')
                        checks = payload.get('checks', {})
                        if not task['acceptance'] or set(checks) != set(task['acceptance']) or any(v is not True for v in checks.values()):
                            raise ContractError('all acceptance checks must pass')
                        task['status'] = 'verified'; task['evidence'] = payload['evidence']; task['blockers'] = []; task['next_action'] = None
                        self.db.execute('INSERT INTO checkpoints VALUES(?,?,?,?,?,?)', (payload['id'], job_id, task_id, revision, 1, canonical(payload)))
                        # Corrections remain active until every affected task has fresh verified proof.
                        for row in self.db.execute('SELECT * FROM corrections WHERE job_id=?', (job_id,)).fetchall():
                            correction = json.loads(row['payload'])
                            affected = set(correction.get('affected_task_ids', [correction['task_id']])) | self._descendants(tasks, correction['task_id'])
                            correction['affected_task_ids'] = sorted(affected)
                            if correction['active'] and all(tasks[t]['status'] == 'verified' for t in affected):
                                correction['active'] = False
                            self.db.execute('UPDATE corrections SET payload=? WHERE id=?', (canonical(correction), row['id']))
                    self._save(task)
                else: raise ContractError('unknown action')
                self.db.execute('UPDATE jobs SET revision=? WHERE id=?', (revision, job_id))
            self.db.execute('INSERT INTO events(job_id,revision,payload) VALUES(?,?,?)', (job_id, revision, canonical(request)))
            result = dict(job_id=job_id, revision=revision, operation_id=operation_id)
            self.db.execute('INSERT INTO operations VALUES(?,?,?)', (operation_id, digest, canonical(result)))
            if manage_tx:
                self.db.commit()
            return result
        except Exception:
            if manage_tx:
                self.db.rollback()
            raise
    def _descendants(self, tasks, target):
        affected = {target}
        while True:
            expanded = affected | {key for key, t in tasks.items() if set(t['deps']) & affected}
            if expanded == affected: return affected
            affected = expanded
    def _invalidate(self, job_id, tasks, target):
        invalidated = self._descendants(tasks, target)
        for row in self.db.execute('SELECT * FROM corrections WHERE job_id=?', (job_id,)).fetchall():
            correction = json.loads(row['payload'])
            if not correction['active']: continue
            historical = set(correction.get('affected_task_ids', [correction['task_id']]))
            affected = historical | self._descendants(tasks, correction['task_id'])
            invalidated |= affected - historical
            correction['affected_task_ids'] = sorted(affected)
            self.db.execute('UPDATE corrections SET payload=? WHERE id=?', (canonical(correction), row['id']))
        for key in invalidated:
            tasks[key]['status'] = 'needs_rechecking'
            tasks[key]['next_action'] = 'recheck against correction or changed prerequisites'
            self._save(tasks[key])
            self.db.execute('UPDATE checkpoints SET valid=0 WHERE job_id=? AND task_id=?', (job_id, key))
    def recover(self, job_id):
        self.db.execute('BEGIN')
        try:
            return self._recover(job_id)
        finally:
            self.db.rollback()
    def _recover(self, job_id):
        job = self.job(job_id); tasks = self.tasks(job_id)
        row = self.db.execute('SELECT * FROM checkpoints WHERE job_id=? AND valid=1 ORDER BY revision DESC LIMIT 1', (job_id,)).fetchone()
        pending = {key: [d for d in t['deps'] if tasks[d]['status'] != 'verified'] for key, t in tasks.items() if t['status'] != 'verified'}
        ready = [dict(task_id=key, action=t['next_action']) for key, t in tasks.items() if key in pending and not pending[key] and t['status'] != 'blocked']
        return dict(contract='local-reference-v1', synthetic_only=True, job_id=job_id, current_revision=job['revision'], goal=json.loads(job['payload']), last_valid_verified_checkpoint=(dict(id=row['id'], revision=row['revision'], task_id=row['task_id'], proof=json.loads(row['payload'])) if row else None), active_corrections=[json.loads(r['payload']) for r in self.db.execute('SELECT payload FROM corrections WHERE job_id=?', (job_id,)) if json.loads(r['payload'])['active']], pending_dependencies=pending, next_permitted_action=(ready[0] if ready else None), tasks=tasks)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', required=True)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('init')
    apply = sub.add_parser('apply'); apply.add_argument('request', help='JSON request file')
    recover = sub.add_parser('recover'); recover.add_argument('job_id')
    args = parser.parse_args(); engine = Engine(args.db)
    try:
        if args.command == 'init':
            result = {'initialized': True}
        elif args.command == 'recover':
            result = engine.recover(args.job_id)
        else:
            body = json.loads(Path(args.request).read_text())
            actor = body.pop('actor_owner', None) or 'cli-actor'
            result = engine.apply(**body, actor_owner=actor)
        print(json.dumps(result, indent=2))
    finally: engine.close()
if __name__ == '__main__': main()
