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
import { STICKY } from './pro-map-sticky';

const SHIFT = -1480;
const rename = (id: string) => (id.startsWith('p_') ? `o_${id.slice(2)}` : id);

const v1Nodes: ProNode[] = (V1_NODES as ProNode[])
  .filter((n) => n.id.startsWith('p_'))
  .map((n) => ({ ...n, id: rename(n.id), x: n.x + SHIFT }));
const v1Edges: ProEdge[] = (V1_EDGES as ProEdge[])
  .filter((e) => e.source.startsWith('p_') && e.target.startsWith('p_'))
  .map((e) => ({ ...e, id: `o_${e.id}`, source: rename(e.source), target: rename(e.target) }));

/** Puts each sticky note inside the pop-up: on the matching example, or on the card when no example title is given. */
function withSticky(n: ProNode): ProNode {
  const notes = STICKY.filter((s) => s.ids.includes(n.id));
  if (!notes.length) return n;
  const det = n.detail ?? {};
  const examples = (det.examples ?? []).map((e) => {
    const mine = notes.filter((s) => s.title === e.title).map(({ text, src }) => ({ text, src }));
    return mine.length ? { ...e, sticky: mine } : e;
  });
  const titles = new Set(examples.map((e) => e.title));
  const card = notes.filter((s) => !s.title || !titles.has(s.title)).map(({ text, src }) => ({ text, src }));
  return { ...n, detail: { ...det, examples, sticky: card.length ? card : det.sticky } };
}
export const PRO_NODES: ProNode[] = [...v1Nodes, ...V2_NODES, ...H_NODES].map(withSticky);
export const PRO_EDGES: ProEdge[] = [...v1Edges, ...V2_EDGES, ...H_EDGES];
export type { ProEdge, ProNode };
