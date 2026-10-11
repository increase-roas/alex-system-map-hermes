# Project-local execution skills

Five canonical skill folders live under `skills/`, with relative links under `.cursor/skills/`, `.agents/skills/` and `.claude/skills/`. Resolve the real canonical path before following relative document links. These are project assets; no global skill home, shared routing rule or remote runtime was changed.

| Skill | Use it for | Do not confuse it with |
| --- | --- | --- |
| [react-flow-system-explorer](../skills/react-flow-system-explorer/SKILL.md) | Extend the supplied Next.js Pro app, visual hierarchy, API integration and app acceptance | A framework migration, new dashboard scaffold or deployment |
| [shadcn](../skills/shadcn/SKILL.md) | Official vendor guidance for existing UI components, registry lookup, theming and composition | A requirement to install every component, migrate primitives or create a design-system showcase |
| [system-repository-lookup](../skills/system-repository-lookup/SKILL.md) | Find mapped private repository code with catalog anchors, live identity and pinned read-only GitHub evidence | A public-library recommendation search or authorization to push changes |
| [system-map-catalog](../skills/system-map-catalog/SKILL.md) | Reconcile facts, sources, coverage and authorized JSON patches | Live service testing or invented relationships |
| [workflow-checkpoint-recovery](../skills/workflow-checkpoint-recovery/SKILL.md) | Recover jobs, handle corrections and verify affected results | Agent dispatch or a replacement for SDK receipts |

## Official shadcn source

The complete 21-file skill was fetched from the official `shadcn-ui/ui` repository, verified against Git blob hashes, and copied unchanged. Pinned commit and per-file hashes are in `reports/shadcn-skill-provenance.json`. The MIT license is retained in `inputs/shadcn-LICENSE.md`. No installer, included script, npm package or MCP was run as part of this source installation.

The vendor skill uses `user-invocable: false` and dynamic `shadcn info` context syntax. The local Codex native validator rejects that extra frontmatter key; its failure is recorded as a validator compatibility limitation, not hidden or claimed as a pass. Preserve the upstream file. Validate its YAML, required fields, all resource links and pinned bytes separately. Cursor use is the intended target; automatic selection and dynamic context injection need a fresh runtime receipt. The agent can explicitly read the skill file and run `shadcn info --json` from `app/` if injection is absent.

Project direction overrides vendor examples: extend the extracted Next.js Pro app; use its existing Radix/Tailwind configuration; preserve original evidence; use `@shadcn` for surrounding controls and official React Flow UI/Pro assets for the graph. Do not run the vendor's optional `add --all`/new-design-system workflow for this task. No extra MCP route is configured; the CLI covers required registry operations.

## Selection and delivery evidence

The initial three project skills passed native structural validation, link checks and an independent recovery exercise in the original foundation reports. The added repository skill passed the same native validator. Those earlier receipts do not certify later document edits; use the latest accelerator verification receipt for this revision.

The installed Cursor CLI is present and reports an authenticated session. No paid model invocation was launched. Directory discovery follows the [official Cursor skill locations](https://cursor.com/docs/skills), but files and links are configured evidence, not proof that a fresh agent selected them. Open the full foundation folder. If discovery is missing, explicitly read the skill paths above; the [copyable starting instruction](CURSOR_FAST_START.md#copyable-first-instruction) names the required sources. Do not install duplicate global copies to work around a missing project entry.

A fresh Cursor session should be checked with a normal request to continue the app using its existing UI assets and to locate connector/Director sources. Record the skills actually loaded and sources chosen. Remote delivery and target-model selection remain NOT_PROVEN until observed.

## Structural checks

Check all five canonical folders, all 15 relative links, local resource targets and immutable upstream bytes. Run the native creator validator for the four project-authored skills. For the unmodified vendor skill, retain the known native-validator diagnostic and validate the upstream field set/resources separately. Do not change a vendor file just to make a narrower validator green.

Changes and rollback: existing local handoff files were backed up under `~/Backups/system-map-accelerators-2026-10-09/`. The original catalog data, workbook and source archive were not edited. The Pro ZIP's source extraction is independently checkable against its receipt.
