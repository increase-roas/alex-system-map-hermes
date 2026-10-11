# Workflow contract v1

This is a local, stdlib Python and SQLite reference for a future Cursor React Flow implementation. It demonstrates persistence and recovery using synthetic records. It does not dispatch agents, contact customers, access accounts, install services, or replace SDK receipts. Passing its demo certifies no real job.

The professional implementation standard used here is transactional consistency with optimistic concurrency: each write supplies the revision it read, and SQLite serializes the transaction with `BEGIN IMMEDIATE`. A recovery read uses one SQLite read transaction. A transaction either stores the state, event and operation result together or stores none of them.

## Guided workflows

`workflows/investigate.json`, `build.json` and `repair.json` provide sequential DAG templates with required inputs and explanatory prompts. Replace `REQUIRED`, `JOB_ID` and `TASK_ID` markers before instantiating them. They are editable recipes, not runnable dispatch definitions. The UI should block submission of placeholders. Tasks inherit job scope and constraints; accounts and permission gates remain the caller's responsibility.

## Records and writes

- `jobs`: unique ID, monotonic revision, goal, scope, constraints, owner and acceptance.
- `tasks`: unique ID, job, goal, owner, dependency IDs, acceptance, status, attempts, outputs, evidence, blockers and next action.
- `checkpoints`: unique ID, job/task, verified revision, validity flag and verifier proof.
- `corrections`: unique ID, job, target task, reason, revision and active flag.
- `events`: ordered append-only mutation requests with job and revision.
- `operations`: global unique operation ID, canonical request hash and original response.

Before a write, the runtime rejects unknown payload fields, malformed types, empty identities/goals/owners, duplicate list entries, empty acceptance, template placeholders and non-Boolean check values. Revisions must be nonnegative integers; Python Boolean values are explicitly rejected. Scope and constraints are string lists. Verification evidence must be a nonempty string list.

All record IDs and operation IDs are distinct in the local database. Replaying exactly the same operation returns its original response even after later revisions. Reusing an operation ID with any changed request field rejects the write. The same ID must be retained after an unknown outcome; query/replay before sending a new operation.

Create expects revision zero; all other mutations expect the current job revision. IDs are caller-provided opaque strings. Dependencies must refer to tasks already in the same job. Adding a cycle or unknown dependency fails atomically. Use `dependencies` to revise a task's prerequisites; this invalidates its and its descendants' existing proof.

## Completion, corrections and recovery

Corrections persist `affected_task_ids` from creation and union newly affected descendants. Removing dependency edges cannot erase the original rechecking obligation; every originally affected task must receive fresh verified proof before the correction closes.

`verify` and `checkpoint` are equivalent verified-completion operations. They require a named verifier different from the owner, nonempty evidence references, and a checks map containing exactly every acceptance item with Boolean `true`. Every prerequisite must already be verified. `update` cannot set verified status and cannot advance a task with unmet prerequisites. There is no job-level completion claim or live dispatch operation.

The engine enforces identity separation and presence of proof, not authentication or evidence truth. A trusted integration must authenticate owners/reviewers, run the acceptance expressions and validate references before issuing verification. This engine never executes supplied acceptance commands. The SQLite database is a local reference, not a tamper-proof audit store.

A correction marks its target and every transitive descendant `needs_rechecking`, invalidates their checkpoints, and preserves attempts, outputs and event history. The correction persists its original affected task IDs and unions newly affected descendants; removing dependency edges cannot erase that obligation. The correction remains active until all affected tasks receive fresh verified proof. Reopening a verified task also invalidates affected proof. Updating from a checkpoint requires its job/task to match, its validity flag to be true, and its revision to equal the caller's current expected revision. Even an otherwise valid older checkpoint cannot drive a next step after an unrelated revision.

The compact recovery packet includes current revision, goal/scope/constraints, last valid verified checkpoint, active corrections, pending dependencies, task states and the first permitted next action. A valid historical checkpoint is context only; use current revision for the next mutation. Blocked tasks never receive a permitted action. The packet can return null when no action is permitted; that is not a claim of completed work.

## CLI and proof

Run from the package root:

```sh
python3 tools/workflow_engine.py --db /tmp/workflow-reference.sqlite init
python3 tools/workflow_engine.py --db /tmp/workflow-reference.sqlite apply examples/workflow-create-request.json
python3 tools/workflow_engine.py --db /tmp/workflow-reference.sqlite recover cli-synthetic-job
python3 tools/workflow_tests.py
python3 tools/workflow_demo.py
```

`apply` takes a JSON object with `job_id`, `expected_revision`, `operation_id`, `action` and action-specific `payload`. Request structure is documented in `schemas/workflow-request.schema.json`; engine tests enforce the behavioral invariants. Supported actions: `create`, `add_task`, `update`, `dependencies`, `correct`, `checkpoint`, `verify`.

The synthetic lamp demo closes and reopens its database after a correction. Its recovery packet intentionally has no valid verified checkpoint, preserves the first inspection attempt, blocks the dependent report, and permits rechecking the inspection. Tests cover process-style restart, revision conflicts, replay and conflicting replay, independent verification, missing evidence, failed acceptance, cycles, atomic rollback, correction propagation, ID reuse, reopening and stale checkpoint rejection. SQLite files for the demo/tests are temporary and deleted afterward.
