'use client';

import { useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import type { LocalEvidence, LocalFileIndex, LocalFinding, LocalRepairChecks, LocalRepairPreview, LocalRepairResult, LocalRepairSource, LocalRepairSuggestion } from '@/lib/types/local-files';

type Props = {
  fileId: string; localToken: string; index: LocalFileIndex; finding: LocalFinding | null;
  onOpenFile: (id: string, line?: number | null) => void;
  onClose: () => void; onLockChange: (locked: boolean) => void;
};
class RepairError extends Error {
  constructor(message: string, public status: number) { super(message); }
}
async function repairRequest<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, options);
  const body = await response.json();
  if (!response.ok) throw new RepairError(String(body.error ?? body.message ?? `Request failed (${response.status})`), response.status);
  return body as T;
}
const text = 'min-w-0 rounded border bg-muted/40 p-3 font-mono text-sm whitespace-pre-wrap break-all';

function BehavioralChecks({ checks, onOpenFile }: { checks: LocalRepairChecks; onOpenFile: Props['onOpenFile'] }) {
  return <div className="min-w-0 space-y-3 rounded border p-3" aria-label="AI behavioral checks">
    <h4 className="font-semibold">Behavioral checks {checks.status}</h4>
    <p className="text-sm">These simulated decisions test the listed scenarios. They do not prove live tool execution or consistency for every instruction.</p>
    {checks.cases.map((item) => <div key={item.id} className="min-w-0 space-y-2 rounded border p-3">
      <h5 className="font-medium">{item.purpose === 'fix' ? 'Intended fix' : 'Preserved behavior'}: {item.scenario}</h5>
      <dl className="space-y-1 text-sm">{(['A', 'B', 'C'] as const).map((choice) => <div key={choice}><dt className="font-medium">{choice}</dt><dd>{item.choices[choice]}</dd></div>)}</dl>
      <p className="text-sm">{`Before: ${item.before}. After: ${item.after}. Expected: ${item.expected}. Result: ${item.status}.`}</p>
      <p className="text-sm">{item.rationale}</p>
      {item.evidence.map((citation, i) => <div key={i}><button type="button" className="break-all text-left text-sm underline underline-offset-4" onClick={() => onOpenFile(citation.file_id, citation.line)}>{citation.file_id}:{citation.line}</button><pre className={text}>{citation.quote}</pre></div>)}
    </div>)}
    {checks.limitations.map((limit, i) => <p key={i} className="text-sm">{limit}</p>)}
    <p className="text-muted-foreground text-sm">Model: {checks.model}. Checked {checks.checked_at}.</p>
  </div>;
}

