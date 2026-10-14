// "Most useful for you" at the top of the palette (Alex, 2026-10-14: "most useful components for us at the top").
// Ranked from Alex's own use, not a guess: how often each component appears in the open flow and in the starter
// flows, then the rest that run here. Pure: safe to import in the browser.

import { STARTERS } from './starters';

type Rankable = { type: string; displayName: string; runs: boolean };

/** How many times each component type is used across the starter flows and the open flow. */
export function usageCounts(openFlowTypes: readonly string[] = []): Map<string, number> {
  const counts = new Map<string, number>();
  const bump = (t: string) => counts.set(t, (counts.get(t) ?? 0) + 1);
  for (const s of STARTERS) for (const e of s.edits()) if (e.kind === 'addNode') bump(e.componentType);
  for (const t of openFlowTypes) bump(t);
  return counts;
}

/** Components for the top group: used ones first (most used first), then the others that run here. */
export function mostUseful<T extends Rankable>(components: readonly T[], openFlowTypes: readonly string[] = []): T[] {
  const counts = usageCounts(openFlowTypes);
  const used = (c: T) => counts.get(c.type) ?? 0;
  return components
    .filter((c) => used(c) > 0 || c.runs)
    .sort((a, b) => used(b) - used(a) || Number(b.runs) - Number(a.runs) || a.displayName.localeCompare(b.displayName));
}
