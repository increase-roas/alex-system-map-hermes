---
paths:
  - "tools/**"
---

# Python builders and the local service (tools/**)

- **Read Alex's files read-only.** Open with mode `r` or `rb`. Never write, rename, chmod or delete anything outside this repo. Paths under `~/.agents`, `~/Alex-Director`, `~/Documents` and the like are sources, not targets.
- **New code writes only inside `app/.data/`** (`org-map.json`, `live-setup.json`, `local.sqlite`, `local-token.json`). The existing editors of the maintained catalog, generated views, receipts and reports (`catalog_controlled_edit.py`, `canonical_maintained_edit.py`, `build_catalog.py`, `load_director_traces.py` and the acceptance scripts) keep their documented targets. Do not add a new write target outside `app/.data/` without Alex. Follow the pattern already in those files: backup first, temp file then `os.replace`, and `expected_revision` compare-and-swap.
- **No network calls to any host that is not allowlisted in the same file.** At base the only network use is loopback (`127.0.0.1`) health and API calls in `tools/*_acceptance.py`. A new host needs an explicit allowlist constant in that file and Alex's yes. No `curl` or `wget` through `subprocess`.
- **Stdlib first.** `requirements-validation.txt` pins openpyxl, jsonschema and PyYAML for the validators only. Do not add a dependency or call `pip install` from a tool.
- **Run as `python3 -B tools/<name>.py`** so no `__pycache__` is written beside the sources.
- **No secrets in output.** Never copy a token or key read from Alex's files into JSON, receipts or logs. Keep `tools/output_screening.py` (and `subprocess_output.py` for child output) in the path of anything that reaches `app/.data/` or an API response.
- **SQLite:** `?` placeholders for every value; table and column names only from fixed constants, never from input; WAL plus `busy_timeout` as in `local_service.py`; writes inside `BEGIN IMMEDIATE`; rollback on error.
- **Acceptance:** a behavior change adds or updates the matching `tools/*_acceptance.py`. Those scripts record each check as `{name, passed, detail}`, print a JSON report, write a receipt (for example `reports/application-verification.json`) and exit 0 only when every check passed. A receipt written outside `app/.data/` is a tracked file: say so in your summary.
