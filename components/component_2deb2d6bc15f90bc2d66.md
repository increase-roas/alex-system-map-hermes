# website-harbor-heat-15-preview-inventory

ID: `component_2deb2d6bc15f90bc2d66`

Capability: D1 database; intended business purpose unknown

Category: **documented_current** · Evidence: **reported** · Observed condition: **unknown**

## Evidence boundary

Recorded resource identity; provider read does not prove runtime health.

## Source records

- `record_72614f01c2cdac835b70`

## Evidence pointers

- `ev_2001ab313dd45cc223b9` — ASSET DIRECTORY row 116 (Saved source row; no new live test)
- `ev_75939ac1092bc197956a` — S04-05 Cloudflare row 11 (Saved source row; no new live test)

## Recorded relationships

- `relationship_37339763ecf7e90a52fc` · Worker binding: d1 · `component_e1ae60fbd01e2b51be7f` → `component_2deb2d6bc15f90bc2d66` · configured

## Open questions and issues

- `issue_9b73de4a566b62206889`: Current runtime health not established. Recorded resource identity; provider read does not prove runtime health.

Read bounded source detail with `python3 tools/catalog.py component <ID>` or `evidence <ID>`.
