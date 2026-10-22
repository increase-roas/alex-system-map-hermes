# Review and repair across Alex's agent setup

This is the implementation map for the universal Review & fix panel. The approved product direction is in `STRATEGY.md`; the requirements are in `docs/plans/2026-10-21-universal-review-repair-plan.md`. Actual production repairs require Alex's exact-bundle approval in the panel. Building and testing this feature does not approve a repair of his real sources.

## Entry point and ownership

The normal dashboard is `http://127.0.0.1:3201/explorer?view=local-files`, served from `~/Projects/alex-system-map/app`. A feature worktree or test port is separate evidence until its changes reach that checkout.

`local-files-panel.tsx` retains the actual-file browser and mounts `repair-targets-panel.tsx`. General Review & fix selects the registered source owner. The older instruction-only editor remains available explicitly, with its existing contract in `APPROVED_RULE_REPAIR.md`.

`/api/repairs` serves inventory, safe source projections and frozen proposals. Approval sends only a plan ID and its digest. `/api/repairs/jobs/[jobId]` reads and resumes the recorded job, reconciles uncertain effects, or queues conditional Undo. Every read and action uses the existing loopback and local-token boundary. Source contents remain data, never instructions to the service or its model.

The TypeScript bridge starts `tools/universal_repairs.py`. That process uses `repair_registry.py` and the JSON-only adapter protocol in `repair_contracts.py`. `app/src/lib/types/repairs.ts` is the corresponding public wire format. Adapters own discovery, safe read, proposal preparation, whole-bundle expansion, preflight, backup, apply, verify, read-only reconciliation and conditional inverse.

## Native source owners

| Area | Implementation and registered scope | What the proof means |
| --- | --- | --- |
| Rules | `repair_local_adapters.py`; canonical shared/platform instruction sources; existing `local_file_distribution.py` and native instruction builder | All candidates are projected together. Dependent outputs are frozen once. A repository receives one exact-path commit after its changes, with normal Git hooks. |
| Skills | Canonical local shared skills, their resource/link context and lifecycle tools | Source and link checks are distinct from a runtime discovering or selecting the skill. Provider-managed caches retain their owner. |
| Owned plugins | `repair_plugin_adapters.py`; registered Git marketplace sources, skill assets, hook scripts and both native manifests | The frozen bundle includes required version changes, one Git publication and native Codex/Claude refresh. Discovery and preparation inspect persisted registries and cache bytes without invoking native plugin commands. Installed CLI tests use temporary homes; desktop activation remains separate. |
| Hooks | Registered Codex/Cursor hook JSON, Claude settings hooks and owned related scripts | Canonical nonsecret command fields are untrusted source data. Credentials stay excluded. Syntax checks never fire a real hook during proposal testing. |
| Claude/Cursor settings and CLI configuration | Registered documented JSON paths and nonsecret keys | Key patches preserve unknown and secret siblings. A file readback does not prove an already running app reloaded it. |
| Owned executable sources | Registered canonical guard/unify/skill scripts, including receipt and handoff sources | Python AST/compile, shell syntax, Node syntax and Go parsing run on temporary candidates. These parsers do not prove the candidate's complete runtime behavior. |
| Codex settings | `repair_native_adapters.py`; installed app-server `config/read` and `config/batchWrite` | Explicit file, user-layer version, native parser, effective readback and versioned inverse. No whole-file TOML replacement. Model and other static defaults apply to future sessions; current desktop thread reload is not inferred. |
| Remote files | `repair_remote_runner.py` and `repair_remote_adapters.py`; registered mini SSH alias and fixed Orgo hosts/roots | Reviewed JSON-stdin runner, target identity, native parsing, hash/mode preconditions, atomic replacement, readback and conditional inverse. No model-generated shell is dispatched. |
| Paperclip | Existing mini-local SSH/REST route; token acquired and used on the mini | Installed validator hash, exact agent/company, native revision capture/rollback where applicable, and field readback. |
| Neon | Existing named custom Composio connection; registered projects/branches | Published native request contracts, account/object/version binding, fixed field updates and fresh native object readback. |
| Hindsight | Existing bank-config admin helper/REST exception; shared memory remains its separate Composio route | Bank/config identity, allowed field updates and conditional inverse. Credentials remain in process memory. |
| SigNoz | Existing named viewer/editor custom Composio accounts; alerts and dashboards | Native object/version/schema-version evidence and fixed native update contracts. A secret-bearing object is never serialized into a full-replacement payload. |

