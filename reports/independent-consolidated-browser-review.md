# Independent consolidated browser review

Read-only review of BROWSER01-08 and APP-REVIEW05. Owner PASS is not independent acceptance. No browser rerun, shared DB/source writes, outside-project reads, install or paid call.

| Item | Result | Accepted evidence / remaining gap |
| --- | --- | --- |
| BROWSER-01 | FAILED | Accepted: Visible REL01 evidence is nonempty in directly inspected screenshot. Runner now reads REL02 text and computed font, stronger than count alone. Gap: No visible assertion or expected actual proof fields/result identity. >40 characters and opening brace can pass unrelated JSON. Screenshot shows REL01, not requested REL02 evidence. Failed/hidden evidence is not exercised. |
| BROWSER-02 | VERIFIED | Accepted: Exact observed eight-layer order: You/direction -> Agents -> SDK -> Access/credentials -> Infrastructure -> Models -> Apps -> Files/evidence. Current source positions by explicit order and distinguishes layer_navigation/membership edges. Gap: Runner itself permits >=6 nodes and near-equal y; weak future regression guard. Current screenshot and source independently establish requested order. |
| BROWSER-03 | VERIFIED | Accepted: Selected Local catalog read test trace visible with span graph, timestamp/status/agent/tool/source content. Consumer source accepts top-level and screened wrapper response shapes. Gap: This accepts bounded displayed trace selection/shape only. Graph labels have visual contrast/clipping defect (BROWSER07); real-source trace unavailable. This is not same-run synthetic sync trace selection. |
| BROWSER-04 | FAILED | Accepted: Workflow guided-start screen visible; current UI source now displays governing_next_action. Gap: Runner only counts Recover packet text and waits for Start guided job. It never clicks start/mutation/correction/recover, restarts app or compares displayed permitted action to backend correction. Screenshot contains no selected job/recover packet. Actual intended UI recovery path missing. |
| BROWSER-05 | FAILED | Accepted: Saved Composio detail screenshot displays purpose, evidence ID and proof labels reached through search. Gap: Search remains conditional, is omitted from required[] and asserts no matching stable detail ID. Subsystem check only react-flow presence; no group expansion, collapse, accessible list, impact traversal or sync refresh interaction. |
| BROWSER-06 | FAILED | Accepted: Receipt reports2351components/59relationships and complete; screenshot text agrees. pageerror listener now exists and is required. Gap: required[] still omits catalog_complete/stats_show_complete/dark_theme_toggled/search_navigation; count checks are nonempty and relationships>=59. Theme flag records click only. No requestfailed/failed-response/console-error collection. No exact count reconciliation gate. |
| BROWSER-07 | FAILED | Accepted: All11PNG widths are1400; old2171px width corrected. Visible reliability JSON is materially larger; current source text-sm/wrapping/contained-scroll configured. Gap: Runner tests page width only before switching views and permits font>=13, below14-16requirement. Reliability screenshot still presents a tall uncontained REL01 JSON whereas current source max-h-48 is192px; render-source identity unresolved. Trace graph has black-on-black unreadable/clipped oversized node labels in directly inspected screenshot. |
| BROWSER-08 | UNVERIFIED | Accepted: Runner explicitly starts Next with -H127.0.0.1 and passes project profile directory to launchPersistentContext; source configuration defects fixed. Gap: No listener readback saved. SKIP_SERVER_START may reuse another listener while report always prints configured command; package/runner identity does not bind served build or listener/profile process. Runtime isolation proof remains missing. |
| APP-REVIEW-05 | FAILED | Accepted: Saved current marker SHA400b2bd493f1579ac22ce794c8d235a003c5c053787feef6a163af7a13c25e73 matches readonly catalog_watch. One receipt/trace/span persisted; payload SHA d8e2d420e5fc08f186946e866e38dbad30f46c522de3abac90554fc0892ced49 matches current receipt and trace_imports; source cursor stores same receipt ID. Bounded manual CLI observe/import/dedup/current persistence accepted. Gap: Source still manually invokes sync-observe twice, then starts fresh sync-status reader. No observer lifecycle, app restart, automatic UI refresh or browser cursor invariants. Captured status_before_restart unused; no cursor-before/after equivalence assertion. Restart_subprocess_ok omitted from synth_ok. Span hardcodes ok and lacks actual start/end, agent/source/evidence identity. Browser picks unrelated catalog-read test trace rather than same-run synthetic mutation receipt. |
| SOURCE-IDENTITY | FAILED | Accepted: Five recorded source hashes and all11screenshots match current bytes. Package.json SHA matches browser receipt. Source/receipt hashes stable across review. Gap: Consolidated next_build_id a9b54bf2c9bee2c2 equals package.json hash prefix, not actual app/.next/BUILD_ID i_SCUW1zzhsjO0FfO1A9q. Browser receipt binds only runner/package, not executed app sources or actual build. App build-source match cannot be accepted. |

