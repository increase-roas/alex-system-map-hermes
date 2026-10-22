'use client';

import { useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import type { RepairCheck, RepairInventory, RepairJob, RepairPlan, RepairResearch, RepairTarget } from '@/lib/types/repairs';

type ReviewFailure = RepairResearch & { diagnostics?: { stage?: string; reason?: string }; checks?: RepairCheck[]; limitations?: string[] };
class RepairResponseError extends Error {
  constructor(message: string, readonly status: number, readonly code?: string, readonly detail?: ReviewFailure) { super(message); }
}

const box = 'min-w-0 space-y-3 rounded-lg border p-4';
const pre = 'max-h-[420px] overflow-auto whitespace-pre-wrap break-all rounded bg-muted p-3 font-mono text-sm';
const storageKey = 'universal-repair-job';
const maxReviewTargets = 16;
const staleCodes = new Set(['analysis_context_changed', 'target_binding_changed', 'stale_preflight', 'proposal_scope_changed']);
const preJobRejections = new Set(['plan_expired', 'checks_not_passed', 'guidance_required', 'guidance_stale', 'guidance_invalid']);
const terminal = new Set(['completed', 'blocked', 'unknown', 'undone']);
const verifiedStates = new Set(['byte_verified', 'effective', 'reloaded']);
const friendly = (value: string) => value.replaceAll('_', ' ');
const date = (value: string) => Number.isNaN(Date.parse(value)) ? value : new Date(value).toLocaleString();
function Checks({ checks }: { checks: RepairCheck[] }) {
  return <div className="space-y-2" aria-label="Tests and evidence">{!checks.length && <p className="text-sm">No checks recorded.</p>}{checks.map((check, i) => <div key={i} className="rounded border p-3 text-sm"><p className="font-medium">{friendly(check.kind)}: {check.status}</p><p>Runner: {check.runner_id}{check.checked_at ? ` · Checked ${date(check.checked_at)}` : ''}</p>{check.kind === 'simulated_behavior' && <p>Simulated behavior checks model choices; it does not prove live runtime acceptance.</p>}{check.evidence.map((e, j) => <p className="break-all" key={j}>{e}</p>)}{check.limitations.map((l, j) => <p key={j}>{l}</p>)}</div>)}</div>;
}
const practiceLabels = { native_contract: 'Native contract', vendor_recommendation: 'Vendor recommendation', alex_policy: "Alex's policy", inference: 'Reasoned inference' };
function Research({ research, targets = [] }: { research: RepairResearch; targets?: RepairTarget[] }) {
  const { guidance, rationales = [], guidance_assessment: assessment } = research;
  return <div className="space-y-3" aria-label="Why this fix fits">
    <h4 className="font-semibold">Why this is the right fix</h4>
    <p className="text-sm">Documentary support: {assessment?.status ?? 'unavailable'}. This assesses the proposed change against captured guidance. Simulation, native acceptance and live runtime each need separate proof.</p>
    {!guidance && <p className="text-sm">Official guidance is unavailable. Request a fresh researched review before approval.</p>}
    {rationales.map((rationale, i) => <article className={box} key={rationale.target_id}>
      <h5 className="font-medium">{targets.find(target => target.id === rationale.target_id)?.owner ?? `Reviewed source ${i + 1}`}</h5>
      <p className="text-sm"><strong>Diagnosis:</strong> {rationale.diagnosis}</p>
      <p className="text-sm"><strong>Recommended fix:</strong> {rationale.recommendation}</p>
      <p className="text-sm"><strong>Basis:</strong> {practiceLabels[rationale.practice_kind]}</p>
      <p className="text-sm"><strong>Why it applies:</strong> {rationale.applicability}</p>
      {rationale.guidance_evidence.map((citation, j) => {
        const source = guidance?.sources.find(item => item.id === citation.source_id);
        return <div key={j} className="space-y-1 text-sm">{source ? <a className="break-words underline" href={source.url} target="_blank" rel="noopener noreferrer">{source.title} ({source.publisher})</a> : <p>Supporting source unavailable</p>}<blockquote className="border-l-2 pl-3">“{citation.quote}”</blockquote></div>;
      })}
      {rationale.alternatives.map((alternative, j) => <p className="text-sm" key={j}><strong>Alternative considered:</strong> {alternative.option}. {alternative.why_rejected}</p>)}
      {assessment?.findings.filter(finding => finding.target_id === rationale.target_id).map((finding, j) => <p className="text-sm" key={j}>Documentary finding: {finding.status}. {finding.reason}</p>)}
      {rationale.limitations.map((limitation, j) => <p className="text-sm" key={j}>{limitation}</p>)}
    </article>)}
    {assessment?.findings.filter(finding => !rationales.some(rationale => rationale.target_id === finding.target_id)).map((finding, i) => <p className="text-sm" key={i}>Documentary finding: {finding.status}. {finding.reason}</p>)}
    {guidance && <details className="space-y-2 rounded border p-3" open><summary className="cursor-pointer text-sm font-medium">Captured official sources and research limits</summary>
      <p className="text-sm">Retrieved {date(guidance.retrieved_at)}. Usable until {date(guidance.expires_at)}. Fresh retrieval does not itself confirm a live crawl.</p>
      {guidance.sources.map(source => <div className="space-y-1 py-2 text-sm" key={source.id}>
        <a className="break-words underline" href={source.url} target="_blank" rel="noopener noreferrer">{source.title} ({source.publisher})</a>
        <p>{source.version ? `Document version: ${source.version}` : 'Version unknown'}. Publication date: {source.publication_date ?? 'unknown'}. Installed version match is not established.</p>
        <p>Retrieved {date(source.retrieved_at)}. Crawl evidence: {source.crawl_status}. {source.crawl_status === 'crawled' ? 'The retrieval service reported a live crawl.' : 'Live crawl not confirmed.'}</p>
        <details><summary className="cursor-pointer">Source proof details</summary><p className="break-all">Source: {source.id} · Content hash: {source.content_sha256}</p><p className="break-all">Route: {guidance.route}</p>{source.passages.map(passage => <blockquote className="border-l-2 pl-3" key={passage.id}>{passage.text}</blockquote>)}</details>
      </div>)}
      {guidance.coverage.map((coverage, i) => <div key={i} className="text-sm"><p>Reviewed source {i + 1}: guidance {coverage.status}.</p>{coverage.limitations.map((limitation, j) => <p key={j}>{limitation}</p>)}</div>)}
      {guidance.limitations.map((limitation, i) => <p className="text-sm" key={i}>{limitation}</p>)}
    </details>}
    {assessment?.limitations.map((limitation, i) => <p className="text-sm" key={i}>{limitation}</p>)}
  </div>;
}
function Target({ target }: { target: RepairTarget }) {
  return <div className="min-w-0 space-y-1 text-sm"><p className="break-all font-medium">{target.owner} · {friendly(target.category)} · {target.scope}</p><p className="break-all">Target: {target.id}</p><pre className="whitespace-pre-wrap break-all text-sm">{JSON.stringify(target.identity, null, 2)}</pre><p>Evidence observed: {date(target.observed_at)}</p><p>Capabilities: {target.capabilities.join(', ') || 'None recorded'}</p>{target.missing_capability && <p>Missing capability: {target.missing_capability}</p>}{target.evidence.map((e, i) => <p className="break-all" key={i}>{e}</p>)}{target.limitations.map((l, i) => <p key={i}>{l}</p>)}</div>;
}
export function RepairTargetsPanel({ localToken, requestedSource }: { localToken: string; requestedSource?: { fileId: string; path: string; nonce: number } | null }) {
  const [inventory, setInventory] = useState<RepairInventory | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [query, setQuery] = useState('');
  const [intent, setIntent] = useState('');
  const [plan, setPlan] = useState<RepairPlan | null>(null);
  const [job, setJob] = useState<RepairJob | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobRevision, setJobRevision] = useState(0);
  const [lookupPending, setLookupPending] = useState(false);
  const [snapshot, setSnapshot] = useState<{ target: RepairTarget; snapshot: unknown } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [reviewFailure, setReviewFailure] = useState<ReviewFailure | null>(null);
  const [stale, setStale] = useState(false);
  const mounted = useRef(true);
  const applying = useRef(false);
  const revision = useRef(0);
  const requests = useRef(new Set<AbortController>());
  async function request<T>(url: string, body?: object, keepalive = false): Promise<T> {
    const controller = new AbortController();
    if (!keepalive) requests.current.add(controller);
    try {
      const response = await fetch(url, { method: body ? 'POST' : 'GET', headers: { 'X-Local-Token': localToken, ...(body ? { 'Content-Type': 'application/json' } : {}) }, ...(body ? { body: JSON.stringify(body) } : {}), signal: keepalive ? undefined : controller.signal, keepalive });
      const data = await response.json();
      if (!response.ok) throw new RepairResponseError(String(data.error ?? `Request failed (${response.status})`), response.status, typeof data.code === 'string' ? data.code : undefined, data);
      return data as T;
    } finally { requests.current.delete(controller); }
  }
  function failed(e: unknown) {
    if (!mounted.current || e instanceof Error && e.name === 'AbortError') return;
    if (e instanceof RepairResponseError && e.code && staleCodes.has(e.code)) { setPlan(null); setStale(true); }
    if (e instanceof RepairResponseError && e.code === 'ai_no_proposals') { setPlan(null); setReviewFailure(e.detail ?? null); }
    setError(e instanceof Error ? e.message : 'Repair request failed.');
  }
  function invalidate() { revision.current += 1; setPlan(null); setStale(false); setSnapshot(null); setReviewFailure(null); setBusy(null); }
  useEffect(() => {
    mounted.current = true;
    if (localToken) request<RepairInventory>('/api/repairs').then(data => { if (mounted.current) setInventory(data); }).catch(failed);
    try { const saved = window.localStorage.getItem(storageKey); if (saved) { setJobId(saved); setLookupPending(true); } } catch { /* Server job remains authoritative if browser storage is unavailable. */ }
    return () => { mounted.current = false; for (const controller of requests.current) controller.abort(); };
  }, [localToken]); // Authorization covers both inventory and durable job reads.
  useEffect(() => {
    if (!requestedSource || !inventory) return;
    const matches = inventory.targets.filter(t => t.identity.file_id === requestedSource.fileId || t.identity.path === requestedSource.path || t.identity.source_path === requestedSource.path || t.id === requestedSource.fileId);
    invalidate(); setSelected(matches.map(t => t.id));
    setError(matches.length ? '' : 'This source has no registered repair target. Search the registered owners below for its canonical source and exact missing capability.');
  }, [requestedSource, inventory]);
  useEffect(() => {
    if (!jobId || !localToken) return;
    let active = true; let timer: ReturnType<typeof setTimeout>;
    const controller = new AbortController();
    async function poll() {
      try {
        const response = await fetch(`/api/repairs/jobs/${encodeURIComponent(jobId!)}`, { headers: { 'X-Local-Token': localToken }, signal: controller.signal });
        const data = await response.json();
        if (!active) return;
        if (response.status === 404) {
          setLookupPending(true);
          timer = setTimeout(() => void poll(), 1500);
          return;
        }
        if (!response.ok) throw new Error(String(data.error ?? 'Job read failed.'));
        setLookupPending(false); setJob(data as RepairJob);
        if (!terminal.has(data.status)) timer = setTimeout(() => void poll(), 1500);
      } catch (e) { if (active && !controller.signal.aborted) { setLookupPending(true); failed(e); } }
    }
    void poll();
    return () => { active = false; clearTimeout(timer); controller.abort(); };
  }, [jobId, localToken, jobRevision]);
  async function refreshCoverage() {
    invalidate(); setBusy('inventory'); setError('');
    try { const data = await request<RepairInventory>('/api/repairs'); if (mounted.current) setInventory(data); } catch (e) { failed(e); } finally { if (mounted.current) setBusy(null); }
  }
  async function propose() {
    if (!selected.length || selected.length > maxReviewTargets || !intent.trim() || busy || activeJob) return;
    const started = revision.current; setBusy('review'); setError(''); setPlan(null); setStale(false); setReviewFailure(null);
    try { const data = await request<RepairPlan>('/api/repairs', { action: 'propose', target_ids: selected, intent }); if (mounted.current && revision.current === started) setPlan(data); } catch (e) { if (revision.current === started) failed(e); } finally { if (mounted.current && revision.current === started) setBusy(null); }
  }
  function recordJob(data: RepairJob) { setLookupPending(false); setJob(data); setJobId(data.job_id); setJobRevision(value => value + 1); try { window.localStorage.setItem(storageKey, data.job_id); } catch { setError(`Browser storage unavailable. Keep job ID ${data.job_id} for recovery.`); } }
  async function apply() {
    if (!plan || approvalBlocked || applying.current || busy || activeJob) return;
    applying.current = true; setBusy('apply'); setError('');
    // The coordinator's durable job ID is the frozen plan ID. Save before sending approval.
    setJob(null); setJobId(plan.plan_id); setLookupPending(true); setPlan(null);
    try { window.localStorage.setItem(storageKey, plan.plan_id); } catch { setError(`Browser storage unavailable. Keep job ID ${plan.plan_id} for recovery.`); }
    try { const data = await request<RepairJob>('/api/repairs', { action: 'apply', plan_id: plan.plan_id, digest: plan.digest }, true); if (mounted.current) { recordJob(data); setPlan(null); } } catch (e) {
      if (mounted.current && e instanceof RepairResponseError && e.status === 409 && Boolean(e.code && preJobRejections.has(e.code))) {
        // These explicit approval failures occur before the coordinator creates any job.
        setJobId(null); setLookupPending(false); setStale(false);
        try { if (window.localStorage.getItem(storageKey) === plan.plan_id) window.localStorage.removeItem(storageKey); } catch { /* The in-memory rejection remains authoritative for this open panel. */ }
        setError(e.code?.startsWith('guidance_') ? 'The proposal needs fresh valid official guidance. No job was created and no repair was applied. Review & fix again for a fresh researched bundle.' : e.code === 'plan_expired' ? 'The tested proposal expired. No job was created and no repair was applied. Review & fix again for a fresh tested bundle.' : 'The proposal checks did not pass. No job was created and no repair was applied. Review & fix again for a fresh tested bundle.');
      } else failed(e);
    } finally { if (mounted.current) setBusy(null); applying.current = false; }
  }
  async function jobAction(action: 'resume' | 'reconcile' | 'undo') {
    if (!job || busy || applying.current) return;
    applying.current = true; setBusy(action); setError('');
    try { const data = await request<RepairJob>(`/api/repairs/jobs/${encodeURIComponent(job.job_id)}`, { action }); if (mounted.current) recordJob(data); } catch (e) { failed(e); } finally { if (mounted.current) setBusy(null); applying.current = false; }
  }
  async function readSource(id: string) {
    invalidate(); const started = revision.current; setBusy('read'); setError('');
    try { const data = await request<{ target: RepairTarget; snapshot: unknown }>(`/api/repairs?target_id=${encodeURIComponent(id)}`); if (mounted.current && revision.current === started) setSnapshot(data); } catch (e) { if (revision.current === started) failed(e); } finally { if (mounted.current && revision.current === started) setBusy(null); }
  }
  const targets = inventory?.targets ?? [];
  const matches = targets.filter(t => JSON.stringify(t).toLowerCase().includes(query.toLowerCase()));
  const activeJob = Boolean(jobId && (!job || lookupPending) || job && (!['completed', 'undone'].includes(job.status) || Boolean(job.unknown_effect)));
  const checks = plan ? [...plan.checks, ...plan.operations.flatMap(op => op.checks)] : [];
  const originalTargetIds = plan?.proposal_target_ids ?? [];
  const researchReady = Boolean(plan?.guidance && plan.guidance_assessment?.status === 'passed' && originalTargetIds.length &&
    originalTargetIds.every(id => plan.guidance!.coverage.some(row => row.target_id === id && row.status === 'available' && row.source_ids.length) &&
      plan.rationales?.length === originalTargetIds.length && plan.rationales.some(row => row.target_id === id && row.guidance_evidence.length && row.guidance_evidence.every(citation => plan.guidance!.sources.some(source => source.id === citation.source_id))) &&
      plan.guidance_assessment!.findings.some(row => row.target_id === id && row.status === 'supported')) &&
    plan.guidance_assessment.findings.every(row => row.status === 'supported') && Date.parse(plan.guidance.expires_at) > Date.now());
  const approvalBlocked = Boolean(!researchReady || !plan?.operations.length || !checks.length || checks.some(c => c.status !== 'passed') || plan?.targets.some(t => t.missing_capability) || plan && Date.parse(plan.expires_at) <= Date.now());
  const allVerified = Boolean(job?.status === 'completed' && !job.unknown_effect && job.steps.length && job.steps.every(s => s.receipt?.ok && verifiedStates.has(s.receipt.state) && s.receipt.checks.some(c => ['owner_lifecycle', 'native_dry_run', 'runtime'].includes(c.kind) && c.status === 'passed') && s.receipt.checks.every(c => c.status === 'passed')));
  return <section id="universal-repair" tabIndex={-1} className={`${box} border-2 border-primary`} aria-label="Universal Review and fix">
    <h3 className="text-lg font-semibold">Review &amp; fix your agent systems</h3>
    <p className="text-sm">Select registered local or remote sources. Official guidance informs the proposed fix and its separate checks; one approval applies it through each native owner.</p>
    <p className="text-sm">Source bytes, effective settings, runtime reload and publication are separate evidence. Pending or unavailable targets remain unfinished.</p>
    {!localToken && <p role="alert">Local authorization is unavailable. Target and job reads require the local token.</p>}
    {error && <p role="alert" className="break-all rounded border border-amber-500 p-3 text-sm">{error}</p>}
    {jobId && lookupPending && <div role="status" className="space-y-2 rounded border border-amber-500 p-3 text-sm"><p className="font-medium">Original job lookup pending</p><p className="break-all">Waiting for the original job: {jobId}. Approval may already have reached the server. This page reads that job and does not submit another application.</p><Button variant="outline" disabled={!localToken || Boolean(busy)} onClick={() => setJobRevision(value => value + 1)}>Check original job again</Button></div>}
    {reviewFailure && <div className={box} aria-label="Failed AI review"><p className="text-sm">Review failed at stage: {friendly(reviewFailure.diagnostics?.stage ?? 'unknown')}. Reason: {friendly(reviewFailure.diagnostics?.reason ?? 'unavailable')}.</p><Research research={reviewFailure} /><Checks checks={reviewFailure.checks ?? []} />{reviewFailure.limitations?.map((limitation, i) => <p key={i} className="text-sm">{limitation}</p>)}</div>}
    {stale && <p role="alert" className="text-sm">Source or native version changed. The old proposal is invalid. Review &amp; fix again to generate a fresh tested bundle.</p>}
    {busy && <p role="status" className="text-sm">{busy === 'review' ? 'Retrieving official guidance, explaining the proposed fix and checking the exact changes. This can take a few minutes. Unavailable evidence will remain visible.' : `Repair action in progress: ${busy}.`}</p>}
    <Button variant="outline" disabled={!localToken || Boolean(busy) || activeJob} onClick={() => void refreshCoverage()}>Refresh target coverage</Button>
    <div className="flex flex-wrap gap-2 text-sm" aria-label="Category coverage">{[...new Set(targets.map(t => t.category))].map(category => <p className="rounded border p-2" key={category}>{friendly(category)}: {targets.filter(t => t.category === category).length} registered · {targets.filter(t => t.category === category && t.missing_capability).length} with missing capability</p>)}</div>
    {inventory?.limitations.map((l, i) => <p key={i} className="text-sm">{l}</p>)}
    {!inventory && localToken && !error && <p role="status">Loading registered target coverage…</p>}
    <label className="block text-sm font-medium" htmlFor="repair-target-search">Search targets, owners, categories and provider objects</label>
    <input id="repair-target-search" className="w-full rounded border bg-background p-2 text-sm" value={query} onChange={e => setQuery(e.target.value)} />
    <p className="text-sm">{matches.length} matching targets · {selected.length} selected. Local: {targets.filter(t => t.scope === 'local').length}; remote: {targets.filter(t => t.scope === 'remote').length}.</p>
    {selected.length > maxReviewTargets && <p role="alert" className="text-sm">Review supports at most {maxReviewTargets} selected targets per batch. All {selected.length} selections are retained; reduce this batch before reviewing. No targets have been reviewed yet.</p>}
    <div className="flex flex-wrap gap-2"><Button variant="outline" disabled={Boolean(busy) || activeJob || !matches.length} onClick={() => { invalidate(); setSelected([...new Set([...selected, ...matches.map(t => t.id)])]); }}>Select all matching targets</Button><Button variant="outline" disabled={Boolean(busy) || activeJob || !selected.length} onClick={() => { invalidate(); setSelected([]); }}>Clear selection</Button></div>
    <div className="grid max-h-[520px] min-w-0 gap-3 overflow-auto md:grid-cols-2">{matches.map(target => <div key={target.id} className={box}><label className="flex items-start gap-2"><input type="checkbox" className="mt-1" checked={selected.includes(target.id)} disabled={Boolean(busy) || activeJob} onChange={() => { invalidate(); setSelected(selected.includes(target.id) ? selected.filter(id => id !== target.id) : [...selected, target.id]); }} aria-label={`Select ${target.owner} ${target.id}`} /><span className="break-all text-sm font-semibold">{target.owner}: {target.id}</span></label><Target target={target} /><Button variant="outline" disabled={Boolean(busy)} onClick={() => void readSource(target.id)}>Read current source</Button></div>)}</div>
    {!matches.length && inventory && <p className="text-sm">No registered targets match. This does not prove full system coverage.</p>}
    {snapshot && <details open className={box}><summary className="cursor-pointer font-medium">Current safe source: {snapshot.target.id}</summary><Target target={snapshot.target} /><pre className={pre}>{typeof snapshot.snapshot === 'string' ? snapshot.snapshot : JSON.stringify(snapshot.snapshot, null, 2)}</pre></details>}
    <label className="block text-sm font-medium" htmlFor="repair-intent">What should this repair fix and preserve?</label>
    <textarea id="repair-intent" rows={3} className="w-full min-w-0 rounded border bg-background p-3 text-sm" value={intent} disabled={Boolean(busy) || activeJob} onChange={e => { invalidate(); setIntent(e.target.value); }} />
    <Button disabled={!localToken || !selected.length || selected.length > maxReviewTargets || !intent.trim() || Boolean(busy) || activeJob} onClick={() => void propose()}>Review &amp; fix</Button>
    {plan && <div className={box} aria-label="Complete immutable tested bundle"><h4 className="font-semibold">Exact tested bundle</h4><p className="text-sm">{plan.intent}</p><details><summary className="cursor-pointer text-sm">Frozen bundle proof details</summary><p className="break-all text-sm">Plan: {plan.plan_id} · Digest: {plan.digest}</p></details><p className="text-sm">Created: {date(plan.created_at)} · Expires: {date(plan.expires_at)}</p><Research research={plan} targets={plan.targets} /><h5 className="font-medium">Affected targets</h5>{plan.targets.map(target => <div className={box} key={target.id}><Target target={target} /></div>)}<Checks checks={plan.checks} />{plan.operations.map(op => <div key={op.step_id} className={box}><h5 className="break-all font-medium">{op.target_id}: {op.action}</h5><p className="break-all text-sm">Step {op.step_id} · Owner adapter {op.adapter_id} ({op.adapter_version})</p><p className="break-all text-sm">Expected source: {op.expected_fingerprint ?? 'Native version'} · Native version: {op.expected_version ?? 'Not recorded'}</p><pre className={pre} aria-label={`Exact diff for ${op.target_id}`}>{op.public_diff || 'No public text diff recorded.'}</pre><Checks checks={op.checks} /></div>)}{plan.limitations.map((l, i) => <p key={i} className="text-sm">{l}</p>)}<p className="text-sm">Approval covers only this immutable tested bundle. The server rechecks current sources and native versions before any write.</p>{researchReady ? <Button disabled={!localToken || Boolean(busy) || approvalBlocked || activeJob} onClick={() => void apply()}>Approve tested bundle</Button> : <p role="alert" className="text-sm">Research is not ready for approval. Request a fresh researched review with applicable sources and supported reasoning for each reviewed source.</p>}{approvalBlocked && <p className="text-sm">This proposal has missing capability, incomplete or failed checks, no operations, or has expired. Generate a fresh review after resolving the reported evidence.</p>}</div>}
    {job && <div className={box} role="status" aria-label="Durable repair progress"><h4 className="font-semibold">{allVerified ? 'All targets verified' : job.status === 'undone' ? 'Undo recorded: inspect each target receipt' : `Repair ${job.status}: review every target`}</h4><p className="break-all text-sm">Job: {job.job_id} · Updated: {date(job.updated_at)}</p><p className="text-sm">This job survives closing and reopening the page. Reopening reads the same job; it does not apply again.</p>{job.error && <p className="text-sm">{job.error}</p>}{job.unknown_effect && <p className="text-sm">Uncertain effect: {job.unknown_effect}. Reconcile current state before resuming.</p>}{job.steps.map(step => <div className={box} key={step.step_id}><h5 className="break-all font-medium">{step.target_id}: {step.phase}</h5><p className="text-sm">{step.outcome ?? 'No outcome recorded'}</p>{step.receipt ? <><p className="text-sm">Acceptance: {friendly(step.receipt.state)} · {step.receipt.ok ? 'Owner reports success' : 'Not verified'}</p>{step.receipt.state === 'byte_verified' && <p className="text-sm">Source bytes verified. Effective settings and runtime reload need their own native proof.</p>}{step.receipt.state === 'pending' && <p className="text-sm">Publication or native acceptance pending. This target is unfinished.</p>}<p className="break-all text-sm">Fingerprint: {step.receipt.fingerprint ?? 'Unavailable'}</p>{step.receipt.evidence.map((e, i) => <p className="break-all text-sm" key={i}>{e}</p>)}<Checks checks={step.receipt.checks} />{step.receipt.limitations.map((l, i) => <p className="text-sm" key={i}>{l}</p>)}</> : <p className="text-sm">No target receipt yet. Acceptance remains unverified.</p>}</div>)}<details className="rounded border p-3"><summary className="cursor-pointer text-sm font-medium">Recorded progress events</summary>{job.events.map((event, i) => <p className="break-all text-sm" key={i}>{date(event.at)} · {event.phase}{event.step_id ? ` · ${event.step_id}` : ''}</p>)}</details><div className="flex flex-wrap gap-2">{!terminal.has(job.status) && <Button variant="outline" disabled={!localToken || Boolean(busy)} onClick={() => void jobAction('resume')}>Recover recorded job</Button>}{['unknown', 'blocked'].includes(job.status) && <Button variant="outline" disabled={!localToken || Boolean(busy)} onClick={() => void jobAction('reconcile')}>Reconcile current state</Button>}{job.status === 'blocked' && !job.unknown_effect && <Button variant="outline" disabled={!localToken || Boolean(busy)} onClick={() => void jobAction('resume')}>Resume recorded job</Button>}{['completed', 'blocked'].includes(job.status) && !job.unknown_effect && job.steps.some(s => s.receipt?.ok && s.receipt.state !== 'undone') && <Button variant="outline" disabled={!localToken || Boolean(busy)} onClick={() => void jobAction('undo')}>Undo reviewed bundle</Button>}</div><p className="text-sm">Undo is conditional and runs in reverse order. The native owner restores only recorded applied state that still matches, preserving unrelated edits. Each result remains visible here.</p></div>}
  </section>;
}
