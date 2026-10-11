# Independent app-path correction review

Delivery **app-path-corrections-20261010-0514**; owner receipt **2026-10-10T05:15:13+00:00**. Reviewed 2026-10-10T05:26:14.128969+00:00. All five receipt-recorded source hashes match current files; eleven tracked paths remained stable across two snapshots. Full hashes and exact proof handles are in [the JSON](independent-app-path-review.json).

Overall: **PARTIAL — owner PASS is not accepted.** Only these two review files were written. Databases were opened read-only; no mutating test, browser, external service or credential read occurred.

| Item | Accepted portion | Remaining verdict |
| --- | --- | --- |
| REL-02 / REL-05 | Real completion command validates date/path and optional proof hash; checks skill files. | FAILED: accepts prior failing review as proof, ignores omitted requirements/skills claim, does not validate proof meaning/use/freshness or gate workflow verify. |
| REL-03 | API uses enhanced recovery; fresh subprocess returns persisted correction and queue. | UNVERIFIED: original next_permitted_action remains actionable; UI ignores governing_next_action. |
| REL-04 | Conditional guard and SQL owner/revision transfer; checkpoint acceptance retained; one operation/event confirmed. | FAILED: omitting client guard fields bypasses owner check; no job binding or atomic workflow/handoff revision enforcement. |
| REL-06 | Trace-get and diagnose-text use actual screening wrappers. | FAILED: error canary test injects no canary; stderr remains raw; trace response wrapper breaks current UI shape. |
| Synthetic sequence | VERIFIED bounded CLI baseline→mutation→observe→linked receipt→fresh status reader→dedup; current hash/import/span/cursor rows agree. | Full application refresh/restart and actual timed/action-linked tracing remain UNVERIFIED; no replacement for original real-source proof. |

Exact bypass/invalid-test evidence:

- Gate pure check returns `accepted=true` with date `2001-01-01T00:00:00+00:00`, prior FAILED/UNVERIFIED review JSON as proof, no proof hash, requirement_set only REL-02, and skills_verified=false. Owner “good” test deliberately uses that prior report: app_path_corrections_acceptance.py:68–89. Gate validates existence and labels, not result: reliability_gate.py:35–47,58–154.
- workflow_apply_guard.py:24 condition requires both client fields. Removing either reaches engine.apply at line32; pure DummyEngine check confirms the call. Existing UI omits both fields. Handoff checkpoint job ID is not checked; separate handoff revision remains1 after workflow revision advances2. Sources: workflow_apply_guard.py:16–32; workflow-panel.tsx:229–243; reliability_store.py:170–196.
- Enhanced recovery only adds governing_next_action at reliability_store.py:204–206; workflow-panel.tsx:373–377 still shows original next_permitted_action. The runtime/application next action is not proven correction-governed.
- Error test at app_path_corrections_acceptance.py:290 supplies `missing-trace-id`, containing no fake canary. All no-leak checks ignore exit/nonempty shape. Node bridge still forwards raw stderr/stdout at python.ts:38–58.
- Trace getter now returns `{payload:{trace,spans},screening_notes}` (trace_store.py:215–221; output_screening.py:44–46). API returns it unchanged; TracingPanel stores it directly at142 then dereferences detail.trace.label at182. This is a concrete source-level response-contract regression. Browser runtime reproduction remains owner work.
- Summary does not require recovery subprocess exit/recheck count, handoff replay_ok, or synthetic restart_subprocess_ok (app_path_corrections_acceptance.py:406–423). Named PASS alone is insufficient.

Readbacks: isolated handoff test has task owner-b, one operation and one matching event; checkpoint acceptance `['check']` retained. Synthetic marker SHA `0db0b4016236b3800518fd0ff3e7b218d917fe304f561f33b171f185f89554a9` matches watch row; live receipt SHA `3c07c2871b2398707eda13a97f001c2987e893223cca7ec85ac694dd861b713c` matches import payload, one trace/span and cursor retained.

Blocker: **goal_not_met_yet** — Mandatory actual ownership/proof enforcement; correction-aware actionable recovery; supported error/trace screening and response-shape repair; full regression/application refresh evidence. No new outside dependency or authority is needed for these local corrections. Browser, controlled edits and real-source trace milestones remain separate owner work.
