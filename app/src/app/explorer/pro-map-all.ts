/**
 * Three full versions side by side:
 *   left   = Version 1, original 13 steps (pro-map-data-v1.ts), ids prefixed o_
 *   middle = Version 2, Codex review, 12 steps (pro-map-data.ts)
 *   right  = Yours, 12 steps (pro-map-data.ts)
 *   far right = Version 4, Hermes Agent (pro-map-data-hermes.ts), ids prefixed h_
 *   farthest right = Version 5, Agency OS checklist (pro-map-data-checklist.ts), ids prefixed k_
 *   then Version 6, Agency OS: where everything lives (pro-map-data-agencyos.ts), ids prefixed s_ (team copy: t_)
 */
import { PRO_EDGES as V2_EDGES, PRO_NODES as V2_NODES, type ProEdge, type ProNode } from './pro-map-data';
import { V1_EDGES, V1_NODES } from './pro-map-data-v1';
import { H_EDGES, H_NODES } from './pro-map-data-hermes';
import { STICKY } from './pro-map-sticky';
import { K_EDGES, K_NODES } from './pro-map-data-checklist';
import { S_EDGES, S_NODES } from './pro-map-data-agencyos';

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
/** Grades assess the described harness, not a promise that a live job will pass.
 * Source review: 2026-10-12. Unknown proof is visible, never upgraded to a pass.
 */
