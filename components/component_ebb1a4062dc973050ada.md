# increase-roas-oauth-gateway

ID: `component_ebb1a4062dc973050ada`

Capability: Worker; intended business purpose unknown

Category: **documented_current** · Evidence: **reported** · Observed condition: **unknown**

## Evidence boundary

Recorded resource identity; provider read does not prove runtime health.

## Source records

- `record_4e96c2677b1347cd7179`

## Evidence pointers

- `ev_9d7d5c8f734ebc311da6` — ASSET DIRECTORY row 194 (Saved source row; no new live test)
- `ev_abeec2b6dcdf62ed6388` — S04-05 Cloudflare row 89 (Saved source row; no new live test)

## Recorded relationships

- `relationship_f164fefeeec080d3b1dc` · Worker binding: d1 · `component_ebb1a4062dc973050ada` → `component_6552be7e6d238ce3a61a` · configured
- `relationship_643b27b1203a6eb47771` · Worker binding: service · `component_ebb1a4062dc973050ada` → `component_ebb1a4062dc973050ada` · configured
- `relationship_643b27b1203a6eb47771` · Worker binding: service · `component_ebb1a4062dc973050ada` → `component_ebb1a4062dc973050ada` · configured

## Open questions and issues

- `issue_b724185db3d5a98df6b5`: Current runtime health not established. Recorded resource identity; provider read does not prove runtime health.

Read bounded source detail with `python3 tools/catalog.py component <ID>` or `evidence <ID>`.