Discovery uses up to four independent worker processes within a 40-second aggregate deadline. A timed-out worker and its child processes are terminated; healthy owners remain visible beside an unavailable coverage row. Provider discovery lists identities without fetching every full object; selected configurations are read afresh when proposed. Hindsight credential acquisition is reused only within the current exchange process, in memory.

The registry is deliberately explicit. An arbitrary file, unregistered host or provider object does not become writable because a model names it. The panel exposes the missing capability instead of claiming universal access. The local file inventory is broader than the registered repair inventory, and both display their coverage limits.

## Proposal and testing

`repair_ai.py` uses the existing subscribed, isolated Codex route in `local_file_ai.py`. The model has no tool authority. It receives bounded safe projections with numbered exact source lines, categories and registered patch paths. It returns exact text edits, complete text candidates or typed JSON patches and exact source citations. Text edits must match uniquely, cannot overlap, and preserve unchanged bytes and line endings; adapters receive the assembled candidate. Python sources use AST-aware credential screening so ordinary token-handling code is retained as data while actual credential literals remain withheld.

Strict native output schemas require every declared patch property. Internally a null means leave a field unchanged; normalization removes those nulls before any adapter sees a patch. Null is never written as a placeholder. Existing nullable nested data is a separate typed value.

The service validates IDs, paths, types and citations, then generates fix and preserve scenarios. Before/candidate simulations receive every changed source together and receive no answer key. A fix case must change from the wrong established choice to the expected choice; preserve cases must keep their expected choice. A separately labeled clarification case requires at least two distinct exact baseline citations to conflicting directives: a valid baseline answer must be ambiguous and the candidate must establish the expected answer. Provider or parser failures never count as ambiguity. Unknown answers still fail ordinary fix and preserve cases. Native parser/lifecycle checks remain separate. Simulation is not live execution or a claim that a hook fired. A failed model review reports its safe stage and reason and never creates an approvable empty bundle.

Each review accepts at most 16 editable targets and four read-only context sources within 256 KiB, with no silent truncation. Local rule, skill, hook and executable reviews automatically include registered canonical shared instructions and the gates reference as read-only context. Context changes invalidate the tested bundle even when the model does not edit that source. Larger selections remain selected and display the batch limit before starting a model call.

Skill references and owned plugin sources receive that same local policy context across source owners. The exact registered gates reference supplies only its canonical named section, blank-padding omitted lines to preserve citations; the fingerprint still binds the entire file. An identically named section in another file receives no special treatment. Each AI call owns an isolated process group, which is stopped and reaped on completion or timeout.

Whole secret-bearing files are not sent to the model or backed up into proposal state. JSON inverse data contains only changed nonsecret fields. Typed leaf patches preserve excluded siblings. The generic file viewer's broad command masking is unchanged; hook owners use a credential-aware projection that retains canonical executable field names as data. The registered receipt-store hook additionally has a fixed, isolated executable before/candidate profile and canonical regression suite, described in `docs/HOOK_REPAIR_PREVIEW.md`. These results are distinct from simulation and live harness activation.

## Official guidance and the explanation preview

Before proposing changes, the server retrieves applicable official sources through the existing named Composio route and a fixed source catalog. Search requests use public product/category identities, never private source contents, repair intent, local paths, account IDs, credentials or client data. Retrieved web text is untrusted evidence. The proposal and documentary assessment models have no tool authority.

The preview puts each original proposed source's diagnosis, recommended fix, applicability, practice kind and rejected alternative before the affected-target list. Native contracts, vendor recommendations, Alex policy and inference retain distinct labels. Direct links come from the captured catalog, with short exact quotes. Full captured passages remain private; the browser receives bounded excerpts and rationale quotes of at most 24 words. Baseline local-file citations establish the diagnosed source behavior separately from documentary citations.

Source provenance includes retrieval time, content hash, publication date when known, document version when known, and the retrieval service's crawl status. A fresh retrieval is not necessarily a live crawl. Unknown versions and missing installed-version matches stay unknown. A captured official page does not establish complete field coverage: Paperclip's exact configuration specification covers only part of the allowed fields. Applicability and coverage limitations remain visible.

Evidence advances through separate stages: documentary assessment checks whether the exact candidate follows the captured guidance; behavior simulation tests modeled choices; native checks test only their stated syntax or owner acceptance scope; source/copy readback, effective settings, runtime activation and publication each require their own receipts. Passing documentation or simulation does not prove a hook executed, an app reloaded or a real destination accepted a change. Unsupported or unavailable guidance/assessment is visible without an approval action.

