# Tested map examples, not an installation

These are the exact Python scripts displayed in the Version 2 and Hermes cards.
`bundle.py` creates the browser copy; `bundle.py --check` rejects drift.
Nothing here installs hooks in Alex's real apps or grants connector access.

## Covered decisions

- `asset_guard.py`: before Claude Write/Edit, validate proposed skills, MCP configuration, scoped/global rules, subagent definitions and targeted settings shape. After tools and at Stop, rescan for changes made by other writers. No rollback. The strict description wording, writing caps and explicit scope/tools requirements are custom policy.
- `read_gate.py`: require a full, successful Read result for every card needed by an exact direct tool or every action in a configured batch. A denied call or retry never creates proof. Unknown names, changed cards, partial reads and corrupt state block.
- `hermes_guard.py`: native Hermes envelope, selected profile config/skills, complete successful read_file receipts and exact mapped MCP routes. This restricted adapter blocks unsupported batch/terminal/patch/delegation/skill_manage routes, rather than pretend to check them. It is not a drop-in policy for the whole Hermes workflow.

## Setup is explicit

Copy the scripts displayed in the cards, merge the displayed hook settings, and replace the example routes and absolute paths with discovered values. Create the non-empty connector cards first. The map's GHL/GitHub action names are illustrative, not live discovery.

Claude needs Python 3.9+ on macOS/Linux, and Claude Code 2.1.295+ for the shown onFailure:block behavior. The scripts are invoked through Python, so chmod +x and jq are not needed. Export READ_GATE_STATE_DIR before starting Claude. It must name an existing 0700 directory outside the project owned by the hook runtime. A same-user agent can still tamper with same-user files: real enforcement needs protected settings, script, policy, state and unguarded-route restrictions.

Hermes needs the active HERMES_HOME/profile and consent to each hook event/command. JSON-formatted YAML works with the standard library. Ordinary YAML requires PyYAML in the same interpreter; that dependency was not installed or tested here. Use the script's --print-hook-config to generate correctly quoted paths. Post-tool observers do not undo work; pre_verify is a bounded edited-code continuation request.

Never list a batch, code-execution or remote-shell wrapper in read_gate direct_tools. Give a batch its own exact adapter and enumerate every action. Client/account identity and spend/send/delete approval are separate checks, not supplied by a read receipt.

## Re-run proof (from app/)

```
python3 -B src/app/explorer/pro-map-guardrails/run_all.py
node src/app/explorer/pro-map-guardrails/check_registration.cjs
python3 -B src/app/explorer/pro-map-guardrails/bundle.py
python3 -B src/app/explorer/pro-map-guardrails/bundle.py --check
node src/app/explorer/pro-map-audit-check.cjs --exercise-hooks
node node_modules/typescript/bin/tsc --noEmit -p . --incremental false
```

The tests write only fixture directories/receipts beside these files. They make no real model or connector calls. `test-receipt.json` binds test results to source hashes. `registration-receipt.json` covers the displayed command strings, not an installed native runtime. The map audit checks that the displayed scripts still match those tested files and that Alex/v1 cards remain unchanged.

Keep .audit-backup and registration-fixture directories out of the eventual app release; retained review evidence is not runtime configuration. Claude owns final review, commit and merge.

## Upkeep still needed for a real deployment

These templates retain session/replay records. Use a dedicated state directory per supervised job and retain it until all related sessions are closed. Only then archive its evidence and retire it. Do not delete active-session records to save space. Long-lived shared state and repeated full scans need measured production tuning; no latency or fleet-scale claim is made.
