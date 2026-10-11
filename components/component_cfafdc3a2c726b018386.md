# website-hot-tub-store-8

ID: `component_cfafdc3a2c726b018386`

Capability: Worker; intended business purpose unknown

Category: **documented_current** · Evidence: **reported** · Observed condition: **unknown**

## Evidence boundary

Recorded resource identity; provider read does not prove runtime health.

## Source records

- `record_4ec956942e238a812be9`

## Evidence pointers

- `ev_47be4cca7f8cb57c26f7` — ASSET DIRECTORY row 207 (Saved source row; no new live test)
- `ev_cfce91b60ae69846797f` — S04-05 Cloudflare row 102 (Saved source row; no new live test)

## Recorded relationships

- `relationship_265aec37aed901874d7c` · Worker binding: d1 · `component_cfafdc3a2c726b018386` → `component_38de329e1a6e7d05391c` · configured
- `relationship_b8c2e41e000d54fb6504` · Worker binding: r2_bucket · `component_cfafdc3a2c726b018386` → `component_f0c1a090816a31d97b9e` · configured
- `relationship_75479864760ffcfc72e7` · Worker binding: kv_namespace · `component_cfafdc3a2c726b018386` → `component_9cdcada6c8b3e78317aa` · configured
- `relationship_406892eab25a469d4b69` · Worker service · `component_25d286deb8ee1cf04343` → `component_cfafdc3a2c726b018386` · configured

## Open questions and issues

- `issue_4d93b90bd019af51ca2b`: Current runtime health not established. Recorded resource identity; provider read does not prove runtime health.

Read bounded source detail with `python3 tools/catalog.py component <ID>` or `evidence <ID>`.
