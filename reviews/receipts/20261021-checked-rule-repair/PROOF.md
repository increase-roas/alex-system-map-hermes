# Checked, one-approval instruction repairs

Implemented for Alex's 2026-10-21 request. Development acceptance changed disposable fixture rules only. The real rule proposal must remain unapplied for Alex's approval.

## Observed outcomes

- Python: 80 tests passed, exit 0. Raw command and output: `python-suite.json`.
- Component/API behavior: 21 tests passed, exit 0. `component-check.json` covers cancellation, source switching, invalidated manual edits, failed checks, honest pending states, exact verification predicates, actionable 422 responses and accurate failed/unavailable-check wording.
- TypeScript: exit 0 in `typecheck.json`. Scoped ESLint: exit 0 in `lint.json`, using installed ESLint's native legacy-config selector for the existing `.eslintrc.json`. No lint rules were disabled. Its deprecation notice is retained.
- Real subscribed Codex produced a synthetic contradiction repair and four checked scenarios. `fixture-ai-checks.json` contains the results. All four before decisions also matched the expected choices, so this proves checked preservation, not a measured behavioral improvement.
- Desktop and narrow browser journeys used the actual HTTP repair route/backend against a disposable home and bare Git remote. One approval updated the source, three generated files, verified the unchanged Claude import, preserved modes/unrelated staged and dirty work, and pushed the exact one-path source commit. `apply-readback.json` contains ten independently checked predicates.
- One conditional Undo restored the source and every original output byte, published the exact restoration, and preserved app config. All eleven predicates in `undo-readback.json` passed. Replayed Apply/Undo reconciled the recorded outcome without another mutation.
- The fixture ran the installed normal pre-commit hook. Its post-commit deliberately failed. Local copy installation and confirmed source publication still succeeded. No live hook was edited or disabled.
- A literal failure at the later Cursor copy left the already-written source/earlier copies and pending state accurately reported. Conditional Undo restored all originals. `partial-copy-failure.json` and the independent readbacks preserve the evidence.
- The real shared-rule context is eight files / 105,038 UTF-8 bytes with the canonical gate excerpt included. `real-context-budget.json` records a 14,414-byte source ceiling and 267-byte growth budget from the unchanged native 32,768-byte limit. A candidate that exceeds that ceiling is rejected before behavioral calls. An already-oversized baseline can still receive a valid shrinking repair; the unchanged native candidate renderer remains authoritative.

## Independent review

The fresh AI, distribution and UI/API reviewers used separate contexts on the same available model family. Reports are `ai-review.md`, `distribution-review.md`, and `ui-review.md`. They inspected source, exact citations/fingerprints, frozen approval bindings, normal-hook behavior, failure recovery, actual fixture Git readbacks and raw test exit statuses. Credible findings were fixed and re-reviewed, including changed-after-push messaging and shrinking an oversized baseline. This is not a paid other-provider review.

## Browser evidence

The synthetic proposal was produced by four real native subscribed model calls. To avoid repeating those calls during the disposable browser journey, its fixture-only CLI wrapper returned that captured proposal. All HTTP authorization, body validation, frozen Apply, actual file writes, copy readback, Git publication and Undo ran through the implementation. There was no browser network interception. The live dashboard has no fixture wrapper.

- `desktop-ai-checks.png`: visible scenarios and decisions.
- `desktop-repair-verified.png`: confirmed Apply result.
- `narrow-repair-verified.png`: narrow scenario layout; despite the historical filename it does not show the result heading.
- `narrow-undo-verified.png`: actual narrow Undo result.
- `browser-apply.txt`, `browser-undo.txt`: displayed status and copy outcomes.

## Limits

Behavioral checks are bounded simulated decisions, with model-planned expectations. They do not prove universal rule consistency or live agent/tool behavior. Context is bounded to eight files / 128 KiB. File hashes do not prove already-running agents loaded the new text; start new sessions where indicated. Only registered native dependents are installed. App-owned Codex settings, unrelated role artifacts and remote machine publication retain their native owners and remain explicitly pending if relevant. Drive undo bytes are verified locally; cloud upload is not claimed. No actual agent-rule Apply was part of acceptance.

The canonical dashboard's final live read-only proposal and integration proof are recorded separately after integration. `reviewed-source-sha256.json` identifies the implementation bytes checked here.

## Real-input follow-up

An initial live run returned a valid contradiction analysis but unavailable behavioral checks, with no preview or writes. Its raw failed plan was not retained, so that exact failure remains unproven. One controlled diagnostic proposer call independently reproduced off-by-one source citations; production validation correctly rejected them. A diagnostic-only copy with uniquely located citations allowed a single planner call to be inspected; its four cases validated. No diagnostic correction was accepted by production or applied to a source. Private raw diagnostic data remains outside this receipt.

The follow-up supplies explicitly numbered source lines with original per-line endings to the proposer and planner, preserves strict raw citation matching and unchanged raw decision inputs, and makes check failures identify their stage. LF, CRLF, mixed endings and no final newline remain distinguishable and reconstruct exact original spans. Failed/unavailable tests now explain that outcome without claiming Alex must decide which rule wins. Normal hooks, native size limits and frozen approval semantics are unchanged.

## Final live result

VERIFIED on the normal dashboard at `http://127.0.0.1:3201/explorer?view=local-files`: a fresh actual Review & fix run found three supported approval-rule contradictions in the real shared source and produced a frozen proposal. All four simulated cases passed. They also passed before the change, so no measured behavior improvement is claimed. The enabled single approval button is visible in `real-proposal-ready.png`. Browser error logs were empty.

`real-proposal.json` records the frozen identity, source fingerprints, four case outcomes, eight context bindings, three generated-file changes and one unchanged import wrapper. `real-proposal-review.md` contains the final independent source/context/copy-plan readback and scope review. The actual source, generated copies and app config remained unchanged. No actual Apply was performed; Alex approves the exact reviewed source and copy plan in the dashboard.
