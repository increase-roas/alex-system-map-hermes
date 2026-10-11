import { useEffect, useRef, useState } from 'react';
import type { ShapeRef, ConnRef, Router } from 'libavoid-js';
import { AvoidLib } from 'libavoid-js';
import { type Node, type Edge } from '@xyflow/react';
import { useReactFlow, useNodesInitialized, useStore } from '@xyflow/react';

// Libavoid will attempt to load the WASM blob using a relative path from the
// package's entry module by default. In development with vite this will work, as
// dependencies aren't bundled, but when building for production vite loses the
// ability to "see" where that WASM blob is and include it in the final bundle.
//
// Because libavoid-js defines an explicit `exports` map in its package.json, we
// can't import it directly. To work around this we have to vendor the blob and
// import it as a URL using vite's `?url` import suffix: this instructs vite to
// keep the asset and generate a deterministic URL for it in the final bundle.
import wasmUrl from '../assets/libavoid.wasm?url';
import { ExampleNodeData, getHandlePosition } from '../components/ExampleNode';

export function useLibavoid() {
  const [router, setRouter] = useState<Router | null>(null);

  // Libavoid ids must always be positive numbers, but React Flow node ids are
  // arbitrary strings. To bridge this gap we maintain an atomic counter for all
  // nodes, and a mapping from React Flow node ids to libavoid shape ids.
  const shapeIds = useRef<Map<string, number>>(new Map());
  const nextShapeId = useRef(1);

  const shapes = useRef<Map<number, ShapeRef>>(new Map());
  const connections = useRef<Map<string, ConnRef>>(new Map());

  const { setEdges } = useReactFlow();
  const nodesInitialized = useNodesInitialized();
  const elements = useStore(
    (state) => ({ nodes: state.nodes, edges: state.edges }),
    compareElements,
  );

  // The `nodeLookup` is a internal mutable map that React Flow uses to store
  // various node internals. We're using it in this hook to get access to the
  // calculated handle positions so we can feed those into libavoid as "pins" that
  // edges connect to.
  const nodeLookup = useStore((state) => state.nodeLookup);

  // React triggers effects twice during development to identify bugs around side
  // effects and hook dependencies. In our case we definitely only want to load
  // the libavoid WASM module exactly once, so we use a ref to track whether that's
  // in progress or not.
  const loading = useRef(false);

  useEffect(() => {
    if (!nodesInitialized || loading.current) return;
    if (!router) {
      loading.current = true;

      AvoidLib.load(wasmUrl)
        .then(() => {
          const instance = AvoidLib.getInstance();
          const router = new instance.Router(instance.OrthogonalRouting);

          // The libavoid router can be configured with a number of different
          // parameters and options. You can find documentation for all of them
          // by taking a look at the original c++ reference:
          //
          // https://www.adaptagrams.org/documentation/namespaceAvoid.html#a8a0154ae39129e7737d98e5a83daed19
          //
          // Below we've configured some options that you'll typically want to
          // set up when working with React Flow.

          // You can think of this option as the "padding" around shapes that
          // means edges wont run directly along the side of a shape. Be mindful
          // that if it is impossible for libavoid to find a path that respects
          // this buffer, no route wlil be produced at all and a straight diagonal
          // line from source to target will be rendered.
          router.setRoutingParameter(instance.shapeBufferDistance, 10);

          // If the previous option is padding around nodes, this option helps apply
          // padding around edges. This stops edges from being too bunched together
          // and can make it easier to read flows with many edges with similar
          // paths.
          router.setRoutingParameter(instance.idealNudgingDistance, 10);

          // Libavoid has a number of heuristics it applies to nudge edge paths
          // to produce better-looking diagrams. This one will move edges slightly
          // apart from one another if they end at the same point, but in React
          // Flow we want our edges to all end exactly on the handle they're
          // connected to, so we disable this heuristic.
          router.setRoutingOption(
            instance.nudgeSharedPathsWithCommonEndPoint,
            false,
          );

          // This option can improve the quality of libavoid's other nudging
          // heuristics by identifying paths that can be unified before running
          // the other nudging steps. This comes at a performance cost, so make
          // sure you're taking that into account for large flows with many edges.
          router.setRoutingOption(
            instance.performUnifyingNudgingPreprocessingStep,
            true,
          );

          setRouter(router);
        })
        .finally(() => {
          loading.current = false;
        });

      return;
    }

    const instance = AvoidLib.getInstance();

    // First, delete and clean up any nodes that no longer exist. Because libavoid
    // is a WASM module, we have to carefully manage memory to avoid leaks!
    const activeShapeIds = new Set(
      elements.nodes.flatMap((node) => shapeIds.current.get(node.id) ?? []),
    );
    for (const [id, shapeRef] of shapes.current) {
      if (!activeShapeIds.has(id)) {
        router.deleteShape(shapeRef);
        shapes.current.delete(id);
      }
    }

    // Next up we need to create or update shapes for each node in the flow: shapes
    // are how libavoid represents obstacles that edges need to route around.
    for (const node of elements.nodes) {
      const width = node.measured?.width ?? 0;
      const height = node.measured?.height ?? 0;

      const topLeft = new instance.Point(node.position.x, node.position.y);
      const bottomRight = new instance.Point(
        node.position.x + width,
        node.position.y + height,
      );

      // If this node is new then we won't have a libavoid shape id for it yet.
      // In that case we take the value of our atomic counter and then bump it
      // for the next new node.
      if (!shapeIds.current.has(node.id)) {
        shapeIds.current.set(node.id, nextShapeId.current++);
      }

      const id = shapeIds.current.get(node.id)!;
      const box = new instance.Rectangle(topLeft, bottomRight);

      // If we already have a shape allocated for this node, we can just move it
      // to its new position. As the shape moves around existing pins are moved
      // along with it, so we don't need to worry about any additional updates.
      //
      // Note: this example won't detect additional handles added *after* a node
      // is created. If you need to support that, you'll want to keep track of
      // known handles the same way we're keeping track of nodes/shape ids and
      // make sure to add/remove pins as needed.
      if (shapes.current.has(id)) {
        router.moveShape(shapes.current.get(id)!, box);
      } else {
        // In libavoid there's no concept of a "node," instead there are only
        // shapes that edges must be routed around and "pins" that edges can
        // connect to.
        const shape = new instance.ShapeRef(router, box);

        // This example assumes all nodes are our custom `ExampleNode`
        const data = node.data as ExampleNodeData;

        const handles = nodeLookup.get(node.id)?.internals.handleBounds;
        const sourceHandles = handles?.source ?? [];
        const targetHandles = handles?.target ?? [];

        for (const handle of [...sourceHandles, ...targetHandles]) {
          const id = Number(handle.id);
          const position = getHandlePosition(data, handle.id!);

          const pin = new instance.ShapeConnectionPin(
            shape,
            id,
            handle.x + handle.width / 2,
            handle.y + handle.height / 2,
            // When `true` libavoid will place this pin relative to the shape's
            // bounding box, with the previous two arguments expected to be numbers
            // between 0 and 1. Because we know the exact position of our handles,
            // we can set this to `false` and provide the absolute coordinates
            // instead.
            false,
            0,
            // libavoid-js doesn't expose these enum values in the generated
            // TypeScript types, but you can find them in the original c++ reference:
            //
            // https://www.adaptagrams.org/documentation/namespaceAvoid.html#abe35ded63bcd354b31e69f6a5414f610
            //
            position === 'top'
              ? instance.ConnDirUp
              : position === 'bottom'
                ? instance.ConnDirDown
                : position === 'left'
                  ? instance.ConnDirLeft
                  : instance.ConnDirRight,
          );

          pin.setExclusive(false);
        }

        shapes.current.set(id, shape);
      }

      // Clean up the temporary box we created to work with this shape.
      instance.destroy(box);
      instance.destroy(bottomRight);
      instance.destroy(topLeft);
    }

    // As with the nodes, remove any edges from the router that no longer exist
    // in the flow.
    const edgeIds = new Set(elements.edges.map((e) => e.id));
    for (const [id, connRef] of connections.current) {
      if (!edgeIds.has(id)) {
        router.deleteConnector(connRef);
        connections.current.delete(id);
      }
    }

    for (const edge of elements.edges) {
      const sourceShapeId = shapeIds.current.get(edge.source);
      const targetShapeId = shapeIds.current.get(edge.target);

      if (!sourceShapeId || !targetShapeId) continue;

      const sourceShape = shapes.current.get(sourceShapeId);
      const targetShape = shapes.current.get(targetShapeId);

      if (!sourceShape || !targetShape) continue;

      const source = new instance.ConnEnd(
        sourceShape,
        Number(edge.sourceHandle),
      );

      const target = new instance.ConnEnd(
        targetShape,
        Number(edge.targetHandle),
      );

      if (connections.current.has(edge.id)) {
        const connection = connections.current.get(edge.id)!;
        connection.setSourceEndpoint(source);
        connection.setDestEndpoint(target);
      } else {
        const connection = new instance.ConnRef(router, source, target);
        connections.current.set(edge.id, connection);
      }

      instance.destroy(source);
      instance.destroy(target);
    }

    // The actual edge routing is batched for the entire flow and performed in a
    // transaction. It is possible to only process certain edges by calling
    // `connection.processTransaction()` directly on a connection, but that's out
    // of scope for this example.
    router.processTransaction();

    setEdges((edges) =>
      edges.map((edge) => {
        const connection = connections.current.get(edge.id);
        if (!connection) return edge;

        // Finally, calling `displayRoute()` actually gives us the array of points
        // we can pass to our `<RoutableEdge />` component.
        const route = connection.displayRoute();
        const numPoints = route.size();
        const points = [];

        // Note how we're excluding the first and last points here. Those positions
        // are already handled by the source/target positions passed to the edge
        // component so we don't need to duplicate them here.
        for (let i = 1; i < numPoints - 1; i++) {
          const point = route.get_ps(i);
          points.push({ x: point.x, y: point.y });
        }

        return { ...edge, data: { points } };
      }),
    );
  }, [router, nodesInitialized, elements, nodeLookup, setEdges]);
}

type Elements = {
  nodes: Array<Node>;
  edges: Array<Edge>;
};

function compareElements(xs: Elements, ys: Elements) {
  return compareNodes(xs.nodes, ys.nodes) && compareEdges(xs.edges, ys.edges);
}

function compareNodes(xs: Array<Node>, ys: Array<Node>) {
  // the number of nodes changed, so we already know that the nodes are not equal
  if (xs.length !== ys.length) return false;

  for (let i = 0; i < xs.length; i++) {
    const x = xs[i];
    const y = ys[i];

    if (!y) return false;

    if (
      x.measured?.width !== y.measured?.width ||
      x.measured?.height !== y.measured?.height
    ) {
      return false;
    }

    if (x.position.x !== y.position.x || x.position.y !== y.position.y) {
      return false;
    }
  }

  return true;
}

function compareEdges(xs: Array<Edge>, ys: Array<Edge>) {
  if (xs.length !== ys.length) return false;

  for (let i = 0; i < xs.length; i++) {
    const x = xs[i];
    const y = ys[i];

    if (x.source !== y.source || x.target !== y.target) return false;
    if (x?.sourceHandle !== y?.sourceHandle) return false;
    if (x?.targetHandle !== y?.targetHandle) return false;
  }

  return true;
}
