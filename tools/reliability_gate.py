"""Application completion gate — used by local_service verified-completion mutations."""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path

from project_context_loader import parse_skills_from_docs
from verification_evidence import (
    PERFORMED_WORK_ACTUALLY_USED,
    catalog_fingerprints,
    resolve_proof_evidence,
)

ROOT = Path(__file__).resolve().parents[1]
ISO8601 = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}')
FABRICATED_EVIDENCE_PREFIXES = ('explorer-manual-verify:', 'local-explorer-evidence')

REL_IDS = ('REL-01', 'REL-02', 'REL-03', 'REL-04', 'REL-05', 'REL-06')
REL_REQUIRED_USE = {
    'REL-01': 'project_context_loader',
    'REL-02': 'reliability_gate_per_requirement',
    'REL-03': 'recover_decision_with_correction',
    'REL-04': 'handoff_owner_and_operation_dedup',
    'REL-05': 'reliability_gate_negative_cases',
    'REL-06': 'multi_surface_canary_screening',
}


def _valid_timestamp(value: str) -> bool:
    if not value or not ISO8601.match(value):
        return False
    try:
        datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return False
    return True


def _proof_ok(
    evidence: dict,
    claim: dict,
    conn: sqlite3.Connection | None = None,
    *,
    workflow_scope: dict | None = None,
    for_workflow_verify: bool = False,
) -> tuple[bool, str]:
    return resolve_proof_evidence(
        evidence,
        claim,
        conn,
        workflow_scope=workflow_scope,
        for_workflow_verify=for_workflow_verify,
    )


def required_skills_installed() -> tuple[bool, list[str]]:
    missing = []
    for rel in parse_skills_from_docs():
        if not (ROOT / rel).is_file():
            missing.append(rel)
    return not missing, missing


