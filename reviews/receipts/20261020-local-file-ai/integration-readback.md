# Main integration readback

- VERIFIED: canonical main HEAD `fe0b9648c5763aee3ea8f09c55dec9ce4b3cd9b6`; all 10 reviewed source hashes match the final source manifest.
- VERIFIED: `http://127.0.0.1:3201/explorer?view=local-files` returns HTTP 200 HTML. Real Chrome DOM loads Local files, shows 3,404 files in the bounded inventory and an enabled Refresh button. The existing partial-coverage notice is visible; this page check does not claim whole-machine coverage.
- VERIFIED: no file selected, no repair panel opened, no AI/Preview/Apply/Undo requested, no source content displayed. Screenshot is cropped to inventory chrome and metadata.
- VERIFIED: owned tab closed, temporary viewport override reset, live 3201 service left running. No tests repeated, source edits or commits performed.

Evidence: `integration-readback.json`, `integration-inventory.jpg`. The earlier frozen worktree proof is unchanged.

| Check | Result | Detail |
| --- | --- | --- |
| `json:reviews/receipts/20261020-local-file-ai/integration-readback.json` | VERIFIED | valid JSON |
| `file:reviews/receipts/20261020-local-file-ai/integration-inventory.jpg non-empty` | VERIFIED | 74731 bytes |
| `contains:reviews/receipts/20261020-local-file-ai/integration-readback.json::"source_manifest_mismatches": []` | VERIFIED | 1 occurrence(s) |
| `contains:reviews/receipts/20261020-local-file-ai/integration-readback.json::"repair_panel_count": 0` | VERIFIED | 1 occurrence(s) |
