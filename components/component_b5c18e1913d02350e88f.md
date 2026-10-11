# hottublaunch-main

ID: `component_b5c18e1913d02350e88f`

Capability: Worker; intended business purpose unknown

Category: **documented_current** · Evidence: **reported** · Observed condition: **unknown**

## Evidence boundary

Recorded resource identity; provider read does not prove runtime health.

## Source records

- `record_b91ca390dea18e51146b`

## Evidence pointers

- `ev_45fd003004b14db0ecff` — ASSET DIRECTORY row 187 (Saved source row; no new live test)
- `ev_8d69c254317a50364088` — S04-05 Cloudflare row 82 (Saved source row; no new live test)

## Recorded relationships

- `relationship_62f8be42432ae1b785dd` · Worker binding: d1 · `component_b5c18e1913d02350e88f` → `component_57084195b42eb46b2ff6` · configured
- `relationship_5bdfa59cbd6f6787e982` · Routes to Worker · `component_9d37adb8daaeea49b941` → `component_b5c18e1913d02350e88f` · configured
- `relationship_6fa030c240b19e0517c8` · Routes to Worker · `component_cf63877770d95a8f9766` → `component_b5c18e1913d02350e88f` · configured

## Open questions and issues

- `issue_7a3b094ada38ae39634f`: Current runtime health not established. Recorded resource identity; provider read does not prove runtime health.

Read bounded source detail with `python3 tools/catalog.py component <ID>` or `evidence <ID>`.
