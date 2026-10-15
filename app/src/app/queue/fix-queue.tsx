'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';

type OpenItem = {
  id: string;
  kind: 'correction' | 'session';
  ts: string;
  age_hours: number;
  aged: boolean;
  serious: boolean;
  owner: string | null;
  where: string;
  summary: string;
};

type ClosedItem = { closed: string; note: string; excerpt: string };

type Queue = {
  generated?: string;
  age_limit_hours?: number;
  open?: OpenItem[];
  closed_recent?: ClosedItem[];
};

function age(hours: number): string {
  if (hours < 1) return 'under an hour old';
  if (hours < 48) return `${Math.round(hours)} hours old`;
  return `${Math.round(hours / 24)} days old`;
}

function when(ts?: string): string {
  return ts ? new Date(ts).toLocaleString() : 'unknown';
}

export function FixQueue() {
  const [queue, setQueue] = useState<Queue | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    fetch('/api/review-queue', { cache: 'no-store' })
      .then((res) => res.json())
      .then((data: { queue: Queue | null }) => setQueue(data.queue))
      .catch(() => setQueue(null))
      .finally(() => setLoaded(true));
  }, []);

  const open = queue?.open ?? [];
  const closed = queue?.closed_recent ?? [];
  const limit = queue?.age_limit_hours ?? 48;

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-6 p-6">
      <header className="flex items-baseline justify-between gap-4">
        <h1 className="text-lg font-medium">Fix-now queue</h1>
        <Link className="text-sm underline" href="/explorer">
          Back to explorer
        </Link>
      </header>
      <p className="text-muted-foreground text-sm">
        Things your agents flagged that need fixing. Anything older than {limit} hours moves to the
        weekly tune-up. Last updated: {loaded ? when(queue?.generated) : 'loading…'}
      </p>

      <section className="flex flex-col gap-3">
        <h2 className="font-medium">Waiting ({open.length})</h2>
        {loaded && open.length === 0 && (
          <div className="rounded-lg border p-6 text-center">Nothing waiting. Good.</div>
        )}
        {open.map((item) => (
          <article
            key={item.id}
            className={`rounded-lg border p-4 ${item.aged ? 'opacity-70' : ''} ${
              item.serious && !item.aged ? 'border-red-400' : ''
            }`}
          >
            <div className="mb-2 flex flex-wrap gap-2 text-xs">
              <span className="rounded bg-muted px-2 py-0.5">
                {item.kind === 'correction' ? 'You corrected an agent' : 'Session problem'}
              </span>
              {item.serious && <span className="rounded bg-red-100 px-2 py-0.5 text-red-800">Serious</span>}
              {item.aged && (
                <span className="rounded bg-amber-100 px-2 py-0.5 text-amber-800">
                  Moved to weekly tune-up
                </span>
              )}
            </div>
            <p className="text-sm">{item.summary}</p>
            <dl className="text-muted-foreground mt-2 grid grid-cols-[auto_1fr] gap-x-3 text-xs">
              <dt>Age</dt>
              <dd>{age(item.age_hours)}</dd>
              <dt>Who&apos;s on it</dt>
              <dd>{item.owner ?? 'nobody yet'}</dd>
              <dt>Came from</dt>
              <dd>{item.where}</dd>
            </dl>
          </article>
        ))}
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="font-medium">Recently closed</h2>
        {loaded && closed.length === 0 && (
          <p className="text-muted-foreground text-sm">Nothing closed recently.</p>
        )}
        {closed.map((item, i) => (
          <article key={`${item.closed}-${i}`} className="rounded-lg border p-4 text-sm">
            <p>
              <span className="font-medium">What fixed it: </span>
              {item.note}
            </p>
            <p className="text-muted-foreground mt-1 truncate text-xs">Was: {item.excerpt}</p>
            <p className="text-muted-foreground text-xs">Closed {when(item.closed)}</p>
          </article>
        ))}
      </section>
    </main>
  );
}
