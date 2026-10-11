'use client';
import React, { memo, useCallback, useEffect, useRef, useState } from 'react';
import {
  type Node,
  NodeProps,
  Position,
  useNodeConnections,
  useNodesData,
  useReactFlow,
} from '@xyflow/react';

import {
  NodeProcessor,
  WorkflowNodeData,
} from '@/app/workflow/components/nodes';
import { BaseNode, BaseNodeContent } from '@/components/base-node';
import { LabeledHandle } from '@/components/labeled-handle';
import { NodeStatusIndicator } from '@/components/node-status-indicator';
import { Textarea } from '@/components/ui/textarea';
import { RunnableNodeHeader } from '../runnable-node-header';
import { Button } from '@/components/ui/button';
import { Lock, LockOpen } from 'lucide-react';
import { cn } from '@/lib/utils';

export type TextInputNodeType = Node<TextInputNodeData, 'text-input-node'>;

export type TextInputNodeData = WorkflowNodeData & {
  text?: string;
};

export const processTextInputNode: NodeProcessor<
  TextInputNodeType
> = async () => {
  return { status: 'success' };
};

function TextInputNode({ id, data }: NodeProps<TextInputNodeType>) {
  const { updateNodeData } = useReactFlow();

  const [disabled, setDisabled] = useState(false)
  // Once the user manually interacts with the disabled toggle, we no longer update
  // it automatically when connections change.
  const disabledTouched = useRef(false)

  const inputConnections = useNodeConnections({
    handleId: 'text-input',
    handleType: 'target',
  });

  const inputNodes = useNodesData(
    inputConnections.map((connection) => connection.source),
  );

  const hasInputs = inputConnections.length > 0;
  const text = data?.text ?? '';

  const onTextChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      updateNodeData(id, { text: e.target.value });
    },
    [id, updateNodeData],
  );

  const onDisabledToggle = useCallback(() => {
    setDisabled((prev) => !prev);
    disabledTouched.current = true;
  }, [])

  // This effect reactively updates the node's data whenever its input connections
  // change. It's not common to use effects for reactive state updates in React,
  // but in this case we treat we can think of this node's input connections as
  // a sort of external store that we want this component to sync with.
  useEffect(() => {
    if (!hasInputs) {
      setDisabled(prev => disabledTouched.current ? prev : false)
      return
    };

    const text = inputConnections.reduce((text, connection) => {
      if (!connection.sourceHandle) return text;

      const node = inputNodes.find((node) => node.id === connection.source)!;
      // Handles in this app follow a naming convention of `${field}-{'input' | 'output'}`
      // and we can take advantage of that by extracting the field name and attempting
      // to read that field from the source node's data.
      const field = connection.sourceHandle.split('-')[0];

      return text + ' ' + (node.data?.[field] ?? '');
    }, '');

    setDisabled(prev => disabledTouched.current ? prev : true)
    updateNodeData(id, { text });
  }, [id, hasInputs, inputConnections, inputNodes, updateNodeData]);

  return (
    <NodeStatusIndicator status={data?.status}>
      <BaseNode className="w-[350px]">
        <RunnableNodeHeader
          nodeId={id}
          title={data?.title}
          icon={data?.icon}
          status={data?.status}
        >
          <Button variant="ghost" className={cn("nodrag px-1!", disabled && 'bg-accent')} onClick={onDisabledToggle}>
            {disabled ? <Lock /> : <LockOpen />}
          </Button>
        </RunnableNodeHeader>
        <BaseNodeContent>
          <div className="flex justify-start text-sm">
            <LabeledHandle
              id="text-input"
              title="Text"
              type="target"
              position={Position.Left}
              className="justify-self-end -left-3"
            />
          </div>

          <Textarea
            value={text}
            disabled={disabled}
            onChange={onTextChange}
            className="w-full nodrag nopan nowheel h-full resize-none"
            placeholder="Enter your text here..."
          />

          <div className="flex justify-end text-sm">
            <LabeledHandle
              id="text-output"
              title="Text"
              type="source"
              position={Position.Right}
              className="justify-self-end -right-3"
            />
          </div>
        </BaseNodeContent>
      </BaseNode>
    </NodeStatusIndicator>
  );
}

export default memo(TextInputNode) as typeof TextInputNode;
