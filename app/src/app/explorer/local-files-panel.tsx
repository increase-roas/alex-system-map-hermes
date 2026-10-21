'use client';

import { useEffect, useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { LocalFileRepairPanel } from './local-file-repair-panel';
import type { LocalFile, LocalFileContent, LocalFileIndex, LocalFinding } from '@/lib/types/local-files';

const FILTERS = ['All files', 'Exact copies', 'Shared links', 'Possible conflicts', 'Repeated rules'] as const;
type Filter = typeof FILTERS[number];
const date = (value: string | null) => value ? new Date(value).toLocaleString() : 'Unavailable';
const box = 'min-w-0 rounded-lg border p-4';
const link = 'text-left text-sm underline underline-offset-4 break-all hover:text-primary focus-visible:outline-2 focus-visible:outline-offset-2';

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, options);
  const body = await response.json();
  if (!response.ok) throw new Error(String(body.error ?? `Request failed (${response.status})`));
  return body as T;
}

export function LocalFilesPanel({ localToken }: { localToken: string }) {
  const [index, setIndex] = useState<LocalFileIndex | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState<Filter>('All files');
  const [limit, setLimit] = useState(60);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [finding, setFinding] = useState<LocalFinding | null>(null);
  const [content, setContent] = useState<LocalFileContent | null>(null);
  const [contentError, setContentError] = useState('');
  const [loadingContent, setLoadingContent] = useState(false);
  const [focusLine, setFocusLine] = useState<number | null>(null);
  const [repairTarget, setRepairTarget] = useState<{ fileId: string; finding: LocalFinding | null } | null>(null);
  const [repairLocked, setRepairLocked] = useState(false);

  async function load(refresh = false) {
    setBusy(true); setError('');
    try {
      const data = await request<LocalFileIndex>('/api/local-files', refresh ? {
        method: 'POST', headers: { 'X-Local-Token': localToken },
      } : undefined);
      setIndex(data);
      if (refresh) { setSelectedId(null); setFinding(null); setContent(null); }
    } catch (e) { setError(e instanceof Error ? e.message : 'Local files could not be loaded.'); }
    finally { setBusy(false); }
  }
  useEffect(() => { void load(); }, []); // Initial read; refresh is explicitly requested.
  useEffect(() => {
    if (!selectedId) return;
    const controller = new AbortController();
    setContent(null); setContentError(''); setLoadingContent(true);
    request<LocalFileContent>(`/api/local-files?id=${encodeURIComponent(selectedId)}`, { signal: controller.signal })
      .then(setContent)
      .catch((e) => { if (!controller.signal.aborted) setContentError(e instanceof Error ? e.message : 'File read failed.'); })
      .finally(() => { if (!controller.signal.aborted) setLoadingContent(false); });
    return () => controller.abort();
  }, [selectedId]);
  useEffect(() => { setLimit(60); }, [query, filter]);
  useEffect(() => {
    if (content && focusLine) document.getElementById(`local-source-line-${focusLine}`)?.scrollIntoView({ block: 'nearest' });
  }, [content, focusLine]);

  const filesById = useMemo(() => new Map(index?.files.map((f) => [f.id, f]) ?? []), [index]);
  const selected = selectedId ? filesById.get(selectedId) : null;
  const changedFromDisplayedScan = Boolean(selected?.sha256 && content?.current_sha256 &&
    content.file_id === selected.id && selected.sha256 !== content.current_sha256);
  const eligible = useMemo(() => {
    if (!index || filter === 'All files') return null;
    if (filter === 'Exact copies' || filter === 'Shared links') return new Set(index.duplicates
      .filter((g) => g.kind === (filter === 'Exact copies' ? 'identical_copy' : 'same_file')).flatMap((g) => g.file_ids));
    return new Set(index.findings.filter((f) => f.kind === (filter === 'Possible conflicts' ? 'conflict_candidate' : 'repeated_rule'))
      .flatMap((f) => f.evidence.map((e) => e.file_id)));
  }, [index, filter]);
  const matches = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (index?.files ?? []).filter((f) => (!eligible || eligible.has(f.id)) &&
      (!q || `${f.path} ${f.real_path ?? ''} ${f.kind} ${f.state}`.toLowerCase().includes(q)));
  }, [index, eligible, query]);
  const matchingIds = useMemo(() => new Set(matches.map((file) => file.id)), [matches]);
  const grouped = useMemo(() => {
    const groups = new Map<string, LocalFile[]>();
    for (const file of matches.slice(0, limit)) groups.set(file.root, [...(groups.get(file.root) ?? []), file]);
    return [...groups];
  }, [matches, limit]);

  function openFile(id: string, line: number | null = null) {
    setSelectedId(id); setFocusLine(line);
    requestAnimationFrame(() => document.getElementById('local-file-detail')?.scrollIntoView({ block: 'nearest' }));
  }
  function reviewFile(id: string, evidence: LocalFinding | null = finding) {
    if (repairLocked) return;
    setRepairLocked(true);
    setRepairTarget({ fileId: id, finding: evidence });
    requestAnimationFrame(() => document.getElementById('local-file-repair')?.scrollIntoView({ block: 'start' }));
  }
  function fileLink(id: string, label?: string, line: number | null = null) {
    return <button type="button" className={link} onClick={() => openFile(id, line)}>{label ?? filesById.get(id)?.path ?? id}{line ? `:${line}` : ''}</button>;
  }

  return (
    <div className="h-full min-w-0 overflow-auto" data-testid="local-files-panel">
      <div className="space-y-4 p-4 md:p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0"><h2 className="text-xl font-semibold">Your local agent files</h2>
            <p className="text-muted-foreground mt-1 text-sm">Open the actual files behind your rules, skills, hooks and settings.</p>
            <p className="mt-2 text-sm">Scan: {index ? date(index.scanned_at) : 'Not loaded'}{index ? ` · ${index.files.length.toLocaleString()} files in this bounded inventory` : ''}</p>
          </div>
          <Button variant="outline" disabled={busy || !localToken || repairLocked} onClick={() => void load(true)}>{busy ? 'Reading files…' : 'Refresh local scan'}</Button>
        </div>
        {repairLocked && <p className="text-sm">A repair draft or request is active. The editor stays open while you inspect other files. Apply or explicitly discard it before refreshing or opening another repair.</p>}
        {!localToken && <p className="text-muted-foreground text-sm">Refresh is unavailable while the local authorization token is missing. Saved inventory and file reads remain available.</p>}
        {error && <div role="alert" className={`${box} border-red-500`}><p>Local scan failed: {error}</p><p className="mt-1 text-sm">{index ? 'The previous snapshot is still shown below.' : 'Coverage is unknown until a scan loads.'}</p><Button className="mt-2" variant="outline" onClick={() => void load()}>Retry read</Button></div>}
        {!index && !error && <p role="status">Loading local inventory…</p>}
        {index && <>
          <div className={`${box} bg-muted/40 text-sm`}>
            <p>Exact copies share bytes. Shared links point to the same physical file. Generated or linked files are not automatically a duplicate problem.</p>
            <p className="mt-2">Possible conflicts and repeated rules are review items with source evidence. They do not decide which instruction has authority.</p>
            {(index.coverage.truncated || index.coverage.errors.length > 0 || index.files.some((f) => f.state !== 'readable')) && <p className="mt-2 font-medium">Partial coverage or file failures are present. Review scan scope below.</p>}
            {index.files.length === 0 && <p className="mt-2 font-medium">No files were inventoried. This does not establish that there are no duplicates or conflicts.</p>}
          </div>
          <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(280px,0.8fr)_minmax(0,1.5fr)]">
            <section className={`${box} space-y-4`} aria-label="Local file list">
              <label className="block text-sm font-medium" htmlFor="local-files-search">Search file paths, types or states</label>
              <Input id="local-files-search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="For example: AGENTS.md or hooks" />
              <div className="flex flex-wrap gap-2" aria-label="File filters">{FILTERS.map((item) => <Button key={item} size="sm" variant={filter === item ? 'default' : 'outline'} aria-pressed={filter === item} onClick={() => setFilter(item)}>{item}</Button>)}</div>
              <p className="text-muted-foreground text-sm" role="status">{matches.length} matching files · showing {Math.min(limit, matches.length)}</p>
              {!matches.length && <p className="text-sm">No files match this filter and search. This is not a full-system all-clear.</p>}
              <div className="max-h-[650px] space-y-4 overflow-y-auto">{grouped.map(([root, files]) => <div key={root}>
                <h3 className="mb-2 text-sm font-semibold break-all">{root}</h3>
                <ul className="space-y-2">{files.map((file) => <li key={file.id}><button type="button" aria-pressed={selectedId === file.id} onClick={() => { setFinding(null); openFile(file.id); }} className={`w-full min-w-0 rounded border p-3 text-left hover:bg-muted ${selectedId === file.id ? 'border-primary bg-muted' : ''}`}>
                  <div className="text-sm font-medium break-all">{file.relative_path}</div>
                  <div className="text-muted-foreground mt-1 text-sm">{file.kind} · {file.state}{file.is_symlink ? ' · linked file' : ''}{file.generated ? ' · generated' : ''}</div>
                </button></li>)}</ul>
              </div>)}</div>
              {matches.length > limit && <Button variant="outline" onClick={() => setLimit((n) => n + 60)}>Show 60 more files</Button>}
            </section>
            <section id="local-file-detail" className="min-w-0 space-y-4" aria-label="File detail and evidence">
              {!selected && <div className={box}><h3 className="font-medium">Select a file to read it</h3><p className="text-muted-foreground mt-2 text-sm">Choose a path on the left, or open an evidence group below. Contents are read on demand and shown as plain text.</p></div>}
              {finding && <div className={box}><h3 className="font-semibold">{finding.topic}</h3><p className="mt-1 text-sm">{finding.reason}</p><p className="text-muted-foreground mt-2 text-sm">{finding.kind === 'conflict_candidate' ? 'Possible conflict: review both sources in context.' : 'Repeated rule: matching wording may be intentional.'}</p>
                <div className="mt-3 grid min-w-0 gap-3 md:grid-cols-2">{finding.evidence.map((e, i) => <div className="min-w-0 rounded border p-3" key={`${e.file_id}-${e.line}-${i}`}>{fileLink(e.file_id, undefined, e.line)}<pre className="mt-2 font-mono text-sm whitespace-pre-wrap break-all">{e.line}: {e.text}</pre><Button className="mt-3" size="sm" variant="outline" disabled={repairLocked} onClick={() => reviewFile(e.file_id, finding)}>Review &amp; fix this source</Button></div>)}</div>
              </div>}
              {selected && <div className={`${box} space-y-3`}>
                <h3 className="font-semibold break-all">{selected.path.split('/').pop()}</h3>
                <Button variant="outline" disabled={repairLocked} onClick={() => reviewFile(selected.id)}>Review &amp; fix</Button>
                <dl className="space-y-2 text-sm">{[
                  ['Full path', selected.path], ['Resolved target', selected.real_path ?? 'Unavailable'], ['Type / state', `${selected.kind} / ${selected.state}`],
                  ['Modified', date(selected.mtime)], ['Size / lines', `${selected.bytes ?? 'Unknown'} bytes / ${selected.line_count ?? 'Unknown'} lines`],
                  ['Scanned SHA-256', selected.sha256 ?? 'Unavailable'], ['Link target', selected.link_target ?? 'Not a symlink'],
                  ['Generated', selected.generated ? 'Yes; distribution is not automatically a defect' : 'Not identified as generated'],
                ].map(([label, value]) => <div key={label}><dt className="text-muted-foreground">{label}</dt><dd className="break-all">{value}</dd></div>)}</dl>
                {!!selected.generated_sources.length && <div className="text-sm"><h4 className="font-medium">Declared generated sources</h4>{selected.generated_sources.map((path) => { const target = index.files.find((f) => f.path === path || f.real_path === path || f.relative_path === path); return <div className="break-all" key={path}>{target ? fileLink(target.id, path) : `${path} (not resolved in this inventory)`}</div>; })}</div>}
                <h4 className="font-medium">Related files</h4>
                <ul className="space-y-2">{index.references.filter((r) => r.source_id === selected.id || r.target_id === selected.id).map((r, i) => <li className="text-sm" key={i}><span>{r.source_id === selected.id ? 'Points to' : 'Referenced by'} · {r.kind.replaceAll('_', ' ')}{r.line ? ` · source line ${r.line}` : ''}: </span>{fileLink(r.source_id === selected.id ? r.target_id : r.source_id, undefined, r.source_id !== selected.id ? r.line : null)}</li>)}</ul>
                {!index.references.some((r) => r.source_id === selected.id || r.target_id === selected.id) && <p className="text-muted-foreground text-sm">No resolved references recorded for this file.</p>}
                <h4 className="font-medium">Current file contents</h4>
                {loadingContent && <p role="status" className="text-sm">Reading selected file…</p>}
                {contentError && <p role="alert" className="text-sm">File read failed: {contentError}</p>}
                {content && <>
                  <p className="text-muted-foreground text-sm">Read: {date(content.read_at)}{content.redacted ? ' · sensitive values withheld' : ''}{content.truncated ? ' · content truncated' : ''}</p>
                  <p className="text-sm break-all">Current SHA-256: {content.current_sha256 ?? 'Unavailable'}</p>
                  {(changedFromDisplayedScan || content.changed_since_scan) && <p role="status" className="rounded border border-amber-500 p-2 text-sm">Changed since scan. Current contents differ from scanned evidence; the displayed inventory hash remains above. Refresh before comparing findings.</p>}
                  {content.error ? <p role="alert" className="text-sm">Contents unavailable: {content.error}</p> : content.content.length === 0 ? <p className="text-sm">File is empty.</p> : <div className="bg-muted max-h-[600px] min-w-0 overflow-y-auto rounded p-2 font-mono text-sm" aria-label="Plain text file contents">{content.content.split('\n').map((line, i) => <div id={`local-source-line-${i + 1}`} className={`grid min-w-0 grid-cols-[3rem_minmax(0,1fr)] gap-2 ${focusLine === i + 1 ? 'bg-primary/15' : ''}`} key={i}><span className="text-muted-foreground text-right select-none">{i + 1}</span><span className="whitespace-pre-wrap break-all">{line || ' '}</span></div>)}</div>}
                </>}
              </div>}
            </section>
          </div>
          {repairTarget && <LocalFileRepairPanel key={repairTarget.fileId} fileId={repairTarget.fileId} localToken={localToken} index={index} finding={repairTarget.finding} onOpenFile={openFile} onLockChange={setRepairLocked} onClose={() => { setRepairTarget(null); setRepairLocked(false); }} />}
          <section className={`${box} space-y-4`} aria-label="Duplicate and instruction evidence">
            <h3 className="text-lg font-medium">Evidence groups</h3>
            <p className="text-muted-foreground text-sm">Open a group, then follow each path to its current contents. Search also limits these groups.</p>
            <div className="grid min-w-0 gap-3 md:grid-cols-2">{index.duplicates.filter((g) => (filter === 'All files' || filter === (g.kind === 'same_file' ? 'Shared links' : 'Exact copies')) && g.file_ids.some((id) => matchingIds.has(id))).slice(0, limit).map((g) => <details className="min-w-0 rounded border p-3" key={g.id}><summary className="cursor-pointer text-sm font-medium">{g.kind === 'same_file' ? 'Shared links' : 'Exact copies'} · {g.file_ids.length} files</summary><p className="my-2 text-sm">{g.reason}</p><ul className="space-y-2">{g.file_ids.map((id) => <li key={id}>{fileLink(id)}</li>)}</ul></details>)}
            {index.findings.filter((f) => (filter === 'All files' || filter === (f.kind === 'conflict_candidate' ? 'Possible conflicts' : 'Repeated rules')) && f.evidence.some((e) => matchingIds.has(e.file_id))).slice(0, limit).map((f) => <button key={f.id} type="button" className="min-w-0 rounded border p-3 text-left hover:bg-muted" onClick={() => { setFinding(f); if (f.evidence[0]) openFile(f.evidence[0].file_id, f.evidence[0].line); }}><span className="text-sm font-medium">{f.kind === 'conflict_candidate' ? 'Possible conflict' : 'Repeated rule'}: {f.topic}</span><p className="mt-1 text-sm break-words">{f.reason}</p><p className="text-muted-foreground mt-2 text-sm">Open {f.evidence.length} file/line excerpts</p></button>)}</div>
            <p className="text-muted-foreground text-sm">Snapshot totals: {index.duplicates.length} duplicate/link groups · {index.findings.length} instruction review items. Groups above follow the active filter and show at most {limit} of each type.</p>
            {(index.duplicates.length > limit || index.findings.length > limit) && <Button variant="outline" onClick={() => setLimit((n) => n + 60)}>Show more evidence groups</Button>}
          </section>
          <details className={box} open={index.coverage.truncated || index.coverage.errors.length > 0}>
            <summary className="cursor-pointer font-medium">Scan scope, exclusions and failures{index.coverage.truncated ? ' · TRUNCATED' : ''}</summary>
            <div className="mt-4 space-y-4 text-sm"><p>This bounded snapshot is not an inventory of every file on the Mac.</p>
              <ul className="space-y-2">{index.coverage.roots.map((r, i) => <li key={`${r.path}-${i}`} className="break-all"><strong>{r.label}</strong>: {r.path} · {r.state} · {r.files} files</li>)}</ul>
              <p>Limits: {index.coverage.limits.max_files} files · depth {index.coverage.limits.max_depth} · {index.coverage.limits.max_bytes} bytes per file.</p>
              <div><h4 className="font-medium">Excluded</h4><ul className="list-disc space-y-1 pl-5">{index.coverage.exclusions.map((x) => <li className="break-all" key={x}>{x}</li>)}</ul></div>
              <div><h4 className="font-medium">Skipped</h4>{index.coverage.skipped.length ? index.coverage.skipped.map((s) => <p key={s.reason}>{s.reason}: {s.count}</p>) : <p>No skipped counts reported.</p>}</div>
              <div><h4 className="font-medium">Scan errors</h4>{index.coverage.errors.length ? index.coverage.errors.map((x, i) => <p className="break-all" key={i}>{x}</p>) : <p>No scan errors reported within this scope.</p>}</div>
            </div>
          </details>
        </>}
      </div>
    </div>
  );
}
