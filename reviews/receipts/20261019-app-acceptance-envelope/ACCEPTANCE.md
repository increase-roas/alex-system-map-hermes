NODE: app-acceptance-payload-envelope-20261019

ACCEPTANCE (frozen, from the Boss Director play):
`tools/app_acceptance.py` reports 13/13 on the current tree in `~/Projects/alex-system-map`, with
`file_browser_archived` and `file_proof_read_only` passing for the right reason.

The defect: `tools/local_service.py` returns its result wrapped as `{"payload": {...}}` while
`app_acceptance.py` lines 123-132 still read `.get('content')` and `.get('label')` at the top
level, so both read None. Realign the reader to the wrapped shape, tolerating the unwrapped shape
if another caller still produces it.

Use `NEXT_DIST_DIR=.next-verify`. Decide deliberately whether to commit the refreshed
`reports/application-verification.json` and say which. Do not touch the 20 pre-existing
`next lint` findings in the five unrelated files. No push, no PR, no branch switch.

ACCEPTANCE EVIDENCE REQUIRED: the 13/13 output, plus the exact lines changed.
