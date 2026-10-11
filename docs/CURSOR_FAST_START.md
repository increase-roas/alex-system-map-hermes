# Reuse first: Cursor's build entry point

Research and local preparation checked October 9, 2026. **Alex's latest direction is to use the paid template directly and minimize new work.** This supersedes the earlier Vite starting-point choice. Extend the supplied Next.js app; keep the required map, evidence and recovery behavior in the [implementation handoff](CURSOR_HANDOFF.md). No measured 100× speedup is claimed.

## Start here, once

1. Open this entire foundation folder as the workspace, not only `app/`. Read the [UI skill](../skills/react-flow-system-explorer/SKILL.md), this page, and the handoff. The data catalog, workflow engine, Pro ZIP, and five skills are already here.
2. For code that may already exist, use [repository lookup](../skills/system-repository-lookup/SKILL.md) and the [repository map](REPOSITORY_MAP.md). Identify the relevant source and revision before creating an alternative. A filename match is a candidate, not proof that an implementation works.
3. The supplied ZIP has already been extracted unchanged into `app/`; inspect its [intake](PRO_TEMPLATE_INTAKE.md) and extraction receipt. It is source prepared for Cursor, not an installed or tested application. Record a small reuse list: source path → adaptation → proof. Keep its license and private source private.
4. Continue `app/` in its existing Next.js + TypeScript structure. If Cursor has already edited it, preserve those edits. Use the official [shadcn skill](../skills/shadcn/SKILL.md) for surrounding UI. Run commands inside `app/`, using pnpm and the existing `pnpm-lock.yaml`. Inspect scripts before installation and use the lockfile rather than regenerating versions casually. Do not scaffold another app or convert frameworks.
5. Build one real path first: top-down overview → component → cited source → safe current or explicitly archived file. Then complete all five views and workflow acceptance. A thin first path is a milestone, not a reduced finish line.

## What to reuse for each need

