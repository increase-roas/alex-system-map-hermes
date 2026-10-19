# Draft: asking Langfuse to credit the overage

**Not sent.** Contacting a real person is Alex's decision. This is a draft for him to send, edit or bin.

Send to Langfuse support (support@langfuse.com, or the in-app chat from
`https://us.cloud.langfuse.com/organization/cmv733aok01e3ad0me2x704qs/settings/billing`).

Keep it short. Support teams credit a first runaway far more often than people expect, especially when the
customer has already fixed the cause and can describe it precisely. The case here is strong on four points: the
cause was a misconfiguration, the data is worthless, it happened in three days, and their own alert fired without
being able to stop anything.

---

Subject: Credit request for accidental overage, org "Increase Roas" (cmv733aok01e3ad0me2x704qs)

Hi,

I'd like to ask for a credit on the usage accrued in my current billing period
(2026-10-16 to 2026-11-16) on org `cmv733aok01e3ad0me2x704qs`, project "Increase Roas".

What happened: on 2026-10-16 I set up OTLP tracing for the Codex desktop app. The exporter turned out to emit a
span for every internal operation rather than one per run. Over the following three days it sent about 6.5 million
units. A breakdown by span name shows what they are:

- `receiving` and `handle_responses`: 3.83M, one span per streaming chunk
- `append_items`, `persist_rollout_items`, `realtime_conversation.running_state`: 1.56M, internal bookkeeping
- `fs.get_metadata` and `fs.read_file`: 766k, individual filesystem calls

Those seven span names are about 91% of the volume. None of them is a run, and the app's spans carry no session
id, so they cannot even be grouped into runs. The data has no observability value to me and I will never query it.

What I've done: I disabled the app's OTLP export at source on 2026-10-19, so the volume stops. I've kept tracing
on my other senders, which produce normal volumes (around 110,000 units a week).

Two things that made this hard to catch, which you may want to know as feedback:

1. My "$200" spend alert triggered on 2026-10-16 and spending continued straight through it, because it is a
   notification and not a cap. I could not find any hard spend limit available on the Core plan. A real cap, or
   an opt-in one, would have stopped this at $200 instead of letting it reach four figures.
2. Every tier includes the same 100,000 units, so there was no upgrade path that would have absorbed this. The
   only lever was sending less, which I only worked out after the fact.

Would you be able to credit the accrued usage for this period, or some part of it? Happy to provide the full
per-span-name breakdown if that helps.

Thanks,
Alex

---

## Notes for Alex before sending

- **Send it before 2026-11-16.** That is when the draft invoice closes and becomes a charge. A credit before
  billing is routine; a refund afterwards is a harder conversation.
- **Do the restart first**, or at least mention it is done. "I have already fixed it" is the sentence that gets
  these approved. Asking for a credit while the meter is still running reads badly.
- Don't inflate it. The figures above are from their own billing page and from the Langfuse API, and they can
  check every one. That accuracy is the strongest thing in the message.
- If they decline, the amount is what it is and the restart still saves the much larger remainder.