def evaluate_requirement_completion(
    requirement_id: str,
    claim: dict,
    conn: sqlite3.Connection | None = None,
) -> dict:
    req = requirement_id.upper()
    if req not in REL_IDS:
        return {
            'accepted': False,
            'reason': 'unknown_requirement',
            'next_unresolved_step': f'Unknown requirement {req}',
        }
    if not claim.get('complete'):
        return {
            'accepted': False,
            'reason': 'complete_not_claimed',
            'next_unresolved_step': claim.get('next_unresolved_step') or 'Provide completion claim with evidence',
        }
    req_set = claim.get('requirement_set')
    if not req_set:
        return {
            'accepted': False,
            'reason': 'requirement_set_required',
            'next_unresolved_step': 'Include full requirement_set listing all REL requirements',
        }
    missing = [r for r in REL_IDS if r not in req_set]
    if missing:
        return {
            'accepted': False,
            'reason': 'requirement_omitted_from_set',
            'next_unresolved_step': 'Include all REL requirements before claiming completion: '
            + ', '.join(missing),
        }
    if claim.get('job_id') is None or claim.get('job_revision') is None:
        return {
            'accepted': False,
            'reason': 'claim_job_scope_required',
            'next_unresolved_step': 'Bind completion to job_id and job_revision',
        }
    evidence = claim.get('evidence') or {}
    evidence['requirement_id'] = req
    if req == 'REL-02' and not evidence.get('skills_verified'):
        return {
            'accepted': False,
            'reason': 'skills_not_verified_in_claim',
            'next_unresolved_step': 'Record skills_verified true after checking canonical skill paths',
        }
    verified_at = evidence.get('verified_at')
    if not _valid_timestamp(str(verified_at or '')):
        return {
            'accepted': False,
            'reason': 'invalid_or_missing_verified_at',
            'next_unresolved_step': 'evidence.verified_at must be ISO8601 dated timestamp',
        }
    if not evidence.get('proof_sha256'):
        return {
            'accepted': False,
            'reason': 'proof_sha256_required',
            'next_unresolved_step': 'Bind proof_path with matching proof_sha256',
        }
    expected_use = REL_REQUIRED_USE[req]
    claim_used = evidence.get('actually_used')
    if claim_used != expected_use and not (
        req == 'REL-02' and claim_used == PERFORMED_WORK_ACTUALLY_USED
    ):
        return {
            'accepted': False,
            'reason': 'actually_used_mismatch',
            'next_unresolved_step': f'Requirement {req} must record actually_used={expected_use!r}',
        }
    live_rel = catalog_fingerprints().get('data/relationships.json')
    if not evidence.get('relationships_sha256') or evidence.get('relationships_sha256') != live_rel:
        return {
            'accepted': False,
            'reason': 'stale_relationships_hash',
            'next_unresolved_step': 'Refresh relationships_sha256 from live catalog',
        }
    ok, proof_reason = _proof_ok(evidence, claim, conn)
    if not ok:
        return {
            'accepted': False,
            'reason': proof_reason,
            'next_unresolved_step': 'Provide existing proof_path and matching proof_sha256 when set',
        }
    doc_path = evidence.get('documented_path')
    if doc_path and not (ROOT / doc_path).is_file():
        return {
            'accepted': False,
            'reason': 'documented_path_missing',
            'next_unresolved_step': f'Documented path not found: {doc_path}',
        }
    if req == 'REL-02':
        if not doc_path:
            return {
                'accepted': False,
                'reason': 'missing_documented_path',
                'next_unresolved_step': 'REL-02 requires documented_path in evidence',
            }
        skills_ok, missing = required_skills_installed()
        if not skills_ok:
            return {
                'accepted': False,
                'reason': 'required_skill_missing',
                'next_unresolved_step': 'Install missing skills: ' + ', '.join(missing),
            }
    if req == 'REL-05':
        return {
            'accepted': False,
            'reason': 'negative_cases_only',
            'next_unresolved_step': 'REL-05 must not pass a positive completion claim',
        }
    if req == 'REL-01' and evidence.get('agent_runtime') != 'UNVERIFIED':
        return {
            'accepted': False,
            'reason': 'agent_runtime_not_labeled',
            'next_unresolved_step': 'REL-01 must label Cursor agent runtime UNVERIFIED when not proven',
        }
    if req == 'REL-03' and not evidence.get('governing_applied'):
        return {
            'accepted': False,
            'reason': 'correction_not_applied',
            'next_unresolved_step': 'REL-03 requires governing_applied true with recheck queue',
        }
    if req == 'REL-04' and evidence.get('event_count_for_operation') != 1:
        return {
            'accepted': False,
            'reason': 'operation_effects_not_exactly_one',
            'next_unresolved_step': 'REL-04 requires exactly one effect for operation id',
        }
    if req == 'REL-06' and not evidence.get('surfaces_exercised_via_local_service'):
        return {
            'accepted': False,
            'reason': 'canary_surfaces_not_proven',
            'next_unresolved_step': 'REL-06 requires surfaces_exercised_via_local_service evidence',
        }
    return {'accepted': True, 'reason': 'ok', 'next_unresolved_step': ''}


