'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';

import type { AnsweredItem, WaitingItem } from '@/lib/board/waiting';

type BoardView = { available: boolean; waiting: WaitingItem[]; answered: AnsweredItem[]; token: string };

function waited(since: string | null): string {
  if (!since) return 'unknown';
  const hours = (Date.now() - Date.parse(since)) / 3_600_000;
  if (hours < 1) return 'under an hour';
  if (hours < 48) return `${Math.round(hours)} hours`;
  return `${Math.round(hours / 24)} days`;
}

function Question({ item, token, onAnswered }: { item: WaitingItem; token: string; onAnswered: () => void }) {
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch('/api/board/answer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Local-Token': token },
        body: JSON.stringify({ id: item.id, text }),
      });
      const data = (await res.json()) as { error?: string };
      if (!res.ok) throw new Error(data.error || 'Could not save the answer');
      setText('');
      onAnswered();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save the answer');
    } finally {
      setBusy(false);
    }
  }

  return (
    <article className={`rounded-lg border p-4 ${item.gate ? 'border-amber-400' : ''}`}>
      <h3 className="font-medium">{item.title}</h3>
      <p className="mt-2 text-sm">{item.ask}</p>
      <p className="text-muted-foreground mt-2 text-xs">
        Waiting {waited(item.since)} · ticket {item.id}
      </p>
      {item.gate ? (
        <p className="mt-3 rounded bg-amber-100 px-3 py-2 text-sm text-amber-900">Say yes in chat for this one.</p>
      ) : !item.answerable ? (
        <p className="text-muted-foreground mt-3 text-sm">This is a task for you, not a question. Handle it in chat.</p>
      ) : (
        <div className="mt-3 flex flex-col gap-2">
          <textarea
            className="min-h-20 rounded border p-2 text-sm"
            placeholder="Your answer"
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          <div className="flex items-center gap-3">
            <button
              className="rounded bg-black px-3 py-1.5 text-sm text-white disabled:opacity-40"
              disabled={busy || !text.trim()}
              onClick={submit}
            >
              {busy ? 'Saving…' : 'Answer'}
            </button>
            {error && <span className="text-sm text-red-700">{error}</span>}
          </div>
        </div>
      )}
    </article>
  );
}

export function WaitingOnYou() {
  const [view, setView] = useState<BoardView | null>(null);

  const refresh = useCallback(() => {
    fetch('/api/board', { cache: 'no-store' })
      .then((res) => res.json())
      .then((data: BoardView) => setView(data))
      .catch(() => setView({ available: false, waiting: [], answered: [], token: '' }));
  }, []);

  useEffect(refresh, [refresh]);

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-6 p-6">
      <header className="flex items-baseline justify-between gap-4">
        <h1 className="text-lg font-medium">Waiting on you</h1>
        <Link className="text-sm underline" href="/explorer">
          Back to explorer
        </Link>
      </header>
      <p className="text-muted-foreground text-sm">
        Questions your agents are stuck on until you answer. Anything about spending money, messaging real people,
        production or deleting needs your yes in chat instead.
      </p>

      <section className="flex flex-col gap-3">
        <h2 className="font-medium">Questions ({view?.waiting.length ?? '…'})</h2>
        {view && !view.available && <p className="text-sm text-red-700">Could not read the task board.</p>}
        {view?.available && view.waiting.length === 0 && (
          <div className="rounded-lg border p-6 text-center">Nothing waiting on you.</div>
        )}
        {view?.waiting.map((item) => (
          <Question key={item.id} item={item} token={view.token} onAnswered={refresh} />
        ))}
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="font-medium">Answered this week</h2>
        {view?.answered.length === 0 && <p className="text-muted-foreground text-sm">No answers yet.</p>}
        {view?.answered.map((a) => (
          <article key={`${a.id}-${a.answer.ts}`} className="rounded-lg border p-4 text-sm">
            <p className="font-medium">
              {a.title} <span className="text-xs font-normal text-green-700">answered</span>
            </p>
            <p className="mt-1">{a.answer.text}</p>
            <p className="text-muted-foreground mt-1 text-xs">
              {new Date(a.answer.ts).toLocaleString()} · {a.answer.source}
            </p>
          </article>
        ))}
      </section>
    </main>
  );
}
