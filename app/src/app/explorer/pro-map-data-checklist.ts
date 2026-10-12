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
    "status": "gap",
    "why": "Blocks a badly formatted skill or a connector with a pasted key or no card.",
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
    "status": "gap",
    "why": "Your map: nothing picks the client today.",
    "sources": [
     "https://code.claude.com/docs/en/memory"
    ]
   },
   {
    "id": "r2",
    "label": "Function router: lead follow-up, website, ads, reporting...",
    "status": "partial",
    "why": "Director routes missions, but only inside Codex.",
    "sources": [
     "https://code.claude.com/docs/en/memory"
    ]
   },
   {
    "id": "r3",
    "label": "Bot router: which bot does which function",
    "status": "partial",
    "why": "Director picks agents for Codex work; Claude, Cursor, Manus, Javar are opened by you.",
    "sources": [
     "https://code.claude.com/docs/en/memory"
    ]
   },
   {
    "id": "r4",
    "label": "Tool router: which tool for which job",
    "status": "partial",
    "why": "App cards already route (e.g. GHL workflows → GHL command builder). Not enforced yet.",
    "sources": [
     "https://code.claude.com/docs/en/memory"
    ]
   },
   {
    "id": "r5",
    "label": "Customer IDs baked into each bot (Meta account, GHL sub-account, tracking IDs)",
    "status": "gap",
    "why": "Goes in each customer folder's CLAUDE.md / AGENTS.md, plus the client lock.",
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
    "why": "Designed (3 example tree clients). Not built.",
    "sources": []
   },
   {
    "id": "c2",
    "label": "Sales numbers per customer",
    "status": "gap",
    "why": "Leads, booked, sold, revenue, by source.",
    "sources": []
   },
   {
    "id": "c3",
    "label": "Sales conversations: objections and replies",
    "status": "gap",
    "why": "Pulled from GHL conversations into data/, summarized, never dumped in chat.",
    "sources": []
   },
   {
    "id": "c4",
    "label": "Website data per customer",
    "status": "gap",
    "why": "Pages, offers, forms, tracking IDs, conversion rates.",
    "sources": []
   },
   {
    "id": "c5",
    "label": "Open gaps list per customer",
    "status": "gap",
    "why": "What they still don't have (reviews, photos, follow-up, ads).",
    "sources": []
   },
   {
    "id": "c6",
    "label": "Grade each customer folder (same A–F rubric)",
    "status": "gap",
    "why": "A = complete data, rules, IDs, finish lines and tests for that customer.",
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
    "status": "gap",
    "why": "Agentflow calls it Start.",
    "sources": [
     "https://docs.flowiseai.com/using-flowise/agentflowv2",
     "https://reactflow.dev/"
    ]
   },
   {
    "id": "n2",
    "label": "LLM nodes (LLM + Agent)",
    "status": "gap",
    "why": "Your Pro Map uses 2 node types (card, band). An agent builder needs real node types.",
    "sources": [
     "https://docs.flowiseai.com/using-flowise/agentflowv2",
     "https://reactflow.dev/"
    ]
   },
   {
    "id": "n3",
    "label": "Judge node (score + written feedback)",
    "status": "gap",
    "why": "Needed for GEPA.",
    "sources": [
     "https://docs.flowiseai.com/using-flowise/agentflowv2",
     "https://reactflow.dev/"
    ]
   },
   {
    "id": "n4",
    "label": "Compare node (new vs current, per test case)",
    "status": "gap",
    "why": "Needed for GEPA.",
    "sources": [
     "https://docs.flowiseai.com/using-flowise/agentflowv2",
     "https://reactflow.dev/"
    ]
   },
   {
    "id": "n5",
    "label": "Promote node (needs your yes)",
    "status": "gap",
    "why": "Needed for GEPA.",
    "sources": [
     "https://docs.flowiseai.com/using-flowise/agentflowv2",
     "https://reactflow.dev/"
    ]
   },
   {
    "id": "n6",
    "label": "Loop node",
    "status": "gap",
    "why": "Your Pro Map uses 2 node types (card, band). An agent builder needs real node types.",
    "sources": [
     "https://docs.flowiseai.com/using-flowise/agentflowv2",
     "https://reactflow.dev/"
    ]
   },
   {
    "id": "n7",
    "label": "The Agentflow 15: Start, LLM, Agent, Tool, Retriever, HTTP, Condition, Condition Agent, Iteration, Loop, Human Input, Direct Reply, Custom Function, Execute Flow, Sticky Note",
    "status": "gap",
    "why": "Use as the design reference; build on your React Flow Pro AI Workflow Editor template.",
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
    "why": "Golden and held-out tasks exist for the system, not per customer job.",
    "sources": [
     "https://arxiv.org/abs/2507.19457",
     "https://dspy.ai/api/optimizers/GEPA/overview/"
    ]
   },
   {
    "id": "p2",
    "label": "Judge that returns score + feedback text",
    "status": "gap",
    "why": "Run → judge with written feedback → reflect and propose a better prompt → compare on a test set → promote with your yes → loop.",
    "sources": [
     "https://arxiv.org/abs/2507.19457",
     "https://dspy.ai/api/optimizers/GEPA/overview/"
    ]
   },
   {
    "id": "p3",
    "label": "Reflect step that proposes the improved prompt or skill",
    "status": "partial",
    "why": "Weekly tune-up writes proposals; not GEPA-style.",
    "sources": [
     "https://arxiv.org/abs/2507.19457",
     "https://dspy.ai/api/optimizers/GEPA/overview/"
    ]
   },
   {
    "id": "p4",
    "label": "Keep the best candidates per test case (Pareto)",
    "status": "gap",
    "why": "Run → judge with written feedback → reflect and propose a better prompt → compare on a test set → promote with your yes → loop.",
    "sources": [
     "https://arxiv.org/abs/2507.19457",
     "https://dspy.ai/api/optimizers/GEPA/overview/"
    ]
   },
   {
    "id": "p5",
    "label": "Promote only with your yes",
    "status": "ok",
    "why": "Your rules and skills already change only after your approval.",
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
    "status": "gap",
    "why": "Weekly tune-up exists, but for your system, not customer accounts.",
    "sources": [
     "https://code.claude.com/docs/en/scheduled-tasks"
    ]
   },
   {
    "id": "s2",
    "label": "2x per week customer update",
    "status": "unknown",
    "why": "Not on your map; check if a workflow already sends these.",
    "sources": [
     "https://code.claude.com/docs/en/scheduled-tasks"
    ]
   },
   {
    "id": "s3",
    "label": "Updates drafted by bots, sent only with your yes",
    "status": "gap",
    "why": "Messaging a client needs your approval.",
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
    "status": "gap",
    "why": "Reverse-engineer scaling companies: cash flow first, LTV to CAC at 3:1 or better.",
    "sources": []
   },
   {
    "id": "d2",
    "label": "LTV : CAC with a 3:1 target line",
    "status": "gap",
    "why": "Reverse-engineer scaling companies: cash flow first, LTV to CAC at 3:1 or better.",
    "sources": []
   },
   {
    "id": "d3",
    "label": "Cost per lead that responded (not just cost per lead)",
    "status": "gap",
    "why": "Reverse-engineer scaling companies: cash flow first, LTV to CAC at 3:1 or better.",
    "sources": []
   },
   {
    "id": "d4",
    "label": "Split test: instant form vs website conversion",
    "status": "gap",
    "why": "Same offer, same budget, compare responded leads and sales.",
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
    "status": "gap",
    "why": "Sheets only as an export or a quick start.",
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
    "status": "gap",
    "why": "Where the numbers live, and how your methods stay yours.",
    "sources": []
   },
   {
    "id": "x4",
    "label": "Keys only in 1Password / Composio, never in repos or chats",
    "status": "ok",
    "why": "Already your rule.",
    "sources": []
   }
  ]
 }
];

const nodes: ProNode[] = [{
  id: 'k_title', label: 'Version 5: Agency OS checklist, 41 items', sub: "2 done, 8 partly, 29 missing, 2 not checked. Status checked 2026-10-12.",
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
