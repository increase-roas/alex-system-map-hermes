import { NodeProps, Node, Position, HandleType, Handle } from '@xyflow/react';

export const EXAMPLE_NODE_TYPE = 'example';

export type ExampleNodeData = {
  label: string;
  /** It's important to know that if you update this node's data to add or remove
   * handles after it's been created, you must call `updateNodeInternals` with the
   * node's id. This lets React Flow know to recalculate each handle's position,
   * which we can then pass to libavoid for proper edge routing.
   */
  handles: Record<
    Position,
    {
      /** Handle ids must be positive integers for libavoid to work correctly, but
       * React Flow works with string ids. We can satisfy both constraints by using
       * TypeScript's template literal types to enforce that handle ids are strings
       * that contain numbers.
       */
      id: `${number}`;
      type: HandleType;
    }[]
  >;
};

export type ExampleNode = Node<ExampleNodeData, typeof EXAMPLE_NODE_TYPE>;

/** This example node is just for demo purposes, and features a dynamic number
 * of handles on each side. This lets us show how libavoid can work with more
 * than one source/target handle on each node.
 */
export function ExampleNodeComponent({ data }: NodeProps<ExampleNode>) {
  const handles = data?.handles ?? {};

  return (
    <>
      <div>{data.label}</div>

      {Object.entries(handles).map(([position, handles]) => (
        <ExampleNodeHandles
          key={position}
          side={position as Position}
          handles={handles}
        />
      ))}
    </>
  );
}

type ExampleNodeHandlesProps = {
  side: Position;
  handles: { id: `${number}`; type: HandleType }[];
};

function ExampleNodeHandles({ side, handles }: ExampleNodeHandlesProps) {
  return (
    <div className="handles" data-side={side}>
      {handles.map((handle) => (
        <Handle
          key={handle.id}
          type={handle.type}
          position={side}
          id={handle.id}
        />
      ))}
    </div>
  );
}

// UTILS -----------------------------------------------------------------------

export const getHandlePosition = (data: ExampleNodeData, handleId: string) => {
  for (const [position, handles] of Object.entries(data.handles)) {
    if (handles.some((handle) => handle.id === handleId)) {
      return position as Position;
    }
  }

  return null;
};

/** Seed the `handles` field of our example node's data with random handles. This
 * is only used in the demo to create new nodes with some handles already in place.
 */
export const generateRandomHandles = (): ExampleNodeData['handles'] => {
  const count = Math.floor(Math.random() * 5) + 1;
  const sides = Object.values(Position).sort(() => Math.random() - 0.5);
  const handles: ExampleNodeData['handles'] = {
    [Position.Top]: [],
    [Position.Right]: [],
    [Position.Bottom]: [],
    [Position.Left]: [],
  };

  for (let id = 1, side = sides.shift(); id <= count; id++) {
    const type = Math.random() < 0.5 ? 'source' : 'target';
    const handle = { id: `${id}`, type } as const;

    handles[side!].push(handle);

    if (sides.length && Math.random() < 0.5) {
      side = sides.shift();
    }
  }

  return handles;
};
