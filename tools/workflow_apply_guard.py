"""Workflow apply path with mandatory handoff owner + job binding."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

from reliability_gate import validate_workflow_requirement_claims
from reliability_store import (
    advance_handoff_revision_cas,
    find_handoff_for_job,
    get_handoff,
    job_revision_in_tx,
    lookup_transfer_operation,
    prepare_connection as prepare_handoff_connection,
    record_handoff,
    record_transfer_operation,
    transfer_handoff_cas,
)
from verification_evidence import prepare_registry
from workflow_engine import ContractError, Engine


def _request_digest(
    job_id: str,
    expected_revision: int,
    operation_id: str,
    action: str,
    payload: dict,
    actor_owner: str,
) -> str:
    request = dict(
        job_id=job_id,
        expected_revision=expected_revision,
        operation_id=operation_id,
        action=action,
        payload=payload,
        actor_owner=actor_owner,
    )
    return hashlib.sha256(
        json.dumps(request, sort_keys=True, separators=(',', ':')).encode()
    ).hexdigest()


def _require_checkpoint_job(checkpoint: dict, job_id: str, handoff_operation_id: str) -> None:
    cp_job = checkpoint.get('job_id')
    if not cp_job:
        raise ContractError('handoff checkpoint missing job_id')
    if cp_job != job_id:
        raise ContractError('handoff job_id mismatch')
    if handoff_operation_id != f'{job_id}-handoff':
        raise ContractError('handoff operation must be canonical job handoff id')


def _assert_owner(conn: sqlite3.Connection, operation_id: str, actor: str) -> None:
    handoff = get_handoff(conn, operation_id)
    if not handoff:
        raise ContractError('missing handoff checkpoint')
    if handoff['owner'] != actor:
        raise ContractError('stale owner: handoff assigned to ' + handoff['owner'])


def _ensure_unified_db(engine: Engine, rel_db_path: Path, wf_db_path: Path) -> sqlite3.Connection:
    if rel_db_path.resolve() != wf_db_path.resolve():
        raise ContractError('workflow and handoff DB paths must match for atomic apply')
    prepare_handoff_connection(engine.db)
    prepare_registry(engine.db)
    return engine.db


def apply_workflow_request(
    engine: Engine,
    rel_conn: sqlite3.Connection,
    request: dict,
    *,
    wf_db_path: Path,
    rel_db_path: Path,
) -> dict:
    del rel_conn
    conn = _ensure_unified_db(engine, rel_db_path, wf_db_path)

    job_id = request['job_id']
    expected_revision = request['expected_revision']
    operation_id = request['operation_id']
    action = request['action']
    payload = dict(request['payload'])
    actor_owner = request.get('actor_owner')
    handoff_operation_id = request.get('handoff_operation_id')

    if not actor_owner or not str(actor_owner).strip():
        raise ContractError('actor_owner required')
    actor = str(actor_owner).strip()
    digest = _request_digest(job_id, expected_revision, operation_id, action, payload, actor)

    conn.execute('BEGIN IMMEDIATE')
    try:
        replay = engine.lookup_operation(operation_id)
        if replay is not None:
            if replay[0] != digest:
                raise ContractError('operation payload conflict')
            handoff = find_handoff_for_job(conn, job_id) if action != 'create' else None
            stored_rev = replay[1].get('revision')
            if (
                handoff
                and stored_rev is not None
                and handoff['revision'] < stored_rev
            ):
                advance_handoff_revision_cas(
                    conn,
                    handoff['operation_id'],
                    handoff['revision'],
                    stored_rev,
                    handoff['owner'],
                    commit=False,
                    workflow_operation_id=operation_id,
                )
            conn.commit()
            return replay[1]

        if action in ('verify', 'checkpoint'):
            validate_workflow_requirement_claims(
                payload, job_id, expected_revision, conn, operation_id=operation_id
            )

        if action == 'create':
            if payload.get('owner') and payload.get('owner') != actor:
                raise ContractError('create owner mismatch')
            payload['owner'] = actor
            result = engine.apply(
                job_id, expected_revision, operation_id, action, payload, actor_owner=actor, manage_tx=False
            )
            handoff_op = handoff_operation_id or f'{job_id}-handoff'
            record_handoff(
                conn,
                handoff_op,
                actor,
                result['revision'],
                {'job_id': job_id, 'acceptance': payload.get('acceptance', [])},
                commit=False,
            )
            conn.commit()
            result['handoff_operation_id'] = handoff_op
            return result

        handoff = get_handoff(conn, handoff_operation_id) if handoff_operation_id else find_handoff_for_job(
            conn, job_id
        )
        if not handoff:
            raise ContractError('missing handoff checkpoint for job')
        if not handoff_operation_id:
            handoff_operation_id = handoff['operation_id']
        checkpoint = json.loads(handoff['checkpoint_json'])
        _require_checkpoint_job(checkpoint, job_id, handoff_operation_id)
        _assert_owner(conn, handoff['operation_id'], actor)
        if expected_revision != handoff['revision']:
            raise ContractError('handoff revision conflict')
        if action in ('add_task', 'update') and 'owner' in payload:
            payload['owner'] = actor

        result = engine.apply(
            job_id, expected_revision, operation_id, action, payload, actor_owner=actor, manage_tx=False
        )
        advance_handoff_revision_cas(
            conn,
            handoff['operation_id'],
            expected_revision,
            result['revision'],
            actor,
            commit=False,
            workflow_operation_id=operation_id,
        )
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise


def _transfer_request_digest(request: dict) -> str:
    transfer = request['payload']
    canonical = json.dumps(
        {
            'action': 'handoff_transfer',
            'operation_id': request.get('operation_id'),
            'actor_owner': request.get('actor_owner'),
            'payload': transfer,
        },
        sort_keys=True,
        separators=(',', ':'),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def transfer_handoff_request(
    rel_conn: sqlite3.Connection,
    engine: Engine,
    request: dict,
    *,
    wf_db_path: Path,
    rel_db_path: Path,
) -> dict:
    del rel_conn
    conn = _ensure_unified_db(engine, rel_db_path, wf_db_path)
    actor_owner = request.get('actor_owner')
    if not actor_owner or not str(actor_owner).strip():
        raise ContractError('actor_owner required for handoff_transfer')
    actor = str(actor_owner).strip()
    transfer_op_id = request.get('operation_id')
    if not transfer_op_id or not str(transfer_op_id).strip():
        raise ContractError('transfer operation_id required')
    transfer_op_id = str(transfer_op_id).strip()
    transfer = request['payload']
    job_id = transfer.get('job_id')
    if not job_id:
        raise ContractError('job_id required for handoff transfer')
    handoff_operation_id = transfer.get('operation_id')
    if handoff_operation_id != f'{job_id}-handoff':
        raise ContractError('foreign handoff operation_id')
    expected_owner = transfer.get('expected_owner')
    if actor != expected_owner:
        raise ContractError('transfer actor must match expected_owner')
    job_revision = transfer.get('job_revision')
    digest = _transfer_request_digest(request)

    conn.execute('BEGIN IMMEDIATE')
    try:
        replay = lookup_transfer_operation(conn, transfer_op_id)
        if replay is not None:
            if replay[0] != digest:
                raise ContractError('transfer operation payload conflict')
            conn.commit()
            return replay[1]

        live_job_revision = job_revision_in_tx(conn, job_id)
        if live_job_revision is None:
            raise ContractError('unknown job for transfer')
        if job_revision != live_job_revision:
            raise ContractError('job_revision mismatch with workflow engine')

        existing = get_handoff(conn, handoff_operation_id)
        if not existing:
            raise ContractError('missing handoff checkpoint')
        checkpoint = json.loads(existing['checkpoint_json'])
        if checkpoint.get('job_id') != job_id:
            raise ContractError('handoff checkpoint job mismatch')
        prior_acceptance = checkpoint.get('acceptance') or []
        incoming_acceptance = transfer.get('acceptance')
        if not incoming_acceptance:
            incoming_acceptance = prior_acceptance
        row = transfer_handoff_cas(
            conn,
            handoff_operation_id,
            expected_owner,
            transfer['expected_revision'],
            transfer['new_owner'],
            job_revision,
            {
                'job_id': job_id,
                'owner': transfer['new_owner'],
                'acceptance': incoming_acceptance,
            },
            commit=False,
        )
        result = {'handoff_transferred': True, 'handoff': row, 'transfer_operation_id': transfer_op_id}
        record_transfer_operation(conn, transfer_op_id, digest, result, commit=False)
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise
