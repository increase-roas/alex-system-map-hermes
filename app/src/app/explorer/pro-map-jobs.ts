/**
 * Walkthrough jobs played on the middle map (Version 2). DEMO: scripted, not a recorded run.
 * Nothing here calls a tool or touches GHL, Google Sheets or a website.
 * Spec: Codex (Astra) 2026-10-12; GHL job from Alex's own ask.
 */
export type CallStatus = 'ok' | 'fail' | 'ask' | 'fixed' | 'info';
export type Call = { agent: string; action: string; result: string; status: CallStatus; ms?: number; cost?: string };
export type Beat = { title: string; say: string; ids: string[]; tone?: 'problem' | 'fix' | 'done'; calls?: Call[] };
export type Job = { id: string; name: string; ask: string; beats: Beat[] };

export const JOBS: Job[] = [
  {
    id: 'ghl-dad-calls',
    name: 'GHL: only customers ring Dad',
    ask: 'My dad is a user in a GHL sub-account (support@ghl.com). Find his user, find out why he gets calls from leads, and only let calls ring him from customers in this Google Sheet.',
    beats: [
      { title: 'You ask', ids: ['p_you', 'p_ui1'], say: 'You type the job in one chat: find Dad\'s user, find why leads call him, only let sheet customers ring him.',
        calls: [{ agent: 'you', action: 'user_prompt', result: 'job received', status: 'info' }] },
      { title: 'Lead identifies the project', ids: ['p_lead', 'p_l1', 'p_g5'], say: 'The lead works out which client this is: Dad\'s sub-account. The session gets only that sub-account\'s key, nothing else.',
        calls: [{ agent: 'lead', action: 'open project', result: 'dads-subaccount repo', status: 'ok' }, { agent: 'lead', action: 'vault', result: 'only this sub-account\'s GHL key', status: 'ok' }] },
      { title: 'Load the right instructions', ids: ['p_load', 'p_ptr1', 'p_lib_skills'], say: 'It loads this project\'s CLAUDE.md and the GHL call-routing skill, with its gotchas.',
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
      { title: 'Problem: the check fails', ids: ['p_aftercheck', 'p_check'], tone: 'problem', say: 'The after-edit check places a fake call from a customer number in the sheet. Dad\'s phone does NOT ring. Something is wrong.',
        calls: [{ agent: 'hook', action: 'PostToolUse -> test_call(customer)', result: 'FAIL: did not ring Dad', status: 'fail', ms: 3100 }] },
      { title: 'Diagnose with the trace', ids: ['p_x3', 'p_result'], tone: 'problem', say: 'The trace shows why: the sheet has phones like (517) 555-0123 but GHL stores +15175550123. No match, so nobody counts as a customer.',
        calls: [{ agent: 'lead', action: 'compare formats', result: 'sheet "(517) 555-0123" vs GHL "+15175550123"', status: 'info' }] },
      { title: 'Auto-fix', ids: ['p_k0', 'p_g2', 'p_t2'], tone: 'fix', say: 'Inside the change you already approved, it converts every sheet number to +1 format and re-syncs. Repair attempt 1 of 2.',
        calls: [{ agent: 'lead', action: 'normalize phones to +1 (E.164)', result: '212 fixed', status: 'fixed', ms: 380 }, { agent: 'lead', action: 're-sync customers', result: '212 matched', status: 'fixed', ms: 1300 }] },
      { title: 'Retest passes', ids: ['p_aftercheck', 'p_check', 'p_rep1'], tone: 'done', say: 'Same tests again: customer number rings Dad, lead number does not. Then it answers you with the before and after.',
        calls: [{ agent: 'hook', action: 'test_call(customer)', result: 'PASS: rang Dad', status: 'ok', ms: 2900 }, { agent: 'hook', action: 'test_call(lead)', result: 'PASS: did not ring Dad', status: 'ok', ms: 2800 }, { agent: 'lead', action: 'answer', result: 'cause, change, proof', status: 'ok', cost: '$0.31' }] },
      { title: 'Learn so it never repeats', ids: ['p_e1', 'p_e5', 'p_e3', 'p_e4'], tone: 'done', say: 'It adds a gotcha to the GHL skill ("match phones in +1 format") and keeps the fake-call test, so this exact mistake gets caught next time. You review before it lands.',
        calls: [{ agent: 'lead', action: 'propose gotcha', result: 'ghl-call-routing: normalize phones', status: 'ok' }, { agent: 'lead', action: 'keep regression test', result: 'evals/customer-rings-dad', status: 'ok' }] },
    ],
  },
  {
    id: 'website',
    name: 'Build a landing page',
    ask: 'Build a mobile-friendly landing page for Acme. Don\'t publish.',
    beats: [
      { title: 'You ask', ids: ['p_you', 'p_ui1'], say: 'You ask for a mobile-friendly landing page, not published yet.', calls: [{ agent: 'you', action: 'user_prompt', result: 'job received', status: 'info' }] },
      { title: 'Prepare', ids: ['p_lead', 'p_l1', 'p_load', 'p_plan'], say: 'The lead picks Acme\'s project, loads its instructions, and sets the checks: builds, and fits a phone screen.',
        calls: [{ agent: 'lead', action: 'Read CLAUDE.md', result: 'loaded', status: 'ok', ms: 40 }] },
      { title: 'Build', ids: ['p_self', 'p_k0', 'p_k2', 'p_g1', 'p_g2', 'p_t2'], say: 'It writes the page. Each file edit passes the permission check first.',
        calls: [{ agent: 'lead', action: 'Write website/index.html', result: 'created', status: 'ok', ms: 120 }, { agent: 'lead', action: 'Bash npm run build', result: 'build ok', status: 'ok', ms: 4200 }] },
      { title: 'Problem', ids: ['p_aftercheck', 'p_check'], tone: 'problem', say: 'The after-edit check tests a phone-width screen. The page spills off the side.',
        calls: [{ agent: 'hook', action: 'PostToolUse -> phone-width test', result: 'FAIL: horizontal overflow', status: 'fail', ms: 2600 }] },
      { title: 'Diagnose', ids: ['p_x3', 'p_result'], tone: 'problem', say: 'The trace shows the failing screenshot and the cause: a box with a fixed 1200px width.',
        calls: [{ agent: 'lead', action: 'read screenshot + CSS', result: '.hero { width: 1200px }', status: 'info' }] },
      { title: 'Repair', ids: ['p_k0', 'p_g1', 'p_g2', 'p_t2'], tone: 'fix', say: 'It swaps the fixed width for one that fits any screen.',
        calls: [{ agent: 'lead', action: 'Edit .hero width -> 100%, max 1200px', result: 'edited', status: 'fixed', ms: 90 }] },
      { title: 'Retest', ids: ['p_aftercheck', 'p_check', 'p_rep1'], tone: 'done', say: 'Same phone test passes. It answers you with before and after screenshots.',
        calls: [{ agent: 'hook', action: 'phone-width test', result: 'PASS', status: 'ok', ms: 2500 }, { agent: 'lead', action: 'answer', result: 'before/after', status: 'ok', cost: '$0.22' }] },
      { title: 'Learn', ids: ['p_e1', 'p_e5', 'p_e3', 'p_e4'], tone: 'done', say: 'It proposes a gotcha ("never fixed widths on sections") and keeps the phone test. You review, then it lands.',
        calls: [{ agent: 'lead', action: 'propose gotcha + keep test', result: 'evals/phone-width', status: 'ok' }] },
    ],
  },
];