export function LocalFileRepairPanel({ fileId, localToken, index, finding, onOpenFile, onClose, onLockChange }: Props) {
  const [source, setSource] = useState<LocalRepairSource | null>(null);
  const [draft, setDraft] = useState('');
  const [preview, setPreview] = useState<LocalRepairPreview | null>(null);
  const [result, setResult] = useState<LocalRepairResult | null>(null);
  const [phase, setPhase] = useState<'reading' | 'suggesting' | 'previewing' | 'applying' | 'undoing' | null>('reading');
  const busy = phase !== null;
  const [error, setError] = useState('');
  const [suggestionError, setSuggestionError] = useState('');
  const [suggestion, setSuggestion] = useState<LocalRepairSuggestion | null>(null);
  const [stale, setStale] = useState(false);
  const activeRequest = useRef<AbortController | null>(null);
  const generation = useRef(0);
  const automaticAttempt = useRef('');
  const dirty = Boolean(source && draft !== source.content && !result);
  const currentState = useRef({ dirty, preview, result, stale });
  currentState.current = { dirty, preview, result, stale };
  const locked = dirty || busy;
  useEffect(() => { onLockChange(locked); }, [locked, onLockChange]);
  useEffect(() => {
    // This bounded local read can finish after cleanup; ignore obsolete results.
    let ignored = false;
    generation.current += 1;
    activeRequest.current?.abort();
    automaticAttempt.current = '';
    setPhase('reading'); setSource(null); setDraft(''); setPreview(null); setResult(null);
    setSuggestion(null); setSuggestionError(''); setError(''); setStale(false);
    repairRequest<LocalRepairSource>(`/api/local-files/repair?id=${encodeURIComponent(fileId)}`)
      .then((data) => { if (!ignored) { setPhase(null); setSource(data); setDraft(data.content); } })
      .catch((e) => { if (!ignored) { setPhase(null); setError(e instanceof Error ? e.message : 'Source could not be opened.'); } });
    return () => { ignored = true; activeRequest.current?.abort(); };
  }, [fileId]);

  async function post<T>(body: object, signal: AbortSignal): Promise<T> {
    return repairRequest<T>('/api/local-files/repair', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Local-Token': localToken }, body: JSON.stringify(body), signal });
  }
  async function requestSuggestion(target: LocalRepairSource, findingId: string | null) {
    if (!target.editable || !target.sha256 || !localToken || target.file_id !== fileId) return;
    const state = currentState.current;
    if (state.dirty || state.preview || state.result || state.stale) return;
    const controller = new AbortController();
    activeRequest.current?.abort(); activeRequest.current = controller;
    const started = generation.current;
    setPhase('suggesting'); setSuggestionError(''); setError(''); setSuggestion(null);
    try {
      const data = await post<LocalRepairSuggestion>({ action: 'suggest', file_id: target.file_id, expected_sha256: target.sha256, finding_id: findingId }, controller.signal);
      if (controller.signal.aborted || generation.current !== started || currentState.current.dirty || currentState.current.result) return;
      setSuggestion(data);
      if (data.status === 'proposed' && data.proposed_content !== null && data.preview && data.checks?.status === 'passed' && data.preview.checks?.status === 'passed') {
        setDraft(data.proposed_content); setPreview(data.preview);
      }
    } catch (e) {
      if (!controller.signal.aborted && generation.current === started) {
        setSuggestionError(e instanceof Error ? e.message : 'AI analysis could not finish.');
        if (e instanceof RepairError && e.status === 409) { setStale(true); setPreview(null); }
      }
    } finally { if (!controller.signal.aborted && generation.current === started) setPhase(null); }
  }
  useEffect(() => {
    if (!source || source.file_id !== fileId || !source.editable || !source.sha256 || !localToken) return;
    const key = `${fileId}:${source.sha256}:${finding?.id ?? ''}:${localToken}`;
    if (automaticAttempt.current === key) return;
    automaticAttempt.current = key;
    void requestSuggestion(source, finding?.id ?? null);
    const request = activeRequest.current;
    // Cancel only this analysis, never a later Apply or Undo request.
    return () => {
      request?.abort();
      if (activeRequest.current === request) setPhase((current) => current === 'suggesting' ? null : current);
    };
    // Draft, preview and result changes must not automatically request a new proposal.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [source, fileId, localToken, finding?.id]);

  function showError(e: unknown) {
    setError(e instanceof Error ? e.message : 'Repair request failed.');
    if (e instanceof RepairError && e.status === 409) { setStale(true); setPreview(null); }
  }
  function adoptEvidenceWording(chosen: LocalEvidence) {
    if (!source?.editable || busy || result || dirty) return;
    const targets = finding?.evidence.filter((e) => e.file_id === source.file_id) ?? [];
    if (targets.length !== 1 || /[\r\n]/.test(targets[0].text) || /[\r\n]/.test(chosen.text)) {
      setError('Choose wording needs one exact target evidence line and one replacement line. This evidence is ambiguous or spans lines. Your draft is unchanged; use the source editor to make a precise change.');
      return;
    }
    // Captured separators retain every original newline byte, including mixed styles.
    const parts = source.content.split(/(\r\n|\n|\r)/);
    const matchingLines: number[] = [];
    for (let i = 0; i < parts.length; i += 2) if (parts[i] === targets[0].text) matchingLines.push(i);
    if (matchingLines.length !== 1) {
      setError(`The target evidence line matches ${matchingLines.length} source lines. Nothing was replaced. Your draft is unchanged; compare the actual source and edit the intended line manually, or reopen fresh evidence.`);
      return;
    }
    parts[matchingLines[0]] = chosen.text;
    setDraft(parts.join(''));
    setPreview(null); setSuggestion(null);
    setError('');
  }
  async function makePreview() {
    if (!source?.editable || !source.sha256) return;
    const controller = new AbortController();
    activeRequest.current?.abort(); activeRequest.current = controller;
    const started = generation.current;
    setPhase('previewing'); setError('');
    try {
      const data = await post<LocalRepairPreview>({ action: 'preview', file_id: source.file_id, expected_sha256: source.sha256, new_content: draft }, controller.signal);
      if (!controller.signal.aborted && generation.current === started) { setPreview(data); setStale(false); }
    } catch (e) { if (!controller.signal.aborted && generation.current === started) showError(e); }
    finally { if (!controller.signal.aborted && generation.current === started) setPhase(null); }
  }
  async function apply() {
    if (!preview || (suggestion && (suggestion.checks?.status !== 'passed' || preview.checks?.status !== 'passed')) || preview.checks && preview.checks.status !== 'passed' || preview.distribution?.status === 'blocked') return;
    const controller = new AbortController();
    activeRequest.current?.abort(); activeRequest.current = controller;
    const started = generation.current;
    setPhase('applying'); setError('');
    try {
      const data = await post<LocalRepairResult>({ action: 'apply', repair_id: preview.repair_id, proposal_sha256: preview.proposal_sha256 }, controller.signal);
      if (!controller.signal.aborted && generation.current === started) setResult(data);
    } catch (e) { if (!controller.signal.aborted && generation.current === started) showError(e); }
    finally { if (!controller.signal.aborted && generation.current === started) setPhase(null); }
  }
  async function undo() {
    if (!result) return;
    const controller = new AbortController();
    activeRequest.current?.abort(); activeRequest.current = controller;
    const started = generation.current;
    setPhase('undoing'); setError('');
    try {
      const data = await post<LocalRepairResult>({ action: 'undo', repair_id: result.repair_id }, controller.signal);
      if (!controller.signal.aborted && generation.current === started) setResult(data);
    } catch (e) { if (!controller.signal.aborted && generation.current === started) showError(e); }
    finally { if (!controller.signal.aborted && generation.current === started) setPhase(null); }
  }
  const generatedFiles = index.references.filter((r) => r.kind === 'generated_from' && r.target_id === fileId)
    .map((r) => index.files.find((f) => f.id === r.source_id)).filter((f) => f !== undefined);
  const publishPending = Boolean(result && !result.pushed) || result?.state === 'applied_publish_pending' || result?.state === 'undone_publish_pending';
  const repairVerified = Boolean(result?.source_verified === true && result.pushed && !publishPending && !result.generated_follow_up && (result.distribution?.status === 'verified' || result.distribution?.status === 'not_needed'));
  const approvalBlocked = Boolean((suggestion && (suggestion.checks?.status !== 'passed' || preview?.checks?.status !== 'passed')) || (preview?.checks && preview.checks.status !== 'passed') || preview?.distribution?.status === 'blocked');
  const applied = result?.state === 'applied' || result?.state === 'applied_publish_pending';

  return <section id="local-file-repair" className="min-w-0 space-y-4 rounded-lg border-2 border-primary p-4 md:p-6" aria-label="Review and fix instruction source">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="text-lg font-semibold">Review &amp; fix</h3><p className="text-muted-foreground mt-1 text-sm">AI reviews the current source and related evidence, then proposes an exact fix for your approval.</p></div>
      <Button variant="outline" disabled={busy} onClick={onClose}>{dirty ? 'Discard draft and close' : 'Close repair'}</Button>
    </div>
    {finding && <details className="space-y-3 rounded border p-3"><summary className="cursor-pointer font-medium">Indexed evidence: {finding.topic}</summary><p className="mt-3 text-sm">{finding.reason}</p><div className="mt-3 grid min-w-0 gap-3 md:grid-cols-2">{finding.evidence.map((e, i) => <div key={`${e.file_id}-${e.line}-${i}`} className="min-w-0"><button type="button" className="text-left text-sm underline underline-offset-4 break-all" onClick={() => onOpenFile(e.file_id, e.line)}>{index.files.find((f) => f.id === e.file_id)?.path ?? e.file_id}:{e.line}</button><pre className={`${text} mt-2`}>{e.text}</pre>{source?.editable && e.file_id !== source.file_id && finding.evidence.some((target) => target.file_id === source.file_id) && <Button className="mt-2" size="sm" variant="outline" disabled={busy || Boolean(result) || dirty || stale} onClick={() => adoptEvidenceWording(e)}>Use this wording manually</Button>}</div>)}</div><p className="text-muted-foreground mt-3 text-sm">Optional manual shortcut: replace one exact target line with this evidence, then preview your change.</p></details>}
    {busy && <div role="status" className="space-y-2 rounded border p-3 text-sm"><p>{phase === 'reading' ? 'Opening the current source…' : phase === 'suggesting' ? 'AI is reading the current source and bounded related context, checking conflicts and simulated before/after decisions, and preparing an exact proposal…' : phase === 'previewing' ? 'Validating and freezing the exact draft change…' : phase === 'applying' ? 'Applying the approved proposal and recording its publication…' : 'Restoring the recorded source and recording its publication…'}</p>{phase === 'suggesting' && <><p className="text-muted-foreground">This can take a few minutes. Source files change only after you approve the proposal.</p><Button size="sm" variant="outline" onClick={() => { activeRequest.current?.abort(); setPhase(null); setSuggestionError('Stopped waiting for AI review. No source change was requested.'); }}>Stop waiting</Button></>}</div>}
    {suggestionError && <div role="alert" className="space-y-2 rounded border border-amber-500 p-3 text-sm"><p className="font-medium">AI proposal unavailable</p><p>{suggestionError}</p><p>No source change was requested. There is no automatic retry.</p>{stale && <p>The source or context changed. Reopen the current source before requesting a fresh proposal.</p>}</div>}
    {suggestion && <div className="min-w-0 space-y-3 rounded border p-4" aria-label="AI source review"><h4 className="font-semibold">{suggestion.status === 'proposed' ? 'AI proposed fix' : suggestion.status === 'no_change' ? 'No change proposed' : 'A decision is needed'}</h4><p className="text-sm">{suggestion.summary}</p><p className="text-sm">{suggestion.rationale}</p>{suggestion.conflicts.map((conflict, i) => <div key={i} className="space-y-2 rounded border p-3"><p className="text-sm">{conflict.explanation}</p>{conflict.evidence.map((citation, j) => <div key={`${citation.file_id}-${citation.line}-${j}`}><button type="button" className="text-left text-sm underline underline-offset-4 break-all" onClick={() => onOpenFile(citation.file_id, citation.line)}>{suggestion.context_files.find((f) => f.file_id === citation.file_id)?.path ?? index.files.find((f) => f.id === citation.file_id)?.path ?? citation.file_id}:{citation.line}</button><pre className={`${text} mt-2`}>{citation.quote}</pre></div>)}</div>)}<details className="rounded border p-3"><summary className="cursor-pointer text-sm font-medium">Files considered and review limits</summary><p className="mt-3 text-sm">Coverage is bounded to these current files; this review does not establish authority across the entire system.</p>{suggestion.context_files.map((f) => <div key={f.file_id} className="mt-2"><button type="button" className="text-left text-sm underline underline-offset-4 break-all" onClick={() => onOpenFile(f.file_id)}>{f.path}</button><p className="text-muted-foreground break-all font-mono text-xs">SHA-256: {f.sha256}</p>{f.applicability && <dl className="mt-2 space-y-1 text-sm"><div><dt className="font-medium">Role</dt><dd>{f.applicability.role}</dd></div><div><dt className="font-medium">Scope</dt><dd>{f.applicability.scope}</dd></div><div><dt className="font-medium">Activation</dt><dd>{f.applicability.activation}</dd></div>{f.applicability.limitations.map((limit, i) => <div key={i}><dt className="sr-only">Limit</dt><dd>{limit}</dd></div>)}</dl>}</div>)}{suggestion.limitations.map((limit, i) => <p key={i} className="mt-2 text-sm">{limit}</p>)}</details><p className="text-muted-foreground text-sm">Model: {suggestion.model}. Uses your existing ChatGPT plan allowance. Availability and usage limits apply. Reviewed {suggestion.generated_at}.</p>{suggestion.checks && <BehavioralChecks checks={suggestion.checks} onOpenFile={onOpenFile} />}{suggestion.status === 'proposed' && suggestion.checks?.status !== 'passed' && <p role="alert" className="text-sm">AI checks {suggestion.checks?.status ?? 'unavailable'}. There is no approvable AI edit.</p>}{suggestion.status !== 'proposed' && <p className="text-sm">There is no approvable edit. {suggestion.status === 'needs_decision' ? 'The evidence did not establish which instruction should win.' : 'The review found no justified replacement.'}</p>}</div>}
    {source?.editable && !result && !preview && !dirty && (suggestionError || suggestion) && <Button variant="outline" disabled={busy || !localToken || stale} onClick={() => void requestSuggestion(source, finding?.id ?? null)}>Try AI again</Button>}
    {error && <div role="alert" className="rounded border border-red-500 p-3 text-sm"><p className="mb-2 font-medium">Source repair request failed</p><p>{error}</p>{stale && <p className="mt-2">Your draft is preserved below. Source or proposal state changed. Copy your draft before closing, reopen the current source, then reconcile it before a new preview.</p>}<p className="mt-2">No automatic retry is made. If the request outcome is uncertain, retain this panel and its repair ID for reconciliation.</p></div>}
    {!localToken && <p className="text-sm">AI review, Preview, Apply and Undo are unavailable because the local authorization token is missing.</p>}
    {source && <>
      <dl className="space-y-2 text-sm"><div><dt className="text-muted-foreground">Repair target</dt><dd className="break-all">{source.path}</dd></div><div><dt className="text-muted-foreground">Source fingerprint when opened (SHA-256)</dt><dd className="break-all">{source.sha256 ?? 'Unavailable'}</dd></div></dl>
      <p className="text-sm">{source.reason}</p>
      {!!source.source_file_ids.length && <div className="space-y-2"><h4 className="font-medium">Open the owning source</h4><p className="text-sm">Generated files and shared links are not rewritten directly. Follow an indexed source, then use its Review &amp; fix button.</p>{source.source_file_ids.map((id) => <div key={id}><button type="button" className="text-left text-sm underline underline-offset-4 break-all" onClick={() => onOpenFile(id)}>{index.files.find((f) => f.id === id)?.path ?? id}</button></div>)}</div>}
      {!source.editable && <p className="rounded border p-3 text-sm">Direct repair is unavailable for this file. {source.reason} No generic configuration, skill or executable-file write is offered.</p>}
      {source.editable && <>
        <details className="min-w-0 rounded border p-3"><summary className="cursor-pointer font-medium">Actual source before this proposal</summary><pre className={`${text} mt-3 max-h-[400px] overflow-y-auto`}>{source.content || '(empty file)'}</pre></details>
        <details className="min-w-0 space-y-3 rounded border p-3"><summary className="cursor-pointer font-medium">Edit manually (optional)</summary>
        <label className="mt-3 block text-sm font-medium" htmlFor="local-repair-draft">Proposed source text</label>
        <textarea id="local-repair-draft" className="min-h-[320px] w-full min-w-0 rounded border bg-background p-3 font-mono text-sm whitespace-pre-wrap break-all focus-visible:outline-2 focus-visible:outline-offset-2" value={draft} disabled={busy || Boolean(result)} onChange={(e) => { setDraft(e.target.value); setPreview(null); setSuggestion(null); }} spellCheck={false} />
        <p className="text-muted-foreground text-sm">{dirty ? 'Unsubmitted draft retained. Refresh and switching repair targets are paused until you apply or explicitly discard it.' : 'No unsubmitted draft.'} Source limit: 64 KiB.</p>
        {!result && <Button variant="outline" disabled={!dirty || busy || !localToken || stale} onClick={() => void makePreview()}>Preview exact change</Button>}
        </details>
      </>}
    </>}
    {preview && <div className="min-w-0 space-y-3 rounded border p-4" aria-label="Frozen repair preview">
      <h4 className="font-semibold">Exact proposed change</h4><p className="text-sm break-all">{preview.path}</p>
      <dl className="space-y-2 text-sm">{[['Before SHA-256', preview.before_sha256], ['After SHA-256', preview.after_sha256], ['Proposal fingerprint', preview.proposal_sha256], ['Repair ID', preview.repair_id], ['Preview expires', preview.expires_at]].map(([label, value]) => <div key={label}><dt className="text-muted-foreground">{label}</dt><dd className="break-all">{value}</dd></div>)}</dl>
      <pre className={`${text} max-h-[500px] overflow-y-auto`} aria-label="Exact before and after diff">{preview.diff || 'No text difference reported.'}</pre>
      <p className="text-sm">Apply writes this frozen source and affected-copy plan after rechecking their current bytes and recovery copies.</p>
      {!suggestion && (preview.checks ? <BehavioralChecks checks={preview.checks} onOpenFile={onOpenFile} /> : <p className="text-sm">Manual draft: not tested by AI. Approval covers only the exact preview below.</p>)}
      {preview.distribution ? <div className="min-w-0 space-y-3" aria-label="Affected copy plan"><h5 className="font-medium">Affected copies: {preview.distribution.status}</h5>{preview.distribution.targets.map((target) => <div key={target.path} className="min-w-0 space-y-2 rounded border p-3"><p className="break-all text-sm">{target.path} ({target.kind})</p><p className="break-all text-sm">Before SHA-256: {target.before_sha256 ?? 'New file'}. After SHA-256: {target.after_sha256}</p><pre className={`${text} max-h-[320px] overflow-y-auto`}>{target.diff || 'No byte change; import wrapper will be verified.'}</pre>{target.requires_new_session && <p className="text-sm">Start a new agent session to load these instructions. File readback cannot confirm session adoption.</p>}</div>)}{preview.distribution.limitations.map((limit, i) => <p key={i} className="text-sm">{limit}</p>)}</div> : <p className="text-sm">Affected-copy plan unavailable in this older preview; distribution is not verified.</p>}
      {!result && <Button disabled={busy || !localToken || stale || approvalBlocked} onClick={() => void apply()}>{suggestion?.status === 'proposed' ? 'Approve proposed fix' : 'Apply reviewed source change'}</Button>}
    </div>}
    {result && <div className={`min-w-0 space-y-3 rounded border p-4 ${!repairVerified ? 'border-amber-500' : ''}`} role="status">
      <h4 className="font-semibold">{repairVerified ? (applied ? 'Repair verified' : 'Undo verified') : (applied ? 'Source updated · follow-up pending' : 'Source restored · follow-up pending')}</h4><p className="text-sm">{result.message}</p>
      <dl className="space-y-2 text-sm">{[['State', result.state], ['Path', result.path], ['Current SHA-256', result.current_sha256], ['Undo copy', result.backup_path], ['Commit', result.commit ?? 'Not recorded'], ['Source readback', result.source_verified === true ? 'Verified by server' : result.source_verified === false ? 'Not verified' : 'Not recorded in this receipt'], ['Push', result.pushed ? 'Confirmed by server' : 'Not confirmed'], ['Repair ID', result.repair_id]].map(([label, value]) => <div key={label}><dt className="text-muted-foreground">{label}</dt><dd className="break-all">{value}</dd></div>)}</dl>
      <p className="text-sm">The undo copy is in the existing Drive backup location. Cloud upload is not verified here.</p>
      {publishPending && <p className="text-sm font-medium">The source write happened, but its commit or push needs follow-up. Do not treat this as complete or retry automatically.</p>}
      {result.distribution ? <div className="space-y-2" aria-label="Copy readback results"><h5 className="font-medium">Copy readback: {result.distribution.status}</h5><p className="text-sm">{result.distribution.message}</p>{result.distribution.targets.map((target) => <div key={target.path} className="rounded border p-3 text-sm"><p className="break-all">{target.path}: {target.status}</p><p className="break-all">SHA-256: {target.sha256 ?? 'Unavailable'}</p><p>{target.reason}</p></div>)}</div> : <p className="text-sm">Copy readback was not recorded in this older receipt. Repair verification is unavailable.</p>}
      {result.generated_follow_up && <p className="text-sm font-medium">Affected generated copies remain pending. Review each destination result.</p>}
      <p className="text-sm">Readback verifies files only. It does not prove an already-running agent reloaded instructions; start a new session where required.</p>
      {applied && <Button variant="outline" disabled={busy || !localToken} onClick={() => void undo()}>Undo this source change</Button>}
      <p className="text-muted-foreground text-sm">Undo is conditional: it restores the recorded before bytes only if the source and affected copies still match this repair. Refresh the inventory after reviewing the outcome.</p>
    </div>}
    {!!generatedFiles.length && <div className="space-y-2"><h4 className="font-medium">Indexed generated copies affected by this source</h4>{generatedFiles.map((f) => <div key={f.id}><button type="button" className="text-left text-sm underline underline-offset-4 break-all" onClick={() => onOpenFile(f.id)}>{f.path}</button></div>)}<p className="text-sm">These references show dependency, not a confirmed rebuild.</p></div>}
  </section>;
}
