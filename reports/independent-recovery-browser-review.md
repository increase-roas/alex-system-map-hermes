# Independent recovery browser review

Final ownerrun a7b9637c at07:31:54: browserexit1. Aggregatepass is not accepted for browser/restart. No rerun or source/DB mutations.

| Item | Status | Evidence/finding |
| --- | --- | --- |
| APP02-browser-final | FAILED | Final run a7b9637c at07:31:54 reports browser exit1, overallpartial and Unexpected end JSON input. No API recovery flags/UI proof/screenshot recorded; proof output directory empty. Aggregatepassed excludes this browser failure. |
| Prior UI recovery history | FAILED | Earlier07:29:38/07:31:06 attempts timed out waiting for visibleworkflow-actionable-next and reported API governing/stale_historyfalse;07:28:12 recorded APItrue but failed UI job selection. These attempts do not establish required browser recovery. |
| Response failure diagnosis | UNVERIFIED | Current runner calls response.json before status/content-type handling. POST route does not catch service/authorization exceptions; bridge rejects errors. INFERENCE: an empty/non-JSON workflow error response is likely. Exact request/stage/status/body cannot be established because runner logs no stage/server output/response metadata. |
| Build/startup/test-state binding | FAILED | Health source exposes no build/version; runner falls backpresent. Actual currentBUILD_ID9tY-IZHmhdkJV7NaPzuYv unbound to served run. Browser runner hash not listed in owner source_identity. Runneruses normal app/.data/local.sqlite through shared API, not two isolated CLI job DBs. No source/DB/listener/PID identity in browser receipt. Serverstdioignored; old listener could satisfy readiness. |
| Actual service restart | UNVERIFIED | Kill of npx plus2.5sec wait does not verify Next process exit, listener release or newprocessidentity. service_restarted settrue evenSKIP_SERVER_START. Final failed run never recorded this flag. |
| Browser two-job scope/history/recheck | UNVERIFIED | Runnercreates onlyonejob with outputs[]. It asserts action length/notstale, not exacttask/job/correctionsource; staleline check onlytextcontains, not computedline-through/actionability. No secondjob UI isolation or affected-output check. Current UI source has actionable/superseded/history/recheck rendering, but DOM source/test IDs are not runtime proof. |
| Mandatory browser failure gates | FAILED | Summarizer returnsnotfailures independently of browserexit; APIgoverning alone may clearbrowser_unverified despiteUIexit1. Runnerallows passed_api exit0 and api_before_governing substitutespostrestartproof. Browserrestart acceptance must requireactualpostrestartAPI+UI+twojobidentity+history andexactexit0, independentfromcoreCLIresult. |
| Scope separation | VERIFIED | Backendtwojob/screening cases are delegated to other reviewer and not independently regraded here. Original browsermatrix and realSDKsourceinput remainopen. No browserlaunch/rerun/sourceedit/outside-projectread performed. |

## Source/receipt machine checks

| Path | Status | SHA256 |
| --- | --- | --- |
| tools/recovery_emitted_screening_acceptance.py | VERIFIED | e82e8ac8c602f1b290ccb69351104f236d643875084771133b73642e0f9b616a |
| app/src/app/api/workflow/recover/[jobId]/route.ts | VERIFIED | 210399169ecd48a9f43a2f55fe5fdfef5863f8b4be5f6b656cfe4f07a670088f |
| app/src/lib/server/python.ts | VERIFIED | f69c42bdf024ec139c2e9da7fcdeb0fe00a8c141d09fc7e5d8205e23a5438f32 |
| app/src/app/explorer/workflow-panel.tsx | VERIFIED | a5d9b9efda509e4090ca78bc5b10c8d860a9ede62261148b672ab2ff053bc1f5 |
| Immutable final pointer/receipt bytes | VERIFIED | dedb4d329ba163fbbe34fbb52614e30e16a97b93586942947961db03d539963c |

Source stable duringreview: True. Browserproof directory: [].

## Smallest next repairs

1. Preserve stage/action/job ID, response HTTP status/content-type and bounded screened body before JSON parsing; save screened server startup stderr/exit. Return a typed JSON error from workflow API for caught service/authorization failures. This locates the exact failing POST/recover rather than changing DOM labels.
2. Bind production build to exactBUILD_ID/source hashes and fixtureDB; failifwronglistenerorstartupchild exits. Await actualNextprocessexit/listenerrelease, verifynewprocessidentity andsameDB beforeafter restart; nevermarkrestart when startup skipped.
3. Require browserexit0 andfullpostrestartUI/APIproof in aggregate. Seedtwojobs inthe same isolated servedappDB with realcorrection/output; assert exactcorrectedaction/job/task/source, unchangedjobB, preservedstalehistorynonactionable/line-through andaffectedoutput recheck; save screenshot and packet hashes. KeepCLIcoresummary separate untilbrowserpasses.

**run_failed:** Successful source/build/DB-bound browser restart recovery for two jobs, exact actionable next and preserved historical note/recheck outputs; final run failedJSONparse and priorUIvisible checks failed.
