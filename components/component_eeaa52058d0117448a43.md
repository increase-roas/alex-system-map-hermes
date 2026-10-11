# website-theme-matrix-qa-7

ID: `component_eeaa52058d0117448a43`

Capability: Worker; intended business purpose unknown

Category: **documented_current** · Evidence: **reported** · Observed condition: **unknown**

## Evidence boundary

Recorded resource identity; provider read does not prove runtime health.

## Source records

- `record_80fbcf36ce8502041962`

## Evidence pointers

- `ev_81304c5897a8e3b24697` — ASSET DIRECTORY row 210 (Saved source row; no new live test)
- `ev_3149d29fca60f19e6af6` — S04-05 Cloudflare row 105 (Saved source row; no new live test)

## Recorded relationships

- `relationship_0b356aaa2105b25fda7f` · Worker binding: d1 · `component_eeaa52058d0117448a43` → `component_e2fb2e3dc0a20538d878` · configured
- `relationship_fb935de8b9d57bd8a679` · Worker binding: r2_bucket · `component_eeaa52058d0117448a43` → `component_2cefdf6ecfe02413651d` · configured
- `relationship_c644dd75d81ea5ef77cd` · Worker binding: kv_namespace · `component_eeaa52058d0117448a43` → `component_2cf6d65bb41fd3d6d122` · configured

## Open questions and issues

- `issue_706a708cb05be9d4e8ae`: Current runtime health not established. Recorded resource identity; provider read does not prove runtime health.

Read bounded source detail with `python3 tools/catalog.py component <ID>` or `evidence <ID>`.
