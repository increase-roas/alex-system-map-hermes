/**
 * Version 5: Agency OS checklist (ids k_), far right of Hermes.
 * Same 41 items as the Agency OS checklist page, checked 2026-10-12.
 * Status: ok = done, partial = partly, gap = missing, unknown = not checked yet.
 * Nothing here is installed by this file; it only shows what exists and what is left.
 */
import type { ProEdge, ProNode, ProStatus } from './pro-map-data';

export const KX = 4300;
const COLS = 3, CW = 300, SP = 320, CH = 125, ROW = 145, HEAD = 50, GAP = 60;
type Item = { id: string; label: string; status: ProStatus; why: string; sources: string[] };
type Section = { key: string; label: string; why: string; items: Item[] };
const SECTIONS: Section[] = [
 {
  "key": "g",
  "label": "1. Guardrails installed for real",
  "why": "The blueprint hooks exist and pass 121 tests. None are in your real settings yet; that is why your map is a D.",
  "items": [
   {
    "id": "g1",
    "label": "Test-install the read-first gate + client lock in a scratch project",
    "status": "gap",
    "why": "Run against a GHL test sub-account. Proves the hooks live; blueprints go to A.",
    "sources": [
     "https://code.claude.com/docs/en/hooks",
     "https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks"
    ]
   },
   {
    "id": "g2",
    "label": "Client lock on GHL calls in your real Claude Code",
    "status": "gap",
    "why": "One login reaches 303 accounts today; nothing blocks the wrong one.",
    "sources": [
     "https://code.claude.com/docs/en/hooks",
     "https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks"
    ]
   },
   {
    "id": "g3",
    "label": "Guard Javar (Hermes pre_tool_call hook)",
    "status": "gap",
    "why": "Spend, send, delete and client checks. Javar has no guard today.",
    "sources": [
     "https://code.claude.com/docs/en/hooks",
     "https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks"
    ]
   },
   {
    "id": "g4",
    "label": "Kill switch",
    "status": "gap",
    "why": "One deny rule or flag that stops all client-facing tools at once.",
    "sources": [
     "https://code.claude.com/docs/en/hooks",
     "https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks"
    ]
   },
   {
    "id": "g5",
    "label": "Skill and connector setup checks installed",
    "status": "partial",
    "why": "Ready-to-use kit in alex-system-map/guardrails-template (install.py, check.py), seen working live in a test folder. Not installed in a real project yet.",
    "sources": [
     "https://code.claude.com/docs/en/hooks",
     "https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks"
    ]
   },
   {
    "id": "g6",
    "label": "Log direct Composio calls",
    "status": "partial",
    "why": "SDK calls are logged; direct Composio calls are not.",
    "sources": [
     "https://code.claude.com/docs/en/hooks",
     "https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks"
    ]
   }
  ]
 },
 {
  "key": "r",
  "label": "2. Routing (the if/else)",
  "why": "Incoming task → which customer → which function → which bot → which tools → execute. No \"which customer?\" questions.",
  "items": [
   {
    "id": "r1",
    "label": "Customer router: incoming task picks the customer",
    "status": "partial",
    "why": "agency-os-kit (after Codex round 3: 71 tests pass + 1 database test). route.py matches exact slugs, location IDs and account IDs, names only outside links, links only by their real host; conflicts return needs_customer, incomplete folders customer_not_ready. Not wired to a live intake.",
    "sources": [
     "https://code.claude.com/docs/en/memory"
    ]
   },
   {
    "id": "r2",
    "label": "Function router: lead follow-up, website, ads, reporting...",
    "status": "partial",
    "why": "agency-os-kit (after Codex round 3: 71 tests pass + 1 database test). routing.json if/else rules pick the function. Director still routes Codex missions separately.",
    "sources": [
     "https://code.claude.com/docs/en/memory"
    ]
   },
   {
    "id": "r3",
    "label": "Bot router: which bot does which function",
    "status": "partial",
    "why": "agency-os-kit (after Codex round 3: 71 tests pass + 1 database test). Each customer.json maps function to bot. Bots are still opened by hand.",
    "sources": [
     "https://code.claude.com/docs/en/memory"
    ]
   },
   {
    "id": "r4",
    "label": "Tool router: which tool for which job",
    "status": "partial",
    "why": "agency-os-kit: bots.json says what each tool can do; tools/gate.py blocks spend, delete, messaging a customer or lead, and deploy until you approve that exact task once (expires in 24h) or record a standing approval; every check is logged. Built and tested; not wired into the live bots yet, and the approval files still need the guardrail hooks to protect them.",
    "sources": [
     "https://code.claude.com/docs/en/memory"
    ]
   },
   {
    "id": "r5",
    "label": "Customer IDs baked into each bot (Meta account, GHL sub-account, tracking IDs)",
    "status": "partial",
    "why": "agency-os-kit (after Codex round 3: 71 tests pass + 1 database test). customer.json ids + AGENTS.md template bake them in. No real customer filled in yet.",
    "sources": [
     "https://code.claude.com/docs/en/memory"
    ]
   }
  ]
 },
 {
  "key": "c",
  "label": "3. Customer repo that scores an A",
  "why": "One folder per customer holding everything, so any bot can pick up any job without asking.",
  "items": [
   {
    "id": "c1",
    "label": "Agency repo with one folder per customer",
    "status": "partial",
    "why": "agency-os-kit (after Codex round 3: 71 tests pass + 1 database test). customers/_template is ready; only a SAMPLE customer exists. Raw data stays out of git.",
    "sources": []
   },
   {
    "id": "c2",
    "label": "Sales numbers per customer",
    "status": "partial",
    "why": "agency-os-kit (after Codex round 3: 71 tests pass + 1 database test). numbers/monthly.csv slot (spend, leads, replied, appointments, sales, revenue, cash). Needs real numbers.",
    "sources": []
   },
   {
    "id": "c3",
    "label": "Sales conversations: objections and replies",
    "status": "partial",
    "why": "agency-os-kit (after Codex round 3: 71 tests pass + 1 database test). objections.md slot (summaries, no names). Needs real GHL conversation summaries.",
    "sources": []
   },
   {
    "id": "c4",
    "label": "Website data per customer",
    "status": "partial",
    "why": "agency-os-kit (after Codex round 3: 71 tests pass + 1 database test). website.md slot. Needs each real site filled in.",
    "sources": []
   },
   {
    "id": "c5",
    "label": "Open gaps list per customer",
    "status": "partial",
    "why": "agency-os-kit (after Codex round 3: 71 tests pass + 1 database test). gaps.md checklist with an updated date. Needs real gaps.",
    "sources": []
   },
   {
    "id": "c6",
    "label": "Grade each customer folder (same A–F rubric)",
    "status": "partial",
    "why": "agency-os-kit (after Codex round 3: 71 tests pass + 1 database test). score_customer.py grades FOLDER COMPLETENESS A to F with blockers (missing IDs, unknown bots, forbidden tools, missing rules, contradicting numbers). Proven on sample folders only, not a real customer.",
    "sources": []
   }
  ]
 },
 {
  "key": "n",
  "label": "4. React Flow node kit",
  "why": "Your Pro Map uses 2 node types (card, band). An agent builder needs real node types.",
  "items": [
   {
    "id": "n1",
    "label": "Input node",
    "status": "ok",
    "why": "Flow Builder tab: Start node. Draws and checks flows; it does not run them.",
    "sources": [
     "https://docs.flowiseai.com/using-flowise/agentflowv2",
     "https://reactflow.dev/"
    ]
   },
   {
    "id": "n2",
    "label": "LLM nodes (LLM + Agent)",
    "status": "ok",
    "why": "Flow Builder tab: LLM and Agent nodes.",
    "sources": [
     "https://docs.flowiseai.com/using-flowise/agentflowv2",
     "https://reactflow.dev/"
    ]
   },
   {
    "id": "n3",
    "label": "Judge node (score + written feedback)",
    "status": "ok",
    "why": "Flow Builder tab: Judge node (score + feedback).",
    "sources": [
     "https://docs.flowiseai.com/using-flowise/agentflowv2",
     "https://reactflow.dev/"
    ]
   },
   {
    "id": "n4",
    "label": "Compare node (new vs current, per test case)",
    "status": "ok",
    "why": "Flow Builder tab: Compare node (new vs current, per case).",
    "sources": [
     "https://docs.flowiseai.com/using-flowise/agentflowv2",
     "https://reactflow.dev/"
    ]
   },
   {
    "id": "n5",
    "label": "Promote node (needs your yes)",
    "status": "partial",
    "why": "Flow Builder Promote node; the check flags any path to Promote, or to an agent or tool that spends, deletes, messages a customer or lead, or deploys, that skips a Human Input \"yes\". Draws and checks only.",
    "sources": [
     "https://docs.flowiseai.com/using-flowise/agentflowv2",
     "https://reactflow.dev/"
    ]
   },
   {
    "id": "n6",
    "label": "Loop node",
    "status": "partial",
    "why": "Flow Builder Loop node; the check requires 1 to 20 rounds, flags cycles without an Iteration or bounded Loop, and flags an Iteration whose \"done\" path leads back into it. Draws and checks only.",
    "sources": [
     "https://docs.flowiseai.com/using-flowise/agentflowv2",
     "https://reactflow.dev/"
    ]
   },
   {
    "id": "n7",
    "label": "The Agentflow 15: Start, LLM, Agent, Tool, Retriever, HTTP, Condition, Condition Agent, Iteration, Loop, Human Input, Direct Reply, Custom Function, Execute Flow, Sticky Note",
    "status": "ok",
    "why": "Flow Builder tab has all 15 Agentflow types plus Judge, Compare, Promote, Route to customer, with GEPA and routing templates.",
    "sources": [
     "https://docs.flowiseai.com/using-flowise/agentflowv2",
     "https://reactflow.dev/"
    ]
   }
  ]
 },
 {
  "key": "p",
  "label": "5. GEPA feedback harness",
  "why": "Run → judge with written feedback → reflect and propose a better prompt → compare on a test set → promote with your yes → loop.",
  "items": [
   {
    "id": "p1",
    "label": "Test set per job (20–50 real cases)",
    "status": "partial",
    "why": "agency-os-kit (after Codex round 3: 71 tests pass + 1 database test). gepa/jobs/<job>/testset.jsonl with train and holdout cases. Only the sample speed-to-lead job (8 cases) exists.",
    "sources": [
     "https://arxiv.org/abs/2507.19457",
     "https://dspy.ai/api/optimizers/GEPA/overview/"
    ]
   },
   {
    "id": "p2",
    "label": "Judge that returns score + feedback text",
    "status": "ok",
    "why": "agency-os-kit (after Codex round 3: 71 tests pass + 1 database test). Judge returns score + written feedback (rule checks; Claude judge option written, not yet seen working).",
    "sources": [
     "https://arxiv.org/abs/2507.19457",
     "https://dspy.ai/api/optimizers/GEPA/overview/"
    ]
   },
   {
    "id": "p3",
    "label": "Reflect step that proposes the improved prompt or skill",
    "status": "partial",
    "why": "agency-os-kit (after Codex round 3: 71 tests pass + 1 database test). Reflect step rewrites the prompt from feedback. Seen working with the offline stub; the Claude version is written, not yet run.",
    "sources": [
     "https://arxiv.org/abs/2507.19457",
     "https://dspy.ai/api/optimizers/GEPA/overview/"
    ]
   },
   {
    "id": "p4",
    "label": "Keep the best candidates per test case (Pareto)",
    "status": "ok",
    "why": "agency-os-kit (after Codex round 3: 71 tests pass + 1 database test). Keeps every candidate that is best on at least one case (Pareto).",
    "sources": [
     "https://arxiv.org/abs/2507.19457",
     "https://dspy.ai/api/optimizers/GEPA/overview/"
    ]
   },
   {
    "id": "p5",
    "label": "Promote only with your yes",
    "status": "partial",
    "why": "agency-os-kit (after Codex round 3: 71 tests pass + 1 database test). gepa.py promote needs --yes, holdout cases and a win over the live prompt. Your rule says the same, but no real prompt has been promoted this way yet.",
    "sources": [
     "https://arxiv.org/abs/2507.19457",
     "https://dspy.ai/api/optimizers/GEPA/overview/"
    ]
   }
  ]
 },
 {
  "key": "s",
  "label": "6. Schedules and customer cadence",
  "why": "Problems found before the customer finds them; customers hear from you twice a week.",
  "items": [
   {
    "id": "s1",
    "label": "Scheduled scans that find problems in each customer account",
    "status": "partial",
    "why": "agency-os-kit (after Codex round 3: 71 tests pass + 1 database test). tools/scan_customer.py finds problems (stale numbers, cost spikes, reply/close drops, negative cash, LTV:CAC under 3, missed updates). Not scheduled yet.",
    "sources": [
     "https://code.claude.com/docs/en/scheduled-tasks"
    ]
   },
   {
    "id": "s2",
    "label": "2x per week customer update",
    "status": "partial",
    "why": "agency-os-kit (after Codex round 3: 71 tests pass + 1 database test). tools/draft_update.py drafts Tue/Fri updates. Not scheduled yet.",
    "sources": [
     "https://code.claude.com/docs/en/scheduled-tasks"
    ]
   },
   {
    "id": "s3",
    "label": "Updates drafted by bots, sent only with your yes",
    "status": "ok",
    "why": "agency-os-kit (after Codex round 3: 71 tests pass + 1 database test). Drafts are marked not sent; nothing sends without your yes.",
    "sources": [
     "https://code.claude.com/docs/en/scheduled-tasks"
    ]
   }
  ]
 },
 {
  "key": "d",
  "label": "7. Scaling dashboard",
  "why": "Reverse-engineer scaling companies: cash flow first, LTV to CAC at 3:1 or better.",
  "items": [
   {
    "id": "d1",
    "label": "Cash flow view per customer",
    "status": "ok",
    "why": "agency-os-kit (after Codex round 3: 71 tests pass + 1 database test). tools/dashboard.py: cash flow by month (tested on SAMPLE numbers).",
    "sources": []
   },
   {
    "id": "d2",
    "label": "LTV : CAC with a 3:1 target line",
    "status": "ok",
    "why": "agency-os-kit (after Codex round 3: 71 tests pass + 1 database test). LTV:CAC tile with the 3:1 target; scan flags under 3.",
    "sources": []
   },
   {
    "id": "d3",
    "label": "Cost per lead that responded (not just cost per lead)",
    "status": "ok",
    "why": "agency-os-kit (after Codex round 3: 71 tests pass + 1 database test). Cost per lead that replied, per month and per test arm.",
    "sources": []
   },
   {
    "id": "d4",
    "label": "Split test: instant form vs website conversion",
    "status": "partial",
    "why": "agency-os-kit: instant form vs website judged once at a planned end month (no peeking), floors of 100 leads and 10 sales per side that cannot be lowered, test arms must add up to the totals. Tested on SAMPLE numbers only.",
    "sources": []
   },
   {
    "id": "d5",
    "label": "Check the existing \"Agency Fulfillment Dashboard\" project",
    "status": "unknown",
    "why": "A project with that name exists; contents not checked.",
    "sources": []
   }
  ]
 },
 {
  "key": "x",
  "label": "8. Data store and privacy",
  "why": "Where the numbers live, and how your methods stay yours.",
  "items": [
   {
    "id": "x1",
    "label": "One database for customer data (Postgres, e.g. Supabase) with per-customer access rules",
    "status": "partial",
    "why": "agency-os-kit (after Codex round 3: 71 tests pass + 1 database test). db/schema.sql for Supabase with per-customer locks and number checks; db/rls_test.sql passed 11 of 11 on Postgres 16 in Claude's workspace (Codex could not rerun it: no Postgres on the Mac). No Supabase project made.",
    "sources": []
   },
   {
    "id": "x2",
    "label": "Proprietary layer kept private: skills, prompts, scoring, playbooks",
    "status": "partial",
    "why": "Lives in your private ~/.agents repo today.",
    "sources": []
   },
   {
    "id": "x3",
    "label": "Customer-facing views show results only, never prompts or methods",
    "status": "partial",
    "why": "agency-os-kit (after Codex round 3: 71 tests pass + 1 database test). dashboard.py --client and update drafts show results and customer_notes.md only (tested). Not yet used with a real customer.",
    "sources": []
   },
   {
    "id": "x4",
    "label": "Keys only in 1Password / Composio, never in repos or chats",
    "status": "partial",
    "why": "Your rule: keys only in 1Password / Composio. Written as a rule; enforcement not verified across every agent.",
    "sources": []
   }
  ]
 }
];