type MapGrade = NonNullable<ProNode['grade']>;
const CC = 'https://code.claude.com/docs/en/';
const areas = ['Accuracy', 'Sources', 'Top-down order', 'Harness completeness', 'Plain English'];
export const GRADES: Record<string, MapGrade> = {
  o_title: {
    letter: '?', note: 'Original kept for comparison. Not re-audited in this change.',
    proof: areas.map((area) => ({ area, grade: '?', why: 'Not checked in this audit; no new grade claimed.', check: 'Original v1 content preserved.' })),
  },
  p_title: {
    letter: 'B', note: 'Map audit, 2026-10-12. Guards seen working in live Claude Code sessions (scratch project). Codex re-grade: Accuracy up to A; overall stays B until the remaining live tests pass.',
    proof: [
      { area: 'Accuracy', grade: 'A', why: 'Codex re-grade 2026-10-12: A (hashes and calls.log verified). Seen working live 2026-10-12: 5 real Claude Code sessions (v2.1.296) in a throwaway project with the hooks registered. Call before card read: blocked, never ran. Read card then call: ran. Bad skill and pasted key: blocked. Not installed in your real setup.', sources: [CC + 'hooks', CC + 'agent-sdk/permissions'] },
      { area: 'Sources', grade: 'A', why: 'Claims link to the relevant Anthropic reference; product limits are stated.', sources: [CC + 'memory', CC + 'agent-sdk/python', CC + 'monitoring-usage'] },
      { area: 'Top-down order', grade: 'A', why: 'Load instructions, check old work, act, read results, combine, verify, report and learn.', sources: ['https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents'], check: 'pro-map-audit-check.cjs: result input, combine order and learning loop pass.' },
      { area: 'Harness completeness', grade: 'B', why: 'Tested skill, connector, card-read and setup checks; full-route protection still needs a protected installation.', sources: [CC + 'hooks', CC + 'permissions'], check: 'Offline: 31 setup + 31 read-gate tests pass. Live: pro-map-guardrails/live-test/live-receipt.json (5 runs, transcript hashes, tool call log shows only the allowed call). Good skill passed the guard; Claude Code then asked before writing in .claude/. Scratch project only. Ready-to-use kit: guardrails-template/ (install.py, check.py, uninstall.py, Hermes installer, card and SKILL.md templates); the live runs used that installer.' },
      { area: 'Plain English', grade: 'B', why: 'Plain labels and visible limits; final worktree screen review still needed.', check: 'TypeScript and title-render checks pass; browser readability remains unverified.' },
    ],
  },
  h_title: {
    letter: 'B', note: 'Hermes map audit, 2026-10-12. Native hooks plus tested custom guard script; protected installation and screen review remain.',
    proof: [
      { area: 'Accuracy', grade: 'B', why: 'Custom native-file and read-first guard now has sample-input tests. Live consent/registration is not proven.', sources: ['https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks', 'https://hermes-agent.nousresearch.com/docs/user-guide/features/delegation'] },
      { area: 'Sources', grade: 'A', why: 'Official feature pages and implementation references identify what each claim rests on.', sources: ['https://hermes-agent.nousresearch.com/docs/user-guide/features/context-files', 'https://github.com/NousResearch/hermes-agent/blob/main/agent/system_prompt.py'], check: 'Checked 2026-10-12; GitHub main is a moving reference, not a pinned installed version.' },
      { area: 'Top-down order', grade: 'A', why: 'Instructions precede decisions; tool results return to the loop; goal checks have explicit non-success exits.', sources: ['https://hermes-agent.nousresearch.com/docs/developer-guide/prompt-assembly', 'https://hermes-agent.nousresearch.com/docs/user-guide/features/goals'], check: 'Graph check: endpoints exist; result follows tool cards, not its enclosing band.' },
      { area: 'Harness completeness', grade: 'B', why: 'Tested custom guard covers supported native setup and connector calls. Other routes and client walls still require enforcement.', sources: ['https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks', 'https://hermes-agent.nousresearch.com/docs/user-guide/features/goals'], check: '59 tests pass; general-YAML test skipped (PyYAML absent). Open h_rulegate for tested script and unsupported routes.' },
      { area: 'Plain English', grade: 'B', why: 'Built-in/custom labels and wider cards; final worktree screen and arrow review still needed.', check: 'Title component and graph checked without a server; not a browser screenshot.' },
    ],
  },
  y_title: {
    letter: 'D', note: 'Your REAL system as the unchanged cards describe it. Snapshot assessment, not a new live audit.',
    proof: [
      { area: 'Accuracy', grade: 'C', why: 'Shared access can reach the wrong client. To reach A: enforce and test client-specific access on every call.', check: 'Card evidence: y_l2, y_g4 (303 accounts; no client walls).' },
      { area: 'Sources', grade: 'C', why: 'Receipts cover only some work. To reach A: connect each job, call, approval and result to saved evidence.', check: 'Card evidence: y_rep3, y_x3 (SDK-only receipts; no shared request ID).' },
      { area: 'Top-down order', grade: 'C', why: 'You bridge separate chats. To reach A: one intake, client selection, job state and checked handoffs.', check: 'Card evidence: y_front, y_rep1; Director and Conductor already exist.' },
      { area: 'Harness completeness', grade: 'D', why: 'Spend/send/delete guards cover 3 apps. New skill, connector-setup and successful-read gates are NOT PROVEN installed. Add them to every route plus client walls and a kill switch.', check: 'Evidence: y_x2, y_x4, y_g4, y_lib_guides. Card-reading instructions are not a read receipt. Rules/subagent/settings validators also unproven; test before upgrading.' },
      { area: 'Plain English', grade: 'C', why: 'Results live in separate apps. To reach A: one plain job report with done, blocked, proof and next action.', check: 'Card evidence: y_rep1, y_rep2. This grades operating clarity, not the drawing.' },
    ],
  },
};
export const PRO_NODES: ProNode[] = [...v1Nodes, ...V2_NODES, ...H_NODES, ...K_NODES, ...S_NODES].map(withSticky)
  .map((n) => (GRADES[n.id] ? { ...n, y: -500, h: 450, grade: GRADES[n.id] } : n));
export const PRO_EDGES: ProEdge[] = [...v1Edges, ...V2_EDGES, ...H_EDGES, ...K_EDGES, ...S_EDGES];
export type { ProEdge, ProNode };
