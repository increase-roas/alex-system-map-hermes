# Selection Grouping Pro Example

This is a [vite](https://vitejs.dev/) app that shows how to build selection-based group nodes with [React Flow](https://reactflow.dev). It focuses on creating parent nodes from a selection, keeping group dimensions in sync with their children, and converting positions between absolute canvas coordinates and parent-relative coordinates.

## Installation

To get started, you can download the source code from our [pro platform](https://pro.reactflow.dev/examples), unzip it and `cd` into the folder.

After that, install the dependencies like this:

```sh
npm install
```

Now you can run the development environment:

```sh
npm run dev
```

## Guide

- [Dependencies](#dependencies)
- [Breakdown](#breakdown)
- [Implementation details](#implementation-details)
- [Related docs](#related-docs)

This example lets users select one or more top-level nodes, group them into a parent node, and later ungroup them again. The group node grows to fit its children, even when the children are moved beyond the current group bounds.

## Dependencies

- `@xyflow/react`

## Breakdown

### Normalizing node changes

`App.tsx` uses `useNodesState` for node state, but overrides the default node change handler. Every React Flow node change is first applied with `applyNodeChanges`, then routed through `expandGroupNodes`:

```tsx
const onNodesChange = useCallback(
  (changes: NodeChange[]) => {
    setNodes((nds) => expandGroupNodes(applyNodeChanges(changes, nds)));
  },
  [setNodes],
);
```

This is useful for flow editors because node updates can come from many places: dragging nodes, selecting nodes, grouping nodes, or calling `setNodes(...)` from a toolbar. Instead of remembering to recalculate group dimensions in every handler, `onNodesChange` makes `expandGroupNodes` the single place where incoming node state is normalized after React Flow changes.

### Creating a group

`SelectedNodesToolbar.tsx` uses `useOnSelectionChange` to track selected nodes. When the user clicks "Group selected nodes", it creates a new `group` node at the bounds of the selected nodes and assigns each selected node a `parentId`.

Children of a parent node use positions relative to that parent. Because of that, grouping has to convert each selected node's absolute canvas position into a group-local position. The toolbar reads the absolute position from React Flow's internal node state, then subtracts the new group position:

```ts
position: {
  x: position.x - groupNodePosition.x,
  y: position.y - groupNodePosition.y,
}
```

### Expanding group nodes

`expandGroupNodes` calculates the size of every group node from its children. It relies on React Flow's node order, where parent nodes come before their children, and walks the array backwards. That lets the function resolve a nested child group before that group contributes to its own parent's bounds.

During the backwards pass, the function keeps a `boundsByParent` map. Each child contributes a padded rectangle to its parent's bounds:

- `x1` and `y1` are the smallest child positions, minus padding.
- `x2` and `y2` are the largest child bottom-right positions, plus padding.
- the new group width and height are `x2 - x1` and `y2 - y1`.

When the loop reaches a group node, it can look up the bounds that were collected for that group. If the bounds differ from the current group size or start at a non-zero offset, `resolveExpansion` creates an expansion:

- `dimension`: the next group width and height.
- `offset`: how far the child bounds start from the current parent origin.
- `position`: the next parent position in its own coordinate system.

The important part is that expanding a group is not just a width and height update. If a child is dragged above or to the left of its parent, the group has to move so the child can still fit inside it. When the parent moves, every child needs the opposite offset applied to its relative position. Otherwise the whole group would visibly jump on the canvas.

For example, if a child sits at `x: -20` inside a group, the group should move left by `20`, and that child should move right by `20` relative to the new group origin. Visually, the child stays in the same canvas position, but the parent now includes it.

After collecting expansions, `expandGroupNodes` builds the next node array. Parent nodes receive their new dimensions and position. Child nodes receive the inverse offset of their parent expansion. Nested group nodes can be both a parent and a child, so the function handles both cases together: the nested group gets its own resized dimensions, while its position is also corrected for the parent group's movement.

Group nodes without enough child bounds are marked as empty and skipped when a new node array is built.

### Ungrouping nodes

`GroupNode.tsx` renders the group node and shows an "Ungroup" toolbar when the node has children. The actual detach logic lives in `useDetachNodes`.

Detaching reverses the coordinate conversion used when grouping. A child node's stored position is relative to its parent, so before removing `parentId`, the parent absolute position is added back:

```ts
position: {
  x: node.position.x + parentNode.internals.positionAbsolute.x,
  y: node.position.y + parentNode.internals.positionAbsolute.y,
}
```

The helper also removes the group node itself when it is passed as `removeParentId`.

## Implementation details

### Node toolbars

This example uses two [NodeToolbar](https://reactflow.dev/api-reference/components/node-toolbar) instances:

- `SelectedNodesToolbar.tsx` attaches a toolbar to the selected top-level nodes and creates a group from them.
- `GroupNode.tsx` attaches a toolbar to group nodes and detaches all children again.

The toolbars keep grouping actions close to the selected nodes instead of placing global controls outside the canvas.

## Related docs

- [React Flow sub flows](https://reactflow.dev/learn/layouting/sub-flows)
- [React Flow NodeToolbar](https://reactflow.dev/api-reference/components/node-toolbar)
