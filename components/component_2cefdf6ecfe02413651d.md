# website-theme-matrix-qa-7-images

ID: `component_2cefdf6ecfe02413651d`

Capability: R2 bucket; intended business purpose unknown

Category: **documented_current** · Evidence: **reported** · Observed condition: **unknown**

## Evidence boundary

Recorded resource identity; provider read does not prove runtime health.

## Source records

- `record_99838ef73e75c095edb6`

## Evidence pointers

- `ev_8b8b45f8f0cc1f870306` — ASSET DIRECTORY row 164 (Saved source row; no new live test)
- `ev_75f5995ef139064db90c` — S04-05 Cloudflare row 59 (Saved source row; no new live test)

## Recorded relationships

- `relationship_fb935de8b9d57bd8a679` · Worker binding: r2_bucket · `component_eeaa52058d0117448a43` → `component_2cefdf6ecfe02413651d` · configured
- `relationship_167ba0831cb9330b0515` · Worker binding: r2_bucket · `component_e11fceb000878b57224f` → `component_2cefdf6ecfe02413651d` · configured

## Open questions and issues

- `issue_cb32ebe48ccc3e204061`: Current runtime health not established. Recorded resource identity; provider read does not prove runtime health.

Read bounded source detail with `python3 tools/catalog.py component <ID>` or `evidence <ID>`.
