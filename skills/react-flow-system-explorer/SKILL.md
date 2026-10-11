---
name: react-flow-system-explorer
description: Implement or revise this project's local React Flow system explorer and workflow-tracking UI from the approved Cursor handoff. Use for graph views, local API integration, provenance panels, and UI acceptance; not a new external service, dispatch system, or unrelated website.
---

# React Flow system explorer

Operate within the application file set. Resolve this canonical skill's real path when reached through a native discovery link. Read [reuse-first start](../../docs/CURSOR_FAST_START.md) and [Cursor handoff](../../docs/CURSOR_HANDOFF.md), then relevant sections of [design specification](../../docs/DESIGN_SPEC.md), [official references](../../docs/REACT_FLOW_REFERENCES.md), and [workflow contract](../../docs/WORKFLOW_CONTRACT.md). These documents own implementation order and acceptance; do not duplicate or replace them.

Alex already owns React Flow Pro. Use relevant examples available through his existing subscription; do not plan another purchase.

Alex's October 9 correction supersedes the earlier Vite choice: use the supplied Pro AI Workflow Editor directly in its Next.js + TypeScript stack. Its unchanged source is already in `app/`; inspect before editing and do not re-extract over existing work. Use [official shadcn](../shadcn/SKILL.md) for existing UI components and [repository lookup](../system-repository-lookup/SKILL.md) to find mapped code before replacing it. Build a Mac-local loopback API with one SQLite write owner, reusing the tested workflow reference engine through an adapter. Next.js Node route handlers may serve that API; a second frontend framework is unnecessary. Preserve stable IDs, provenance, job revisions and operation receipts. Add no external service, deployment or agent dispatch.

Implement all named destinations and guided templates from the design. Use ELK top-down, collapsed layer/subsystem aggregates, focused relationships, readable 14–16 px text, light/dark themes, labeled condition/evidence cues, keyboard access and a searchable non-graph alternative. The Braintrust screenshot is a visual reference, not integration proof.

Persist graph positions, viewport and viewing preferences separately from facts/workflow history. Dragging a node cannot change a relationship, status or evidence. Use validated service operations for workflow mutations; do not expose direct browser/agent database writes. The v1 catalog is read-only in the browser; factual correction proposals become review tasks, then authorized agents use the catalog skill's single-editor patch/validate/reload process. Handle current-job revision conflicts and operation reconciliation exactly as the workflow contract specifies.

Finish by exercising the handoff's runtime acceptance: crash/resume, stale revisions, corrections, evidence tracing, fresh-agent continuity, visual isolation and accessibility. Save actual command outputs, screenshots and receipts. A written interface or passing foundation engine tests do not prove the application works. Mark missing app/runtime evidence pending with the exact blocker; do not claim remote delivery or global skill installation.

Alex supplied `inputs/pro-ai-workflow-editor.zip`. Read [the intake](../../docs/PRO_TEMPLATE_INTAKE.md). Extend that app without framework conversion. Its provider generation routes, browser key storage and demo runner remain sample code, not the operational backend. Before the first accepted run, make the viewer work without an OpenAI key and verify no provider calls occur. Include the handoff file browser and two-way file-use navigation, with current/archive and evidence distinctions. The Pro template is an acceleration asset, not proof of the required app behavior.
