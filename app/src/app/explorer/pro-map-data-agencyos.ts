/**
 * Version 6: Agency OS, where everything lives (ids s_ for Alex, t_ for the team copy).
 * One builder, two audiences: buildHomesMap('owner') is Alex's full view; buildHomesMap('team') hides
 * owner-only cards (private repo, money numbers, owner-only setup) so the same map can be handed to an employee.
 * Status: ok = done, partial = partly, gap = missing, reference = a label. Checked 2026-10-12.
 * Nothing here installs anything; it shows the plan and what is left.
 */
import type { ProEdge, ProNode, ProStatus } from './pro-map-data';

export const SX = 5500;
const COLS = 3, CW = 300, SP = 320, CH = 125, ROW = 145, HEAD = 50, GAP = 60;
type Audience = 'owner' | 'team';
type Item = { id: string; label: string; status: ProStatus; why: string; sources: string[]; owner?: boolean };
type Section = { key: string; label: string; why: string; items: Item[] };

const SRC = {
  rls: 'https://supabase.com/docs/guides/database/postgres/row-level-security',
  cfSupa: 'https://developers.cloudflare.com/workers/databases/third-party-integrations/supabase/',
  vercel: 'https://vercel.com/docs/limits/fair-use-guidelines',
  ccCheck: 'https://code.claude.com/docs/en/checkpointing',
  codexUndo: 'https://github.com/openai/codex/pull/3914',
  hermesCheck: 'https://hermes-agent.nousresearch.com/docs/user-guide/checkpoints-and-rollback',
  skills: 'https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices',
  mem: 'https://code.claude.com/docs/en/memory',
  harness: 'https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents',
  composio: 'https://docs.composio.dev',
  ghRoles: 'https://docs.github.com/en/organizations/managing-user-access-to-your-organizations-repositories/managing-repository-roles/repository-roles-for-an-organization',
  drive: 'https://support.google.com/a/users/answer/12380484',
};

