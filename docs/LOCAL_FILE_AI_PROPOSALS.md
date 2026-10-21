# AI proposals for local instruction repairs

Alex requested AI-written contradiction fixes on 2026-10-20: Review & fix should explain the conflict, show the proposed exact change, and let him approve it without choosing wording. This extends LOCAL_FILE_REPAIRS.md. Source mutation still uses its existing explicit, frozen Apply and conditional Undo.

## Behavior and acceptance

1. Opening Review & fix on an editable handwritten source automatically requests an AI proposal. Show progress, then a plain explanation, current source citations and the exact diff with an Approve button. Manual editing remains optional. A no-conflict or unresolved-authority result explains why it has no approvable edit.
2. The server selects the indexed target and related finding files, rereads screened current contents, and supplies bounded context. Browser inputs are only target ID, expected hash and optional indexed finding ID. Files are evidence, never instructions to the proposal worker. Show which files were considered and that coverage is bounded. Generated and unsupported sources retain owner routing.
3. Use the installed Codex CLI and existing ChatGPT login, not a new key, API provider or paid Claude run. Enforce ChatGPT authentication, ignore user/project settings for this isolated proposal invocation, and disable model tools/hooks/apps/shell and web access using supported per-invocation settings. No changes to Alex's Codex settings. The worker returns structured analysis and exact replacement edits; it has no authority to apply them.
4. Validate the structured response, exact current citations and uniquely matching target edits before creating the existing frozen preview. Reject malformed, secret-shaped, invented or stale edits. Bind all AI context fingerprints into that frozen proposal and reject a changed supporting file or resolved target before approval writes the target. AI suggestion, preview, failure, cancellation and no-change paths never alter actual source bytes. Provider failure permits an explicit retry or manual editing without falsely declaring source staleness. Do not silently retry, choose a different provider or charge an API account on failure. Deduplicate simultaneous requests for the same source/finding.
5. Approval uses only the existing frozen proposal ID/fingerprint. It preserves backup, exact Git preimage, one-path commit/push, stale-edit protection and conditional Undo. Changing the draft invalidates the AI preview. A failed/uncertain model request is visibly different from a failed source publication.
6. Focused automated tests cover context selection, exact citations/replacement validation, stale context, no-change/needs-decision, malformed/secret output, provider failure and no-write behavior. A synthetic fixture uses the real subscribed Codex route to produce a reviewable proposal, then a real browser journey proves automatic analysis, rationale/citations/diff and explicit approval behavior with disposable sources/remotes only. One final TypeScript check. A context-separated independent verifier binds the final source and evidence, with no actual agent Apply during acceptance.

## Interface

POST /api/local-files/repair adds `{action:'suggest', file_id, expected_sha256, finding_id: string|null}` under the existing local/token/body boundary. The server resolves all paths/context; no client prompt, model, command or source body.

`LocalRepairSuggestion` contains `status` (`proposed`, `no_change`, `needs_decision`), `summary`, `rationale`, `conflicts` (explanation plus exact citations), `limitations`, `context_files` (IDs/paths/hashes), `model`, `generated_at`, `proposed_content: string|null`, and `preview: LocalRepairPreview|null`. Citations are `{file_id,line,quote}`. Only a valid proposed status has content and a frozen preview.

The worker schema uses the same analysis fields plus `edits: {old_text,new_text}[]`, never full file paths or commands. The server applies uniquely matching nonoverlapping replacements to its own target snapshot, validates the result and generates the existing preview. Ambiguous authority must produce needs_decision, not invent a newest instruction or silently remove a gate.

## Ownership

Backend: tools/local_file_ai.py, tools/test_local_file_ai.py, app/src/lib/server/local-file-ai.ts, repair route integration. Frontend: local-file-repair-panel.tsx. Parent: shared types and specification reconciliation. Existing local_file_repairs.py mutation behavior remains unchanged unless a demonstrated compatibility defect requires a separately reviewed fix.

Official implementation references checked 2026-10-20: https://learn.chatgpt.com/docs/non-interactive-mode and https://learn.chatgpt.com/docs/config-schema.json. Installed codex exec help confirms ignore-user-config, ignore-rules, ephemeral and output-schema; live login status reports ChatGPT. This consumes existing plan usage; it does not promise unlimited availability.
