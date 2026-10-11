/**
 * Plain-English "What does this mean?" text for every card, chip and problem on the live map.
 * Three lines each: what it is, should Alex care (yes / no / maybe + why), and one thing to do.
 * Written for a non-technical owner: no jargon, one action or "Nothing".
 */

export type Care = 'yes' | 'no' | 'maybe';
export type Explanation = { what: string; care: Care; why: string; todo: string };

type Meta = Record<string, unknown>;
type NodeLike = { id: string; kind: string; label: string; meta: Meta };
type ProblemLike = { severity: string; title: string; detail: string };

const HOOKS: Record<string, string> = {
  composio_guard:
    'A safety check that runs before your AI uses an outside app. It stops spending money, messaging customers or deleting records until you say yes in chat.',
  chat_guard:
    'A safety check around every Claude chat. It keeps long chats and helper agents from using up your Mac’s memory and crashing it.',
  'herdr-agent-state':
    'A small note-taker from the herdr app. When an AI chat starts, it tells herdr so herdr can show which agents are running.',
  'deny-fast-subagent':
    'A Cursor rule that blocks helper agents set to the model called “fast”. They have to use the main model or a named one instead.',
};

const apps = (runs: unknown) =>
  [...new Set((Array.isArray(runs) ? (runs as string[]) : []).map((r) => r.split(':')[0].replace(' desktop', '')))].join(', ');

export function explainNode(n: NodeLike, problemWord: string | null): Explanation {
  const m = n.meta;
  switch (n.kind) {
    case 'app':
      return {
        what: `${n.label} is one of your AI apps. It’s where you chat with an AI that can work on your files.`,
        care: 'no', why: 'It shares the same rules, skills and connections as your other AI apps, and nothing on it is flagged.',
        todo: 'Nothing.',
      };
    case 'hub':
      return n.id === 'hub:shared-skills'
        ? { what: 'The one folder every AI app reads its how-to guides (skills) from.',
            care: 'maybe', why: 'If this folder breaks, all three apps lose their skills at once. Right now it’s fine.',
            todo: 'Nothing. Its GitHub check guards it.' }
        : { what: 'Composio is the one door your AI apps use to reach outside apps like Gmail, Slack or GoHighLevel.',
            care: 'maybe', why: 'Every outside app goes through it, so if it’s down, those tasks stop. It’s not flagged now.',
            todo: 'Nothing.' };
    case 'connector':
      return {
        what: `A direct plug called “${n.label}” that some of your AI apps use, outside Composio (usually because it only runs on your Mac).`,
        care: 'no', why: 'It’s a known local-only plug and nothing on it is flagged.',
        todo: 'Nothing.',
      };
    case 'hook':
      return {
        what: HOOKS[n.label] ?? `An automatic check called “${n.label}” that your AI apps run on their own.`,
        care: m.broken ? 'yes' : 'no',
        why: m.broken ? 'Its script file is missing, so the check isn’t running.' : `It’s running in ${apps(m.runs)} and its file is in place.`,
        todo: m.broken ? 'Tell me “fix the missing guard” and I’ll restore it from the backup.' : 'Nothing.',
      };
    case 'check': {
      const passed = m.state === 'success';
      const unknown = m.state === 'unknown';
      const unpushed = Number(m.unpushed ?? 0);
      return {
        what: 'An automatic test GitHub runs every time your shared settings change. It catches broken settings and leaked keys.',
        care: passed && !unpushed ? 'no' : 'yes',
        why: unknown ? 'The map couldn’t read the last result (signed out of GitHub or offline).'
          : !passed ? 'The last test failed, so broken settings may be saved on GitHub.'
          : unpushed ? `It passed, but ${unpushed} change(s) on your Mac aren’t on GitHub yet.`
          : 'The last test passed.',
        todo: unknown ? 'Run “gh auth login” in Terminal once.'
          : !passed ? 'Click “Open on GitHub” and tell me what it says, or ask me to fix it.'
          : unpushed ? 'Run: cd ~/.agents && git push origin main'
          : 'Nothing.',
      };
    }
    case 'director': {
      const quiet = (m.quiet as { bucket: string }[] | undefined) ?? [];
      const needsMe = quiet.filter((q) => q.bucket === 'needs me').length;
      return {
        what: 'Your Director is the AI that runs your projects. It keeps a list of missions and hands the work to other agents.',
        care: quiet.length ? 'yes' : 'no',
        why: quiet.length ? `${quiet.length} of its active missions haven’t moved in 5+ days, and ${needsMe} of those are waiting on you.` : 'Everything it calls active has moved in the last 5 days.',
        todo: needsMe ? 'Open the “needs me” missions below and answer them in the Director chat.' : 'Nothing.',
      };
    }
    case 'skill': {
      const spot = Boolean(m.director || m.conductor);
      if (problemWord === 'broken') {
        return { what: `A how-to guide your AI follows for one kind of job: “${n.label}”.`, care: 'yes',
          why: 'It points to a file or folder that no longer exists, so it will fail when used.', todo: 'Tell me “fix that skill” and I’ll repoint or remove the missing path.' };
      }
      if (problemWord === 'setup') {
        return { what: `A how-to guide your AI follows for one kind of job: “${n.label}”.`, care: 'no',
          why: 'It needs a one-time login to its tool the first time you use it. That’s normal, not broken.', todo: 'Nothing until you want to use it. It will ask you to log in then.' };
      }
      return {
        what: spot ? `“${n.label}” is the rulebook your ${m.director ? 'Director' : 'Conductor'} follows to run projects.` : `A how-to guide your AI follows for one kind of job: “${n.label}”.`,
        care: spot ? 'maybe' : 'no',
        why: spot ? 'It shapes how all your project work gets done. It’s healthy right now.' : 'Nothing on it is flagged.',
        todo: 'Nothing.',
      };
    }
    case 'repo':
      return n.id === 'home:alex-director'
        ? { what: 'The folder where your Director keeps its mission list, rules and receipts.', care: 'maybe',
            why: 'If this folder gets messy or broken, the Director loses track of its work. It’s fine now.', todo: 'Nothing.' }
        : { what: `A project folder on your Mac (“${n.label}”) that one of your skills points to.`, care: 'no',
            why: 'It’s only here to show which skills use which projects.', todo: 'Nothing.' };
    default:
      return { what: n.label, care: 'no', why: 'Nothing on it is flagged.', todo: 'Nothing.' };
  }
}

