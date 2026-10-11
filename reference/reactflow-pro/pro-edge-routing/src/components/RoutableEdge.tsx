import { useMemo } from 'react';
import type { Edge, EdgeProps } from '@xyflow/react';
import { BaseEdge, XYPosition, getSmoothStepPath } from '@xyflow/react';

export type RoutableEdge = Edge<{
  /**
   * An array of points that the edge should pass through, *excluding* the source
   * and target handle positions.
   */
  points: XYPosition[];
}>;

export const ROUTABLE_EDGE_TYPE = 'routable';

export function RoutableEdgeComponent({
  sourceX,
  sourceY,
  targetX,
  targetY,
  markerStart,
  markerEnd,
  data,
  style,
}: EdgeProps<RoutableEdge>) {
  const points = data?.points ?? [];
  const path = usePath(points, sourceX, sourceY, targetX, targetY);

  return (
    <BaseEdge
      style={style}
      path={path}
      markerStart={markerStart}
      markerEnd={markerEnd}
    />
  );
}

// HOOKS -----------------------------------------------------------------------

const usePath = (
  points: XYPosition[],
  sourceX: number,
  sourceY: number,
  targetX: number,
  targetY: number,
) => {
  return useMemo(() => {
    if (points.length === 0) {
      // It's possible that libavoid cannot calculate a route for a given edge
      // because it would not satisfy any of the constraints we've set (like the
      // buffer distance). We can detect those cases by checking if the `points`
      // array is empty, and if so falling back to React Flow's built-in smooth
      // step edge.
      //
      // This won't route the path intelligent around other nodes, but *will*
      // produce an orthogonal path that matches those produced by libavoid.
      const [path] = getSmoothStepPath({
        sourceX,
        sourceY,
        targetX,
        targetY,
        offset: 0,
        borderRadius: 0,
      });

      return path;
    }

    const source = { x: sourceX, y: sourceY };
    const target = { x: targetX, y: targetY };
    const allPoints = [source, ...points, target];

    let path = '';

    for (const point of allPoints) {
      const x = point.x.toFixed(2);
      const y = point.y.toFixed(2);

      path += path ? ` L ${x} ${y}` : `M ${x} ${y}`;
    }

    return path;
  }, [points, sourceX, sourceY, targetX, targetY]);
};
