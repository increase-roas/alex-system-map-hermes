NODE: local-file-repairs
REVIEWER: gpt-6.1-sol, context-separated from implementers
SANDBOX: acceptance writes only disposable fixture sources, local bare remotes and named proof artifacts
VERDICT: VERIFIED for six frozen feature criteria

- Criterion 1: VERIFIED. Current fixture source and seven candidate excerpts opened. Generated Codex source routed to alpha; aliases, managed skills, screened and unsupported sources refused direct edits. Evidence: browser-receipt.json; evidence/api-negatives.json; evidence/generated-owner.jpg
- Criterion 2: VERIFIED. Exact Use this wording substitution preserved other text; stale/ambiguous wording kept draft. Frozen path/hashes/diff displayed before explicit browser Apply; source unchanged before Apply. Evidence: evidence/desktop-preview.jpg; browser-receipt.json; evidence/narrow-ambiguous.jpg; evidence/narrow-stale-evidence.jpg
- Criterion 3: VERIFIED. 22 negative/API checks exercised stale source/fingerprint, link swap, divergent actual bare remote, secret/body/token/path boundaries. Exact verified backup observed before successful replacement. Evidence: evidence/api-negatives.json; evidence/apply-readback.json
- Criterion 4: VERIFIED. Real one-path commit and bare remote blob/head readback matched frozen bytes and0640 mode. Unrelated staged/dirty files preserved. Apply replay reconciled; actual rejecting-push receipt stayed pending without retry. Evidence: evidence/apply-readback.json; evidence/replay-stale-undo.json; evidence/publish-pending-readback.json
- Criterion 5: VERIFIED. Real browser Undo restored exact preimage and remote blob; newer edit returned409 unchanged. Rejected restoration push was visible; Undo replay did not add commit/push. Evidence: evidence/undo-readback.json; evidence/replay-stale-undo.json; evidence/undo-publish-pending-readback.json; evidence/narrow-undo-publish-pending.jpg
- Criterion 6: VERIFIED. Recorded focused repair10 and scanner10 tests inspected against source; final TypeScript exit0, real desktop/390px browser,13 final source hashes. Actual inventory200 in9.517s; six canonical sources editable; generated Codex has three owners. No actual agent Preview/Apply/Undo. Evidence: machine-acceptance.md; source-manifest.json; evidence/actual-readonly-source-flags.json

Native rules-only post-commit prerequisite is parent-owned independent review. This lane did not execute the live generator.
Main3201 integrated browser check: pending parent fast-forward; no actual Preview/Apply will be sent.
Temporary3203 fixture server stopped; fixture cleanup follows parent readback and integrated browser check.

Machine checks:
| Check | Result | Detail |
| --- | --- | --- |
| `json:reviews/receipts/20261020-local-file-repairs/source-manifest.json` | VERIFIED | valid JSON |
| `json:reviews/receipts/20261020-local-file-repairs/browser-receipt.json` | VERIFIED | valid JSON |
| `contains:reviews/receipts/20261020-local-file-repairs/evidence/local-file-repairs-green.txt::Ran 10 tests` | VERIFIED | 1 occurrence(s) |
| `contains:reviews/receipts/20261020-local-file-repairs/evidence/local-files-performance-green.txt::Ran 10 tests` | VERIFIED | 1 occurrence(s) |
| `absent:reviews/receipts/20261020-local-file-repairs/evidence/local-file-repairs-green.txt::FAILED` | VERIFIED | 0 occurrence(s) |
| `cmd:cd app && ./node_modules/.bin/tsc --noEmit > ../reviews/receipts/20261020-local-file-repairs/evidence/tsc-final.txt 2>&1` | VERIFIED | exit 0;  |
| `cmd:python3 -c 'import pathlib,json,hashlib; p=pathlib.Path("reviews/receipts/20261020-local-file-repairs"); m=json.loads((p/"source-manifest.json").read_text()); assert len(m["files"])==13 and all(pathlib.Path(x["path"]).stat().st_size==x["bytes"] and hashlib.sha256(pathlib.Path(x["path"]).read_bytes()).hexdigest()==x["sha256"] for x in m["files"]); a=json.loads((p/"evidence/actual-readonly-source-flags.json").read_text()); assert a["inventory_status"]==200 and a["inventory_seconds"]<60 and all(x["editable"] for x in a["canonical_source_flags"]) and not a["generated_codex"]["editable"] and a["generated_codex"]["owner_count"]==3'` | VERIFIED | exit 0;  |

