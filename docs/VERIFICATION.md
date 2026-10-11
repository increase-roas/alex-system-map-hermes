> October 9 accelerator revision: the latest user correction selects the supplied Next.js Pro app directly. Read `CURSOR_FAST_START.md` and `reports/cursor-accelerator-verification.md` for current preparation checks. Earlier Vite/three-skill statements in historical reports describe the prior handoff, not the current implementation direction. The original catalog/workflow proof remains separate from pending app runtime acceptance.

# Verification and repeatable checks

The foundation and the eventual application have separate acceptance boundaries.

## Foundation checks

From this folder, with Python 3.12+ and the dependencies in `requirements-validation.txt` available:

```sh
python3 tools/validate_schemas.py
python3 tools/validate_catalog.py
python3 tools/workflow_tests.py
```

Read `reports/catalog-validation.json`, `reports/schema-validation.json`, the workflow reports, and the independent verifier reports. The catalog validator compares against original workbook rows and actual archived file hashes. The workflow tests use temporary synthetic databases; they perform no customer work or external operations.

For a correction demonstration, run `python3 tools/workflow_demo.py`. Its recovery packet is explicitly synthetic. A fresh agent should use the packet and workflow skill to determine the next permitted step, rather than assume the earlier completed report is still acceptable.

## Reproducible derived views

`python3 tools/build_catalog.py --render-only` regenerates component pages and the companion workbook from canonical JSON. Compare Markdown bytes and workbook cell content, not ZIP timestamps inside XLSX. The initial full import is a separate reproducibility check and must not overwrite later maintained JSON edits.

## Pending Cursor application acceptance

The local server, authenticated owner/verifier context, React Flow interface, browser restart behavior, actual UI accessibility and visual checks are not implemented here. Cursor must test them using the handoff. Local reference-engine success does not establish cross-agent adoption or live fleet behavior.

Project skill frontmatter and native links can be checked locally. Fresh Codex/Cursor/Claude selection and remote delivery need their own observed proof. Opening this package in one editor does not install skills on other computers.
