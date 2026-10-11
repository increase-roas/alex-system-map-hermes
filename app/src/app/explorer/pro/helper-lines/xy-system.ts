import type { Box, InternalNode, Node } from '@xyflow/react';
/** Local copy of @xyflow/system nodeToBox (that package is not a direct dependency here). */
export function nodeToBox(node: InternalNode | Node): Box {
  const { x, y } = 'internals' in node ? node.internals.positionAbsolute : node.position;
  const w = node.measured?.width ?? node.width ?? 0;
  const h = node.measured?.height ?? node.height ?? 0;
  return { x, y, x2: x + w, y2: y + h };
}
