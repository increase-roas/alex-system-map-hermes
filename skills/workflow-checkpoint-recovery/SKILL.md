---
name: workflow-checkpoint-recovery
description: Create guided local tracking runs, recover interrupted jobs, record corrections, and verify checkpoints through this project's SQLite workflow reference engine. Use for durable job continuity and rechecking affected results; not agent dispatch, production execution, or generic chat memory.
---

# Workflow checkpoint recovery

Operate from the foundation package root. Resolve this canonical skill's real path when reached through a native discovery link. Read [the authoritative workflow contract](../../docs/WORKFLOW_CONTRACT.md) and [agent protocol](../../docs/AGENT_PROTOCOL.md#fresh-agent-entry). Use existing `tools/workflow_engine.py`, `schemas/workflow-request.schema.json`, and the guided `workflows/investigate.json`, `build.json`, or `repair.json` template. Do not create another ledger or replace existing SDK receipts.

Recover before acting: read the current job revision, valid checkpoints, active corrections, dependencies, attempts, blockers and next permitted action. Replace template markers with approved real values before instantiation. An old checkpoint is context, not authority to write at an old revision. Create expects revision zero; all other mutations use the current job revision. Stable caller-provided IDs and a unique operation ID identify each intended mutation.

Apply only contract-supported actions. Retain the same operation ID after an uncertain outcome and query/replay to reconcile; a changed request with that ID is rejected. A stale revision requires a fresh read and reconsideration, never an overwrite. Corrections invalidate target and descendant proof while preserving attempts/history; resume at the permitted recheck.

Verification requires a verifier distinct from the owner, evidence references and true results for every acceptance item. The reference engine checks presence and identity separation; the integration must authenticate identities, run checks and validate evidence truth. Never fabricate passing checks or make a job-level completion claim from an empty recovery action.

For local engine acceptance run `python3 tools/workflow_tests.py` and `python3 tools/workflow_demo.py`. These use synthetic data and prove reference behavior only. For real authorized tracking changes, read back current state and operation receipts before reporting them as changed. Include exact gaps/blockers and the next permitted action. Tracking permission grants no dispatch, external account action, spend, deployment or customer message.
