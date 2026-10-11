# Mem0 has scoped CRUD, exact-write reconciliation, and task-start recall code

ID: `component_b688793f44c5023cfe35`

MemoryProfile fixes account/user scope; Mem0Client and MemoryService support search/get/history/save/update/reconcile, with stable operation IDs, authorization, content hashes and exact scoped-content readback. Task recall is bounded and records provenance hashes; worker delivery is approval-gated by exact composed-message hash.

Category: **documented_current** · Evidence: **reported** · Observed condition: **unknown**

## Evidence boundary

The source supports implementation claims. The workbook explicitly says no new 1.5.1 Mem0 execution occurred and the one live recall belongs to 1.5.0.

## Source records


## Evidence pointers

- `ev_cec043f7d813d1f532b8` — FILE CATALOG row 952 (Saved source row; no new live test)

## Recorded relationships


## Open questions and issues

- `issue_2e2aa3b327920ff09d25`: Current runtime health not established. The source supports implementation claims. The workbook explicitly says no new 1.5.1 Mem0 execution occurred and the one live recall belongs to 1.5.0.

Read bounded source detail with `python3 tools/catalog.py component <ID>` or `evidence <ID>`.
