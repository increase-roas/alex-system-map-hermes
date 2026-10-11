# website-sun-pool-17-preview

ID: `component_8ab352dc97364d481b2a`

Capability: Worker; intended business purpose unknown

Category: **documented_current** · Evidence: **reported** · Observed condition: **unknown**

## Evidence boundary

Recorded resource identity; provider read does not prove runtime health.

## Source records

- `record_840143f6b5d452e7a26a`

## Evidence pointers

- `ev_936ac57f1fa5fd01bed0` — ASSET DIRECTORY row 209 (Saved source row; no new live test)
- `ev_c16fb5f14714fe7f7337` — S04-05 Cloudflare row 104 (Saved source row; no new live test)

## Recorded relationships

- `relationship_d336d75392a26461d1d8` · Worker binding: d1 · `component_8ab352dc97364d481b2a` → `component_233c4823a7782f8da323` · configured
- `relationship_b4689178365b2a981571` · Worker binding: r2_bucket · `component_8ab352dc97364d481b2a` → `component_355a1b78b01fd0aaf702` · configured
- `relationship_ca6b0b8a0de21dc620fd` · Worker binding: kv_namespace · `component_8ab352dc97364d481b2a` → `component_1a4847213021847fdef5` · configured

## Open questions and issues

- `issue_236390152bcc85f15fed`: Current runtime health not established. Recorded resource identity; provider read does not prove runtime health.

Read bounded source detail with `python3 tools/catalog.py component <ID>` or `evidence <ID>`.
