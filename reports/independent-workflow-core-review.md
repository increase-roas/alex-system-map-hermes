# Independent workflow core review

Owner receipt06:08:35 UTC: **FAILED independent acceptance**, despite ownerPASS. Five recorded source hashes and positive proof SHA match current bytes. Sample stable06:10:34–06:11:11 UTC. Full hashes and disposition are in JSON.

| Area | Verdict | Accepted | Still missing |
| --- | --- | --- | --- |
| APP-REVIEW-01 | FAILED | Known failed/nonJSON proof, absent set/hash, and manual-only workflow evidence rejected; actual workflow gate connected | Truthful successful proof bound to job/revision/source; real freshness; actual handler regression controls |
| APP-REVIEW-03 | FAILED | Missing actor/job checkpoint rejection; sequential replay and payload collision; saved exact operation/event dedup | Transfer actor/job enforcement; atomic or recoverable crossDB ownership; concurrency/interruption proof |

Pure read-only checks accepted January2026 and future2099 timestamps; accepted unrelated examples/agent-trace-fixture.json asREL02 proof; accepted the same positive artifact for different-job/revision99 with binding omitted. Source uses year>=2026 (reliability_gate.py:157-164), optional proof requirement matching (66-68), fall-through success (83), optional claim job/revision (327-332), no proof job/revision comparison. The supposed legitimate proof contains7 assertion fields and no actual check outputs, source identity or job/revision. Bytes/hash correctness does not establish the proof's claim.

Actual mutation fix is useful: workflow_apply_guard.py:79-80 now invokes claims validation; missing actor rejected at68-69 and missing/foreign checkpointjob at47-52. Replay now reconciles digest at73-77 before revision rejection. Independent SQLite mode=ro readback shows core-h-op1 exactly1 operation and1 matching event, alongside1 create event, plus owner-b and checkpointrevision2 with acceptance retained. Owner test counts total events2 and never requires exact matching event count; current independent readback supplies that narrow evidence.

Transfer still ignores nonempty actor's relationship to expected owner and chosen checkpoint's job (workflow_apply_guard.py:126-154). Pure mocked call accepts intruder actor/foreigncheckpoint operation and can replace acceptance with[]. Engine commit precedes separate handoffCAS (112-122): injected CAS failure commits1 engine effect; retry returns success leaving handoffrevision2 vs result3. No concurrency/interruption test or replay reconciliation repairs that gap. Actor identity is still supplied by caller.

First failure bytes are retained, not erased: reports/workflow-core-failures/APP-REVIEW-01.json and supervisor hash-matching copy307fe16d0430 both contain verify_accepts_gate_bound_claim.accepted=false. Current failure list[] omits them. Root report reports/workflow-core-history-check.json independently records this distinction. Fixed-case save_failure overwrites future failures (acceptance.py:128-132); append-only history remains UNVERIFIED. Earlier06:08:21 timestamp is coordination context, not in retained file.

Next checks: use measured successful proof recording actual checks and mandatory job/revision/source identity; reject expired/future or source-stale proof; exercise missing proof and required regressions through handler. Bind transfer actor/checkpoint to authoritative owner/job; preserve acceptance; test concurrent transfer/write and crash after Engine commit with repair on replay. Keep exact per-operation event assertions and explicit error reasons. No outside dependency is required.

Blocker: **goal_not_met_yet** — fresh truthful completion proof plus mandatory owner/job transfer and atomic/recoverable concurrency/replay.