def evaluate_negative_case(case: str, claim: dict) -> dict:
    if case == 'missing_requirement':
        req_set = claim.get('requirement_set') or []
        missing = [r for r in REL_IDS if r not in req_set]
        rejected = len(missing) > 0 or not claim.get('complete')
        if claim.get('complete') and not missing:
            gate = evaluate_requirement_completion(claim.get('requirement_id', 'REL-02'), claim)
            rejected = not gate['accepted']
            reason = gate.get('reason')
            step = gate.get('next_unresolved_step', '')
        else:
            reason = 'requirement_omitted_from_set'
            step = 'Include all REL requirements before claiming completion'
        return {
            'case': case,
            'rejected_by_gate': rejected,
            'reason': reason,
            'next_unresolved_step': step,
        }
    if case == 'skipped_skill':
        skills_ok, missing = required_skills_installed()
        claim_complete = claim.get('complete', False)
        rejected = claim_complete and (not skills_ok or not claim.get('evidence', {}).get('skills_verified'))
        if not rejected and claim_complete:
            gate = evaluate_requirement_completion(claim.get('requirement_id', 'REL-02'), claim)
            rejected = not gate['accepted']
            reason = gate.get('reason')
            step = gate.get('next_unresolved_step', '')
        else:
            reason = 'required_skill_missing' if missing else 'skills_not_verified_in_claim'
            step = 'Record skills_verified after checking canonical skill paths'
        return {
            'case': case,
            'rejected_by_gate': rejected,
            'reason': reason,
            'next_unresolved_step': step,
            'missing_skills': missing,
        }
    if case == 'stale_data_simulation':
        stale = claim.get('evidence', {}).get('relationships_sha256', '')
        gate = evaluate_requirement_completion(claim.get('requirement_id', 'REL-02'), claim)
        rejected = not gate['accepted'] and gate.get('reason') == 'stale_relationships_hash'
        if not rejected:
            actual = hashlib.sha256((ROOT / 'data/relationships.json').read_bytes()).hexdigest()
            rejected = stale != actual
        return {
            'case': case,
            'rejected_by_gate': rejected,
            'reason': gate.get('reason', 'stale_relationships_hash'),
            'next_unresolved_step': gate.get('next_unresolved_step', ''),
        }
    result = evaluate_requirement_completion(claim.get('requirement_id', 'REL-02'), claim)
    return {
        'case': case,
        'rejected_by_gate': not result['accepted'],
        'reason': result.get('reason'),
        'next_unresolved_step': result.get('next_unresolved_step', ''),
    }


def validate_workflow_requirement_claims(
    payload: dict,
    job_id: str,
    job_revision: int,
    conn: sqlite3.Connection | None = None,
    *,
    operation_id: str | None = None,
) -> None:
    from workflow_engine import ContractError

    claims = payload.get('requirement_claims')
    if not isinstance(claims, list) or not claims:
        raise ContractError('requirement_claims required for verify/checkpoint')
    workflow_scope = {
        'task_id': payload.get('task_id'),
        'operation_id': operation_id,
        'verifier': payload.get('verifier'),
    }
    allowed_proof_paths: set[str] = set()
    for claim in claims:
        if not isinstance(claim, dict):
            raise ContractError('requirement_claims entries must be objects')
        claim = dict(claim)
        claim['complete'] = True
        claim.setdefault('owner', payload.get('verifier') or 'workflow-verifier')
        claim['job_id'] = job_id
        claim['job_revision'] = job_revision
        evidence = claim.get('evidence') or {}
        ok, reason = _proof_ok(
            evidence,
            claim,
            conn,
            workflow_scope=workflow_scope,
            for_workflow_verify=True,
        )
        if not ok:
            raise ContractError(reason or 'requirement gate rejected claim')
        gate = evaluate_requirement_completion(str(claim.get('requirement_id', '')), claim, conn)
        if not gate.get('accepted'):
            raise ContractError(gate.get('reason') or 'requirement gate rejected claim')
        proof_path = (claim.get('evidence') or {}).get('proof_path')
        if proof_path:
            allowed_proof_paths.add(str(proof_path).replace('\\', '/').lstrip('/'))
    evidence = payload.get('evidence') or []
    if not isinstance(evidence, list) or not evidence:
        raise ContractError('verification evidence must list bound proof_path values')
    for item in evidence:
        if not isinstance(item, str):
            raise ContractError('evidence entries must be proof path strings')
        if any(item.startswith(prefix) for prefix in FABRICATED_EVIDENCE_PREFIXES):
            raise ContractError('fabricated client evidence strings are not permitted')
        normalized = item.replace('\\', '/').lstrip('/')
        if normalized not in allowed_proof_paths:
            raise ContractError('evidence must reference proof_path from requirement_claims')
