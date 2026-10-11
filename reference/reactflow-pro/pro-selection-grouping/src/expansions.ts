import type { Dimensions, Node, XYPosition } from '@xyflow/react';

type Expansion = {
  dimension: Dimensions;
  offset: XYPosition;
  position: XYPosition;
};

type Bounds = {
  x1: number;
  x2: number;
  y1: number;
  y2: number;
  numberOfChildren: number;
};

function getDimensions(node: Node): Dimensions {
  return {
    width: node.width ?? node.measured?.width ?? 0,
    height: node.height ?? node.measured?.height ?? 0,
  };
}

function addRectToBounds(
  bounds: Bounds,
  position: XYPosition,
  dimensions: Dimensions,
  padding: number,
) {
  const { x, y } = position;
  const x1 = x - padding;
  const y1 = y - padding;
  bounds.x1 = x1 < bounds.x1 ? x1 : bounds.x1;
  bounds.y1 = y1 < bounds.y1 ? y1 : bounds.y1;

  const x2 = x + dimensions.width + padding;
  const y2 = y + dimensions.height + padding;
  bounds.x2 = x2 > bounds.x2 ? x2 : bounds.x2;
  bounds.y2 = y2 > bounds.y2 ? y2 : bounds.y2;
  bounds.numberOfChildren += 1;
}

function getBounds(boundsByParent: Map<string, Bounds>, parentId: string) {
  let bounds = boundsByParent.get(parentId);

  if (!bounds) {
    bounds = {
      x1: Infinity,
      y1: Infinity,
      x2: -Infinity,
      y2: -Infinity,
      numberOfChildren: 0,
    };
    boundsByParent.set(parentId, bounds);
  }

  return bounds;
}

function resolveExpansion(
  parent: Node,
  childBounds: Bounds,
): Expansion | undefined {
  const { x1, y1, x2, y2 } = childBounds;
  const width = x2 - x1;
  const height = y2 - y1;
  const parentDimensions = getDimensions(parent);

  if (
    width === parentDimensions.width &&
    height === parentDimensions.height &&
    x1 === 0 &&
    y1 === 0
  ) {
    return undefined;
  }

  const { x, y } = parent.position;

  const dimension = { width, height };
  const offset = { x: x1, y: y1 };
  const position = { x: x + x1, y: y + y1 };

  return { dimension, offset, position };
}

export function expandGroupNodes<T extends Node>(
  nodes: T[],
  padding = 25,
): T[] {
  const markedForDeletion = new Map<string, Node>();
  const boundsByParent = new Map<string, Bounds>();

  /** We save any expansion of parents, to be able to offset any children
   * when the parent resizes. This is essential because children have
   * relative positions to their parents.
   */
  const parentExpansions = new Map<string, Expansion>();

  /**
   * We know that children always come after their parents in the nodes array,
   * so we iterate backwards to determine the bounds of children, and calculate
   * the correct expansion when we reach the parent.
   * This is essential because parents might be nested. When we get to the parent
   * of a parent, we need to know any new dimensions children (who are parents themselves)
   * might have.
   */
  for (let i = nodes.length - 1; i >= 0; i--) {
    const node = nodes[i];
    // see if we've already calculated the bounds of this node's children
    const childBounds = boundsByParent.get(node.id);

    // We mark empty groups or groups with a single child for deletion
    if (
      (!childBounds || childBounds.numberOfChildren === 1) &&
      node.type === 'group'
    ) {
      markedForDeletion.set(node.id, node);
      continue;
    }
    // if we have, use them to calculate the new position & dimensions of the node
    const expansion = childBounds
      ? resolveExpansion(node, childBounds)
      : undefined;

    // if we have an expansion, store it for the parent
    // so we can use it for any potential parents.
    if (expansion) {
      parentExpansions.set(node.id, expansion);
    }

    // we can ignore nodes that don't have a parent for the further steps
    if (!node.parentId) continue;

    // When a node has a parentId it might contribute to the bounds of its parent
    const bounds = getBounds(boundsByParent, node.parentId);
    addRectToBounds(
      bounds,
      expansion ? expansion.position : node.position,
      expansion ? expansion.dimension : getDimensions(node),
      padding,
    );
  }

  // We don't have to update any nodes if we don't have any expansions
  if (parentExpansions.size === 0) {
    return nodes;
  }

  const newNodes = [];
  for (const node of nodes) {
    if (markedForDeletion.has(node.id)) {
      continue;
    }

    const parentMarkedForDeletion = markedForDeletion.get(node.parentId || '');
    if (parentMarkedForDeletion) {
      newNodes.push({
        ...node,
        position: {
          x: node.position.x + parentMarkedForDeletion.position.x,
          y: node.position.y + parentMarkedForDeletion.position.y,
        },
        parentId: undefined,
      });
      continue;
    }

    // the node might be a parent and is expanding
    const expansion = parentExpansions.get(node.id);
    // the node might be child and its parent is expanding
    const parentExpansion = parentExpansions.get(node.parentId || '');

    /**
     * Obviously if the node is expanding itself, we need to adjust its position & dimensions.
     * If its parent is expanding, we need to offset its position to account for the parent's expansion.
     */
    if (expansion && parentExpansion) {
      newNodes.push({
        ...node,
        ...expansion.dimension,
        position: {
          x: expansion.position.x - parentExpansion.offset.x,
          y: expansion.position.y - parentExpansion.offset.y,
        },
      });
      continue;
    }

    if (expansion) {
      newNodes.push({
        ...node,
        ...expansion.dimension,
        position: expansion.position,
      });
      continue;
    }

    if (parentExpansion) {
      newNodes.push({
        ...node,
        position: {
          x: node.position.x - parentExpansion.offset.x,
          y: node.position.y - parentExpansion.offset.y,
        },
      });
      continue;
    }

    // if there is nothing to adjust, return the node to avoid an unnecessary re-render
    newNodes.push(node);
  }
  return newNodes;
}
