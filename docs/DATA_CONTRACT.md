# System catalog contract — 1.0.0

The exchange standard is JSON Schema 2020-12. Each collection is `{ "schema_version": "1.0.0", "records": [...] }`. Schemas live in `schemas/`. Workflow state and requests use the separate [workflow contract](WORKFLOW_CONTRACT.md).

## Collections and identity

| Collection | Responsibility |
|---|---|
| `components` | Immutable ID, display name, aliases, layer, kind, purpose, boundary, state dimensions, record/evidence IDs |
| `relationships` | Explicit source ID, target ID, relationship type, label, evidence, resolution and state dimensions |
| `evidence` | Exact source, workbook coordinates, raw cell claims/comments/links, observed date and proof scope |
| `sources` | Original archive member, recorded hash, reader pointer and original location; package inputs have relative paths |
| `source-records` | Loss-aware transcription of every coverage row and linked full asset row |
| `coverage` | Every original inventory record's placement, component and source identity |
| `issues` | Named gaps and dated findings; current health unknown is informational, not a failure |
| `table-index` | Bounded access to every original workbook tab in `data/tables/` |
| `layers` | Eight explanatory layers in top-down order |

Initial IDs are derived from existing identity keys or names under an explicit namespace. **After import, preserve the ID across renames.** Do not regenerate an ID because its display name, evidence or position changed. Merge only after identity reconciliation; retain old IDs as aliases and retarget references in one reviewed change. Identical asset keys share an entity while all source observations remain separate. Conflicting observations are not resolved by file modification time.

`category` is one of `documented_current`, `historical`, `planned`, `unresolved`. It describes the record in the saved snapshot. `evidence_level` is `reported`, `configured`, `tested`, or `unverified`. `observed_condition` is `working`, `failing`, `blocked`, or `unknown`. A stronger state needs dated, scoped evidence; no component is marked currently working by this import. Keep original source wording beside normalized state.

## Edges and containment

Only the explicit Relationships source table generates factual edges in this initial import. Unmatched endpoints get stable unresolved-reference records, scoped to their source where the same localhost string could identify different machines. Do not collapse localhost endpoints from different origins.

The 201 Worker Binding Fields rows expose names/types without target values. They remain table evidence and a visible issue, never credential edges. Saved prose such as 1Password usage remains available with original dates; it is not automatically parsed into verified consumers.

`views/overview.json` stores ordering and memberships. Membership means explanatory placement and is not an execution relationship. Layout coordinates, zoom and collapse preferences belong to separate view state. System relationship graphs may cycle. Workflow dependency graphs may not.

## Updates and regeneration

`tools/catalog.py` is read-only. Before Cursor builds the authenticated local write API, authorized catalog edits are scoped file changes: back up affected canonical JSON, preserve IDs/evidence/history, add a correction/issue when needed, validate schemas and references, regenerate derived pages/XLSX with `tools/build_catalog.py --render-only`, and compare the results. This is a single-editor foundation workflow, not a concurrency-safe JSON editor.

Running `build_catalog.py` without `--render-only` repeats the initial import from the pinned workbook. Do not run that over later maintained catalog edits. Its role is reproducibility of this release. The future local API must provide expected revisions, operation IDs, scoped authorization, atomic changes and durable receipts before concurrent agents write catalog facts.

Workflow writes already have a separate SQLite reference engine and operation contract. Cursor should put one trusted local service in front of it, not let browser code or arbitrary agents edit its database directly.

## Preservation and secret boundaries

Source tables preserve populated cells, comments and hyperlink targets; the original XLSX preserves formatting, embedded media and complete details. Original archived bytes remain in the source ZIP. Generated text masks recognized credential-shaped values and reports their coordinates without values in `reports/redactions.json`. This is conservative pattern screening, not a claim to recognize every possible opaque credential. No credential values were fetched for this task. Treat raw preserved originals as private evidence, not public web assets.

Original absolute paths are historical source locations, not automatic access authority and not required for portable reads. Prefer packaged relative paths and archive members. File existence or a matching checksum proves identity, not factual accuracy or runtime operation.
