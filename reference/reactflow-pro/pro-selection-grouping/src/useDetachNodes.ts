import { useCallback } from 'react';
import { useReactFlow, type Node } from '@xyflow/react';

function useDetachNodes() {
  const { setNodes, getNodes, getInternalNode } = useReactFlow();

  const detachNodes = useCallback(
    (ids: string[], removeParentId?: string) => {
      const idsToDetach = new Set(ids);
      const nextNodes: Node[] = [];

      for (const node of getNodes()) {
        if (removeParentId === node.id) {
          continue;
        }

        if (idsToDetach.has(node.id) && node.parentId) {
          const parentNode = getInternalNode(node.parentId);

          nextNodes.push({
            ...node,
            position: {
              x:
                node.position.x +
                (parentNode?.internals.positionAbsolute.x ?? 0),
              y:
                node.position.y +
                (parentNode?.internals.positionAbsolute.y ?? 0),
            },
            parentId: undefined,
          });
        } else {
          nextNodes.push(node);
        }
      }

      setNodes(nextNodes);
    },
    [setNodes, getNodes, getInternalNode],
  );

  return detachNodes;
}

export default useDetachNodes;
