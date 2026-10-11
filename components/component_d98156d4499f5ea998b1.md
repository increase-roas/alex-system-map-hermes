# Agent profiles and identity bindings narrow the master profile

ID: `component_d98156d4499f5ea998b1`

A derived agent profile constrains capabilities, filesystem roots, accounts, effects and command recipes; sourced bindings describe agent host, accounts and owned remote paths. The code rejects widening and mismatched tool bindings.

Category: **documented_current** · Evidence: **reported** · Observed condition: **unknown**

## Evidence boundary

A configured or caller-asserted account label is not proof of provider identity or current agent use.

## Source records


## Evidence pointers

- `ev_76f8f0cf63b4e2b47604` — FILE CATALOG row 930 (Saved source row; no new live test)

## Recorded relationships


## Open questions and issues

- `issue_a277049585263b9a1fed`: Current runtime health not established. A configured or caller-asserted account label is not proof of provider identity or current agent use.

Read bounded source detail with `python3 tools/catalog.py component <ID>` or `evidence <ID>`.
