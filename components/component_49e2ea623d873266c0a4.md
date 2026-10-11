# Javar EA Tunnel

ID: `component_49e2ea623d873266c0a4`

Capability: Tunnel; intended business purpose unknown

Category: **documented_current** · Evidence: **reported** · Observed condition: **unknown**

## Evidence boundary

Recorded resource identity; provider read does not prove runtime health.

## Source records

- `record_9e767ea52eb538d8817c`

## Evidence pointers

- `ev_cdb37defcf73ca4cf255` — ASSET DIRECTORY row 165 (Saved source row; no new live test)
- `ev_4313bb2dff1b1e2c96b3` — S04-05 Cloudflare row 60 (Saved source row; no new live test)

## Recorded relationships

- `relationship_45b8760334abffc5d3df` · Tunnel ingress · `component_49e2ea623d873266c0a4` → `reference_9d63c1c9a4e3274f0392` · configured
- `relationship_019e1036407a0e3c45dc` · Tunnel ingress · `component_49e2ea623d873266c0a4` → `reference_c445fc86ff60891d5941` · configured

## Open questions and issues

- `issue_128d44df729c5cf6b7ab`: Current runtime health not established. Recorded resource identity; provider read does not prove runtime health.

Read bounded source detail with `python3 tools/catalog.py component <ID>` or `evidence <ID>`.