const SECTIONS: Section[] = [
  {
    key: 'who', label: '1. Who uses it', why: 'Each person and bot gets its own key. Removing one person removes one key and nothing else changes.',
    items: [
      { id: 'owner', label: 'Owner: Alex', status: 'ok', why: 'Sees everything. The only one who can approve spend, messages to customers and deleting client data.', sources: ['~/Projects/agency-os-kit/tools/gate.py', '~/Projects/agency-os-kit/bots.json'], owner: true },
      { id: 'employee', label: 'Employee', status: 'gap', why: 'Own logins, assigned customers only, runs playbooks, approves routine steps. Not invited yet: needs a GitHub username and may cost a seat.', sources: [SRC.ghRoles] },
      { id: 'bots', label: 'Bots: Claude, Codex, Javar, Javante', status: 'partial', why: 'Read the same playbooks and shared knowledge, act through Composio, stop at the gate for a yes. Shared knowledge home not built yet.', sources: [SRC.harness] },
    ],
  },
  {
    key: 'homes', label: '2. Where everything lives', why: 'GitHub is the brain, Google Drive is the team reading copy, machines are just desks.',
    items: [
      { id: 'gh_team', label: 'GitHub team repo (increase-roas, private)', status: 'gap', why: 'Kit, playbooks, skills, shared knowledge, system map. Today these live only on the Mac: no GitHub copy yet.', sources: [SRC.ghRoles, 'reviews/receipts/2026-10-12-no-remotes.txt'] },
      { id: 'gh_private', label: 'GitHub private repo (owner only)', status: 'gap', why: 'Your personal setup, proprietary notes and money numbers. The employee never sees it.', sources: [SRC.ghRoles], owner: true },
      { id: 'cust_repos', label: 'Customer site repos', status: 'partial', why: 'Repos exist. Auto-save to an autosave branch is not set up; main stays the live site.', sources: ['https://github.com/increaseroasir/hottublaunchmainb2bfunnel', 'https://code.claude.com/docs/en/checkpointing'] },
      { id: 'drive', label: 'Google Drive: Company OS', status: 'gap', why: 'Readable copies of playbooks, guides and customer reports, auto-updated from GitHub. Mirror not built yet.', sources: [SRC.drive] },
      { id: 'supa', label: 'Supabase: agency-os project', status: 'partial', why: 'Customer numbers plus logins, locked per customer. 11 of 11 lock tests pass on the Mac; waiting on the project and your Composio login.', sources: [SRC.rls, '~/Projects/agency-os-kit/db/schema.sql', '~/Projects/agency-os-kit/db/rls-receipt-2026-10-12-mac.txt', 'reviews/receipts/2026-10-12-connections.md'] },
      { id: 'cf', label: 'Cloudflare Pages: dashboard host', status: 'gap', why: 'Hosts the one dashboard app for every customer. Free plan allows business use (Vercel free does not).', sources: [SRC.cfSupa, SRC.vercel] },
      { id: 'composio', label: 'Composio: everyone\'s app logins', status: 'ok', why: 'Each person connects their own logins; keys never shared. Kit runner seen working with 3 live read-only calls.', sources: [SRC.composio, '~/Projects/agency-os-kit/tools/run.py', '~/Projects/agency-os-kit/composio/live-preview-2026-10-12.txt'] },
      { id: 'machines', label: 'Mac, Mac mini, Orgo computers', status: 'gap', why: 'Should be working copies only. Today the Mac is still the only home for the kit and the map.', sources: ['reviews/receipts/2026-10-12-no-remotes.txt'] },
    ],
  },
  {
    key: 'build', label: '3. How a job runs', why: 'Customer folder says WHO, router says WHERE, playbook says HOW, skills do the steps, the gate waits for a yes.',
    items: [
      { id: 'folder', label: 'Customer folder (WHO)', status: 'ok', why: 'IDs, numbers, objections, website, gaps. Scorer grades it A to F. Codex: A.', sources: ['~/Projects/agency-os-kit/customers/_template', '~/Projects/agency-os-kit/tools/score_customer.py', 'reviews/receipts/2026-10-12-codex-round12.md'] },
      { id: 'router', label: 'Router (WHERE)', status: 'ok', why: 'Task to customer to function to bot to tools. Never asks which customer. Codex: A.', sources: ['~/Projects/agency-os-kit/tools/route.py', '~/Projects/agency-os-kit/routing.json', 'reviews/receipts/2026-10-12-codex-round12.md'] },
      { id: 'playbook', label: 'Playbook (HOW)', status: 'gap', why: 'The recipe: steps in order, who does each, which skill and tool, what done looks like, where it stops for a yes.', sources: [SRC.harness, 'reviews/receipts/2026-10-12-kit-no-playbooks.txt'] },
      { id: 'skills', label: 'Skills (DO)', status: 'partial', why: 'Skills exist; playbook steps do not name them yet, so bots can still guess.', sources: [SRC.skills, 'reviews/receipts/2026-10-12-kit-no-playbooks.txt'] },
      { id: 'gate', label: 'Gate (YOUR YES)', status: 'ok', why: 'Spend, customer messages, deletes and deploys stop for approval. Codex: A.', sources: ['~/Projects/agency-os-kit/tools/gate.py', 'reviews/receipts/2026-10-12-codex-round12.md'] },
      { id: 'log', label: 'Log (WHO DID WHAT)', status: 'partial', why: 'Every gate decision is logged. Logs do not name the person yet (needed for the employee).', sources: ['~/Projects/agency-os-kit/tools/gate.py'] },
    ],
  },
  {
    key: 'list', label: '4. The list', why: 'Everything still to do, in the order it will run. Green = done, orange = partly, pink = missing.',
    items: [
      { id: 'l16', label: '16. Move everything to GitHub + Drive', status: 'gap', why: 'First, so nothing more is built only on the Mac.', sources: ['reviews/receipts/2026-10-12-no-remotes.txt'] },
      { id: 'l17', label: '17. Team access: roles and logins', status: 'gap', why: 'Owner, employee, bot. Per-person logins, onboarding and offboarding playbooks.', sources: [SRC.ghRoles] },
      { id: 'l1', label: '1-4. Kit to all A (Codex round 13)', status: 'partial', why: 'Round 12: A on 7 parts, B checklist, C GEPA and Composio. Fixes written, not graded.', sources: ['reviews/receipts/2026-10-12-codex-round12.md'] },
      { id: 'l2', label: '2. GEPA leak check', status: 'partial', why: 'Rerun done; outputs not checked for leaks yet.', sources: ['~/Projects/agency-os-kit/gepa/receipts/2026-10-12-claude', '~/Projects/agency-os-kit/gepa/gepa.py'] },
      { id: 'l3', label: '3. Composio "did it really work" checks', status: 'gap', why: 'Codex asked for checks on the actual reply, not just "no error".', sources: ['~/Projects/agency-os-kit/tools/run.py', 'reviews/receipts/2026-10-12-codex-round12.md'] },
      { id: 'l9', label: '9. Playbooks', status: 'gap', why: 'Recipe format plus 2 real ones: customer onboarding and dealer site launch.', sources: [SRC.harness, 'reviews/receipts/2026-10-12-kit-no-playbooks.txt'] },
      { id: 'l10', label: '10. A+ guide: how to write a playbook', status: 'gap', why: 'Template plus a scorer that grades a new playbook A+ to F with a fix list.', sources: ['~/Projects/agency-os-kit/tools/score_customer.py'] },
      { id: 'l11', label: '11. Skills plugged into playbooks', status: 'gap', why: 'Each step names its skill, so bots never guess.', sources: [SRC.skills, 'reviews/receipts/2026-10-12-kit-no-playbooks.txt'] },
      { id: 'l12', label: '12. Shared knowledge for all agents', status: 'gap', why: 'One team binder every bot reads; one copy plus pointers, never five copies.', sources: [SRC.mem, 'reviews/receipts/2026-10-12-kit-no-playbooks.txt'] },
      { id: 'l14', label: '14. Playbook: GHL sub-account setup', status: 'gap', why: 'Snapshot, IDs, pipelines, workflows, calendars, phone, and the checks that prove it is ready.', sources: ['reviews/receipts/2026-10-12-kit-no-playbooks.txt'] },
      { id: 'l13', label: '13. Auto-save every customer repo', status: 'gap', why: 'Backup branch every few minutes, key scanner, never main, one-command restore.', sources: [SRC.ccCheck, SRC.codexUndo, 'https://code.claude.com/docs/en/checkpointing', 'https://github.com/openai/codex/pull/3914'] },
      { id: 'l15', label: '15. Turn on Hermes checkpoints', status: 'gap', why: 'Off by default in Hermes, so Javar and Javante likely have no undo today.', sources: [SRC.hermesCheck], owner: true },
      { id: 'l18', label: '18. Hosted customer dashboard', status: 'gap', why: 'One app, customer logins, Supabase locks, Cloudflare host. Check htl-client-dashboard first.', sources: [SRC.rls, SRC.cfSupa] },
      { id: 'l19', label: 'Scheduled problem scans', status: 'gap', why: 'Scan script written; nothing runs it on a schedule yet.', sources: ['~/Projects/agency-os-kit/tools/scan_customer.py', 'reviews/receipts/2026-10-12-connections.md'] },
      { id: 'l20', label: '2x/week customer update drafts', status: 'gap', why: 'Drafter written; not scheduled. Sending still needs a yes.', sources: ['~/Projects/agency-os-kit/tools/draft_update.py', 'reviews/receipts/2026-10-12-connections.md'] },
      { id: 'l5', label: '5. Hermes guard live test (B to A)', status: 'partial', why: '59 tests pass; never run live in a scratch Hermes profile. Javar untouched.', sources: [SRC.hermesCheck, 'app/src/app/explorer/pro-map-guardrails/test_hermes_guard.py', 'https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks'] },
      { id: 'l6', label: '6. Supabase project + login', status: 'gap', why: 'Waiting on Alex: create agency-os in the free org, click the Composio link.', sources: [SRC.rls, 'reviews/receipts/2026-10-12-connections.md'], owner: true },
      { id: 'l21', label: 'Check Supabase\'s new features', status: 'gap', why: 'Asked for after the build; not done.', sources: ['https://supabase.com/changelog'] },
      { id: 'l7', label: '7. GitHub app card login', status: 'partial', why: 'Edited on the Mac, on hold, not live.', sources: ['~/.agents/tools/cards/github.md', 'reviews/receipts/2026-10-12-connections.md'], owner: true },
      { id: 'l8', label: '8. Excalidraw in Composio', status: 'ok', why: 'Already there, no login, seen working.', sources: ['reviews/receipts/2026-10-12-connections.md'] },
    ],
  },
];

