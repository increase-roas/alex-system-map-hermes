'use client';

import type { Explanation } from './explain';

const CARE_COLOR = { yes: '#ff0071', maybe: '#f5a524', no: '#17c964' } as const;

/** The three-line "What does this mean?" box. Collapsible where space is tight. */
export function Meaning({ e, collapsible = false }: { e: Explanation; collapsible?: boolean }) {
  const body = (
    <dl className="mt-1.5 space-y-1.5 text-xs leading-snug">
      <div>
        <dt className="text-muted-foreground text-[10px] tracking-wide uppercase">What it is</dt>
        <dd>{e.what}</dd>
      </div>
      <div>
        <dt className="text-muted-foreground text-[10px] tracking-wide uppercase">Should I care?</dt>
        <dd>
          <span className="mr-1 font-semibold capitalize" style={{ color: CARE_COLOR[e.care] }}>{e.care}.</span>
          {e.why}
        </dd>
      </div>
      <div>
        <dt className="text-muted-foreground text-[10px] tracking-wide uppercase">What to do</dt>
        <dd className="font-medium">{e.todo}</dd>
      </div>
    </dl>
  );
  if (!collapsible) {
    return (
      <div className="bg-muted/40 mt-2 rounded-md border p-2">
        <div className="text-[11px] font-semibold text-[#ff4d9a]">What does this mean?</div>
        {body}
      </div>
    );
  }
  return (
    <details className="group mt-2 rounded-md border p-2" onClick={(ev) => ev.stopPropagation()}>
      <summary className="cursor-pointer list-none text-[11px] font-semibold text-[#ff4d9a] select-none">
        <span className="mr-1 inline-block transition-transform group-open:rotate-90 motion-reduce:transition-none">›</span>
        What does this mean?
      </summary>
      {body}
    </details>
  );
}
