# Receipt hook proposal support

Observed 2026-10-22. Feature commit: `f7027abc3b839f3173f539b1d292c9405bf5f02a`.

## Real source diagnosis

Source: `~/.agents/tools/approvals/receipt_store_guard.py`.
Before SHA256: `62b5a77c1d4c2636ebc8fd3ee29b37b401a1714379d5573effc117fc1f582aec`.
Independent review read back the same hash after implementation. No live hook repair was applied.

Static configuration/import inspection found Claude, Codex and Cursor wrappers sharing this source. This is not observed live activation.

Exact copied source produced valid protocol responses in all 13 fixed cases and the existing owner regression suite. The harmless source-read plus unrelated history-search case returned deny when allow was expected. The other 12 fixed cases and the canonical owner regressions passed. This is the reproduced defect, not a claim that all historical refusals have the same cause.

## Research

Official documentation was retrieved through Composio Exa on 2026-10-22, account `exa_mars-saite`:

- [Claude hooks reference](https://code.claude.com/docs/en/hooks), hook JSON stdin and exit/output decision contract.
- [Python shlex](https://docs.python.org/3/library/shlex.html), lexical parsing limits. Retrieved page identifies Python 3.15.1; the native fixture uses Apple's installed Python 3.9, so an exact version match is not claimed.
- Native `sandbox-exec(1)` documentation identifies the macOS API as deprecated. Unsupported confinement does not execute a candidate.

The parser correction is a custom inference from Alex's source and policy. Vendor documentation establishes the integration contract, not an exact patch to this custom hook. Installed Claude Code was 2.1.301 and Codex CLI was 0.160.0; unversioned vendor documentation is not proof of exact installed-version compatibility.

## Feature verification

- Python repair suite: 257 tests, OK.
- Native macOS runner tests after the final launcher import correction: seven tests, OK.
- Component suites: 58 tests, passed. TypeScript passed. Lint passed with two existing lifecycle warnings.
- [GitHub repair checks](https://github.com/increase-roas/alex-system-map/actions/runs/39723040739) passed on the feature commit; Linux skips native macOS execution.
- Context-separated same-model-family verifier accepted the final bounded feature, including original adversarial failures after correction.

The controller runs separately from candidate code, checks expected regression completion/count/no skips, and forwards each canonical reason input to a fresh confined hook process. Candidate stdout cannot certify test completion. Credential projection rejects mutated/shadowed regex aliases, including indirect mutation. These are fixes to the proposal/test feature; no new installed hook or approval restriction was added.

Both [project app checks](https://github.com/increase-roas/alex-system-map/actions/runs/39723040714) and repair checks passed on the feature commit.

## Actual proposal in the normal dashboard

At 00:38 EDT the normal dashboard, `http://127.0.0.1:3201/explorer?view=local-files`, displayed plan `b5813839bb0d4d97b070966b2325d736`. The plan is local private state, not part of this repository. No apply request was submitted.

The AI proposed two changes: ignore individually proven independent read operands when gathering mutation targets, preserving pipe boundaries; and use parsed operands instead of also rescanning the raw full command when a parse is available. The exact diff is in the preview.

Actual executable evidence: the mixed read changed from deny to allow; the other 12 fixed cases retained their expected outcomes; the seven-test canonical owner suite passed before and after through the separate controller. Syntax, simulation, documentary assessment and exact Git path-set lifecycle checks passed. The dashboard's `Approve tested bundle` button was enabled and left unclicked.

Alex's approval remains required before applying that exact hook bundle. No live activation, whole-history diagnosis or coverage of every hook is claimed.

A context-separated verifier reviewed that exact frozen candidate and found no material regression within the stated profile. Seven additional sandboxed cases passed: conditional writes, stderr-pipe execution, relative writes, Python writes and tee writes stayed denied, while mixed sed/history reading was allowed. The tested candidate hash matched the frozen bytes. The live source still matched its original SHA256, and no job existed for this plan. This review used the same model family, not a second provider.