| Need | Start from | Project-specific adaptation |
| --- | --- | --- |
| Canvas, node shells, sidebar and themes | Extracted `app/`, unchanged from `inputs/pro-ai-workflow-editor.zip`; exact files listed in the intake | Keep its Next.js architecture and existing visuals. Connect real catalog records and workflow state. |
| Hierarchy and collapsed subsystems | [Pro Expand/Collapse](https://reactflow.dev/examples/layout/expand-collapse), [Pro Auto Layout](https://reactflow.dev/examples/layout/auto-layout) | These are reference patterns, not downloaded assets in this package. Use existing subscription access when available. Preserve the full canonical graph separately from visible projections; use ELK as approved. Tree examples require adaptation for multiple parents and system cycles. |
| Status nodes, grouped nodes, search and zoom | [React Flow UI](https://reactflow.dev/ui), especially [Node Search](https://reactflow.dev/ui/components/node-search) | Search the entire catalog, including hidden/collapsed records. Derive labels from category/evidence/condition separately. |
| Navigation, details and filters | Official shadcn `Sidebar`, `Tabs`, `Sheet`, `Command`, `Badge`, `Table`, `Resizable`, `Collapsible` | Inspect ZIP's existing components first. Add only missing components from `@shadcn`; no full component-library install. |
| Guided investigate/build/repair forms | Existing `workflows/` plus shadcn fields, inputs, dialogs and alerts | Show owners, dependencies, acceptance and proof. UI submits validated operations; it does not directly write SQLite. |
| Restart, corrections and stale updates | Existing `tools/workflow_engine.py`, `tools/workflow_tests.py`, schemas and workflow contract | Adapt or wrap this tested reference. Do not substitute the sample's client-side runner. Keep SDK receipts as authoritative external references. |
| Existing agent/connector architecture | [Repository map](REPOSITORY_MAP.md) and `tools/catalog.py` | Use bounded, revision-pinned reads. No bulk clone or full-history ingestion is needed to find a source. |
| API uncertainty | [React Flow llms.txt](https://reactflow.dev/llms.txt) and shadcn `info`, `docs`, `search`, `view` | Read targeted pages and installed versions. Avoid loading an entire documentation corpus into each agent's context. |

## Compatibility decisions already made

The supplied ZIP uses Next.js 15, React 19, React Flow 12, Tailwind 4, Zustand 5, Radix primitives, Lucide icons, and a `new-york` shadcn configuration. These are package ranges from the ZIP; no dependencies have been installed here. Its existing App Router, `rsc: true` and `src/app/globals.css` setup can be retained. TypeScript is already part of this template; it is not an extra replacement project.

Preserve its Radix component family when reusing those components. The current shadcn skill supports several primitive families; do not casually mix Base UI's `render` API with Radix's `asChild`, or initiate a migration just because the newest generator defaults differ. Inspect the existing `components.json`; no new shadcn initialization is needed just to use this template. Confirm aliases and the actual global CSS path, and keep one lockfile. The app's actual installed versions win over this snapshot. Follow [React Flow UI's CSS ordering](https://reactflow.dev/ui): its stylesheet belongs in the global stylesheet after Tailwind/shadcn styles, not an arbitrary component import.

Alex's design is already specified: readable 14–16 px body text, normal body weight, medium headings, restrained semantic colors, light/dark modes. Implement these with shared tokens. The vendor skill's optional whole design-system showcase or `add --all` workflow is not this project. The chosen sources here are `@shadcn` for surrounding controls and the official React Flow UI/Pro assets for the canvas; no registry-choice question is necessary for those scoped uses.

`shadcn info --json` embedded in the official skill may not be executed automatically by every agent runtime. Run it explicitly inside `app/` when needed. The template already has `components.json`. Inspect its scripts against installed Next.js tooling before running them; fix an incompatible lint command narrowly rather than replacing the stack. The AI-provider routes, API-key cookie storage and demo execution state remain sample code until replaced or disabled for the map/tracker; source preparation did not execute them. Cursor must make the app usable without an OpenAI key and without triggering AI requests, and must test that absence before accepting v1.

## Skill routing

| Task | Load |
| --- | --- |
| Build graph and app behavior | `react-flow-system-explorer` |
| Compose surrounding UI and inspect registry components | Official `shadcn` |
| Locate existing private repository code/maps | `system-repository-lookup` |
| Reconcile catalog facts and evidence | `system-map-catalog` |
| Recover a job or handle a correction | `workflow-checkpoint-recovery` |

Five canonical folders live in `skills/`; native project links point there. If native discovery misses one, read its named `SKILL.md` directly. Do not install another copy globally. The shared instruction home and app cards still govern external operations.

## What the shortcuts do not supply

The UI assets do not supply this system's evidence reconciliation, durable correction semantics, safe file access, local API identity and revision enforcement, schema migration/backup behavior, or app-level failure tests. Those remain explicit implementation work in the handoff. Cost/token displays need actual receipts and known pricing scope; show unknown when absent. A trace does not prove acceptance, and a saved node does not prove a working integration.

Before a custom component or dependency, check the local asset and targeted official source once, then record reuse/adapt/build with its reason. Continue implementation; do not turn discovery into an unbounded search project. Optional undo/redo applies to view/editor preferences, never to append-only evidence history.

## Research decisions

- **React Flow:** use the owned Pro source and targeted docs. The [vendor's March 25 article](https://xyflow.com/blog/llms-txt-agent-skills-ai-development) reports useful results from documentation indexes and little benefit from its experimental Pro-example skills. No supported official React Flow skill distribution was established in this check. Our existing project skill supplies the application-specific rules.
- **shadcn:** the [official skill](https://ui.shadcn.com/docs/skills) is installed here with all 21 upstream files unchanged and a pinned source receipt. Its [MCP](https://ui.shadcn.com/docs/mcp) is another registry interface; the CLI already supplies the needed operations. No additional MCP was configured, avoiding an extra route and preserving Alex's tool policy.
- **Harness.io:** see [the fit assessment](HARNESS_FIT.md). It is a candidate for later telemetry/delivery integration, not a dependency of this local build.

## Copyable first instruction

> Continue the supplied React Flow Pro AI Workflow Editor already extracted in app/. Keep its Next.js setup; do not convert it to Vite or start another app. Read START_HERE.md, docs/CURSOR_FAST_START.md and docs/CURSOR_HANDOFF.md. Load the named project skills, including the official shadcn skill and system-repository-lookup. Reuse the template and mapped existing code before implementing a replacement. Preserve the JSON catalog, SQLite workflow contract and original evidence. Build and test the complete local application described in the handoff; record any unavailable source as a specific gap rather than guessing.
