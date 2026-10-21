| Check | Result | Detail |
| --- | --- | --- |
| `cmd:PYTHONPATH=tools python3 -B -m unittest test_local_file_ai.AITests.test_all_tool_feature_defaults_explicitly_disabled test_local_file_ai.AITests.test_catalog_disables_model_tools_preserving_metadata_and_live_bytes test_local_file_ai.AITests.test_catalog_missing_model_static_failure_without_fallback test_local_file_ai.AITests.test_command_disables_direct_nonfeature_tools_and_binds_temp_catalog > reviews/receipts/20261020-local-file-ai/independent-isolation-green.log 2>&1` | VERIFIED | exit 0;  |
| `cmd:python3 reviews/receipts/20261020-local-file-ai/final-proof.py` | VERIFIED | exit 0; } |
| `json:reviews/receipts/20261020-local-file-ai/source-manifest.json` | VERIFIED | valid JSON |
| `json:reviews/receipts/20261020-local-file-ai/final-native-inference.json` | VERIFIED | valid JSON |
| `contains:reviews/receipts/20261020-local-file-ai/independent-focused-green.log::Ran 35 tests` | VERIFIED | 1 occurrence(s) |
| `contains:reviews/receipts/20261020-local-file-ai/backend-catalog-green.log::Ran 39 tests` | VERIFIED | 1 occurrence(s) |
| `contains:reviews/receipts/20261020-local-file-ai/provider-failure-dom.txt::Try AI again` | VERIFIED | 1 occurrence(s) |
| `file:reviews/receipts/20261020-local-file-ai/desktop-proposal.jpg non-empty` | VERIFIED | 117004 bytes |
| `file:reviews/receipts/20261020-local-file-ai/narrow-applied.jpg non-empty` | VERIFIED | 63828 bytes |
| `absent:tools/local_file_ai.py::dangerously-bypass-approvals-and-sandbox` | VERIFIED | 0 occurrence(s) |