The private guidance packet, exact source IDs/passages, rationale, independent assessment and limitations bind into the existing immutable plan digest. The plan cannot outlive the guidance window. The public server-derived `proposal_target_ids` identifies original proposed sources so generated copies and publication targets do not require invented rationales. Unresearched legacy plans require a fresh review. These preview changes preserve the single existing approval, which still sends only `action`, `plan_id` and `digest`.

## Approval, effects and recovery

Private state lives under `app/.data/universal-repairs`. Plans bind exact operations, target identities, adapter versions, source/native versions, projections, checks and expiry. Public previews omit private candidates and recovery data except for the exact safe diff. Editing an intent or rereading changed source invalidates the preview.

One approval creates a deterministic job whose ID equals the plan ID. The panel stores that ID before sending the short keepalive request. Reopening performs a read of that original job. Repeating the same approval resolves the same job instead of minting another effect. Definitive pre-job expiry, failed-check and `guidance_required`, `guidance_stale` or `guidance_invalid` rejections clear pending lookup and the saved ID, and explain that a fresh review is needed. Existing approved-job replay is resolved before guidance expiry checks. Definitive pre-job rejection permits a new proposal; a lost response remains a recovery lookup.

Before the first effect, all steps pass preflight and all required preimages are captured and read back. Real local file preimages use the existing Drive-backed `~/Backups/universal-repairs` location; a local Drive-folder readback is not proof that cloud upload finished. Native settings use changed-key inverse data rather than full secret-bearing configuration copies.

Each effect has a durable intent before execution and a recorded result afterward. An interrupted or uncertain write stops later steps. Reconciliation reads the native target and compares candidate/preimage state. It never blindly repeats a write. Once the result is known, the same forward or inverse worker resumes automatically. Known pre-effect Undo conflicts are blocked, not mislabeled as uncertain writes.

Undo runs in reverse order. It restores only fields/files that still match the applied state, preserving later unrelated JSON fields. Changed repaired fields are left untouched. Dynamic projection metadata can legitimately change after an approved hook repair; it is distinct from fixed owner/path/account/adapter identity.

Owned-plugin Undo restores the previous canonical source and refreshes installed copies from it. It does not recreate a pre-existing stale-copy inconsistency. This limitation is included in the frozen preview. Native plugin listing can itself materialize a new source version, so even native discovery commands are restricted to the approved refresh phase.

This is an ordered, recoverable sequence, not a distributed atomic transaction. Codex uses native expected-version writes. Remote files are anchored and compared immediately before atomic replacement, leaving a small comparison-to-replacement race. Provider locks serialize this adapter's jobs on this machine, but vendors without conditional writes cannot exclude a simultaneous change from their own UI or another machine. Native read-before-write and readback do not create a transaction the vendor does not provide; the preview and receipts disclose that limit.

## Evidence and current limits

The panel distinguishes written, byte-verified, effective, reloaded, pending, blocked and unknown. A successful write does not prove all destinations accepted it. Missing runtime reload/discovery, remote publication or provider proof stays visible beside the target.

Custom Composio metadata and CLI dry-run lookups currently return 404 for some working custom tools. Actual named-account reads succeeded. Accordingly adapters bind reviewed published contract hashes and available native service/object versions; they do not claim a fresh deployed tool-input-schema fingerprint. Paperclip additionally uses its installed native validator. Other providers label local published-contract validation as syntax, and explicitly disclose the lack of a mutation-free native acceptance endpoint. A changed native contract may reject a write; the recorded job must then reconcile its real outcome. Metadata failure alone is not used to declare a working route unavailable.

The test suite exercises disposable files, repositories, native Codex and Claude homes, SSH/Orgo protocol processes, provider state and a Paperclip HTTP/validator fixture. Installed CLI tests are skipped only when their required binary is absent; local receipts record the native tests. Real systems are used for read-only discovery and proposal evidence during development. No fixture success is production mutation proof.

Run the deduplicated Python suite with `python3 -B tools/run_repair_tests.py`, the two component harnesses with `node --test tools/test_local_file_repair_source.cjs tools/test_universal_repair_source.cjs`, and app TypeScript checks. `.github/workflows/repair-checks.yml` runs those checks and focused lint on PRs. Browser screenshots and final receipts belong in `reviews/receipts/20261021-universal-review-repair/`.
