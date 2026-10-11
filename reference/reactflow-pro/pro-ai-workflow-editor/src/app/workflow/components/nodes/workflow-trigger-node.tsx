'use client';
import React, { memo, useCallback, useState } from 'react';
import {
  getIncomers,
  getOutgoers,
  IsValidConnection,
  type Node,
  NodeProps,
  OnConnect,
  Position,
  useReactFlow,
} from '@xyflow/react';
import { Play, GripVertical } from 'lucide-react';

import {
  NodeProcessor,
  WorkflowNodeData,
} from '@/app/workflow/components/nodes';
import { BaseNode } from '@/components/base-node';
import { NodeStatusIndicator } from '@/components/node-status-indicator';
import { Button } from '@/components/ui/button';
import { BaseHandle } from '@/components/base-handle';
import { useWorkflowRunner } from '../../hooks/use-workflow-runner';

export type WorkflowTriggerNodeType = Node<
  WorkflowTriggerNodeData,
  'workflow-trigger-node'
>;

export type WorkflowTriggerNodeData = WorkflowNodeData;

export const processWorkflowTriggerNode: NodeProcessor<
  WorkflowTriggerNodeType
> = async () => {
  return { status: 'success' };
};

/**
 *
 */
function WorkflowTriggerNode({ id }: NodeProps<WorkflowTriggerNodeType>) {
  const { getNodes, getEdges, setEdges } = useReactFlow();
  const { runWorkflow, stopWorkflow } = useWorkflowRunner();
  const [running, setRunning] = useState(false);

  // To determine a valid connection we want to check the target node's ancestors
  // to see if any of them are connected to the same trigger. If any are, then
  // this node will eventually be processed as the workflow runs and we don't want
  // to allow a connection that would cause a node to be processed more than once.
  const isValidTriggerConnection = useCallback<IsValidConnection>(
    (connection) => {
      let ancestorWillBeTriggered = false;

      const nodes = getNodes();
      const edges = getEdges();
      const ancestors = getIncomers({ id: connection.target }, nodes, edges);
      const seen = new Set<string>();

      while (ancestors.length) {
        const ancestor = ancestors.shift()!;

        if (seen.has(ancestor.id)) {
          continue;
        }

        if (ancestor.id === connection.source) {
          ancestorWillBeTriggered = true;
          break;
        }

        seen.add(ancestor.id);
        ancestors.push(...getIncomers({ id: ancestor.id }, nodes, edges));
      }

      return !ancestorWillBeTriggered;
    },
    [getEdges, getNodes],
  );

  // While the `isValidTriggerConnection` logic prevents users from connecting
  // a trigger to a node that would cause it to be processed multiple times, we
  // also need to handle the case where the trigger is connected to a node and
  // one of that node's descendants is _already_ connected to the trigger.
  //
  // Instead of invalidating the connection, we want to allow it but automatically
  // remove the downstream connection from the trigger to the descendant node,
  // since that node will now be processed as part of the workflow run triggered
  // by one of its ancestors.
  const onConnect = useCallback<OnConnect>(
    (connection) => {
      const trigger = connection.source;
      const nodes = getNodes();
      const edges = getEdges();
      // We start with an array of the target node's immediate descendants, and then
      // walk the
      const descendants = getOutgoers({ id: connection.target }, nodes, edges);
      const edgesToRemove = new Set<string>();
      const seen = new Set<string>();

      while (descendants.length) {
        // Non-null assertion here is always safe because we just checked that there's
        // at least one element in the array.
        const descendant = descendants.shift()!;

        if (seen.has(descendant.id)) {
          continue;
        }

        const triggerEdge = edges.find(
          (edge) => edge.source === trigger && edge.target === descendant.id,
        );

        if (triggerEdge) {
          edgesToRemove.add(triggerEdge.id);
        }

        seen.add(descendant.id);
        descendants.push(...getOutgoers({ id: descendant.id }, nodes, edges));
      }

      setEdges(edges.filter((edge) => !edgesToRemove.has(edge.id)));
    },
    [getEdges, getNodes, setEdges],
  );

  const handleClick = () => {
    if (running) {
      stopWorkflow();
    } else {
      const nodes = getNodes();
      const edges = getEdges();
      const startNodes = getOutgoers({ id }, nodes, edges);

      setRunning(true);
      runWorkflow(startNodes.map((node) => node.id)).finally(() => {
        setRunning(false);
      });
    }
  };

  return (
    <NodeStatusIndicator status={running ? 'loading' : 'initial'}>
      <BaseNode className="p-1">
        <div className="flex items-center">
          <GripVertical className="fill-red-50" size="20" />
          <Button
            variant="ghost"
            className="nodrag aspect-square"
            disabled={running}
            onClick={handleClick}
          >
            <Play className="stroke-blue-500 fill-blue-500" />
          </Button>
        </div>
        <BaseHandle
          type="source"
          position={Position.Bottom}
          id="trigger-output"
          isValidConnection={isValidTriggerConnection}
          onConnect={onConnect}
        />
      </BaseNode>
    </NodeStatusIndicator>
  );
}

export default memo(WorkflowTriggerNode) as typeof WorkflowTriggerNode;
