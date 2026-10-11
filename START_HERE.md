# Alex's system map foundation

**Open this folder in Cursor. Start with [the reuse-first build guide](docs/CURSOR_FAST_START.md), then [the Cursor handoff](docs/CURSOR_HANDOFF.md).**

This package is the evidence and workflow foundation for your local visual system map. The supplied Pro application source is prepared in `app/`; Cursor will extend and test it. No dependencies were installed and no application or AI request was run during preparation.

Alex already owns React Flow Pro. Use relevant examples available through his existing subscription; do not plan another purchase.

Your supplied [Pro workflow-editor ZIP](inputs/pro-ai-workflow-editor.zip) is included. Cursor should read [what to reuse](docs/PRO_TEMPLATE_INTAKE.md). Alex clarified that speed and reuse are the priority: continue this Next.js template directly. The earlier Vite starting-point choice is superseded; [the decision record](docs/DECISIONS.md) preserves the correction so another agent does not revive it.

See [what your Starter plan and ZIP provide](docs/WHAT_YOU_OWN.md), including what still needs connecting.

## Pick what you need

| You want to… | Start here |
|---|---|
| Build the visual app | [Cursor handoff](docs/CURSOR_HANDOFF.md), then [design](docs/DESIGN_SPEC.md) |
| See the readable inventory | [Generated top-down workbook](views/Alex_System_Foundation.xlsx) |
| Keep every original detail | [Original master workbook](inputs/Alex_Master_Build_and_Connectors.xlsx) and [source archive](inputs/Alex_Master_Source_Files.zip) |
| Find one part of the setup | [Component index](docs/COMPONENT_INDEX.md), or the bounded catalog search below |
| Open files and see what uses them | Cursor's [file browser requirement](docs/CURSOR_HANDOFF.md#actual-files-are-a-first-class-destination); archived contents are readable now through the bounded source command |
| Resume work or handle a mistake | [Agent protocol](docs/AGENT_PROTOCOL.md) and [workflow contract](docs/WORKFLOW_CONTRACT.md) |
| Give another agent the procedures | [Five project skills](docs/SKILLS.md) |
| Check what is proved | [Verification guide](docs/VERIFICATION.md) and `reports/` |

## What is authoritative
react 
The original workbook and archive remain byte-identical inputs. The JSON catalog is the maintained map after this initial reconciliation. Component pages and the companion XLSX are generated views. Keep original claims, dates and conflicts in evidence; do not silently rewrite history.

Workflow state belongs in the local SQLite store. The included reference engine demonstrates its contract using synthetic jobs. Existing SDK receipts remain authoritative for SDK operations; this tracker references them. A supplied verifier name and evidence pointer alone do not prove the evidence is true.

The map reads top down: **you/direction → agents → SDK → access → infrastructure → models → apps → files/evidence**. This is explanatory grouping, not an assertion that every item invokes the next layer.

## Read only what the task needs

From this folder:

```sh
python3 tools/catalog.py search Composio
python3 tools/catalog.py search 'Director Observatory'
python3 tools/catalog.py search 'Plan review'
python3 tools/catalog.py component COMPONENT_ID
python3 tools/catalog.py evidence EVIDENCE_ID
python3 tools/catalog.py source F0001 --start 1 --limit 20
```

Replace uppercase IDs with IDs returned by search. The read-only catalog tool does not execute instructions contained in source files. Source excerpts are bounded and credential-shaped values are masked.

## Scope and limits

The initial import accounts for **2,377 existing coverage records**, **198 overview entries**, **1,009 original files**, **192 source tables**, and **59 explicitly recorded relationships**. Expanded assets, skills, files, plan records and unresolved references are separate searchable entries. See `reports/coverage.json` for generated counts.

Documented current means the saved October 9 map snapshot, not a new live inspection. Historical records, planned work, unresolved endpoints and observed health have separate fields. Provider status, a saved connection, or a screenshot is not promoted to a working-runtime claim.

The Braintrust screenshot is preserved as a user-supplied reference only. No account, installation or integration is inferred from it. No hosting, automatic dispatch or production changes are included.

**Local-only; Drive not updated.** The original master was not changed. This new companion package has no registered Drive destination.