const nodes: ProNode[] = [{
  id: 'k_title', label: 'Version 5: Agency OS checklist, 41 items', sub: "11 done, 25 partly, 4 missing, 1 not checked. Updated 2026-10-12 after Codex round 3.",
  why: 'Everything needed to run each customer\'s whole flow: guardrails, routing, customer repo, node kit, feedback loop, schedules, dashboard and privacy. Green = done, orange = partly, pink = missing, gray = not checked.',
  status: 'reference', sources: [], x: KX - 10, y: -110, w: COLS * SP + 20, h: 60, band: true,
}];
const edges: ProEdge[] = [];
let y = 0;
SECTIONS.forEach((s, i) => {
  const rows = Math.ceil(s.items.length / COLS);
  const h = HEAD + rows * ROW;
  const done = s.items.filter((it) => it.status === 'ok').length;
  nodes.push({ id: `k_band_${s.key}`, label: s.label, sub: `${done} of ${s.items.length} done`, why: s.why, status: 'reference', sources: [], x: KX - 10, y, w: COLS * SP + 20, h, band: true });
  s.items.forEach((it, n) => nodes.push({
    id: `k_${it.id}`, label: it.label, sub: '', status: it.status, why: it.why, sources: it.sources,
    tag: s.label, trace: s.why, x: KX + (n % COLS) * SP + (SP - CW) / 2, y: y + HEAD + Math.floor(n / COLS) * ROW, w: CW, h: CH,
  }));
  if (i > 0) edges.push({ id: `k_e${i}`, source: `k_band_${SECTIONS[i - 1].key}`, target: `k_band_${s.key}`, kind: 'flow', label: 'then' });
  y += h + GAP;
});
export const K_NODES = nodes;
export const K_EDGES = edges;
