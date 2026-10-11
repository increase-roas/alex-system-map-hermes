# Independent outcome/replay/rollback review

Receipt **06:35:18 UTC**, run935f027b: **FAILED full independent acceptance**. Seven recorded source hashes match stable sampled bytes2026-10-10T06:36:40.010804+00:00–2026-10-10T06:37:14.165928+00:00. Full identities in JSON. No mutating rerun.

| Item | Verdict | Evidence |
| --- | --- | --- |
| Real post-Engine-write failure rollback | VERIFIED bounded proof | Actual CAShelper targeted fault after Engine writes; before/after snapshots identicalSHA; failed task/op/event absent, later retry1effect |
| Historical replay | VERIFIED | Old resultrevision3 preserves later owner-c handoff/jobrevision5 |
| Transfer retry/digest/current read | VERIFIED |1 ledger row, same-result retry, payload collision; jobread insideBEGIN |
| Requested-work outcome | FAILED | Arbitrary/nonexistent output strings satisfy allchecks; saved verifiedtask points to nonexistent bounded-output.txt |
| Operation/verifier handler negatives | UNVERIFIED | Wrongoperation masks stale revision; wrongverifier masks replay collision |
| Immutable receipt/history hashes | FAILED | Recorded1a9229d... differs from finalfilebf0728e...;2 prior run hashes also mismatch |

Rollback evidence is now substantive: reports/outcome-replay-rollback-proofs/be9b2be6-1e15-45b7-acff-7374079fa777/before-failed-attempt.sqlite and after-failed-attempt.sqlite hashfc326871a9b5d5ed2883ae9ab1286f1442799683d1f81b31435b23049f2f102e. Read-only complete selected-table comparison matches; job/checkpointrevision2, no t2, no orr-post-write-fail operation/event. Actual helper hook (reliability_store263-276) occurs after guard Engine.apply161-163, before CAScommit; rollback175-177. Finalretry database has1 matching operation/event and revision3. This is bounded injected-fault proof, not process-kill durability.

Historical replay guard98-119 now only advances a lagging checkpoint; laterrevision5 owner-c remains intact. Transfer guard180-271 now has a distinct operation ID/digest/result ledger, performs jobrevision read underBEGIN and records result in same transaction. Saved orr-transfer-attempt-1 ledger1row/owner-b and receipt collision protocol support narrow fixes.

Outcome checker remains false completion: verification_evidence87-95 returns all nonempty outputstrings for proof-bound/gate-bound proof. Pure pending tasks with totally-unrelated-text or missing-output.txt return allTrue. Saved truth-job t1 is verified with bounded-output.txt, which does notexist; helper430-445 only adds its name to outputs and never creates content. Check produced artifacts/results against the actual criterion, with nonexistent/wrongcontent/wrongresult negatives and observed hash/results. No arbitrary general verifier is demanded; unsupported criteria can stay unverified.

Scope proofs: wrongtask returns exact task mismatch. Wrongoperation helper539-572 issues and requests identical operationID, then rejects stalerevision3 after positive jobrevision4. Wrongverifier574-602 reuses successful opID and alters payload, so rejects digestcollision before verifier validation. Preserve accepted validators, but require fresh/currentrevision isolated handler controls and exact operation/verifier mismatch reasons.

Unique receipt files are an improvement, but current immutablefile hashbf0728e2b8fd5f551ce2dde213c40d34f771fb8c35d4e816589ac8f7414c28cb disagrees with declared/history1a9229d667fe95150ab1015cbcf838df8d3f4a47aaa5de31a4dbfdd8e4501b10. Writer678-685 hashes then rewrites; failedruns rewrite again. All3 new unique runreceipt historyhashes mismatch. Finalize once, hash finalbytes, publish hash in separate manifest/history. Original307fe and current49330d failure artifacts are now separately hash-linked and preserved.

Blocker: **goal_not_met_yet** — actual outcome checking, isolated operation/verifier handler negatives, and trustworthy immutable final-byte receipts. Other required queue stays open; no outside dependency for these local items.
