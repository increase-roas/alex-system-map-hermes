# React Flow Pro: what we have and what the map uses

Downloaded 2026-10-11 from reactflow.dev (Alex's Pro account). Source zips in `zips/`, unzipped next to this file.
Map uses (2026-10-11): Parent Child, Expand/Collapse, Edge Routing (vendored libavoid), Helper Lines, Shapes. Code in app/src/app/explorer/pro/.

| Pro feature | Here? | Map status | Why |
|---|---|---|---|
| Parent Child Relation | yes | IN MAP | Customer boxes with missions inside |
| Selection Grouping | yes | NOT NEEDED YET | Groups come from Director data, not hand grouping |
| Expand and Collapse | yes | IN MAP | Open or close a customer's missions |
| Auto Layout | yes | NOT NEEDED YET | Map already places boxes in fixed rows; revisit if rows get crowded |
| Dynamic Layouting | yes | NOT NEEDED YET | Layout reflows when boxes are added |
| Edge Routing | yes | IN MAP | Lines go around boxes (libavoid) |
| Helper Lines | yes | IN MAP | Snap guides when dragging |
| Shapes | yes | IN MAP | Diamond = Director, circle = connector, etc |
| AI Workflow Editor | yes (older download) | LATER | Full editor app; idea source, not needed now |
| Node Position Animation | no | LATER | Smooth slide on layout change |
| Undo and Redo | no | LATER | Undo a bad drag |
| Force Layout | no | SKIP | Bouncy physics, less readable than tree layout |
| Editable Edge | no | SKIP | Map lines come from evidence, not hand drawing |
| Collaborative | no | SKIP | Only you use the map |
| Copy and Paste | no | SKIP | Map is generated, not hand built |
| Freehand Draw | no | SKIP | Whiteboard feature |
| Server Side Image Creation | no | SKIP | Free "Download Image" covers snapshots |
