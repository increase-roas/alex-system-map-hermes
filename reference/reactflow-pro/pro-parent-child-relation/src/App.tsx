import { useCallback } from 'react';
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  useNodesState,
  useEdgesState,
  addEdge,
  OnConnect,
  Edge,
} from '@xyflow/react';

import SimpleNode from './SimpleNode';
import { initialNodes, initialEdges } from './initial-elements';
import { useNodeDragHandlers } from './useNodeDragHandlers';

import '@xyflow/react/dist/style.css';

const proOptions = {
  hideAttribution: true,
};

const nodeTypes = {
  node: SimpleNode,
};

export default function DynamicParentChild() {
  const [nodes, , onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const onConnect: OnConnect = useCallback(
    (edge) => setEdges((eds: Edge[]) => addEdge(edge, eds)),
    [setEdges]
  );

  const { onNodeDrag, onNodeDragStop } = useNodeDragHandlers();

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      onEdgesChange={onEdgesChange}
      onNodesChange={onNodesChange}
      onConnect={onConnect}
      onNodeDrag={onNodeDrag}
      onNodeDragStop={onNodeDragStop}
      proOptions={proOptions}
      fitView
      selectNodesOnDrag={false}
      nodeTypes={nodeTypes}
      colorMode="system"
    >
      <Background color="#bbb" gap={50} variant={BackgroundVariant.Dots} />
    </ReactFlow>
  );
}
