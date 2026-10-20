Same-provider context-separated acceptance. Formal other-family COMPLETE gate remains pending.

- Criterion 1: VERIFIED — Actual path/stat/hash sample and all required harness files readable. Evidence: actual-home-final.json.
- Criterion 2: VERIFIED — Fixture exact-vs-linked groups; generated source classification; actual790 shared groups. Evidence: browser-receipt.json; desktop-candidate-evidence.jpg; fairness-green.
- Criterion 3: VERIFIED — Candidate labels and four file/line excerpts shown at desktop and390px. No authority inference. Evidence: desktop-candidate-evidence.jpg; narrow-candidate-evidence.jpg.
- Criterion 4: VERIFIED — On-demand numbered current content, redaction, changed hash and stale displayed index warning. Scanner only writes its own snapshot. Evidence: desktop-stale-ui-warning.jpg; desktop-redacted-fixture.jpg; stale-ui-new-backend.json.
- Criterion 5: VERIFIED — Default/direct URL, search, filters, group selection, generated-source related navigation; no390px horizontal overflow. Evidence: browser-receipt.json; narrow-inventory.jpg.
- Criterion 6: VERIFIED — Visible included/excluded/limit/failure/partial coverage. Actual final scan3407 files; critical harness singletons preserved despite bounded skill trees. Evidence: actual-home-final.json; browser-receipt.json.
- Criterion 7: VERIFIED — Local200; nonlocal/cross-site/Tailscale403; arbitrary path400; invalid id404; unauth refresh401; valid token POST200. Evidence: api-checks.json; actual-home-final.json.
- Criterion 8: VERIFIED — Recorded focused9-test final pass inspected with source; independent negative probes; final TypeScript exit0 and real CUA proof. Evidence: machine-acceptance.md; adversarial-privacy-final.json; tsc-final.txt.

Machine acceptance table:

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

