# pts-quote-funnel

ID: `component_318bd6fbbdeae5cb15aa`

Capability: Worker; intended business purpose unknown

Category: **documented_current** · Evidence: **reported** · Observed condition: **unknown**

## Evidence boundary

Recorded resource identity; provider read does not prove runtime health.

## Source records

- `record_1f150c6ed0172f992088`

## Evidence pointers

- `ev_354f31a0544a41d317f8` — ASSET DIRECTORY row 200 (Saved source row; no new live test)
- `ev_6f4a90e76de10fc178c7` — S04-05 Cloudflare row 95 (Saved source row; no new live test)

## Recorded relationships

- `relationship_48c583349054df38cba5` · Worker service · `component_76fcea20fed4c657333c` → `component_318bd6fbbdeae5cb15aa` · configured
- `relationship_77781b9b348337da1f83` · Worker service · `component_0f026319193f8a297946` → `component_318bd6fbbdeae5cb15aa` · configured
- `relationship_ffbea6a84a65a91da444` · Routes to Worker · `component_f8eea7ba238e541cf9f9` → `component_318bd6fbbdeae5cb15aa` · configured
- `relationship_79b7fed1f66f1db5e76b` · Routes to Worker · `component_788c25f23a224a748783` → `component_318bd6fbbdeae5cb15aa` · configured

## Open questions and issues

- `issue_4122160b6fe8d12cdf40`: Current runtime health not established. Recorded resource identity; provider read does not prove runtime health.

Read bounded source detail with `python3 tools/catalog.py component <ID>` or `evidence <ID>`.
