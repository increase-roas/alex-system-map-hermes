# Supervision initial review (revision 1 follow-up)

Date: 2026-10-10 (UTC). Source: `docs/BUILD_SUPERVISION.md` revision 1 and independent re-read of foundation files.

## Findings

| Check | Expected | Observed in Cursor build (prior) | Re-read now |
| --- | --- | --- | --- |
| Components | 2351 | 2351 loaded | OK |
| Factual relationships | 59 | **0** (load gap treated as empty) | **59**, SHA256 `a23e77ce…` |
| Coverage records | 2377 | gap / not asserted | **2377**, SHA256 `3e824e09…` |
| Overview memberships | 2351 | synthetic fallback | **2351**, SHA256 `a0ee4c55…` |
| Pro ZIP | `5b69062b…` | unreadable | **readable**, hash matches |

Prior `tools/app_acceptance.py` **PASS was partial**: import check passed with `relationships: 0` and three `load_gaps`. That must fail full acceptance.

## Required corrections

1. Strict catalog completeness and hash verification in loader and acceptance tests.
2. Replace raw-JSON workflow UI with guided investigate/build/repair templates tied to `workflows/*.json` and workflow engine operations.
3. Milestone 2: catalog file sync status and controlled maintained-record edits through server.
4. Milestone 3: Agent Tracing view with durable local span storage and real fixture import (labeled); no invented SDK receipts.
5. Browser/restart/crash proof, not API-only self-PASS.

## Stale blocker

Earlier `errno 11` / iCloud placeholder reads are **stale** on independent re-check; do not use degraded loading as the steady state.
