# Independent atomic/fixture review

Latest receipt **06:24:29 UTC**, runac770f61: **FAILED independent full acceptance**. Four recorded source hashes match. Sample stable2026-10-10T06:27:42.910271+00:00–2026-10-10T06:28:37.743055+00:00; JSON records hashes for gate/Engine/local_service omitted from owner receipt. Read-only review only.

| Check | Verdict | Evidence / remaining work |
| --- | --- | --- |
| Implicit executescript commit | VERIFIED source repair | Individual DDLexecute + preparedconnection before BEGIN; no implicit commit script in inner handoff helpers |
| Saved concurrent loser | VERIFIED bounded race | ab-concurrent0op/0event; jobrevision2/checkpointrevision2 owner-c |
| Post-write CAS rollback | UNVERIFIED | Claimed CASfault is expectedrev1 vs handoff2, rejected before Engine/CAS |
| Fixture exclusion | VERIFIED | Real workflow rejects fixture_only; standalone fixtures require isolated flag/prefix |
| Registry and task/op/verifier binding | VERIFIED validators | Correct registry accepted; wrongSHA/path and each individualscope rejected; owner combinedscope test fails earlier revision mismatch |
| Measured positive task proof | FAILED | Measures criterion text membership/set equality, not acceptance outcome |
| Historical replay | FAILED | Pure old replay attempts handoffrevision4→2 |
| Transfer idempotency | FAILED | No unique transfer-operation receipt/digest/result reconciliation |

The concurrent DB app/.data/workflow-core-tests/concurrent-atomic-failure-fixture-boundary-20261010-0622.sqlite contains only ab-create/ab-add events; ab-concurrent absent. Job and canonical handoff bothrevision2; owner-c. This closes the previously observed durable loser for this ordering.

The separate cas_failure_zero_side_effects test (acceptance221-242) supplies revision1 after setuprevision2. Error is handoff revision conflict (guard147-148), before Engine writes152-154 and CAS155-162. It proves early rejection, not post-write rollback. Final atomicDB contains1 ab-fail-cas event/operation after authorizedretry and job/checkpointrevision3. Require real fault after actualwrites, zero task/job/handoff/operation/event effects, then retry/replay1.

Positive recordb38d1be7 is exact registered hash/path, scope real-verify-job/revision2/t1/ab-verify-good/reviewer-b, fixture_only=false. Validator/registry improvements are real (verification_evidence285-293,329-354). Saved t1 is verified using checks task_exists, acceptance_proof_bound, acceptance_set_matches. measure_workflow_verify_checks (85-101) only compares listed acceptance strings; pending task with no outputs/evidence and criterion file exists still returns allTrue. issue_measured_workflow_verify_record (211-235) labels that proof REL02 and calls set equality skills_verified. Measure actual criterion results or retain truthful checkedoutput handles; list membership/preconditions cannot verify taskwork.

Owner wrongscope test uses recordrevision2 against requestrevision3 (acceptance485-518), so its observed rejection does not isolate task/op/verifier. Independent purechecks with matchingrevision reject each exact scope mismatch. Correct registry row accepts; wrong fileSHA/path rejects. Fixture realverify rejection is explicit.

Historical replay remains unsafe (guard95-110): pure replay of stored resultrevision2 against checkpointrevision4 owner-c attemptsCAS4→2. Return original receipt without changing newer state. Transfer (170-228) has no attemptoperation ledger; canonical handoff ID cannot reconcile lost-response retry. Add digest/result operation identity and read jobrevision insidetransaction.

History:10 append entries, latest receipt hash matches. Current fixedAPP01 file49330d differs from previous416816 and original307fe; original307fe remains supervisor copy. Latest link names currenthash and originalcopypath but no copyhash. Per-run failure8babfdc3 file exists. Full immutable historical receipts remain UNVERIFIED because receipt path is overwritten and failure historyhash is computed before receipt rewrite. Source acceptance601-654.

Blocker: **goal_not_met_yet** — actualpost-write rollback proof, truthful acceptance-result checks, historical replay preservation, idempotent transfers and immutable runreceipt links. No outside dependency.
