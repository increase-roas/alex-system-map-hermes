import { useCallback } from 'react';
import {
  ReactFlow,
  Background,
  useNodesState,
  useEdgesState,
  addEdge,
  OnConnect,
  SelectionMode,
  Edge,
  NodeChange,
  applyNodeChanges,
} from '@xyflow/react';

import GroupNode from './GroupNode';
import SelectedNodesToolbar from './SelectedNodesToolbar';
import { initialNodes, initialEdges } from './initial-elements';
import { expandGroupNodes } from './expansions';

import '@xyflow/react/dist/style.css';

const proOptions = {
  hideAttribution: true,
};

const nodeTypes = {
  group: GroupNode,
};

export default function DynamicGrouping() {
  const [nodes, setNodes] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const onConnect: OnConnect = useCallback(
    (edge) => setEdges((eds: Edge[]) => addEdge(edge, eds)),
    [setEdges],
  );
  const onNodesChange = useCallback(
    (changes: NodeChange[]) => {
      setNodes((nds) => expandGroupNodes(applyNodeChanges(changes, nds)));
    },
    [setNodes],
  );

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      onEdgesChange={onEdgesChange}
      onNodesChange={onNodesChange}
      onConnect={onConnect}
      proOptions={proOptions}
      fitView
      nodeTypes={nodeTypes}
      selectionMode={SelectionMode.Full}
      colorMode="system"
    >
      <Background />
      {/* 👇 This is toolbar is displayed when multiple nodes are selected to group them */}
      <SelectedNodesToolbar />
    </ReactFlow>
  );
}
