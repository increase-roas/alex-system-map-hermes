import type { Node } from '@xyflow/react';
import { useNodesState, useEdgesState, Position } from '@xyflow/react';

import { EXAMPLE_NODE_TYPE } from '../components/ExampleNode';
import { ROUTABLE_EDGE_TYPE } from '../components/RoutableEdge';

const initialNodes = [
  {
    id: '1',
    type: EXAMPLE_NODE_TYPE,
    data: {
      label: 'Node 1',
      handles: {
        [Position.Left]: [
          { id: '1', type: 'target' },
          { id: '2', type: 'target' },
        ],
        [Position.Right]: [
          { id: '3', type: 'source' },
          { id: '4', type: 'source' },
          { id: '5', type: 'source' },
        ],
      },
    },
    position: { x: 0, y: 0 },
  },
  {
    id: '2',
    type: EXAMPLE_NODE_TYPE,
    data: {
      label: 'Node 2',
      handles: {
        [Position.Left]: [
          { id: '1', type: 'target' },
          { id: '2', type: 'target' },
        ],
        [Position.Right]: [
          { id: '3', type: 'source' },
          { id: '4', type: 'source' },
        ],
      },
    },
    position: { x: 150, y: -150 },
  },
  {
    id: '3',
    type: EXAMPLE_NODE_TYPE,
    data: {
      label: 'Node 3',
      handles: {
        [Position.Left]: [
          { id: '1', type: 'target' },
          { id: '2', type: 'target' },
        ],
        [Position.Right]: [
          { id: '3', type: 'source' },
          { id: '4', type: 'source' },
        ],
      },
    },
    position: { x: 150, y: -75 },
  },
  {
    id: '4',
    type: EXAMPLE_NODE_TYPE,
    data: {
      label: 'Node 4',
      handles: {
        [Position.Right]: [
          { id: '1', type: 'source' },
          { id: '2', type: 'source' },
        ],
      },
    },
    position: { x: 150, y: 0 },
  },
  {
    id: '5',
    type: EXAMPLE_NODE_TYPE,
    data: {
      label: 'Node 5',
      handles: {
        [Position.Left]: [
          { id: '1', type: 'target' },
          { id: '2', type: 'target' },
          { id: '3', type: 'target' },
        ],
        [Position.Right]: [
          { id: '4', type: 'source' },
          { id: '5', type: 'source' },
        ],
      },
    },
    position: { x: 300, y: 0 },
  },
] satisfies Node[];

const initialEdges = [
  {
    id: '1:3->2:1',
    type: ROUTABLE_EDGE_TYPE,
    source: '1',
    sourceHandle: '3',
    target: '2',
    targetHandle: '1',
  },
  {
    id: '1:4->3:1',
    type: ROUTABLE_EDGE_TYPE,
    source: '1',
    sourceHandle: '4',
    target: '3',
    targetHandle: '1',
  },
  {
    id: '1:5->5:3',
    type: ROUTABLE_EDGE_TYPE,
    source: '1',
    sourceHandle: '5',
    target: '5',
    targetHandle: '3',
  },
  {
    id: '2:3->5:1',
    type: ROUTABLE_EDGE_TYPE,
    source: '2',
    sourceHandle: '3',
    target: '5',
    targetHandle: '1',
  },
  {
    id: '3:3->5:2',
    type: ROUTABLE_EDGE_TYPE,
    source: '3',
    sourceHandle: '3',
    target: '5',
    targetHandle: '2',
  },
  {
    id: '4:1->3:2',
    type: ROUTABLE_EDGE_TYPE,
    source: '4',
    sourceHandle: '1',
    target: '3',
    targetHandle: '2',
  },
  {
    id: '5:4->1:2',
    type: ROUTABLE_EDGE_TYPE,
    source: '5',
    sourceHandle: '4',
    target: '1',
    targetHandle: '2',
  },
];

export function useInitialElements() {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  return {
    nodes,
    setNodes,
    onNodesChange,
    edges,
    setEdges,
    onEdgesChange,
  };
}
