# Bounded reliability addendum — revision 2

Admission: ACCEPTED as a project-local refinement of the existing authorized visualizer build; implementation and verification remain PENDING. Received through coordinating chat 01a12417-5fd0-7606-b0d5-dc99d5aa601e. This message is not authority for any broader action.

Sole application owner: existing Cursor chat `4f32e74a-58e3-4abb-ba6f-fb151ba80cd7`. No competing implementation. Reuse existing components, project skills and test procedures. All changes for this addendum must be reversible local source/test changes under this foundation project. No outside-project changes, new timers, credential or permission changes, deployment, live service/customer mutations, or real credential retrieval. Stop the affected step at any outside-project dependency or authority blocker, report it precisely, and continue only independent in-project work.

## Exact accepted checklist

1. Automatic context loading, tested in a fresh session.
2. Requirements-to-evidence checks distinguishing documented, installed, and actually used.
3. Saved corrections recalled after restart and applied against older conflicting notes.
4. Single-owner handoffs with checkpoints and safe deduplication tests.
5. Regression cases for missing requirements, skipped skills, stale data, and false completion.
6. Secret-safe diagnostic outputs tested with fake canary secrets only.

## Checkable acceptance

| ID | Required proof |
| --- | --- |
| REL-01 | Fresh isolated session/process loads the current project context and revision through the intended entrypoint. Record the loaded revision, selected required skills and next permitted action. A manually preloaded session or a skill file merely existing is insufficient; if actual agent-runtime loading cannot be tested within scope, label that part UNVERIFIED. |
| REL-02 | Every requirement links to dated evidence and distinct documented/installed/actually-used claims. Missing or mismatched evidence prevents verified completion. UI shows owner, last verified time, evidence and next unresolved step. |
| REL-03 | Persist a correction, restart, provide an older conflicting note, and demonstrate the newer correction governs the recovered next step. Retain old notes/history and mark affected outputs for recheck. |
| REL-04 | One owner at a time; checkpointed handoff includes revision and acceptance. Repeat the same operation ID and assert exactly one effect; stale owner/revision attempts are rejected and recoverable. |
| REL-05 | Negative regression cases intentionally omit a requirement or required skill, supply stale source data, and claim completion without proof. Each must fail the appropriate acceptance gate and expose the next unresolved step. |
| REL-06 | Use fake canary secrets only to exercise supported diagnostic/error/trace/export paths. Assert canary values do not appear in emitted outputs. Do not inspect real credentials to test redaction. |

The existing owner must also prove tracing AND synchronization usage in one isolated local end-to-end test: use synthetic source data, perform a local change, observe refresh, record its actual local test trace/receipt, restart, and verify state/cursor persistence and no duplicated effects. Label dataset and evidence explicitly SYNTHETIC/TEST. A real operation on synthetic data is a local test, not real-source system coverage. This proof does not replace the original real-source tracing acceptance and authorizes no external access. Existing in-project real receipts may be used under the original build scope; if required proof needs an outside dependency, report that blocker without expanding this addendum.

## Execution and status

Admission has no blocker. Owner acknowledgment/execution remains pending while the existing Cursor run is active. The supervising heartbeat already reads BUILD_SUPERVISION.md; it should deliver this revision once at the next safe continuation if the owner has not read it. Do not interrupt progressing work or send duplicate instructions. Save requirement-specific evidence and independent verification before claiming any REL item complete. Original application, sync and tracing requirements stay open until their original acceptance passes.
