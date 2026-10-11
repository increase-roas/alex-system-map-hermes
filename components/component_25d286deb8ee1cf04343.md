# increaseroasai.com

ID: `component_25d286deb8ee1cf04343`

Custom domain routing to an actual Worker service

Category: **documented_current** · Evidence: **reported** · Observed condition: **unknown**

## Evidence boundary

Recorded resource identity; provider read does not prove runtime health.

## Source records

- `record_f83d888bd8303867d917`

## Evidence pointers

- `ev_0c9163e67058ba6bde29` — ASSET DIRECTORY row 214 (Saved source row; no new live test)
- `ev_2a5aec576e31e81f77b1` — S04-05 Cloudflare row 109 (Saved source row; no new live test)

## Recorded relationships

- `relationship_406892eab25a469d4b69` · Worker service · `component_25d286deb8ee1cf04343` → `component_cfafdc3a2c726b018386` · configured
- `relationship_91a174fee5d84bc54d32` · DNS zone · `component_25d286deb8ee1cf04343` → `component_fb0c0ffaec983d66f9c7` · configured

## Open questions and issues

- `issue_d518be5f7fc0075bd456`: Current runtime health not established. Recorded resource identity; provider read does not prove runtime health.

Read bounded source detail with `python3 tools/catalog.py component <ID>` or `evidence <ID>`.
