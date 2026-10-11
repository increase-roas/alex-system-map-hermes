# htl-client-dashboard-tenants

ID: `component_b2c090cee616dce47638`

Capability: KV namespace; intended business purpose unknown

Category: **documented_current** · Evidence: **reported** · Observed condition: **unknown**

## Evidence boundary

Recorded resource identity; provider read does not prove runtime health.

## Source records

- `record_3a32129483411cb9f80f`

## Evidence pointers

- `ev_0b6376a84150423ac84b` — ASSET DIRECTORY row 137 (Saved source row; no new live test)
- `ev_a0dcf346c87f68fdea17` — S04-05 Cloudflare row 32 (Saved source row; no new live test)

## Recorded relationships

- `relationship_d8c7a0e1221306c3fe27` · Worker binding: kv_namespace · `component_5db35cf2f5e8d8165916` → `component_b2c090cee616dce47638` · configured

## Open questions and issues

- `issue_28bb11d04bb1e3a4373a`: Current runtime health not established. Recorded resource identity; provider read does not prove runtime health.

Read bounded source detail with `python3 tools/catalog.py component <ID>` or `evidence <ID>`.
