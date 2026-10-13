# Independent alex-reviewer: Langflow nodes

NODE: langflow-nodes (task identifier inferred from packet; no formal node ID supplied)   WORKER: claude-opus-5-5 (Anthropic)   REVIEWER: Codex (OpenAI, other family)   TRACE: not supplied

VERDICT: FAIL

## Scope and standard

Reviewed `reviews/2026-10-13-langflow-nodes-review-packet.md` against its seven acceptance rows and the linked audit, using the alex-reviewer frozen-acceptance standard. No reliance on previous chat or memory for verdict. HEAD inspected: `d92827b55ada76dc92a46ae4119d5429c05f5459`, branch `langflow-dashboard`, base `3572d39`.

Read-only review, apart from this required review artifact. No application/source/configuration changes, flow saves/imports/runs, push, deployment, or messages. Existing dirty Python bytecode and untracked `.codex/` were present before review and left alone. Runtime evidence differs from the packet: installed lfx metadata, disk catalog, local HTTP and tailnet HTTPS all now identify lfx 1.12.5, langflow 1.12.5. Index SHA256: `18a74ad8e33b19f91da9e8277fb1376496b226484933d99f0e4ed116d244bb6f`.

PASS below means the specified evidence was independently opened and corroborated where read-only checks permit. It does not mean the reviewer reran write-producing suites. No claim of exhaustive security assurance.

## Frozen acceptance, one verdict per row

- **1 Catalog: “Route returns the 63 current components and the audited tier counts”**: PASS. `step1-catalog.txt`; `app/src/lib/langflow/catalog.ts`; independent catalog probe: 63 current, 22 local, 41 nonlocal, 18 currently enabled, 0 unknown. GET `http://127.0.0.1:3200/api/langflow/components` and `https://alexs-macbook-pro.tailde26a1.ts.net/api/langflow/components` both returned HTTP 200, 63 components, the same current engine/index identity.
- **2 Palette: “Searchable, keyboard reachable; each of the 63 added and accepted by lfx validate”**: UNVERIFIED for full validator acceptance. `step2-palette.txt`, `engine-1125.txt`, `app/src/app/explorer/langflow-panel.tsx:99`, `app/src/lib/langflow/tests/components-live.test.mts:60`. Palette search/keyboard code and recorded browser exercise are present; independent in-memory add accepted 63/63. But the validator test never checks process exit status, permits level-4 errors, and skips registry validation on every file. The receipts prove narrower structural/edge checks, not the frozen unqualified acceptance. Repeating the save/validate suite is UNCHECKABLE within this read-only skill because it writes flow files.
- **3 Edit kinds: “addNode, deleteNode, connect (type checked, Langflow handles), disconnect; refused edits save nothing”**: PASS on opened evidence plus independent in-memory checks. `step3-edits.txt`, `app/src/lib/langflow/tests/edits.test.mts`, `app/src/lib/langflow/handles.ts`, `app/src/app/api/langflow/flows/[flowId]/route.ts`. Add, connect, disconnect, deleting connected nodes and type-mismatch rejection behaved correctly in memory; rejected batches return before saveFlow in the route. Existing route receipt covers no-write-on-refusal and handle fixture equality. Persistence tests were not rerun.
- **4 Canvas wiring: “Owner can wire; tailnet gets 403 on every new edit kind”**: PASS on opened browser/API receipts and code. `step4-canvas.txt`, `step3-edits.txt`, `fix-everything.txt`, `app/src/app/explorer/langflow-panel.tsx:682`, `app/src/lib/langflow/policy.ts`, `app/src/app/api/langflow/flows/[flowId]/route.ts`. Owner callbacks and canSave gates are present; route authorization precedes parsing or storage for all edit kinds. Independent pure-policy probe strips write grants from a synthetic tailnet identity even with localhost Host. Middleware and policy diffs from base are empty. Tailnet GET was independently repeated; actual PATCH refusal is recorded evidence, not repeated by this read-only reviewer.
- **5 Setting editors: “Multiline, slider, tab, dict, table; secrets never stored; untouched round trip unchanged”**: FAIL. `step5-settings.txt`, `app/src/lib/langflow/model.ts:59`, `app/src/lib/langflow/model.ts:470`, `app/src/lib/langflow/tests/settings.test.mts:78`. Secret-shaped container values bypass edit, import, export and canvas screening (F1). Unchanged serialization with no edits is preserved; however the packet's stronger claim that every editable setting can be re-saved unchanged is false for two defaults (F2). Supported editor kinds are present.
- **6 Run scope: “One live engine test per enabled local component; failures stay off and are listed”**: PASS on recorded engine evidence. `live-components.txt`, `review-fixes.txt`, `engine-1125.txt`, `app/src/lib/langflow/tests/live-components.test.mts`, `app/src/lib/langflow/tiers.ts`. Opened per-component output for all 18 enabled components and reasons/refusals for the four disabled local components. The 1.12.5 receipt records an initial 15/18 result followed by optional-package installation and 18/18 output. Independent in-memory gate evaluation allows exactly 18 catalog entries, blocks the other 45, rejects changed code and the component-as-note disguise. No live engine was launched by the reviewer; post-switch production-dependency parity was not independently established.
- **7 Docs and checks: “Doc updated; tsc, build, unit and route tests, live tests, desktop and phone browser checks”**: FAIL for completed acceptance/sign-off. `final-checks.txt`, `fix-everything.txt`, `engine-1125.txt`, `docs/LANGFLOW_DASHBOARD.md`, both supplied JPGs, `.claude/commands/verify.md`. Independent `./node_modules/.bin/tsc --noEmit --incremental false` exited 0. Build and unit/live receipts were read; screenshot evidence shows finished 14 and 42 results. But the gate receipt explicitly says NOT-READY with four acceptance scripts failing, and later cleanup does not provide passing or baseline results. Current documentation also says the new-build tailnet check remains undone and engine remains rc3, despite later receipt/live evidence. Physical-device testing is not added as a requirement: the packet explicitly drops it and labels the 375 px check as emulation.

