# Next correction queue

Review: independent-app-path-review-20261010-0526. All findings retained from the saved independent review.

Current browser milestone stays active. Deliver only after verified safe completion; preserve accepted subproof and independently retest actual application behavior.

## APP-REVIEW-01: REL-02_gate_and_REL-05_negatives

- Positive test uses prior independent-reliability-corrected-detail.json (which explicitly FAILED/UNVERIFIED items) as proof, and gate accepts based on file existence/hash alone. It never binds proof content/result to requirement or dated source identity.
- Pure read-only check accepted REL-02 with a 2001 timestamp, prior failure report as proof, omitted other requirements, skills_verified=false and no proof_sha256. Matching labels still substitute for actual-use proof.
- Requirement-set and skills_verified omission checks exist only in evaluate_negative_case; real completion does not call them. Local_service workflow verify/checkpoint still routes to Engine through guard, never to requirement completion gate; UI fabricates checks=true and evidence local-explorer-evidence (workflow-panel.tsx:254-265).
- New receipt does not cover REL-05 four regressions; existing helper/source change is not application regression proof.

Next: Parse and bind requirement-specific successful proof/results/freshness; enforce all required claims/skills in real completion and workflow verification path; run four actual application negative cases.

## APP-REVIEW-02: REL-03_recovery

- merge_recover_packet adds governing_next_action but retains original next_permitted_action. UI still displays/uses that original field and ignores governing_next_action/reliability_recovery; correction governs an extra field, not proven actual selected next action.
- API hardcodes one old-note string, and correction/recheck helper remains global/hardcoded to supervision state; generalized affected outputs and acceptance restart case remain unproved.

Next: Make the actual displayed/permitted action correction-aware; retain old note/history; demonstrate conflicting note through intended restart path with affected outputs for recheck.

## APP-REVIEW-03: REL-04_handoff

- Guard is conditional on handoff_operation_id AND actor_owner. Omitting either falls through directly to engine.apply; ordinary UI request omits both. Nonmutating DummyEngine check confirms omitted fields invoke unguarded engine.
- Guard does not verify handoff checkpoint job_id matches request job_id. Actor identity remains client supplied.
- Handoff transfer is in separate reliability DB from workflow task mutation; guard/check and apply are not atomic, handoff revision is not advanced after workflow write, and retry replay is checked only after handoff revision/owner guard.
- Receipt tests conditional field path only; lacks omission/foreign-job/concurrent transfer/recoverability negatives. Summary omits replay_ok from acceptance.

Next: Derive active handoff/current owner from authoritative job state; require/enforce identity without optional bypass, bind job ID, synchronize revision atomically, and reconcile retries before rejecting stale revision.

## APP-REVIEW-04: REL-06_screening

- Error canary test requests missing-trace-id without injecting a canary into the error, so error_no_leak is vacuous. Test ignores command exit statuses and output shape/content; empty output could pass.
- Node stderr/invalid-JSON error bridge remains raw (python.ts:38-58). trace-list, workflow events and other outputs still print raw values; full supported diagnostic/error/trace/export proof missing.
- Output wrapper changes trace-get shape to {payload:{trace,spans},screening_notes}; API passes through, TracingPanel setsDetail(response) then reads detail.trace.label. Source proves consumer contract mismatch, likely runtime crash; no browser action taken.

Next: Preserve/unpack trace response contract; inject fake canary into actual emitted error/stdout/stderr/export paths, assert nonempty expected shape/screened content and no leaks, and cover remaining supported outputs.

## APP-REVIEW-05: combined_synthetic_sync_trace

- No browser/automatic UI refresh/observer lifecycle proof; test exercises manual CLI observe and fresh status reader.
- Generated span lacks actual start/end times and agent/source/evidence IDs; it hardcodes status ok instead of recording subprocess result. Broader tracing schema/real-source acceptance remains open.
- Summary does not require restart_subprocess_ok; no receipt cursor-before/after assertion. This review supports current stored cursor, not equivalence across runtime restart.

Next: Keep accepted CLI test; add actual observed action metadata/status/timestamps and application observer/UI restart/cursor invariants. Do not substitute this synthetic proof for original real-source tracing.

## Separate open proof

- REL-01: UNVERIFIED — Fresh-agent automatic current context/skill loading and correct action recovery; file existence/Python helper alone insufficient.
- full_application_sync_tracing: UNVERIFIED — Automatic UI refresh, actual observer/application restart, cursor invariants, timestamps and IDs/status from observed action, original real SDK receipt source matching; accepted synthetic CLI mechanics preserved.
- browser_visual: NOT_RUN_at_review — Current owner to produce actual installed-Chrome assertions; awaiting new evidence.

No additional authority dependency established for these local corrections.
