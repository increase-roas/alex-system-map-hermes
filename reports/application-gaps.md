# Application build gaps (2026-10-10)

## Local filesystem: iCloud / errno 11 placeholders

Several foundation and template files exist with size metadata but cannot be read on this Mac (`Resource deadlock avoided`). Expected SHA-256 values are recorded in `reports/independent-foundation-graph.json`.

| Path | Expected SHA-256 (when known) | Impact |
| --- | --- | --- |
| `data/relationships.json` | `a23e77ce66167eee853754b4a7800d22c25a89e713d2b7a4b5d9add6dfd4e298` | Graph shows layer aggregates; factual edges empty until file is local |
| `data/coverage.json` | `3e824e092430c86dc6575c6775b3a419a8b422a17ddf98d3a83eee80e6ca4687` | In-app coverage table empty; summary still in `reports/coverage.json` |
| `views/overview.json` | (unavailable) | Synthetic flat memberships by layer used; labeled in API `load_gaps` |
| `inputs/pro-ai-workflow-editor.zip` | `5b69062bfdf61535125bfb64c75f68aae3e7e5ba363553d84146645c153e7ec3` | Cannot re-read Pro ZIP for deadlocked template files |
| Multiple `app/src/app/workflow/**` and UI files | see extraction receipt | Removed unreadable template files; explorer replaces `/workflow` |

**Remediation:** Download/offline-pin the listed paths in Finder (or restore from the pinned originals under `inputs/`). Do not regenerate maintained JSON via the full importer without an authorized catalog edit.

## Pro template reuse (adapted)

| Source (intake) | Adaptation | Proof |
| --- | --- | --- |
| `src/components/base-node.tsx` | System map node shells | Used in `app/src/app/explorer/nodes.tsx` |
| `src/app/workflow/utils/layout-helper.ts` | ELK layout pattern | Adapted in `app/src/lib/graph/build-graph.ts` + explorer layout |
| `src/components/theme-provider.tsx`, `globals.css` | Light/dark themes | Root layout + explorer |
| `src/components/ui/*` (readable) | Toolbar controls | Explorer header |
| Deadlocked workflow editor tree | Not recoverable locally | Replaced by `/explorer` implementation |

## External authorization

None required for v1 loopback operation. No OpenAI key, Composio, or deployment steps were used.
