// Test helper: Langflow's real connection rule, checked on a saved flow file.
// A normal edge is compatible when the source type is in the target input's inputTypes (or "Any").
// A loop feedback edge (target handle has no fieldName) is compatible when the source type is in the target
// node's loop output's types or loop_types, read from the target node in the same file. Used by the live
// tests to prove that the engine validator's level-3 warnings are false alarms.

type Handle = { output_types?: string[]; inputTypes?: string[]; fieldName?: string; name?: string };
type Output = { name?: string; types?: string[]; loop_types?: string[]; allows_loop?: boolean };
export type SavedFlow = {
  data: {
    nodes: Array<{ id: string; data?: { node?: { outputs?: Output[] } } }>;
    edges: Array<{ source: string; target: string; data: { sourceHandle: Handle; targetHandle: Handle } }>;
  };
};

/** Returns one line per edge whose source type the target does not accept (empty when all are compatible). */
export function edgeTypeMismatches(flow: SavedFlow): string[] {
  const out: string[] = [];
  for (const e of flow.data.edges) {
    const src = e.data.sourceHandle.output_types?.[0];
    const t = e.data.targetHandle;
    let accepts: string[];
    if (typeof t.fieldName === 'string') {
      accepts = t.inputTypes ?? [];
    } else {
      const node = flow.data.nodes.find((n) => n.id === e.target);
      const loop = node?.data?.node?.outputs?.find((o) => o.name === t.name && o.allows_loop === true);
      accepts = loop ? [...(loop.types ?? []), ...(loop.loop_types ?? [])] : [];
    }
    if (!src || !(accepts.includes(src) || accepts.includes('Any'))) {
      out.push(`${e.source} -> ${e.target} (${t.fieldName ?? `loop:${t.name}`}): sends ${src ?? 'nothing'}, accepts ${accepts.join(' or ') || 'nothing'}`);
    }
  }
  return out;
}
