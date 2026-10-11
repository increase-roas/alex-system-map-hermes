# mcp-hub

ID: `component_3bd5d672fe1dbec783f9`

Capability: Tunnel; intended business purpose unknown

Category: **documented_current** · Evidence: **reported** · Observed condition: **unknown**

## Evidence boundary

Recorded resource identity; provider read does not prove runtime health.

## Source records

- `record_90a3bbeec211081f920d`

## Evidence pointers

- `ev_2ad311a54aaa827b5907` — ASSET DIRECTORY row 168 (Saved source row; no new live test)
- `ev_22270928933256cb47b1` — S04-05 Cloudflare row 63 (Saved source row; no new live test)

## Recorded relationships

- `relationship_fd81eff32c743a8d73fc` · Tunnel ingress · `component_3bd5d672fe1dbec783f9` → `reference_fea87b1b64212bc5b81f` · configured

## Open questions and issues

- `issue_e27ba7676c8cf92f3dd9`: Current runtime health not established. Recorded resource identity; provider read does not prove runtime health.

Read bounded source detail with `python3 tools/catalog.py component <ID>` or `evidence <ID>`.