## Findings

### F1, high: secrets survive when the sensitive key contains an array or object

Location: `app/src/lib/langflow/model.ts:59` (visitSecretValues), especially lines 69-74; edit check at 472; import/export at 930/947. Export route `app/src/app/api/langflow/flows/[flowId]/export/route.ts` returns the redacted flow directly.

Using the real CSVAgent dictionary setting `pandas_kwargs`, these synthetic values are accepted and retained:

```json
{"token":["FAKE_REVIEW_VALUE"]}
{"token":{"value":"FAKE_REVIEW_VALUE"}}
{"headers":[{"key":"Authorization","value":["FAKE_REVIEW_VALUE"]}]}
```

Independent result for each: editAccepted=true, importRemoved=0, retainedOnImport=true, retainedOnExport=true, retainedOnCanvas=true. The control `{"token":"FAKE_REVIEW_VALUE"}` is correctly rejected and stripped. The same array bypass was reproduced against the committed component-index fixture, not only the now-changed installed engine. `screenDeep(toCanvas(...))` also leaves the synthetic opaque value intact.

Cause: a sensitive property is handled only when its immediate value is a string; recursive descent loses the sensitive-parent context. This is not the packet's disclosed limitation about secrets hidden under innocent names. A normal editable JSON field can save these values, and readers/exports can receive them. No real credential was used or disclosed, and no actual flow was saved.

Required fix/proof: propagate sensitive context through arrays/objects (and key/value table forms) or reject nonempty sensitive subtrees wholesale. Cover model edits, import-to-disk, export and authorized read responses with synthetic canaries and benign-control round trips.

### F2, medium: “every editable setting” round-trip proof only covers a subset

Locations: `app/src/lib/langflow/tests/settings.test.mts:78` hardcodes 12 component types; `model.ts:490` refuses null and `model.ts:493` refuses empty numeric text.

