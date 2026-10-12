/**
 * Walkthrough jobs played on the middle map (Version 2). DEMO: scripted, not a recorded run.
 * Nothing here calls a tool or touches GHL, Google Sheets or a website.
 * Spec: Codex (Astra) 2026-10-12; GHL job from Alex's own ask.
 */
export type CallStatus = 'ok' | 'fail' | 'ask' | 'fixed' | 'info';
export type Call = { agent: string; action: string; result: string; status: CallStatus; ms?: number; cost?: string };
/** path = the green arrows for this step (from, to). Without it, the cards are chained in order. */
export type Beat = { title: string; say: string; ids: string[]; tone?: 'problem' | 'fix' | 'done'; calls?: Call[]; path?: [string, string][] };
export type Job = { id: string; name: string; ask: string; beats: Beat[] };

export const JOBS: Job[] = [
  {
    id: 'ghl-dad-calls',
    name: 'GHL: only customers ring Dad',
    ask: 'My dad is a user in a GHL sub-account (support@ghl.com). Find his user, find out why he gets calls from leads, and only let calls ring him from customers in this Google Sheet.',
    beats: [
      { title: 'You ask', ids: ['p_you', 'p_ui1'], say: 'You type the job in one chat: find Dad\'s user, find why leads call him, only let sheet customers ring him.',
        calls: [{ agent: 'you', action: 'user_prompt', result: 'job received', status: 'info' }] },
      { title: 'Open the client session', ids: ['p_session', 'p_lead', 'p_l1'], say: 'In this demo, the launcher opens Dad\'s project with a credential already limited to that sub-account. A folder or vault alone would not limit a broad GHL login.',
        calls: [{ agent: 'lead', action: 'open project', result: 'dads-subaccount repo', status: 'ok' }, { agent: 'lead', action: 'custom credential check', result: 'demo credential limited to this sub-account', status: 'ok' }] },
      { title: 'Load the right instructions', ids: ['p_load', 'p_ptr1', 'p_lib_skills'], say: 'Before its first decision, the session loads instructions. It then reads the call-routing skill. For a resumed job, it reads progress and checks the current state before changing anything.',
        calls: [{ agent: 'lead', action: 'Read CLAUDE.md', result: '84 lines', status: 'ok', ms: 40 }, { agent: 'lead', action: 'Skill ghl-call-routing', result: 'loaded', status: 'ok', ms: 30 }] },
      { title: 'Decide how to do the work', ids: ['p_plan', 'p_self'], say: 'Small job, so the lead does it itself. Plan: find the user, find the cause, build the allow-list, change routing (needs your yes), test with fake calls.' },
      { title: 'Find Dad and the cause (read only)', ids: ['p_k2', 'p_g2', 'p_t1', 'p_result'], say: 'Read-only calls are allowed by the rules. It finds Dad\'s user, then the cause: a "New Lead Call Connect" workflow rings him for every new lead.',
        calls: [
          { agent: 'lead', action: 'ghl_users_search(email)', result: 'found: Dad (user)', status: 'ok', ms: 640 },
          { agent: 'lead', action: 'ghl_phone_numbers_list', result: 'main line forwards to Dad', status: 'ok', ms: 510 },
          { agent: 'lead', action: 'ghl_workflows_search("call")', result: 'cause: New Lead Call Connect rings Dad on every new lead', status: 'ok', ms: 720 },
          { agent: 'lead', action: 'sheets_read(customers)', result: '212 customer rows', status: 'ok', ms: 900 },
        ] },
      { title: 'Change needs your yes', ids: ['p_g1', 'p_g3'], say: 'Changing call routing on a client account matches an ask rule, so it stops and asks you first. You approve.',
        calls: [{ agent: 'gateway', action: 'tool_decision: ghl_workflow_update', result: 'ask -> approved by Alex', status: 'ask' }] },
      { title: 'Make the change', ids: ['p_t1', 'p_result'], say: 'It turns off the lead call-connect for Dad and adds a rule: ring Dad only if the caller is in the customer list.',
        calls: [{ agent: 'lead', action: 'ghl_workflow_update', result: 'lead calls no longer ring Dad', status: 'ok', ms: 830 }, { agent: 'lead', action: 'sync customers -> tag "customer"', result: '212 synced', status: 'ok', ms: 1400 }] },
      { title: 'Problem: the check fails', ids: ['p_aftercheck', 'p_check'], tone: 'problem', say: 'A custom check simulates a customer call in a sandbox. The simulated Dad phone does not ring. No real phone is called by this demo.',
        calls: [{ agent: 'hook', action: 'custom post-call check -> simulated customer', result: 'FAIL: did not ring Dad', status: 'fail', ms: 3100 }] },
      { title: 'Diagnose with the trace', ids: ['p_x3', 'p_result'], tone: 'problem', say: 'The saved check output gives the clue: the sheet has phones like (517) 555-0123 but GHL stores +15175550123. No match, so nobody counts as a customer.',
        calls: [{ agent: 'lead', action: 'compare formats', result: 'sheet "(517) 555-0123" vs GHL "+15175550123"', status: 'info' }] },
      { title: 'Auto-fix', ids: ['p_k0', 'p_g2', 'p_t2'], tone: 'fix', say: 'Inside the change you already approved, it converts every sheet number to +1 format and re-syncs. Repair attempt 1 of 2.',
        calls: [{ agent: 'lead', action: 'normalize phones to +1 (E.164)', result: '212 fixed', status: 'fixed', ms: 380 }, { agent: 'lead', action: 're-sync customers', result: '212 matched', status: 'fixed', ms: 1300 }] },
      { title: 'Retest passes', ids: ['p_aftercheck', 'p_check', 'p_rep1'], tone: 'done', say: 'Same tests again: customer number rings Dad, lead number does not. Then it answers you with the before and after.',
        calls: [{ agent: 'hook', action: 'test_call(customer)', result: 'PASS: rang Dad', status: 'ok', ms: 2900 }, { agent: 'hook', action: 'test_call(lead)', result: 'PASS: did not ring Dad', status: 'ok', ms: 2800 }, { agent: 'lead', action: 'answer', result: 'cause, change, proof', status: 'ok', cost: '$0.31' }] },
      { title: 'Keep a test for this mistake', ids: ['p_e1', 'p_e5', 'p_e3', 'p_e4'], tone: 'done', say: 'It proposes a gotcha for the GHL skill ("match phones in +1 format") and keeps the fake-call test, so this exact mistake gets caught next time. You review before it lands.',
        calls: [{ agent: 'lead', action: 'propose gotcha', result: 'ghl-call-routing: normalize phones', status: 'ok' }, { agent: 'lead', action: 'keep regression test', result: 'evals/customer-rings-dad', status: 'ok' }] },
    ],
  },
  {
    id: 'website',
    name: 'Build a landing page (with helpers)',
    ask: 'Build a mobile-friendly landing page for Acme, based on what the top 3 competitors do. Don\'t publish.',
    beats: [
      { title: 'You ask', ids: ['p_you', 'p_ui1'], say: 'You ask for a landing page based on the top 3 competitors, not published yet.',
        calls: [{ agent: 'you', action: 'user_prompt', result: 'job received', status: 'info' }] },
      { title: 'Prepare', ids: ['p_session', 'p_lead', 'p_l1', 'p_load', 'p_plan'], say: 'The launcher opens Acme\'s project. Instructions load before the lead decides. On a resumed job, check the saved progress and existing page first. Then split independent research and page structure work.',
        path: [['p_ui1', 'p_session'], ['p_session', 'p_lead'], ['p_lead', 'p_l1'], ['p_l1', 'p_load'], ['p_load', 'p_plan']],
        calls: [{ agent: 'lead', action: 'Read CLAUDE.md', result: 'loaded', status: 'ok', ms: 40 }] },
      { title: 'Split: hand out tasks', ids: ['p_helpers', 'p_a1', 'p_a2'], say: 'Here it breaks into helpers. Research helper studies 3 competitor pages. Build helper makes the page structure; the final copy waits for the research. Custom helpers get their handoff and project instructions.',
        path: [['p_plan', 'p_helpers'], ['p_helpers', 'p_a1'], ['p_helpers', 'p_a2']],
        calls: [{ agent: 'lead', action: 'Agent(researcher)', result: 'started', status: 'ok' }, { agent: 'lead', action: 'Agent(site-builder)', result: 'started', status: 'ok' }] },
      { title: 'Where the helpers go', ids: ['p_a1', 'p_a2', 'p_k0', 'p_g2', 'p_t1', 'p_t2'], say: 'Both helpers run the same tool loop: find the tool, pass the permission check, run it. Research uses web search; the builder writes files.',
        path: [['p_a1', 'p_k0'], ['p_a2', 'p_k0'], ['p_k0', 'p_g2'], ['p_g2', 'p_t1'], ['p_g2', 'p_t2']],
        calls: [{ agent: 'researcher', action: 'WebSearch x3', result: '3 competitor pages', status: 'ok', ms: 5200 }, { agent: 'site-builder', action: 'Write website/index.html', result: 'created', status: 'ok', ms: 120 }] },
      { title: 'Problem', ids: ['p_t2', 'p_aftercheck', 'p_check'], tone: 'problem', say: 'A custom file-change check saves a failed phone-width test. The final Stop check reruns it and asks the helper to repair. FileChanged alone does not tell the model to continue.',
        path: [['p_t2', 'p_aftercheck'], ['p_aftercheck', 'p_check']],
        calls: [{ agent: 'hook', action: 'custom test + Stop repair feedback', result: 'FAIL: horizontal overflow', status: 'fail', ms: 2600 }] },
      { title: 'Diagnose', ids: ['p_check', 'p_x3'], tone: 'problem', say: 'The custom test saved a screenshot and its path in the job evidence. The helper reads that screenshot and the CSS: a box is fixed at 1200px. Telemetry alone does not save this evidence.',
        path: [['p_check', 'p_x3']],
        calls: [{ agent: 'site-builder', action: 'read screenshot + CSS', result: '.hero { width: 1200px }', status: 'info' }] },
      { title: 'Auto-fix', ids: ['p_a2', 'p_t2'], tone: 'fix', say: 'The failure goes back to the build helper. It replaces the fixed width and retests the selected phone widths. Repair 1 of 2; if both attempts fail, report blocked with the saved evidence.',
        path: [['p_x3', 'p_a2'], ['p_a2', 'p_t2']],
        calls: [{ agent: 'site-builder', action: 'Edit .hero width -> 100%, max 1200px', result: 'edited', status: 'fixed', ms: 90 }] },
      { title: 'Helpers come back together', ids: ['p_a1', 'p_a2', 'p_combine'], say: 'Both helpers hand back short summaries. The lead combines the competitor notes with the page.',
        path: [['p_a1', 'p_combine'], ['p_a2', 'p_combine']],
        calls: [{ agent: 'lead', action: 'combine summaries', result: 'copy updated from research', status: 'ok' }] },
      { title: 'Retest and answer', ids: ['p_combine', 'p_check', 'p_rep1'], tone: 'done', say: 'Same phone test passes on the combined page. The lead answers you with before and after screenshots.',
        path: [['p_combine', 'p_check'], ['p_check', 'p_rep1']],
        calls: [{ agent: 'hook', action: 'phone-width test', result: 'PASS', status: 'ok', ms: 2500 }, { agent: 'lead', action: 'answer', result: 'before/after', status: 'ok', cost: '$0.48' }] },
      { title: 'Learn', ids: ['p_e1', 'p_e5', 'p_e3', 'p_e4'], tone: 'done', say: 'It proposes a gotcha ("never fixed widths on sections") and keeps the phone test. You review, then it lands.',
        path: [['p_rep1', 'p_e1'], ['p_e1', 'p_e5'], ['p_e5', 'p_e3'], ['p_e3', 'p_e4']],
        calls: [{ agent: 'lead', action: 'propose gotcha + keep test', result: 'evals/phone-width', status: 'ok' }] },
    ],
  },
];
