| Check | Result | Detail |
| --- | --- | --- |
| `json:reviews/receipts/20261020-local-file-repairs/source-manifest.json` | VERIFIED | valid JSON |
| `json:reviews/receipts/20261020-local-file-repairs/browser-receipt.json` | VERIFIED | valid JSON |
| `contains:reviews/receipts/20261020-local-file-repairs/evidence/local-file-repairs-green.txt::Ran 10 tests` | VERIFIED | 1 occurrence(s) |
| `contains:reviews/receipts/20261020-local-file-repairs/evidence/local-files-performance-green.txt::Ran 10 tests` | VERIFIED | 1 occurrence(s) |
| `absent:reviews/receipts/20261020-local-file-repairs/evidence/local-file-repairs-green.txt::FAILED` | VERIFIED | 0 occurrence(s) |
| `cmd:cd app && ./node_modules/.bin/tsc --noEmit > ../reviews/receipts/20261020-local-file-repairs/evidence/tsc-final.txt 2>&1` | VERIFIED | exit 0;  |
| `cmd:python3 -c 'import pathlib,json,hashlib; p=pathlib.Path("reviews/receipts/20261020-local-file-repairs"); m=json.loads((p/"source-manifest.json").read_text()); assert len(m["files"])==13 and all(pathlib.Path(x["path"]).stat().st_size==x["bytes"] and hashlib.sha256(pathlib.Path(x["path"]).read_bytes()).hexdigest()==x["sha256"] for x in m["files"]); a=json.loads((p/"evidence/actual-readonly-source-flags.json").read_text()); assert a["inventory_status"]==200 and a["inventory_seconds"]<60 and all(x["editable"] for x in a["canonical_source_flags"]) and not a["generated_codex"]["editable"] and a["generated_codex"]["owner_count"]==3'` | VERIFIED | exit 0;  |
