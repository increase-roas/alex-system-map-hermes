# dev-rag.increaseroas.ai

ID: `component_fdd1b98981274debf1be`

Custom domain routing to an actual Worker service

Category: **documented_current** · Evidence: **reported** · Observed condition: **unknown**

## Evidence boundary

Recorded resource identity; provider read does not prove runtime health.

## Source records

- `record_153a082ee05ebcfb1c7d`

## Evidence pointers

- `ev_81158d19b1f78d5b8e3a` — ASSET DIRECTORY row 213 (Saved source row; no new live test)
- `ev_17652a68b3ffbd676a49` — S04-05 Cloudflare row 108 (Saved source row; no new live test)

## Recorded relationships

- `relationship_89254d445479dee93945` · Worker service · `component_fdd1b98981274debf1be` → `component_5c5891e1f2f4d5f58652` · configured
- `relationship_7696251aad0fa478f3ac` · DNS zone · `component_fdd1b98981274debf1be` → `component_a76ada145529b2bd281d` · configured

## Open questions and issues

- `issue_c2430dc6301aa05d935e`: Current runtime health not established. Recorded resource identity; provider read does not prove runtime health.

Read bounded source detail with `python3 tools/catalog.py component <ID>` or `evidence <ID>`.
