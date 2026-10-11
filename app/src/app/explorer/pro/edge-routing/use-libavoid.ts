'use client';
/**
 * Edge routing around boxes (React Flow Pro "Edge Routing" example, adapted for the org map).
 * Differences from the Pro example: absolute positions (customer boxes have children), lane titles and
 * open customer boxes are not obstacles, and every handle is id "1" = top (target), "2" = bottom (source).
 */
import { useEffect, useRef, useState } from 'react';
import { useNodesInitialized, useReactFlow, useStore, type Edge } from '@xyflow/react';
import { AvoidLib } from '@/vendor/libavoid';

/* eslint-disable @typescript-eslint/no-explicit-any */
type Avoid = any;
const WASM_URL = '/libavoid.wasm';

function isObstacle(id: string, data: unknown) {
  if (id.startsWith('lane:')) return false;
  if (id.startsWith('project:') && (data as { open?: boolean })?.open) return false;
  return true;
}

export function useLibavoid(enabled: boolean) {
  const [router, setRouter] = useState<Avoid | null>(null);
  const shapeIds = useRef<Map<string, number>>(new Map());
  const nextShapeId = useRef(1);
  const shapes = useRef<Map<number, Avoid>>(new Map());
  const connections = useRef<Map<string, Avoid>>(new Map());
  const loading = useRef(false);
  const { setEdges } = useReactFlow();
  const nodesInitialized = useNodesInitialized();
  const nodeLookup = useStore((s) => s.nodeLookup);
  const sig = useStore((s) =>
    s.nodes.map((n) => `${n.id}:${Math.round(n.position.x)},${Math.round(n.position.y)},${n.measured?.width ?? 0},${n.measured?.height ?? 0}`).join('|') +
    '#' + s.edges.map((e) => `${e.id}`).join('|'));

  // Route only after boxes stop moving (drag or slide animation), not on every frame.
  const [stable, setStable] = useState(sig);
  useEffect(() => { const t = setTimeout(() => setStable(sig), 180); return () => clearTimeout(t); }, [sig]);

  useEffect(() => {
    if (!enabled || !nodesInitialized || loading.current) return;
    if (!router) {
      loading.current = true;
      AvoidLib.load(WASM_URL)
        .then(() => {
          const lib = AvoidLib.getInstance();
          const r = new lib.Router(lib.OrthogonalRouting);
          r.setRoutingParameter(lib.shapeBufferDistance, 8);
          r.setRoutingParameter(lib.idealNudgingDistance, 8);
          r.setRoutingOption(lib.nudgeSharedPathsWithCommonEndPoint, false);
          r.setRoutingOption(lib.performUnifyingNudgingPreprocessingStep, true);
          setRouter(r);
        })
        .catch(() => { /* routing is an extra: plain lines stay */ })
        .finally(() => { loading.current = false; });
      return;
    }
    const lib = AvoidLib.getInstance();
    const live = [...nodeLookup.values()].filter((n) => !n.hidden && isObstacle(n.id, n.data));
    const liveIds = new Set(live.map((n) => shapeIds.current.get(n.id)).filter(Boolean));
    for (const [id, ref] of shapes.current) {
      if (!liveIds.has(id)) {
        for (const [eid, c] of connections.current) { try { router.deleteConnector(c); } catch { /* gone */ } connections.current.delete(eid); }
        try { router.deleteShape(ref); } catch { /* gone */ }
        shapes.current.delete(id);
      }
    }
    for (const n of live) {
      const { x, y } = n.internals.positionAbsolute;
      const w = n.measured?.width ?? 0, h = n.measured?.height ?? 0;
      if (!w || !h) continue;
      const tl = new lib.Point(x, y), br = new lib.Point(x + w, y + h), box = new lib.Rectangle(tl, br);
      if (!shapeIds.current.has(n.id)) shapeIds.current.set(n.id, nextShapeId.current++);
      const id = shapeIds.current.get(n.id)!;
      if (shapes.current.has(id)) {
        router.moveShape(shapes.current.get(id), box);
      } else {
        const shape = new lib.ShapeRef(router, box);
        const hb = n.internals.handleBounds;
        for (const hnd of [...(hb?.source ?? []), ...(hb?.target ?? [])]) {
          const pin = new lib.ShapeConnectionPin(shape, Number(hnd.id), hnd.x + hnd.width / 2, hnd.y + hnd.height / 2, false, 0,
            hnd.id === '1' ? lib.ConnDirUp : lib.ConnDirDown);
          pin.setExclusive(false);
        }
        shapes.current.set(id, shape);
      }
      lib.destroy(box); lib.destroy(br); lib.destroy(tl);
    }
    setEdges((edges: Edge[]) => {
      const ids = new Set(edges.map((e) => e.id));
      for (const [id, c] of connections.current) {
        if (!ids.has(id)) { try { router.deleteConnector(c); } catch { /* gone */ } connections.current.delete(id); }
      }
      for (const e of edges) {
        const s = shapes.current.get(shapeIds.current.get(e.source) ?? -1);
        const t = shapes.current.get(shapeIds.current.get(e.target) ?? -1);
        if (!s || !t) continue;
        const src = new lib.ConnEnd(s, 2), dst = new lib.ConnEnd(t, 1);
        const c = connections.current.get(e.id);
        if (c) { c.setSourceEndpoint(src); c.setDestEndpoint(dst); }
        else connections.current.set(e.id, new lib.ConnRef(router, src, dst));
        lib.destroy(src); lib.destroy(dst);
      }
      router.processTransaction();
      return edges.map((e) => {
        const c = connections.current.get(e.id);
        if (!c) return e;
        const route = c.displayRoute();
        const points: { x: number; y: number }[] = [];
        for (let i = 1; i < route.size() - 1; i++) { const p = route.get_ps(i); points.push({ x: p.x, y: p.y }); }
        return { ...e, data: { ...(e.data ?? {}), points } };
      });
    });
  }, [enabled, router, nodesInitialized, stable, nodeLookup, setEdges]);
}