/** Flows between the homes (only drawn when both ends are visible). */
const LINKS: [string, string, string][] = [
  ['machines', 'gh_team', 'auto-save'],
  ['gh_team', 'drive', 'mirror'],
  ['gh_team', 'cf', 'deploys dashboard'],
  ['supa', 'cf', 'numbers + logins'],
  ['composio', 'supa', 'pulls Meta, GHL'],
  ['folder', 'router', 'then'],
  ['router', 'playbook', 'then'],
  ['playbook', 'skills', 'each step'],
  ['skills', 'gate', 'risky step'],
  ['gate', 'log', 'recorded'],
];

export function buildHomesMap(audience: Audience): { nodes: ProNode[]; edges: ProEdge[] } {
  const p = audience === 'owner' ? 's_' : 't_';
  const x0 = audience === 'owner' ? SX : SX + COLS * SP + 200;
  const visible = SECTIONS.map((s) => ({ ...s, items: s.items.filter((it) => audience === 'owner' || !it.owner) }));
  const all = visible.flatMap((s) => s.items);
  const done = all.filter((it) => it.status === 'ok').length;
  const nodes: ProNode[] = [{
    id: `${p}title`,
    label: audience === 'owner' ? 'Version 6: Agency OS, where everything lives (Alex)' : 'Agency OS for the team',
    sub: `${done} of ${all.length} done. Checked 2026-10-12.`,
    why: audience === 'owner'
      ? 'Who uses it, where each piece lives, how a job runs, and the full to-do list. Owner-only cards are marked; the team copy hides them.'
      : 'Who uses it, where each piece lives and how a job runs. Spend, customer messages and deleting client data still need the owner\'s yes.',
    status: 'reference', sources: [], x: x0 - 10, y: -110, w: COLS * SP + 20, h: 60, band: true,
  }];
  const edges: ProEdge[] = [];
  let y = 0;
  visible.forEach((s, i) => {
    const rows = Math.ceil(s.items.length / COLS);
    const h = HEAD + rows * ROW;
    const ok = s.items.filter((it) => it.status === 'ok').length;
    nodes.push({ id: `${p}band_${s.key}`, label: s.label, sub: `${ok} of ${s.items.length} done`, why: s.why, status: 'reference', sources: [], x: x0 - 10, y, w: COLS * SP + 20, h, band: true });
    s.items.forEach((it, n) => nodes.push({
      id: `${p}${it.id}`, label: it.label, sub: it.owner ? 'Owner only' : '', status: it.status, why: it.why, sources: it.sources,
      tag: s.label, trace: s.why, x: x0 + (n % COLS) * SP + (SP - CW) / 2, y: y + HEAD + Math.floor(n / COLS) * ROW, w: CW, h: CH,
    }));
    if (i > 0) edges.push({ id: `${p}e${i}`, source: `${p}band_${visible[i - 1].key}`, target: `${p}band_${s.key}`, kind: 'flow', label: 'then' });
    y += h + GAP;
  });
  const ids = new Set(nodes.map((n) => n.id));
  for (const [a, b, label] of LINKS) {
    if (ids.has(p + a) && ids.has(p + b)) edges.push({ id: `${p}${a}-${b}`, source: p + a, target: p + b, kind: 'link', label });
  }
  return { nodes, edges };
}

const owner = buildHomesMap('owner');
export const S_NODES = owner.nodes;
export const S_EDGES = owner.edges;