Independent sweep across all 63 installed templates: 254 editable defaults re-save without changing bytes, 2 are refused:

- RunFlow.flow_name_selected: no value in template, canvas null, rejected with “Flow Name needs a value.”
- EmbeddingModel.request_timeout: optional float with value empty string, rejected with “Request Timeout takes a number.”

The underlying flow is not corrupted by either refusal. This is a setting-edit/default-handling and coverage gap, not a claim that no-edit saves rewrite data. Both components are show/edit-only by scope, so their editor behavior still matters.

Required fix/proof: preserve optional empty defaults and missing-vs-empty semantics, or honestly make these fields noneditable when they need native-server support. Sweep all 63 templates, not the 12-template subset, and prove accepted unchanged values remain byte-identical plus optional numeric values can be cleared.

### F3, medium: test grading is weaker than the frozen template-validation acceptance

Locations: `app/src/lib/langflow/tests/components-live.test.mts:60-80`, receipts `step2-palette.txt` and `engine-1125.txt`.

The helper ignores child exit status and accepts required-input errors. Registry checking is skipped for all 63 templates. These may be reasonable limitations for empty templates, but they are not equivalent to “accepted by lfx validate.” The gap was disclosed; it was not closed. This is missing proof, not proof that the templates are broken.

Required proof: actual command outcomes with stage-level results and enough populated fixtures for claimed full validation, or an explicitly approved amendment limiting acceptance to structural/edge validation with separately demonstrated registry identity. The reviewer does not amend frozen acceptance.

### F4, medium: final gate remains red; cleanup is not a passing rerun

`final-checks.txt` records failures in maintained_edit_cas, recovery_emitted_screening, canonical_edit_sync and recovery_screening_real_paths. It explicitly says no base comparison was run. `fix-everything.txt` removes leftover artifacts, but supplies no passing run or equivalent baseline evidence. These could be unrelated selection/sandbox failures; that is not established. Do not classify them as regressions or harmless without evidence.

Required proof: passing receipts, or same-environment base/current comparison with an authoritative documented gate-scope determination. Refresh docs/packet to match current engine and completed tailnet evidence.

## Independent read-only checks executed

- Installed catalog read: 63 current, tiers correct, 18 executable, 0 unknown.
- In-memory add of all 63: accepted 63.
- In-memory sweep of editable defaults: 254 unchanged successes, 2 refusals as above.
- Connect/disconnect/delete and incompatible Embeddings-to-ChatOutput refusal: expected results.
- Code-hash and disguised-note negative probes: blocked.
- Run tiers for all 63: 18 allowed, 45 blocked.
- Tailnet pure-policy check: save/run/stop 403 despite config write grants and localhost Host.
- Local and same-Mac Tailscale Serve catalog GET: 200, same 63 entries and current 1.12.5 identity.
- TypeScript, no emit and no incremental cache: exit 0.
- Both supplied screenshots opened: desktop layout shown, narrow screenshot shows completed result 42 and earlier result 14. Screenshots alone do not prove keyboard, gestures or absence of all layout overflow.

Build, route persistence, live-engine suites, browser mutation checks and acceptance-script reruns are UNCHECKABLE as fresh executions under this skill's no-write rule. Their supplied receipts were inspected instead. Only this review artifact was written. No Director state was touched.

## MISSING, actionable proof for the controller

MISSING: Passing regression evidence that secret-valued arrays/objects/table values cannot be saved or leaked by import, read or export, with fake canaries only.
MISSING: Complete 63-template editable-default coverage resolving the two refusals, or accurately scoped noneditable handling.
MISSING: Full validator acceptance evidence, or explicit approval of the narrower structural/edge acceptance with the registry limitation retained.
MISSING: Resolution of all four red acceptance gates through passing evidence or controlled baseline/scope evidence, not just cleanup.
MISSING: Updated review packet and docs reflecting installed lfx 1.12.5 and the later tailnet check.

No build-complete or Director-verified claim is authorized by this review.
