# Local map application design specification

Status: implementable design, application pending. Use React Flow and TypeScript for the graph canvas, a local loopback API for reads/mutations, and SQLite with one service writer for persisted state. Follow the tested workflow reference engine and `WORKFLOW_CONTRACT.md` for workflow behavior. The engineering standard is explicit source provenance, transactional revisions and recoverable operations; the interface target is WCAG 2.2 AA with keyboard access, sufficient contrast, visible focus and non-color status cues. Conformance must be tested in the built app.

**Alex already owns React Flow Pro. Use relevant examples available through his existing subscription; do not plan another purchase.**

## Structure and views

Use the eight layers in this order: Direction, Agents, SDK, Access, Infrastructure, Models, Apps, Evidence. Preserve canonical layer IDs. A top bar offers search, view selection, issue/evidence filters, theme and current local snapshot/revision. A left pane holds layer/subsystem navigation; the center shows the active graph or tracking view; a right pane shows the selected record and provenance. On small windows, make side panes drawers with explicit open/close controls.

Implement five main views. Keep History as a directly accessible tab inside Workflows, and link to relevant history from component details.

| Destination | Content and interaction |
| --- | --- |
| Overview | Eight layer aggregates, counts derived from records, prominent cross-layer connections and issue badges. Expand one layer/subsystem on demand. |
| Subsystem | Selected layer/group, its assets and immediate neighbors; limit edges to the relevant selection. Breadcrumb back to overview. |
| Detail | One component's purpose, boundary, aliases, conditions, evidence level, source rows, inbound/outbound relationships and related issues. Open an original-source pointer when available. |
| Problems | Searchable list by severity/status/category/evidence level with unresolved-reference and coverage gaps visible. Selecting an issue focuses affected entities and cited evidence. |
| Workflows and history | Guided templates, run status, next allowed action, blockers, revision and latest event. A History tab shows ordered persisted events, operation IDs, revisions, corrections, receipts and evidence links. Start/resume/mutate only via the workflow contract. |

## Graph behavior

### File browser and contents

Keep a searchable **Files** list available beside the map, with filename, real location, source date, copy/authority status and relationship badges. The content panel shows actual safely read current file contents when accessible; otherwise it explicitly shows an archived snapshot, unavailable state or unsupported binary format. A summary may sit beside the file but never replace it silently. Display read time, modification time and hash with their scope. Unknown purpose or authority remains unknown.

Clicking a file focuses its supported readers, references and writers across agents, skills, connectors and workflow tasks. Clicking one of those entities reveals its underlying files. Use different text labels for documented references, dated runtime-use evidence and unresolved consumers. Duplicate snapshots, possible stale copies, missing connector docs and old files still referenced should be reachable through Problems. Do not invent a relationship to make a lonely node look connected.

Keep credential values concealed before browser delivery, clearly mark withheld content, and do not execute markup, scripts or instructions from source files. File browsing is read-only; it does not install, clean up or replace the user's existing system. Test source-opening, archive/current distinctions and both navigation directions as specified in the handoff.

Use ELK for top-down layout. Group by layer/subsystem, with stable ordering to prevent unnecessary movement after reload. Store layout algorithm/options/version with presentation state. Manual drag positions override generated positions until reset. Node positions, camera, collapse state and filtering are presentation only; they never change a factual field or assert a relationship.

Start collapsed at aggregates. Show connection counts and representative labeled links; expand only on user demand. Route visible edges to group boundaries where useful and use selection/focus to show adjacent paths. Avoid rendering every relationship at overview scale. A collapsed group is a visual aggregate; its count and facts are derived from underlying stable IDs. Persist expansion preferences separately.

Each node shows a readable name and a short kind/category cue. Evidence level and observed condition are separate badges. Unknown/unresolved placeholders use an explicit “Unresolved reference” label with their source clue, preserving provenance. A relationship has a label/type and its own evidence; adjacency is not proof of operational integration. Clicking an edge opens evidence and endpoint details.

Search names, IDs, aliases and source record keys. Resolve exact IDs first and show ambiguous matches for selection. Never merge assets automatically because names look alike. Filters may hide visible results but must show active filters and hidden-result counts. Fit-to-view, reset layout, zoom and focus-selection controls need keyboard equivalents.

## Visual system

Use a system sans-serif font, 14–16 px for primary interface text, regular/medium weights, generous line spacing and readable node widths. Use a clear title/value hierarchy instead of tiny metadata. Show full labels in detail/tooltips without relying on hover alone. Use restrained neutral surfaces and one selected-state accent; layer colors may supplement readable layer names.

Provide light and dark themes. Text and interactive controls need sufficient contrast in both. Condition/evidence indicators always have text/icon labels as well as color. Reduced-motion preferences suppress animated edge/camera transitions. Maintain visible keyboard focus, accessible names, tab order and selection announcements. Provide a list/table alternative to graph navigation so essential information is available without spatial interaction.

Keep the graph calm: no decorative animation, overlapping labels or dense edge bundles. On demand, expose relationship details in the side pane and focused graph. Empty/error/loading states say what is missing, where the evidence lives, and which next action is available. Separate “no records,” “filtered out,” “source pointer unavailable,” and “failed validation.”

## Tracking and correction UX

Guided templates display purpose, inputs, prerequisites, ordered steps, definition of done and allowed transitions from the canonical workflow contract. A run shows the exact next allowed actions and blocker reason. A stale revision prompts reload/review; it must never silently overwrite. An uncertain response prompts operation-ID reconciliation before retry.

Correction flow: select record → propose field change → attach evidence/source record → review before/after → record a correction-review task through the service with expected job revision → read back its receipt/history. In v1 the catalog remains read-only in the browser. An authorized agent applies a reviewed patch through the documented single-editor catalog process, validates it, and reloads the app snapshot. Keep rejected proposals visible enough to explain the failure. Original row metadata stays inspectable; corrections never destroy source evidence.

The Braintrust screenshot is a user-provided visual reference for organization and tracking. It does not prove any Braintrust integration, subscription, API access, or required external dependency. Use its useful layout ideas within the local design only.

## Persisted boundaries

Canonical facts and source identity belong to the validated JSON catalog. Workflow state/events belong to the existing reference engine. Presentation state belongs to separate SQLite tables or a distinct presentation store accessed through the service. Only that service writes SQLite. Browser code and agents cannot bypass workflow revision checks or modify the database directly. The only v1 catalog-write path is the explicitly authorized single-editor patch/validate/regenerate process; the browser remains read-only for facts.

No deployment, paid service, customer messages, agent dispatch or external integration belongs to this UI build. Project-local guidance can help any agent use the app; it does not prove a globally installed skill or delivery to other agents/machines.

## UI verification evidence to retain

Save browser screenshots for overview, focused subsystem, detail/provenance, problems, workflows and history in both themes; record the tested viewport sizes. Save automated test output for keyboard navigation, readable labels, collapse/expand, search/filter, stale revisions and visual-only persistence. Visual review must inspect actual screenshots in addition to structural tests. Application evidence is pending until Cursor builds and exercises these flows.
