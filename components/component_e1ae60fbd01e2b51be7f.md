# website-harbor-heat-15-preview

ID: `component_e1ae60fbd01e2b51be7f`

Capability: Worker; intended business purpose unknown

Category: **documented_current** · Evidence: **reported** · Observed condition: **unknown**

## Evidence boundary

Recorded resource identity; provider read does not prove runtime health.

## Source records

- `record_f368356f04a052ec3071`

## Evidence pointers

- `ev_1cede720392b45f5a0e9` — ASSET DIRECTORY row 206 (Saved source row; no new live test)
- `ev_39fd4f80bf6567bb0d13` — S04-05 Cloudflare row 101 (Saved source row; no new live test)

## Recorded relationships

- `relationship_37339763ecf7e90a52fc` · Worker binding: d1 · `component_e1ae60fbd01e2b51be7f` → `component_2deb2d6bc15f90bc2d66` · configured
- `relationship_7613a2a0ec38b7fcdf3f` · Worker binding: r2_bucket · `component_e1ae60fbd01e2b51be7f` → `component_963c983722f6d75d21a3` · configured
- `relationship_cbfdb6d345883925d363` · Worker binding: kv_namespace · `component_e1ae60fbd01e2b51be7f` → `component_a4e78d5e9b17387a14ca` · configured

## Open questions and issues

- `issue_98e6aee06545b72c10ba`: Current runtime health not established. Recorded resource identity; provider read does not prove runtime health.

Read bounded source detail with `python3 tools/catalog.py component <ID>` or `evidence <ID>`.
