# What Alex has, and what Cursor should use

Evidence date: October 9, 2026. Alex's supplied dashboard screenshot shows **React Flow Pro — Starter plan**. That screenshot is saved as `inputs/react-flow-starter-plan.png`; current account billing was not inspected.

| Item | What it gives you | How it helps this build |
| --- | --- | --- |
| React Flow library | The interactive graph engine | Already a dependency of the supplied app. Do not build a graph engine or clone the whole xyflow library to start the app. |
| Pro examples | Source examples for advanced features | Reuse hierarchy/collapse and automatic layout patterns where needed. Other Pro examples have not been downloaded in this package. |
| Pro templates | Ready-made application source | The AI Workflow Editor ZIP is the fastest concrete starting point available here. It is already extracted to `app/`. |
| Prioritized GitHub issues | Vendor gives issues priority, as shown in the dashboard | Potential help with a genuine React Flow problem; no issue or message was sent. |
| Team access and onboarding call | Dashboard offers invitations and scheduling | Available dashboard options; exact seat allowance and scheduling were not verified or used. |
| Individual support | Screenshot labels this as an upgrade | Do not assume it is included with the displayed Starter plan. No upgrade is needed to begin with the downloaded source. |

## The ZIP already includes

Next.js + TypeScript, the React Flow canvas and node components, shadcn/Radix UI, Tailwind styling, sidebar layouts, themes, ELK layout support, Zustand presentation state, and example text/image AI workflow code. All **71 source files** were extracted unchanged from the **92-entry ZIP** (the other entries are directories). The original ZIP remains preserved.

Next.js is the framework this paid starter uses. TypeScript is its programming language. They are already together in the template. There is no reason to change to Vite simply to build this map.

The “OpenAI API key is not set” popup in Alex's screenshot belongs to the sample AI generation features. Owning the template does not provide provider API credits or connect Alex's existing agents. Cursor should make the map and workflow tracker usable without that key or any AI request. A later request to actually execute AI workflows would use Alex's established SDK/connector route and spending scope.

## What still needs implementation

The template does not already know Alex's setup or implement his complete recovery rules. Cursor must connect the prepared catalog, implement the five views and safe file viewer, and attach the tested durable workflow state behind the interface. The templates save interface work; the foundation saves inventory/reconciliation and recovery-design work. Both are useful parts of the same app.

Current preparation includes five local skills, mapped GitHub entry points, the original evidence, and source-backed reuse instructions. The visual app is not installed or tested yet. Begin with [CURSOR_FAST_START.md](CURSOR_FAST_START.md).

Sources: supplied screenshots and ZIP; official [AI Workflow Editor](https://reactflow.dev/ui/templates/ai-workflow-editor), [React Flow UI](https://reactflow.dev/ui), [React Flow Pro](https://reactflow.dev/pro), and [shadcn skills](https://ui.shadcn.com/docs/skills). See the extraction and upstream-skill provenance receipts in `reports/`.
