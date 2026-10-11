"""Job-scoped recovery merge: workflow corrections govern next action (not global reliability state)."""
from __future__ import annotations


def _affected_outputs_for_job(job_id: str, tasks: dict) -> list[dict]:
    affected: list[dict] = []
    for task_id, task in tasks.items():
        if task.get('status') != 'needs_rechecking':
            continue
        for raw in task.get('outputs') or []:
            affected.append(
                {
                    'job_id': job_id,
                    'task_id': task_id,
                    'output': raw,
                    'reason': task.get('next_action'),
                }
            )
    return affected


def _correction_history_entries(tasks: dict, corrections: list[dict]) -> list[dict]:
    entries: list[dict] = []
    for corr in corrections:
        tid = corr.get('task_id')
        task = tasks.get(tid) if tid else None
        entries.append(
            {
                'correction_id': corr.get('id'),
                'task_id': tid,
                'reason': corr.get('reason'),
                'superseded_next_action': corr.get('superseded_next_action'),
                'revision': corr.get('revision'),
                'attempts_preserved': len(task.get('attempts') or []) if task else 0,
            }
        )
    return entries


def _task_actionable(task_id: str, tasks: dict, pending: dict) -> tuple[bool, list[str]]:
    task = tasks.get(task_id) or {}
    if task.get('status') == 'blocked':
        return False, ['blocked']
    unmet = list(pending.get(task_id) or [])
    if unmet:
        return False, unmet
    if task.get('status') not in ('pending', 'in_progress', 'needs_rechecking'):
        return False, [f"status:{task.get('status')}"]
    return True, []


def merge_job_recover_packet(engine_packet: dict, presented_note: str | None = None) -> dict:
    job_id = engine_packet['job_id']
    merged = dict(engine_packet)
    tasks = merged.get('tasks') or {}
    pending = merged.get('pending_dependencies') or {}
    engine_next = engine_packet.get('next_permitted_action')
    active = [c for c in (merged.get('active_corrections') or []) if c.get('active')]
    affected = _affected_outputs_for_job(job_id, tasks)
    merged['affected_outputs_needing_recheck'] = affected
    blocked_corrected_tasks: list[dict] = []
    for corr in active:
        tid = corr.get('task_id')
        if not tid:
            continue
        task = tasks.get(tid) or {}
        governing_action = task.get('next_action') or corr.get('reason') or ''
        corr_actionable, blockers = _task_actionable(tid, tasks, pending)
        if not corr_actionable and blockers:
            blocked_corrected_tasks.append(
                {
                    'task_id': tid,
                    'correction_id': corr.get('id'),
                    'reason': corr.get('reason'),
                    'action': governing_action,
                    'blockers': blockers,
                    'source': 'workflow_correction',
                }
            )
    merged['blocked_corrected_tasks'] = blocked_corrected_tasks

    stale_note = (presented_note or '').strip()
    if not stale_note and engine_next:
        stale_note = str(engine_next.get('action') or '').strip()

    recovery: dict = {
        'job_id': job_id,
        'governing_applied': False,
        'presented_note': stale_note or None,
        'superseded_notes': [],
        'affected_outputs_needing_recheck': affected,
        'history_retained': True,
        'active_workflow_corrections': active,
        'correction_history': _correction_history_entries(tasks, merged.get('active_corrections') or []),
    }

    if active:
        primary = sorted(active, key=lambda c: int(c.get('revision') or 0), reverse=True)[0]
        governed_task_id = primary.get('task_id')
        governed_task = tasks.get(governed_task_id) or {}
        governing_action = governed_task.get('next_action') or primary.get('reason') or ''
        superseded = (primary.get('superseded_next_action') or stale_note or '').strip()

        if superseded and governing_action and superseded != governing_action:
            recovery['governing_applied'] = True
            recovery['superseded_notes'] = [
                {'note': superseded, 'superseded_by_correction': primary.get('id'), 'job_id': job_id}
            ]
            merged['governing_next_action'] = governing_action
            merged['superseded_next_permitted_action'] = {
                'task_id': governed_task_id,
                'action': superseded,
                'source': 'pre_correction_stale',
                'actionable': False,
            }
            corr_actionable, blockers = _task_actionable(governed_task_id, tasks, pending)
            merged['correction_governed_task'] = {
                'task_id': governed_task_id,
                'action': governing_action,
                'actionable': corr_actionable,
                'blockers': blockers,
                'source': 'workflow_correction',
            }
            if corr_actionable:
                merged['next_permitted_action'] = {
                    'task_id': governed_task_id,
                    'action': governing_action,
                    'source': 'workflow_correction',
                    'actionable': True,
                }
            elif engine_next:
                en_task = engine_next.get('task_id')
                en_ok, _ = _task_actionable(en_task, tasks, pending) if en_task else (False, [])
                if en_task and en_ok:
                    merged['next_permitted_action'] = {
                        **engine_next,
                        'source': 'workflow_engine',
                        'actionable': True,
                    }
                else:
                    merged['next_permitted_action'] = None
            else:
                merged['next_permitted_action'] = None
        elif governing_action:
            ok, _ = _task_actionable(governed_task_id, tasks, pending)
            if ok:
                merged['next_permitted_action'] = {
                    'task_id': governed_task_id,
                    'action': governing_action,
                    'source': 'workflow_engine',
                    'actionable': True,
                }
    elif engine_next:
        en_task = engine_next.get('task_id')
        ok, _ = _task_actionable(en_task, tasks, pending) if en_task else (True, [])
        merged['next_permitted_action'] = {
            **engine_next,
            'source': engine_next.get('source') or 'workflow_engine',
            'actionable': ok,
        }

    merged['reliability_recovery'] = recovery
    return merged
