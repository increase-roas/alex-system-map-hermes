'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  Background,
  Connection,
  Edge,
  ReactFlow,
  useNodesInitialized,
  useReactFlow,
} from '@xyflow/react';
import { useShallow } from 'zustand/react/shallow';

import FlowContextMenu from '@/app/workflow/components/flow-context-menu';
import { nodeTypes } from '@/app/workflow/components/nodes';
import { useDragAndDrop } from '@/app/workflow/hooks/useDragAndDrop';
import { useAppStore } from '@/app/workflow/store';
import { AppStore } from '@/app/workflow/store/app-store';
import { layoutGraph } from '../utils/layout-helper';
import { WorkflowControls } from './controls';

const selector = (state: AppStore) => ({
  nodes: state.nodes,
  edges: state.edges,
  onNodesChange: state.onNodesChange,
  onEdgesChange: state.onEdgesChange,
  onConnect: state.onConnect,
  setNodes: state.setNodes,
});

// We assume that the handle ids are in the format `${typeFlowingOnWire}-${handleId}`
// For example `image-output` or `text-prompt`.
// See also:
// - `components/nodes/index.tsx` for definition of the node configuration
// - `data/workflow-data.tsx` for a definition of an initial flow
// - Components `generate-text-node.tsx` and `generate-image-node.tsx`
const isValidConnection = (c: Edge | Connection) => {
  return (
    typeof c.sourceHandle === 'string' &&
    typeof c.targetHandle === 'string' &&
    c.sourceHandle.split('-')[0] === c.targetHandle.split('-')[0]
  );
};

export default function Workflow() {
  const store = useAppStore(useShallow(selector));
  const { onDragOver, onDrop } = useDragAndDrop();
  const { fitView } = useReactFlow();
  const [hasLayouted, setHasLayouted] = useState(false);
  const nodesInitialized = useNodesInitialized();

  const layoutNodes = useCallback(async () => {
    const layoutedNodes = await layoutGraph(store.nodes, store.edges);
    store.setNodes(layoutedNodes);
    setHasLayouted(true);
    fitView();
  }, [fitView, store]);

  useEffect(() => {
    if (nodesInitialized && !hasLayouted) {
      layoutNodes();
    }
  }, [nodesInitialized, hasLayouted, layoutNodes]);

  return (
    <ReactFlow
      nodes={store.nodes}
      edges={store.edges}
      onNodesChange={store.onNodesChange}
      onEdgesChange={store.onEdgesChange}
      onConnect={store.onConnect}
      nodeTypes={nodeTypes}
      onDragOver={onDragOver}
      onDrop={onDrop}
      isValidConnection={isValidConnection}
      colorMode="system"
    >
      <Background />
      <WorkflowControls />
      <FlowContextMenu />
    </ReactFlow>
  );
}
