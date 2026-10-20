| Check | Result | Detail |
| --- | --- | --- |
| `file:app/src/app/explorer/local-files-panel.tsx non-empty` | VERIFIED | 17993 bytes |
| `file:app/src/app/api/local-files/route.ts non-empty` | VERIFIED | 1513 bytes |
| `json:app/.data/local-files-acceptance/source-manifest.json` | VERIFIED | valid JSON |
| `json:app/.data/local-files-acceptance/actual-home-final.json` | VERIFIED | valid JSON |
| `json:app/.data/local-files-acceptance/browser-receipt.json` | VERIFIED | valid JSON |
| `contains:/private/tmp/local-files-fairness-green.txt::Ran 9 tests` | VERIFIED | 1 occurrence(s) |
| `contains:/private/tmp/local-files-fairness-green.txt::OK` | VERIFIED | 1 occurrence(s) |
| `absent:/private/tmp/local-files-fairness-green.txt::FAILED` | VERIFIED | 0 occurrence(s) |
| `cmd:cd app && ./node_modules/.bin/tsc --noEmit > .data/local-files-acceptance/tsc-final.txt 2>&1` | VERIFIED | exit 0;  |
| `cmd:python3 -c 'import json,pathlib,hashlib; p=pathlib.Path("app/.data/local-files-acceptance"); m=json.loads((p/"source-manifest.json").read_text()); assert all(pathlib.Path(x["path"]).stat().st_size==x["bytes"] and hashlib.sha256(pathlib.Path(x["path"]).read_bytes()).hexdigest()==x["sha256"] for x in m["files"]); a=json.loads((p/"actual-home-final.json").read_text()); assert all(a["critical_files_readable"].values()) and all(a["metadata_sample"].values()) and a["authenticated_refresh_status"]==200 and a["snapshot_after_scanner"]'` | VERIFIED | exit 0;  |
