# professional-tree-surgeons.com

ID: `component_76fcea20fed4c657333c`

Custom domain routing to an actual Worker service

Category: **documented_current** · Evidence: **reported** · Observed condition: **unknown**

## Evidence boundary

Recorded resource identity; provider read does not prove runtime health.

## Source records

- `record_27e23becc77429dc0262`

## Evidence pointers

- `ev_5a840e30527c90cf1df5` — ASSET DIRECTORY row 215 (Saved source row; no new live test)
- `ev_50f017a13793f992f795` — S04-05 Cloudflare row 110 (Saved source row; no new live test)

## Recorded relationships

- `relationship_48c583349054df38cba5` · Worker service · `component_76fcea20fed4c657333c` → `component_318bd6fbbdeae5cb15aa` · configured
- `relationship_cd1315dfa0ba8b3655ff` · DNS zone · `component_76fcea20fed4c657333c` → `component_49a01490277e2d542929` · configured

## Open questions and issues

- `issue_75fa0e9387c7384484bb`: Current runtime health not established. Recorded resource identity; provider read does not prove runtime health.

Read bounded source detail with `python3 tools/catalog.py component <ID>` or `evidence <ID>`.
