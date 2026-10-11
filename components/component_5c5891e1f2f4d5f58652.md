# dev-rag-worker

ID: `component_5c5891e1f2f4d5f58652`

Capability: Worker; intended business purpose unknown

Category: **documented_current** · Evidence: **reported** · Observed condition: **unknown**

## Evidence boundary

Recorded resource identity; provider read does not prove runtime health.

## Source records

- `record_3de7d3cf065277f2646a`

## Evidence pointers

- `ev_a166a861a4cad23886f6` — ASSET DIRECTORY row 183 (Saved source row; no new live test)
- `ev_e0b53abe580b07689413` — S04-05 Cloudflare row 78 (Saved source row; no new live test)

## Recorded relationships

- `relationship_f5c0dec284cbc7201d3d` · Worker binding: durable_object_namespace · `component_5c5891e1f2f4d5f58652` → `component_94dbd10d38b8c2d6272c` · configured
- `relationship_e5db5bee04bd80bbf249` · Worker service · `component_0de0f4f0d6bfdb4ebd95` → `component_5c5891e1f2f4d5f58652` · configured
- `relationship_89254d445479dee93945` · Worker service · `component_fdd1b98981274debf1be` → `component_5c5891e1f2f4d5f58652` · configured

## Open questions and issues

- `issue_c30f7646165e8875d1c2`: Current runtime health not established. Recorded resource identity; provider read does not prove runtime health.

Read bounded source detail with `python3 tools/catalog.py component <ID>` or `evidence <ID>`.
