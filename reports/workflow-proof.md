# Workflow foundation proof

Scope: local workflow reference only; synthetic demo, no services or UI. Account: local only. No external operations or real job certification.

Evidence:

- [E1] `tools/workflow_engine.py`: SQLite reference engine and CLI.
- [E2] `tools/workflow_tests.py`: eleven meaningful behavior tests including CLI subprocess smoke test.
- [E3] `reports/workflow-tests.txt`: fresh command output, 11 tests passed, exit 0.
- [E4] `reports/workflow-acceptance.txt`: eight check_acceptance.py items VERIFIED, exit 0.
- [E5] `examples/workflow-recovery-synthetic.json`: named synthetic lamp correction packet after database reopen.
- [E6] `workflows/investigate.json`, `workflows/build.json`, `workflows/repair.json`: guided templates.
- [E7] `docs/WORKFLOW_CONTRACT.md`, `schemas/workflow-request.schema.json`, `examples/workflow-create-request.json`: contract, request envelope and CLI example.

Implemented revision checks, operation replay/conflict handling, globally distinct IDs, DAG checks, transactional rollback, verifier/evidence/acceptance requirements, dependency guards, correction propagation, historical preservation, stale-checkpoint rejection and a compact read-consistent recovery packet. [E1] Coverage and command result: [E2] [E3]. Added the three guided JSON templates and named synthetic demo. [E5] [E6] Documented the local-only proof and trust boundaries. [E7]

Negative checks reject a cycle, stale revision/checkpoint, conflicting operation replay, missing evidence, owner-as-verifier, failed acceptance, unknown dependencies, duplicate IDs and direct completion through update. [E2] [E3]

Machine-checkable acceptance items (paths are relative to package root):

```text
file:tools/workflow_engine.py non-empty
file:docs/WORKFLOW_CONTRACT.md non-empty
json:workflows/investigate.json
json:workflows/build.json
json:workflows/repair.json
json:schemas/workflow-request.schema.json
contains:examples/workflow-recovery-synthetic.json::"last_valid_verified_checkpoint": null
cmd:python3 tools/workflow_tests.py
```

Limit: the engine checks distinct verifier identity and nonempty evidence references, but cannot authenticate the reviewer or establish reference truth. Trusted callers must perform actual evidence checks before passing verification. No live dispatch, Cursor UI integration or SDK receipt replacement is proven or included. [E1] [E7]

Final refinement: typed request validation rejects malformed/placeholder/internal-field injection requests without database mutation; corrections persist their original affected task set even after dependency edits. Regression and malformed-input tests passed. [E1] [E2] [E3]