export function explainProblem(p: ProblemLike): Explanation {
  switch (p.severity) {
    case 'high':
    case 'medium':
      return { what: `Something on your setup is broken: ${p.title}.`, care: 'yes',
        why: 'An app, skill or guard will fail when it’s used.', todo: `Tell me “fix: ${p.title}” and I’ll repair it with a backup first.` };
    case 'you':
      return { what: 'The Director stopped and is waiting for your answer.', care: 'yes',
        why: 'Nothing on this mission moves until you reply.', todo: 'Answer it in the Director chat.' };
    case 'watch':
      return { what: 'Some missions the Director calls “active” haven’t moved in 5+ days.', care: 'yes',
        why: 'Active work that sits still is either stuck, already done or waiting on you. Each one is sorted on the Director card.',
        todo: 'Click this to open the sorted list on the Director card, then start with the “needs me” ones.' };
    case 'setup':
      return { what: 'A skill expects a one-time login or file from its tool, and it isn’t there yet.', care: 'no',
        why: 'It only matters when you want to use that skill. Nothing is broken.', todo: 'Nothing until you need it.' };
    default:
      return { what: p.title, care: 'maybe', why: 'A small tidy-up, not a failure.', todo: p.detail.startsWith('Run:') ? p.detail : 'Nothing urgent.' };
  }
}

export function explainChip(key: string, text: string): Explanation {
  switch (key) {
    case 'broken':
      return text === 'Nothing broken'
        ? { what: 'A count of real failures the map found on your Mac.', care: 'no', why: 'It found none.', todo: 'Nothing.' }
        : { what: 'A count of real failures the map found on your Mac.', care: 'yes', why: 'Each one will fail when it’s used.', todo: 'Click a red item in the problem list and tell me to fix it.' };
    case 'you':
      return { what: 'Director missions that stopped to wait for you.', care: 'yes', why: 'They don’t move until you answer.', todo: 'Answer them in the Director chat.' };
    case 'director':
      return { what: 'What your Director is working on: active missions, quiet ones and parked ones.', care: 'yes',
        why: 'Quiet “active” missions are the ones that are stuck, done or waiting on you.', todo: 'Open the Director card and work the “needs me” list first.' };
    case 'hooks':
      return { what: 'Automatic safety checks your AI apps run on their own (guards).', care: text.includes('broken') ? 'yes' : 'no',
        why: text.includes('broken') ? 'A guard’s file is missing, so that protection is off.' : 'All of them are in place.', todo: text.includes('broken') ? 'Tell me “fix the missing guard”.' : 'Nothing.' };
    case 'gh':
      return { what: 'The automatic GitHub test on your shared settings.', care: text.endsWith('passed') ? 'no' : 'yes',
        why: text.endsWith('passed') ? 'The last test passed.' : 'The last test didn’t pass or couldn’t be read.', todo: text.endsWith('passed') ? 'Nothing.' : 'Open the GitHub card on the map for the exact step.' };
    case 'setup':
      return { what: 'Skills that need a one-time login to their tool before first use.', care: 'no',
        why: 'Normal for tools you haven’t used yet. Nothing is broken.', todo: 'Nothing until you want to use one.' };
    default:
      return { what: text, care: 'maybe', why: '', todo: 'Nothing.' };
  }
}

export const BUCKET_TEXT: Record<string, { label: string; todo: string; color: string }> = {
  'needs me': { label: 'Needs me', todo: 'Answer it in the Director chat.', color: '#f5a524' },
  'looks stuck': { label: 'Looks stuck', todo: 'Ask the Director: “why hasn’t this moved, and what unblocks it?”', color: '#ff0071' },
  'looks done': { label: 'Looks done (close it)', todo: 'Tell the Director to close or park it so it stops counting as active.', color: '#17c964' },
};
