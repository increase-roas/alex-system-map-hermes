| Check | Result | Detail |
| --- | --- | --- |
| `file:/Users/alexlobaito/Projects/alex-system-map-pro-map4/app/src/app/explorer/pro-map-guardrails/read_gate.py non-empty` | VERIFIED | 18554 bytes |
| `file:/Users/alexlobaito/Projects/alex-system-map-pro-map4/app/src/app/explorer/pro-map-guardrails/test_read_gate.py non-empty` | VERIFIED | 19335 bytes |
| `contains:/Users/alexlobaito/Projects/alex-system-map-pro-map4/app/src/app/explorer/pro-map-guardrails/read_gate.py::fcntl.flock` | VERIFIED | 1 occurrence(s) |
| `contains:/Users/alexlobaito/Projects/alex-system-map-pro-map4/app/src/app/explorer/pro-map-guardrails/read_gate.py::os.replace` | VERIFIED | 1 occurrence(s) |
| `contains:/Users/alexlobaito/Projects/alex-system-map-pro-map4/app/src/app/explorer/pro-map-guardrails/read_gate.py::truncatedByTokenCap` | VERIFIED | 4 occurrence(s) |
| `contains:/Users/alexlobaito/Projects/alex-system-map-pro-map4/app/src/app/explorer/pro-map-guardrails/read_gate.py::IS NOT a security boundary` | VERIFIED | 1 occurrence(s) |
| `absent:/Users/alexlobaito/Projects/alex-system-map-pro-map4/app/src/app/explorer/pro-map-guardrails/read_gate.py::import requests` | VERIFIED | 0 occurrence(s) |
| `cmd:python3 -B /Users/alexlobaito/Projects/alex-system-map-pro-map4/app/src/app/explorer/pro-map-guardrails/test_read_gate.py` | VERIFIED | exit 0; OK |
| `json:/Users/alexlobaito/Projects/alex-system-map-pro-map4/app/src/app/explorer/pro-map-guardrails/read-fixtures/test-results.json` | VERIFIED | valid JSON |
| `json:/Users/alexlobaito/Projects/alex-system-map-pro-map4/app/src/app/explorer/pro-map-guardrails/read-fixtures/schema-evidence.json` | VERIFIED | valid JSON |
| `cmd:python3 -B -c 'import json; from pathlib import Path; r=json.loads(Path("/Users/alexlobaito/Projects/alex-system-map-pro-map4/app/src/app/explorer/pro-map-guardrails/read-fixtures/test-results.json").read_text()); assert r["successful"] and r["tests_run"] == 31 and r["failures"] == 0 and r["errors"] == 0'` | VERIFIED | exit 0;  |
| `contains:/Users/alexlobaito/Projects/alex-system-map-pro-map4/app/src/app/explorer/pro-map-guardrails/read_gate.py::require(name in cfg['direct_tools'] or name in cfg['batches'])` | VERIFIED | 1 occurrence(s) |
| `json:/Users/alexlobaito/Projects/alex-system-map-pro-map4/app/src/app/explorer/pro-map-guardrails/read-fixtures/policy.example.json` | VERIFIED | valid JSON |
| `json:/Users/alexlobaito/Projects/alex-system-map-pro-map4/app/src/app/explorer/pro-map-guardrails/read-fixtures/settings.example.json` | VERIFIED | valid JSON |
