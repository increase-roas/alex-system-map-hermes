# One-approval AI instruction repairs

Authorized by Alex in chat 2026-10-21. Implement the existing Review & fix flow, using the researched design in work/2026-10-21_local-rule-autofix/research.md. Development uses disposable source/home/Git fixtures only; do not apply a real agent-rule proposal in acceptance. Native engine, shared task worktree, disjoint owners; no new provider, dependency, schedule, hook or app settings change.

## Contract

AI proposal still uses current source citations, isolated subscribed Codex and frozen Apply. Add source applicability/ownership metadata so aliases/generated copies and scoped conditions are not treated as independent blanket authority. Coverage remains bounded and disclosed.

Before freezing an AI preview, plan 2-4 citation-backed multiple-choice behavioral scenarios in a separate tool-free model call, including an intended fix and preserved behavior. Run the before and candidate instructions in separate isolated calls with the same scenarios/options but without expected answers. Compare their choices deterministically with expected choices. A passed check means these simulated decisions passed, not proof of arbitrary consistency or live tool execution. Report baseline choices, after choices, expected choices and evidence. Malformed/unavailable/failed checks have no approvable AI preview. No silent retries or paid fallback. Current proposal validation still applies. Existing manual draft previews remain possible and visibly untested by AI.

Use at most four subscribed model calls per suggest (proposal, scenario planning, before run, candidate run), bounded to existing provider invocation isolation. Increase only the existing server's total suggestion time budget to fit those calls. An interrupted request never writes a source.

Supply the native instruction byte budget to the proposer and reject an oversized UTF-8 candidate before behavioral calls. Prefer concise references to canonical policy over repeated wording. The unchanged native candidate renderer remains authoritative. A baseline already over its limit must still permit a valid shrinking repair; neither config nor the platform limit is relaxed.

### Shared response fields

LocalRepairChecks: {status:'passed'|'failed'|'unavailable',checked_at:string,model:string,cases:LocalRepairCase[],limitations:string[]}.
LocalRepairCase: {id:string,scenario:string,purpose:'fix'|'preserve',choices:{A:string,B:string,C:string},expected:'A'|'B'|'C',before:'A'|'B'|'C'|'unknown',after:'A'|'B'|'C'|'unknown',status:'passed'|'failed'|'unknown',rationale:string,evidence:LocalCitation[]}.
Context files may add applicability:{role:string,scope:string,activation:string,limitations:string[]}.
Suggestion adds checks:LocalRepairChecks|null. Failed checks return status needs_decision (or an explained nonapprovable result), proposed_content:null, preview:null.

RepairService.preview gains keyword checks=None, in addition to existing context_fingerprints. For AI previews bind checks into the private proposal fingerprint and public preview. Do not accept checks or copy plans from browser requests.

LocalRepairPreview adds checks?:LocalRepairChecks|null and distribution?:LocalRepairDistributionPlan.
LocalRepairDistributionPlan: {status:'ready'|'not_needed'|'blocked',targets:{path:string,before_sha256:string|null,after_sha256:string,diff:string,kind:'generated'|'import',requires_new_session:boolean}[],limitations:string[]}.
LocalRepairResult adds source_verified?:boolean and distribution?:{status:'verified'|'pending'|'not_needed',targets:{path:string,status:'verified'|'pending',sha256:string|null,reason:string}[],message:string}.
Existing state and pushed remain about source publication. generated_follow_up is true only while affected local generated copies remain pending; its previous permanent-pending behavior is superseded. Full repair verified requires source pushed and distribution verified/not_needed. File verification is not proof an already-running agent reloaded instructions.

### Distribution semantics

Reuse the live native instruction builder's pure build(rules_only=True), snapshots, lock/stage/fsync primitives. Resolve only fixed server-owned source and output locations under the service home. Do not call broad apply, touch Codex config, copy credentials, install roles or start remote publication work. The fixed native generated_bundle/install_generated artifacts also include roles and omit some Claude/Cursor outputs; do not use that broad artifact set for this repair.

Freeze exact current bytes/modes and native after projections for only this source's dependent generated/import outputs. Bind all native source/builder/config inputs needed for those projections. Include copy diffs before approval. No source change during preview. Unsupported ownership or app-owned settings dependencies must be explicit, never claimed synchronized. Exclude unrelated generated outputs. Import wrappers need verification even if their bytes do not change.

One approved Apply: revalidate frozen source/context/generator inputs and destination baseline; back up all affected actual before bytes/modes in existing Drive location before source or copy writes; update exact source, install the frozen native dependent outputs without clobbering newer work, verify readbacks, commit/push the source through existing scoped Git path, and return per-destination status. Local generation is independent of remote notes sync; keep existing repository hooks enabled. If the hook already produced an exact expected output, reconcile it. Do not silently apply a new generated plan after approval. A post-source failure remains applied with truthful pending status and retained recovery. Retried Apply reconciles, not repeats uncertain writes.

Undo preflights the source and all affected outputs against recorded applied state before changing anything. Restore exact saved preimages and verify; refuse to overwrite newer source/copy edits. Handle created outputs with backed recovery, not unbacked deletion. Preserve unrelated staged/dirty files and app config. A later unrelated canonical input change must not be overwritten.

UI shows cases and results, all current context/scope limits, affected-copy diffs, one approval button, and per-source/copy/push outcomes afterward. Manual changes invalidate AI checks. Pending publication or destination state never displays Repair verified. Existing source-read cancellation fix stays intact. No extra approval dialog after the frozen approval.

## Ownership and acceptance

- AI owner: tools/local_file_ai.py, tools/test_local_file_ai.py, new tools/local_file_checks.py and/or tools/local_file_scope.py with tests. No repair writer/TS edits.
- Distribution owner: tools/local_file_repairs.py, tools/test_local_file_repairs.py and new tools/local_file_distribution.py with tests. No AI/TS edits.
- Frontend owner: app/src/lib/types/local-files.ts, app/src/lib/server/local-file-ai.ts, app/src/lib/server/local-file-repairs.ts, app/src/app/explorer/local-file-repair-panel.tsx, tools/test_local_file_repair_source.cjs or new corresponding focused component test. No Python backend edits.
- Primary: docs/spec reconciliation, integration, real subscribed fixture and browser journey, independent review and shipping. Do not modify actual rules for tests.

Behavioral verification: failing tests first, focused unit evidence per owner, one relevant combined Python suite after integration, one final TypeScript check and component suite, actual desktop/narrow browser journey against disposable sources, actual subscribed AI oracle including checks, temporary Git source/copy Apply/Undo with exact remote readback, stale/copy interference and partial-failure recovery. Independent reviewer checks final code/evidence and scope before completion. Preserve all existing source/context/token/path/secret/publication boundaries. Tests prove outcomes, not internal call counts alone.
