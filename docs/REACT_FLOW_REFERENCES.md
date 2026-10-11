# React Flow implementation references

**Alex already owns React Flow Pro. Use relevant examples available through his existing subscription; do not plan another purchase.**

These official public references were inspected during foundation planning on 2026-10-09. The supplied Pro ZIP and its unchanged extraction are recorded separately below. The October 9 user screenshot shows a Starter subscription and template/example access; it is screenshot evidence, not a live account inspection or application runtime proof. Cursor must check the actual installed dependencies and use the examples Alex can access through his existing subscription. React Flow core is MIT; Pro examples/support are a separate offering. Preserve applicable licenses when copying source.

| Official source | Use in this application | Proof boundary |
| --- | --- | --- |
| [AI Workflow Editor](https://reactflow.dev/ui/templates/ai-workflow-editor) | Current starting point: Alex's supplied Next.js + TypeScript Pro app, prepared in `app/`. | Source ready; installation, adaptation and runtime proof pending. |
| [React Flow Pro](https://reactflow.dev/pro) | Find relevant examples available through Alex's subscription. | No purchase planned; no authenticated access claimed here. |
| [Layouting](https://reactflow.dev/learn/layouting/layouting) | Understand layout options; use ELK top-down and persist positions separately from facts. | Algorithm suitability is a design choice to verify with the actual graph. |
| [Performance](https://reactflow.dev/learn/advanced-use/performance) | Stable props/callbacks, selective rendering and collapse/focus patterns. | Guidance; actual performance needs measurement. |
| [Accessibility](https://reactflow.dev/learn/advanced-use/accessibility) | Keyboard behavior, accessible labels and focus handling. | Built-in features do not establish full app conformance. |
| [Workflow editor template](https://reactflow.dev/ui/templates/workflow-editor) | UI patterns for guided editing and side panels. | Adapt to the existing tracking contract; do not add dispatch semantics. |
| [Expand/collapse example](https://reactflow.dev/examples/layout/expand-collapse) | Collapsed aggregates and on-demand detail. | Use only examples/source available to Alex; do not claim acquired Pro code. |

Implementation choices from these references must preserve stable IDs, evidence links, unresolved placeholders, expected revisions and operation receipts. React Flow describes the presentation graph. Its node/edge callbacks must call typed service operations rather than becoming a factual or workflow store. Check the library's actual version and API signatures during implementation and record them in the application's verification report.

## Supplied Pro source

Alex supplied `inputs/pro-ai-workflow-editor.zip`; see [Pro template intake](PRO_TEMPLATE_INTAKE.md) for verified archive paths, source paths, direct template reuse and acceptance. Keep it private and preserve its license notices. No code from it has been run.


## Agent and component shortcuts

Use [llms.txt](https://reactflow.dev/llms.txt) to find focused docs. The [vendor AI development article](https://xyflow.com/blog/llms-txt-agent-skills-ai-development), March 25, 2026, reports that its experimental Pro-example skills added little benefit; no supported official skill distribution was verified here. Use this project's UI skill plus vendor docs.

[React Flow UI](https://reactflow.dev/ui) supplies components compatible with shadcn. [Node Search](https://reactflow.dev/ui/components/node-search) can be adapted to the full catalog. [Pro Auto Layout](https://reactflow.dev/examples/layout/auto-layout) supplies a reusable layout pattern; keep ELK as the one chosen layout engine. The [official xyflow repository](https://github.com/xyflow/xyflow) is the library source, not Alex's ready-made application.
