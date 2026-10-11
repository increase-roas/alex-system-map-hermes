# htl-dashboard-connection-monitor

ID: `component_5db35cf2f5e8d8165916`

Capability: Worker; intended business purpose unknown

Category: **documented_current** · Evidence: **reported** · Observed condition: **unknown**

## Evidence boundary

Recorded resource identity; provider read does not prove runtime health.

## Source records

- `record_1807438e72acd464118e`

## Evidence pointers

- `ev_03e080dbc68a9a58e820` — ASSET DIRECTORY row 189 (Saved source row; no new live test)
- `ev_20a261d9f28dba445df3` — S04-05 Cloudflare row 84 (Saved source row; no new live test)

## Recorded relationships

- `relationship_d8c7a0e1221306c3fe27` · Worker binding: kv_namespace · `component_5db35cf2f5e8d8165916` → `component_b2c090cee616dce47638` · configured

## Open questions and issues

- `issue_0c953c954b5f6f52173c`: Current runtime health not established. Recorded resource identity; provider read does not prove runtime health.

Read bounded source detail with `python3 tools/catalog.py component <ID>` or `evidence <ID>`.
