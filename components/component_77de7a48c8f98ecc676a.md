# website-hot-tub-store-8-preview

ID: `component_77de7a48c8f98ecc676a`

Capability: Worker; intended business purpose unknown

Category: **documented_current** · Evidence: **reported** · Observed condition: **unknown**

## Evidence boundary

Recorded resource identity; provider read does not prove runtime health.

## Source records

- `record_67716ae94999aa7ba89a`

## Evidence pointers

- `ev_b2b763869afccbd8b575` — ASSET DIRECTORY row 208 (Saved source row; no new live test)
- `ev_ebb1575917f681b60ddd` — S04-05 Cloudflare row 103 (Saved source row; no new live test)

## Recorded relationships

- `relationship_4e002f38b8cc0e4a5318` · Worker binding: d1 · `component_77de7a48c8f98ecc676a` → `component_b488e09675fc182b48eb` · configured
- `relationship_3a59943e90c6b0fca36b` · Worker binding: r2_bucket · `component_77de7a48c8f98ecc676a` → `component_f0c1a090816a31d97b9e` · configured
- `relationship_9dac2a5e4aabd71c1455` · Worker binding: kv_namespace · `component_77de7a48c8f98ecc676a` → `component_ad121644855c05f22b19` · configured

## Open questions and issues

- `issue_bdfa8247c055ad0d000d`: Current runtime health not established. Recorded resource identity; provider read does not prove runtime health.

Read bounded source detail with `python3 tools/catalog.py component <ID>` or `evidence <ID>`.
