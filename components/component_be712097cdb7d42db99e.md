# funnel.hottublaunch.com/*

ID: `component_be712097cdb7d42db99e`

Zone path pattern routing to an actual Worker script

Category: **documented_current** · Evidence: **reported** · Observed condition: **unknown**

## Evidence boundary

Recorded resource identity; provider read does not prove runtime health.

## Source records

- `record_bd54931eec1833c8e055`

## Evidence pointers

- `ev_2bf0840777ce7376ff08` — ASSET DIRECTORY row 219 (Saved source row; no new live test)
- `ev_88a172981c6693cbbc76` — S04-05 Cloudflare row 114 (Saved source row; no new live test)

## Recorded relationships

- `relationship_5e89c7d8b1d6a266f36e` · Routes to Worker · `component_be712097cdb7d42db99e` → `component_88d29b98f492687da903` · configured

## Open questions and issues

- `issue_ca20a0acbd2b9464c551`: Current runtime health not established. Recorded resource identity; provider read does not prove runtime health.

Read bounded source detail with `python3 tools/catalog.py component <ID>` or `evidence <ID>`.
