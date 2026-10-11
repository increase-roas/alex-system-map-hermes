# React Flow Pro: what we have and what the map uses

Downloaded 2026-10-11 from reactflow.dev (Alex's Pro account). Source zips in `zips/`, unzipped next to this file.
Map today uses only free parts: Background, Controls, MiniMap, elkjs.

| Pro feature | Here? | Map status | Why |
|---|---|---|---|
| Parent Child Relation | yes | PLANNED | Customer boxes with missions inside |
| Selection Grouping | yes | PLANNED | Group/ungroup boxes by hand |
| Expand and Collapse | yes | PLANNED | Open or close a customer's missions |
| Auto Layout | yes | PLANNED | Neat placement (dagre/elk/d3) |
| Dynamic Layouting | yes | PLANNED | Layout reflows when boxes are added |
| Edge Routing | yes | PLANNED | Lines go around boxes (libavoid) |
| Helper Lines | yes | PLANNED | Snap guides when dragging |
| Shapes | yes | PLANNED | Diamond = Director, circle = connector, etc |
| AI Workflow Editor | yes (older download) | LATER | Full editor app; idea source, not needed now |
| Node Position Animation | no | LATER | Smooth slide on layout change |
| Undo and Redo | no | LATER | Undo a bad drag |
| Force Layout | no | SKIP | Bouncy physics, less readable than tree layout |
| Editable Edge | no | SKIP | Map lines come from evidence, not hand drawing |
| Collaborative | no | SKIP | Only you use the map |
| Copy and Paste | no | SKIP | Map is generated, not hand built |
| Freehand Draw | no | SKIP | Whiteboard feature |
| Server Side Image Creation | no | SKIP | Free "Download Image" covers snapshots |
