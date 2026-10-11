import { useCallback } from 'react';
import {
  type OnConnect,
  type ProOptions,
  type EdgeTypes,
  type DefaultEdgeOptions,
  type NodeTypes,
} from '@xyflow/react';
import { ReactFlow, ReactFlowProvider, addEdge } from '@xyflow/react';

import '@xyflow/react/dist/style.css';

import {
  ROUTABLE_EDGE_TYPE,
  RoutableEdgeComponent,
} from './components/RoutableEdge';

import {
  EXAMPLE_NODE_TYPE,
  ExampleNodeComponent,
} from './components/ExampleNode';

import { useInitialElements } from './hooks/useInitialElements';
import { useLibavoid } from './hooks/useLibavoid';

const proOptions = {
  hideAttribution: true,
} satisfies ProOptions;

const nodeTypes = {
  [EXAMPLE_NODE_TYPE]: ExampleNodeComponent,
} satisfies NodeTypes;

const edgeTypes = {
  [ROUTABLE_EDGE_TYPE]: RoutableEdgeComponent,
} satisfies EdgeTypes;

const defaultEdgeOptions = {
  type: ROUTABLE_EDGE_TYPE,
  animated: true,
} satisfies DefaultEdgeOptions;

function LibavoidEdgeRoutingExample() {
  const { nodes, onNodesChange, edges, setEdges, onEdgesChange } =
    useInitialElements();

  const onConnect: OnConnect = useCallback(
    (connection) => setEdges((edges) => addEdge(connection, edges)),
    [setEdges],
  );

  useLibavoid();

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      edgeTypes={edgeTypes}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      onConnect={onConnect}
      defaultEdgeOptions={defaultEdgeOptions}
      proOptions={proOptions}
      zoomOnDoubleClick={false}
      fitView
    />
  );
}

const ReactFlowWrapper = () => {
  return (
    <ReactFlowProvider>
      <LibavoidEdgeRoutingExample />
    </ReactFlowProvider>
  );
};

export default ReactFlowWrapper;
