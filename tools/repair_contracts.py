"""Versioned JSON-only adapter boundary. Selectors never originate in the browser.

Private snapshots/backups may contain inverse data and must never be serialized publicly.
prepare_bundle receives all candidates once, enabling union projections and one publication
operation per repository. Every method is synchronous; durable workers own execution.
"""
from typing import Any, Protocol

Json = dict[str, Any]
SCHEMA_VERSION = 1


class RepairError(Exception):
    """Only code is public; provider exception text remains private."""
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class RepairAdapter(Protocol):
    adapter_id: str
    version: str

    def discover(self) -> list[Json]: ...
    def read(self, target: Json) -> Json: ...
    def prepare(self, target: Json, snapshot: Json, proposal: Json) -> Json: ...
    def prepare_bundle(self, operations: list[Json], targets: dict[str, Json]) -> list[Json]: ...
    def preflight(self, target: Json, operation: Json) -> Json: ...
    def backup(self, target: Json, operation: Json, backup_dir: str) -> Json: ...
    def apply(self, target: Json, operation: Json, backup: Json) -> Json: ...
    def verify(self, target: Json, operation: Json, result: Json) -> Json: ...
    def reconcile(self, target: Json, operation: Json, backup: Json) -> Json: ...
    def undo(self, target: Json, operation: Json, backup: Json, applied: Json) -> Json: ...

# Target: id, adapter_id, category, owner, scope, identity, capabilities,
# observed_at, evidence, limitations; optional missing_capability.
# Snapshot: fingerprint, version, projection (safe model/public data), context_fingerprint.
# prepare -> operation: action, selector, candidate/patch, expected_fingerprint,
# expected_version, context_fingerprint, checks, inverse, public_diff.
# Coordinator adds step_id, target_id, adapter_id, adapter_version, target_identity.
# prepare_bundle -> full ordered operation list; may append registered distribution/
# publication targets; must preserve source operations and bind every appended target.
# preflight -> {ok: bool, ...safe evidence}; backup -> private JSON recovery descriptor.
# apply -> private JSON receipt (must be idempotent/CAS); verify -> public receipt:
# {ok: bool, state: written|byte_verified|effective|reloaded|pending|blocked|unknown,
# fingerprint?, evidence: list[str], checks: list[Check], limitations: list[str]}.
# reconcile -> {outcome: applied|not_applied|unknown, result?: private apply receipt,
# evidence: list[str]}; never writes. undo -> same public receipt, with state undone
# or blocked; adapter MUST compare current changed fields with recorded applied state.
# Check: kind, status passed|failed|unavailable, runner_id, input_digest,
# output_digest, evidence, checked_at, limitations.
