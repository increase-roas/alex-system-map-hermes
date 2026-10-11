# Application verification (local)

Run from foundation root:

```sh
python3 tools/workflow_tests.py
python3 tools/app_acceptance.py
cd app && npx pnpm@9 run build
cd app && npx next start -p 3000
```

Open `http://127.0.0.1:3000/explorer` (root redirects).

Machine-readable results: `reports/application-verification.json`.

**Note:** Full catalog edge loading remains blocked until `data/relationships.json` is readable locally (see `reports/application-gaps.md`).
