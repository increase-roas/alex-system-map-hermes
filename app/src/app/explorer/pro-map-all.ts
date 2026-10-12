/**
 * Three full versions side by side:
 *   left   = Version 1, original 13 steps (pro-map-data-v1.ts), ids prefixed o_
 *   middle = Version 2, Codex review, 12 steps (pro-map-data.ts)
 *   right  = Yours, 12 steps (pro-map-data.ts)
 *   far right = Version 4, Hermes Agent (pro-map-data-hermes.ts), ids prefixed h_
 */
import { PRO_EDGES as V2_EDGES, PRO_NODES as V2_NODES, type ProEdge, type ProNode } from './pro-map-data';
import { V1_EDGES, V1_NODES } from './pro-map-data-v1';
import { H_EDGES, H_NODES } from './pro-map-data-hermes';

const SHIFT = -1480;
const rename = (id: string) => (id.startsWith('p_') ? `o_${id.slice(2)}` : id);

const v1Nodes: ProNode[] = (V1_NODES as ProNode[])
  .filter((n) => n.id.startsWith('p_'))
  .map((n) => ({ ...n, id: rename(n.id), x: n.x + SHIFT }));
const v1Edges: ProEdge[] = (V1_EDGES as ProEdge[])
  .filter((e) => e.source.startsWith('p_') && e.target.startsWith('p_'))
  .map((e) => ({ ...e, id: `o_${e.id}`, source: rename(e.source), target: rename(e.target) }));

export const PRO_NODES: ProNode[] = [...v1Nodes, ...V2_NODES, ...H_NODES];
export const PRO_EDGES: ProEdge[] = [...v1Edges, ...V2_EDGES, ...H_EDGES];
export type { ProEdge, ProNode };