## Machine identity checks

| Path | Result | SHA256 / identity |
| --- | --- | --- |
| tools/workflow_apply_guard.py | VERIFIED | ad2b89f3d6b556ad809be4e8e4db46cb25158e11de6ba0251179c26b4796af79 |
| tools/reliability_gate.py | VERIFIED | ff3d29faf6f10738011bfb85cb4c743fd7346e4ba6cdda770e22b4b15e25fd49 |
| tools/trace_store.py | VERIFIED | 3a36705f2eccd67906d80033907c83201dd7a633046d871a4bb4868eadfe0189 |
| app/src/lib/graph/build-graph.ts | VERIFIED | 25e1412fb401182f6bc9307503319b8eb82c3947aa8dca013286a90ccdcc0491 |
| tools/browser_acceptance.mjs | VERIFIED | 1e1dd9c2379daca9a15003243fea43cd36a3546080e060bbf35c306d035a439b |
| reports/browser-proof/01-explorer-overview-light.png | VERIFIED | e363993fdd962822aef3b8092a248c93da2bce56d9dc253199fc554f0450ca0e |
| reports/browser-proof/02-explorer-overview-dark.png | VERIFIED | 668abdd492d2e2deac69e677d6157cbe94e72a8232a45b053d8e3e33bee98d5e |
| reports/browser-proof/view-subsystem.png | VERIFIED | 55ce51d8b23d77ad3c3040cf84da5b36266f969561398374bbc84ce64aaa3479 |
| reports/browser-proof/view-files.png | VERIFIED | 81beb7e76404602ff03c56685f79529a884bd3504a8db7a45b754898f576c5f2 |
| reports/browser-proof/view-problems.png | VERIFIED | 39dfa497f90aa3412cd4ae5ed8889b8c3e1120b504d70b6427397ed92a913fb4 |
| reports/browser-proof/view-workflows.png | VERIFIED | 705018a40fff55482f485469e27ca12a25ae2ef5074874bfa2e31564f508a5d2 |
| reports/browser-proof/view-tracing.png | VERIFIED | f9f4c0be2b4db3a3eafff4d4693ac7fe0107aa883c288cbb142361876dff9ee5 |
| reports/browser-proof/view-reliability.png | VERIFIED | acde6c9d9e59a5d481d6cc9c8342d25e7dc4b225cd1dd8848bc27587f7404773 |
| reports/browser-proof/view-tracing-detail.png | VERIFIED | b7c869139638f3fc2a952d2ad3e6deb6f4c601d46ce8dda6e06835baa26fa7c6 |
| reports/browser-proof/view-subsystem-impact.png | VERIFIED | d1caa0d3fa1b836f794bf2a35f84d552db0805ca4af32f99b059f6e646a47083 |
| reports/browser-proof/component-detail-from-search.png | VERIFIED | ed6293afdf6f8d071418a1c90b3522b3f237abcdf0755d9e41c1a1fbba9812f6 |
| Rendered build identity | FAILED | i_SCUW1zzhsjO0FfO1A9q |

Source/receipt snapshot stable during review: True. Changed: [].

**goal_not_met_yet:** Visible requirement-specific evidence check; actual workflow correction/recovery UI run; mandatory exact catalog/theme/search/error gates; readable trace graph and every-view sizing; listener/rendered-build binding; same-run synthetic observer/UI refresh restart and before/after cursor invariants.
