# Local intent ledgers, stable operation IDs, resume, and same-ledger locking exist

ID: `component_aca3edbd89cea870f8d9`

The workflow stores a manifest keyed by operation ID and detects a changed manifest; operation services retain durable receipts and reconcile uncertain memory writes; local locks serialize access to the same ledger/root.

Category: **documented_current** · Evidence: **reported** · Observed condition: **unknown**

## Evidence boundary

These controls do not demonstrate distributed ownership, cross-agent stale-attempt prevention, or successful recovery after interruption on both target runtimes.

## Source records


## Evidence pointers

- `ev_fe6125340acd4c479fbd` — FILE CATALOG row 939 (Saved source row; no new live test)

## Recorded relationships


## Open questions and issues

- `issue_2b42e0ac45a272f92cf7`: Current runtime health not established. These controls do not demonstrate distributed ownership, cross-agent stale-attempt prevention, or successful recovery after interruption on both target runtimes.

Read bounded source detail with `python3 tools/catalog.py component <ID>` or `evidence <ID>`.
