import { useState } from 'react';
import {
  Node,
  NodeToolbar,
  useReactFlow,
  useOnSelectionChange,
} from '@xyflow/react';

import { getId } from './utils';

/**
 * This toolsbar is not bound to a specific node, but to the selected nodes.
 * It will show up when multiple nodes are selected and allow to group them.
 */
export default function SelectedNodesToolbar() {
  const { setNodes, getNodesBounds, getNodes, getInternalNode } =
    useReactFlow();
  const [selectedNodes, setSelectedNodes] = useState<Node[]>([]);

  useOnSelectionChange({
    onChange: ({ nodes }) => {
      setSelectedNodes(nodes.filter((node) => node.type !== 'group'));
    },
  });

  if (selectedNodes.length <= 1) {
    return null;
  }

  const selectedNodeIds = selectedNodes.map((node) => node.id);

  const onGroup = () => {
    const nodes = getNodes();
    const groupId = getId('group');
    const selectedNodesRectangle = getNodesBounds(selectedNodes);
    const groupNodePosition = {
      x: selectedNodesRectangle.x,
      y: selectedNodesRectangle.y,
    };

    // this is a new node that gets added to our nodes
    const groupNode = {
      id: groupId,
      type: 'group',
      position: groupNodePosition,
      data: {},
    };

    const nextNodes: Node[] = nodes.map((node) => {
      if (selectedNodeIds.includes(node.id)) {
        const internalNode = getInternalNode(node.id);
        if (!internalNode) return node;
        const position = internalNode.internals.positionAbsolute;
        return {
          ...node,
          // here we calculate a relative position of the node inside the group
          position: {
            x: position.x - groupNodePosition.x,
            y: position.y - groupNodePosition.y,
          },
          parentId: groupId,
          selected: node.selected ? false : undefined,
        };
      }

      return node;
    });

    setNodes([groupNode, ...nextNodes]);
  };

  return (
    <NodeToolbar nodeId={selectedNodeIds} isVisible>
      <button className="xy-theme__button" onClick={onGroup}>
        Group selected nodes
      </button>
    </NodeToolbar>
  );
}
