# dev-rag.increaseroas.com

ID: `component_0de0f4f0d6bfdb4ebd95`

Custom domain routing to an actual Worker service

Category: **documented_current** · Evidence: **reported** · Observed condition: **unknown**

## Evidence boundary

Recorded resource identity; provider read does not prove runtime health.

## Source records

- `record_182b69dd69bcfd0dd624`

## Evidence pointers

- `ev_ffe3b1c9f5d70a768b7e` — ASSET DIRECTORY row 212 (Saved source row; no new live test)
- `ev_51403c0b96c721d9a4a5` — S04-05 Cloudflare row 107 (Saved source row; no new live test)

## Recorded relationships

- `relationship_e5db5bee04bd80bbf249` · Worker service · `component_0de0f4f0d6bfdb4ebd95` → `component_5c5891e1f2f4d5f58652` · configured
- `relationship_8f924f42e770f7e21310` · DNS zone · `component_0de0f4f0d6bfdb4ebd95` → `component_3dd0b312aa826f153328` · configured

## Open questions and issues

- `issue_64689bac449019e2fbfe`: Current runtime health not established. Recorded resource identity; provider read does not prove runtime health.

Read bounded source detail with `python3 tools/catalog.py component <ID>` or `evidence <ID>`.
