# Browser proof (pending complete Chromium install)

API acceptance passes in `reports/application-verification.json`. UI screenshots require a **complete** Playwright browser under `app/.playwright-browsers/`.

On this host, a partial Chromium download may leave the framework binary missing (`Google Chrome for Testing Framework` dlopen error). **Do not block reliability or API work on an incomplete download.** The verifier assesses already-installed routes read-only (project Chrome-for-Testing binary if present, else system Google Chrome) and parses `report.json` checks (status `PASS`, screenshot files exist)—report file presence alone is not a pass.

When you choose to finish install locally:

```sh
cd app
PLAYWRIGHT_BROWSERS_PATH=$PWD/.playwright-browsers npx playwright install chromium
# optional headless shell:
PLAYWRIGHT_BROWSERS_PATH=$PWD/.playwright-browsers npx playwright install chromium-headless-shell

npx next start -p 3200
# separate terminal from repo root:
PLAYWRIGHT_BROWSERS_PATH=app/.playwright-browsers SKIP_SERVER_START=1 BROWSER_TEST_PORT=3200 node tools/browser_acceptance.mjs
```

Success writes `report.json` and PNGs in this folder.
