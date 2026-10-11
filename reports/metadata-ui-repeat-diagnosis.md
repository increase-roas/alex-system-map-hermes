# Metadata UI repeated-failure diagnosis

Read-only review 2026-10-10T11:12:04.268591+00:00; saved failure at 2026-10-10T11:01:39+00:00.

Current source stayed stable during reading; browser/panel differ from saved failing receipt. Latest owner run not interrupted.

- **VERIFIED — Saved failing runtime boundary.** At 11:01:39 metadata_ui_passed and ui_apply_passed false, metadata UI revision0, browser exit1. Canonical component frozen-preview/API/disk equality true. Saved browser has no submitted metadata request, response, preview/apply error or exact DOM field readback; runtime root cause is not captured. Evidence: `reports/run-receipts/canonical-review-fixes-20261010-1044-ea4a6866-fbfd-4aac-9a6a-0e6e40d5d329.json`

- **VERIFIED — Current selection/frozen request source race.** Refresh checks dirty/frozen state only before awaiting fetch. On response it unconditionally installs state without request generation or active target validation. Mode change force-refreshes, leaving previous request pending. Preview selects field from mode but target/document/revision from state. A delayed prior-mode response can therefore overwrite the selected target or filled policy after correct metadata selection. Frozen apply preserves whichever request was previewed, including a wrong/stale selection. This is a concrete source race; occurrence in saved failure is not proven. Evidence: `app/src/app/explorer/maintained-edit-panel.tsx:75`, `app/src/app/explorer/maintained-edit-panel.tsx:95`, `app/src/app/explorer/maintained-edit-panel.tsx:120`, `app/src/app/explorer/maintained-edit-panel.tsx:147`

- **VERIFIED — Current browser ordering and selector limits.** Current browser waits actual state.path metadata before filling policy and awaiting frozen preview, then waits expected revision. This is stronger than a mode-label-only test. It does not prevent a delayed catalog refresh after path wait, and bare revision values overlap between metadata and component targets. Latest active browser outcome not observed; no sleeps or assertion weakening recommended. Evidence: `tools/browser_canonical_review_fixes.mjs:141`, `tools/browser_canonical_review_fixes.mjs:153`

- **VERIFIED — Metadata API/backend routing.** Optional record_id is forwarded consistently. Metadata read without record_id returns whole document; preview validates metadata/update_policy. Current panel explicitly drops record_id in doc-mode read state. No current metadata-route mismatch established from inspected source. Incorrect stale state from UI remains possible, not a backend route diagnosis. Evidence: `app/src/app/api/catalog/edit/route.ts:13`, `app/src/app/api/catalog/edit/state/route.ts:15`, `tools/local_service.py:563`, `tools/canonical_maintained_edit.py:194`, `tools/canonical_maintained_edit.py:381`

- **UNVERIFIED — Exact runtime cause and latest owner pass.** No safe metadata submitted request/response/error handle in saved failure; latest run remains active. Browser/panel changed since failed receipt, backend handler unchanged. Do not diagnose stale build as sole cause: coordinator observed exact panel source-map equality, not independently repeated here. Source-race explanation is INFERRED as likely contributor, not confirmed exact runtime failure. Evidence: `reports/run-receipts/canonical-review-fixes-20261010-1044-ea4a6866-fbfd-4aac-9a6a-0e6e40d5d329.json`

**INFERRED likely contributor:** Late prior-mode/in-flight refresh can replace metadata selection/draft or preview source state; revision-only assertions cannot establish correct target. Exact saved runtime cause unproven.

Minimal implementation fix: Bind refresh responses to a monotonic request generation and selected target/mode/record identity; discard obsolete responses and responses arriving after draft/preview activity. On mode switch mark state loading/clear stale target and disable Preview/Apply until state identity matches selected target. Preview must require matching mode/path/record; keep frozen mutation exact.

Required proof: Retain exact safe projected selected mode/state path+record, frozen policy/request revision/hash, response status/error class and metadata disk/API/DOM policy+revision equality. Wait for target-bound successful apply/readback, not a revision number alone. Preserve genuine canonical and metadata equality assertions; no sleeps/relaxation.

Blocker: **missing_evidence** — Safe submitted metadata preview/apply identity and policy plus response/error and target-bound API/disk/DOM readback for current run.

Later parent update: run `ae094cc8-5a7f-425e-9f4b-5deb31afeec8` reportedly passed at 11:11:30 UTC after this diagnosis was saved. It was not independently reviewed here. Findings remain bound to the prior failure and read-time source snapshot; fresh full milestone review is required.
