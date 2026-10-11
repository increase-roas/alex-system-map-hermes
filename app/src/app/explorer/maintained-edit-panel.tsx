'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';

const CATALOG_TABLE = 'data/components.json';
const DEFAULT_RECORD_ID = 'component_6f112167c8a413f0f3ab';
const METADATA_PATH = 'data/catalog-metadata.json';
const FETCH_DEADLINE_MS = 120_000;

type EditState = {
  path: string;
  record_id?: string;
  sha256: string;
  revision: number;
  document: Record<string, unknown>;
};

type FrozenApplyRequest = {
  path: string;
  record_id?: string;
  expected_sha256: string;
  next_revision: number;
  document: Record<string, unknown>;
  preview_token: string;
  projected_purpose?: string;
  projected_update_policy?: string;
  target_key: string;
};

type SyncStatus = {
  last_observation?: string;
  files?: { path: string; sha256?: string | null; readable?: boolean | number; error?: string | null }[];
};

function previewToken(body: Record<string, unknown>, req: FrozenApplyRequest): string {
  const payload = JSON.stringify({
    after_sha256: body.after_sha256,
    before_sha256: body.before_sha256,
    expected_sha256: req.expected_sha256,
    next_revision: req.next_revision,
    record_id: req.record_id,
    path: req.path,
    target_key: req.target_key,
  });
  let h = 0;
  for (let i = 0; i < payload.length; i += 1) {
    h = (h * 31 + payload.charCodeAt(i)) >>> 0;
  }
  return `pv-${h.toString(16)}`;
}

function targetKey(mode: 'catalog_record' | 'maintained_doc', recordId: string): string {
  return mode === 'catalog_record' ? `${CATALOG_TABLE}#${recordId}` : METADATA_PATH;
}

async function fetchJsonWithDeadline(url: string, init?: RequestInit): Promise<{ ok: boolean; json: unknown }> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), FETCH_DEADLINE_MS);
  try {
    const res = await fetch(url, { ...init, signal: ctrl.signal });
    const text = await res.text();
    let json: unknown;
    try {
      json = text ? JSON.parse(text) : {};
    } catch {
      throw new Error('invalid JSON response');
    }
    return { ok: res.ok, json };
  } finally {
    clearTimeout(timer);
  }
}

export function MaintainedEditPanel({ localToken }: { localToken: string }) {
  const [mode, setMode] = useState<'catalog_record' | 'maintained_doc'>('catalog_record');
  const [recordId, setRecordId] = useState(DEFAULT_RECORD_ID);
  const [state, setState] = useState<EditState | null>(null);
  const [preview, setPreview] = useState<Record<string, unknown> | null>(null);
  const [frozenApply, setFrozenApply] = useState<FrozenApplyRequest | null>(null);
  const [draftDirty, setDraftDirty] = useState(false);
  const [outcome, setOutcome] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sync, setSync] = useState<SyncStatus | null>(null);
  const [syncError, setSyncError] = useState<string | null>(null);
  const [lastGood, setLastGood] = useState<{ revision: number; sha256: string; path: string } | null>(null);
  const lastSyncFp = useRef<string | null>(null);
  const lastGoodRef = useRef(lastGood);
  const purposeRef = useRef<HTMLTextAreaElement>(null);
  const policyRef = useRef<HTMLTextAreaElement>(null);
  const refreshGen = useRef(0);
  const refreshAbort = useRef<AbortController | null>(null);
  const previewGen = useRef(0);
  const previewAbort = useRef<AbortController | null>(null);
  const pollInflight = useRef(false);
  const pollAbort = useRef<AbortController | null>(null);
  const activeTarget = useRef(targetKey(mode, recordId));

  useEffect(() => {
    lastGoodRef.current = lastGood;
  }, [lastGood]);

  useEffect(() => {
    activeTarget.current = targetKey(mode, recordId);
  }, [mode, recordId]);

  const editPath = mode === 'catalog_record' ? CATALOG_TABLE : METADATA_PATH;

  const refresh = useCallback(
    async (opts?: { force?: boolean; preserveOutcome?: boolean }) => {
      if (!opts?.force && (draftDirty || frozenApply)) {
        return;
      }
      const gen = ++refreshGen.current;
      refreshAbort.current?.abort();
      const ac = new AbortController();
      refreshAbort.current = ac;
      const requestedTarget = targetKey(mode, recordId);
      setError(null);
      const qs = new URLSearchParams({ path: editPath });
      if (mode === 'catalog_record') {
        qs.set('record_id', recordId);
      }
      try {
        const res = await fetch(`/api/catalog/edit/state?${qs.toString()}`, { signal: ac.signal });
        const text = await res.text();
        let body: Record<string, unknown>;
        try {
          body = text ? (JSON.parse(text) as Record<string, unknown>) : {};
        } catch {
          if (gen !== refreshGen.current || requestedTarget !== activeTarget.current) return;
          setError('Unreadable state JSON');
          const lkg = lastGoodRef.current;
          if (lkg) {
            setOutcome(`LKG ${lkg.path} rev ${lkg.revision} · ${lkg.sha256.slice(0, 12)}…`);
          }
          return;
        }
        if (gen !== refreshGen.current || requestedTarget !== activeTarget.current) {
          return;
        }
        if (!res.ok) {
          setError(String(body.error ?? 'state failed'));
          const lkg = lastGoodRef.current;
          if (lkg) {
            setOutcome(`Stale/LKG ${lkg.path} rev ${lkg.revision} · ${lkg.sha256.slice(0, 12)}…`);
          }
          return;
        }
        const doc = (body.document ?? {}) as Record<string, unknown>;
        const next: EditState = {
          path: String(body.path ?? editPath),
          record_id:
            mode === 'catalog_record'
              ? body.record_id
                ? String(body.record_id)
                : recordId
              : undefined,
          sha256: String(body.sha256 ?? ''),
          revision: Number(body.revision ?? 0),
          document: doc,
        };
        if (next.path !== editPath) {
          return;
        }
        setState(next);
        setLastGood({ revision: next.revision, sha256: next.sha256, path: next.path });
        setPreview(null);
        setFrozenApply(null);
        setDraftDirty(false);
        if (!opts?.preserveOutcome) {
          setOutcome(null);
        }
      } catch (e) {
        if ((e as Error).name === 'AbortError') return;
        if (gen !== refreshGen.current) return;
        setError(String(e));
      }
    },
    [draftDirty, editPath, frozenApply, mode, recordId],
  );

  useEffect(() => {
    refreshGen.current += 1;
    refreshAbort.current?.abort();
    previewAbort.current?.abort();
    setPreview(null);
    setFrozenApply(null);
    void refresh({ force: true });
  }, [editPath, mode, recordId, refresh]);

  useEffect(() => {
    let cancelled = false;
    async function pollSync() {
      if (pollInflight.current) return;
      pollInflight.current = true;
      pollAbort.current?.abort();
      const ac = new AbortController();
      pollAbort.current = ac;
      try {
        const res = await fetch('/api/sync/status', { signal: ac.signal });
        const text = await res.text();
        let payload: SyncStatus;
        try {
          payload = text ? (JSON.parse(text) as SyncStatus) : {};
        } catch {
          if (!cancelled) setSyncError('sync status JSON unreadable');
          return;
        }
        if (cancelled) return;
        setSyncError(null);
        setSync(payload);
        const fp = (payload.files ?? [])
          .map((f) => `${f.path}:${f.sha256 ?? 'none'}:${f.readable ?? '?'}`)
          .sort()
          .join('|');
        if (lastSyncFp.current && lastSyncFp.current !== fp && !draftDirty && !frozenApply) {
          void refresh();
        }
        lastSyncFp.current = fp;
      } catch (e) {
        if ((e as Error).name !== 'AbortError' && !cancelled) {
          setSyncError(String(e));
        }
      } finally {
        pollInflight.current = false;
      }
    }
    void pollSync();
    const timer = setInterval(() => void pollSync(), 3000);
    return () => {
      cancelled = true;
      clearInterval(timer);
      pollAbort.current?.abort();
    };
  }, [draftDirty, frozenApply, refresh]);

  async function runPreview() {
    if (!state || !localToken) return;
    const gen = ++previewGen.current;
    previewAbort.current?.abort();
    const ac = new AbortController();
    previewAbort.current = ac;
    setError(null);
    const purposeValue = purposeRef.current?.value ?? '';
    const policyValue = policyRef.current?.value ?? '';
    const tk = targetKey(mode, recordId);
    const nextDoc =
      mode === 'catalog_record'
        ? { ...state.document, purpose: purposeValue }
        : { ...state.document, update_policy: policyValue };
    const req: FrozenApplyRequest = {
      path: state.path,
      record_id: state.record_id,
      expected_sha256: state.sha256,
      next_revision: state.revision + 1,
      document: nextDoc,
      preview_token: '',
      projected_purpose: mode === 'catalog_record' ? purposeValue : undefined,
      projected_update_policy: mode === 'maintained_doc' ? policyValue : undefined,
      target_key: tk,
    };
    try {
      const res = await fetch('/api/catalog/edit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Local-Token': localToken },
        body: JSON.stringify({
          path: req.path,
          record_id: req.record_id,
          expected_sha256: req.expected_sha256,
          next_revision: req.next_revision,
          document: req.document,
          preview_only: true,
        }),
        signal: ac.signal,
      });
      const text = await res.text();
      let body: Record<string, unknown>;
      try {
        body = text ? (JSON.parse(text) as Record<string, unknown>) : {};
      } catch {
        if (gen !== previewGen.current) return;
        setError('Preview response unreadable');
        setFrozenApply(null);
        return;
      }
      if (gen !== previewGen.current || tk !== activeTarget.current) {
        return;
      }
      if (!res.ok) {
        setError(String(body.error ?? 'preview failed'));
        setFrozenApply(null);
        return;
      }
      req.preview_token = previewToken(body, req);
      setPreview(body);
      setFrozenApply(req);
      setDraftDirty(false);
    } catch (e) {
      if ((e as Error).name === 'AbortError') return;
      if (gen !== previewGen.current) return;
      setError(String(e));
    }
  }

  async function runApply() {
    if (!state || !localToken || !frozenApply) {
      setError('Preview required before apply');
      return;
    }
    if (draftDirty) {
      setError('Draft changed since preview; preview again');
      return;
    }
    if (frozenApply.target_key !== targetKey(mode, recordId)) {
      setError('Frozen preview target mismatch; preview again');
      return;
    }
    setError(null);
    const res = await fetchJsonWithDeadline('/api/catalog/edit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Local-Token': localToken },
      body: JSON.stringify({
        path: frozenApply.path,
        record_id: frozenApply.record_id,
        expected_sha256: frozenApply.expected_sha256,
        next_revision: frozenApply.next_revision,
        document: frozenApply.document,
        operation_id: `maintained-ui-${frozenApply.preview_token}-${Date.now()}`,
        frozen_preview_token: frozenApply.preview_token,
      }),
    });
    const body = res.json as Record<string, unknown>;
    if (!res.ok) {
      setError(String(body.error ?? 'apply failed'));
      return;
    }
    setOutcome(
      `Applied revision ${String(body.revision)} · record ${String(frozenApply.record_id ?? frozenApply.path)} · after ${String(body.after_sha256).slice(0, 12)}…`,
    );
    setFrozenApply(null);
    setDraftDirty(false);
    await refresh({ force: true, preserveOutcome: true });
  }

  return (
    <div className="space-y-4 p-4" data-testid="maintained-edit-panel">
      <div>
        <h2 className="font-medium">Maintained catalog edit</h2>
        <p className="text-muted-foreground text-xs">
          Canonical JSON records consumed by map/list/detail; preview freezes the validated apply request.
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button
          size="sm"
          variant={mode === 'catalog_record' ? 'default' : 'outline'}
          onClick={() => setMode('catalog_record')}
          data-testid="maintained-edit-mode-catalog"
        >
          Catalog record
        </Button>
        <Button
          size="sm"
          variant={mode === 'maintained_doc' ? 'default' : 'outline'}
          onClick={() => setMode('maintained_doc')}
          data-testid="maintained-edit-mode-doc"
        >
          Maintained document
        </Button>
      </div>
      {mode === 'catalog_record' ? (
        <div className="space-y-2">
          <label className="text-xs font-medium">Component record ID</label>
          <Input
            value={recordId}
            onChange={(e) => setRecordId(e.target.value)}
            data-testid="maintained-edit-record-id"
          />
        </div>
      ) : null}
      {state ? (
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs" data-testid="maintained-edit-state">
          <dt className="text-muted-foreground">Observation revision</dt>
          <dd data-testid="maintained-edit-revision">{state.revision}</dd>
          <dt className="text-muted-foreground">Editable path</dt>
          <dd data-testid="maintained-edit-path">{state.path}</dd>
          <dt className="text-muted-foreground">Content SHA256</dt>
          <dd className="break-all" data-testid="maintained-edit-sha256">
            {state.sha256}
          </dd>
          {state.record_id ? (
            <>
              <dt className="text-muted-foreground">Record ID</dt>
              <dd data-testid="maintained-edit-record-id-display">{state.record_id}</dd>
            </>
          ) : null}
        </dl>
      ) : null}
      {sync ? (
        <p className="text-muted-foreground text-xs" data-testid="maintained-edit-sync-line">
          Sync last {sync.last_observation ?? 'unknown'}
          {lastGood ? ` · last success rev ${lastGood.revision}` : null}
        </p>
      ) : null}
      {syncError ? (
        <p className="text-sm text-red-700 dark:text-red-300" data-testid="maintained-edit-sync-error">
          {syncError}
        </p>
      ) : null}
      {frozenApply ? (
        <p className="text-xs text-amber-800 dark:text-amber-200" data-testid="maintained-edit-frozen-preview">
          Frozen preview · token {frozenApply.preview_token} · rev {frozenApply.next_revision}
        </p>
      ) : null}
      {draftDirty ? (
        <p className="text-xs text-amber-800 dark:text-amber-200" data-testid="maintained-edit-draft-dirty">
          Draft changed since preview — preview again before apply
        </p>
      ) : null}
      <div className="space-y-2">
        {mode === 'catalog_record' ? (
          <>
            <label className="text-xs font-medium">Purpose (factual field)</label>
            <Textarea
              key={`purpose-${state?.sha256 ?? 'none'}-${state?.revision ?? 0}`}
              ref={purposeRef}
              defaultValue={String(state?.document?.purpose ?? '')}
              data-testid="maintained-edit-purpose"
              onInput={() => {
                setDraftDirty(true);
              }}
            />
          </>
        ) : (
          <>
            <label className="text-xs font-medium">Update policy</label>
            <Textarea
              key={`policy-${state?.sha256 ?? 'none'}-${state?.revision ?? 0}`}
              ref={policyRef}
              defaultValue={String(state?.document?.update_policy ?? '')}
              data-testid="maintained-edit-update-policy"
              onInput={() => {
                setDraftDirty(true);
              }}
            />
          </>
        )}
      </div>
      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant="outline" onClick={() => void refresh({ force: true })} data-testid="maintained-edit-reload">
          Reload state
        </Button>
        <Button size="sm" onClick={() => void runPreview()} data-testid="maintained-edit-preview">
          Preview diff
        </Button>
        <Button size="sm" variant="default" onClick={() => void runApply()} data-testid="maintained-edit-apply">
          Apply frozen preview
        </Button>
      </div>
      {preview ? (
        <pre className="bg-muted max-h-48 overflow-auto rounded p-2 text-xs" data-testid="maintained-edit-diff">
          {JSON.stringify(preview.diff ?? preview, null, 2)}
        </pre>
      ) : null}
      {frozenApply?.projected_purpose ? (
        <span className="hidden" data-testid="maintained-edit-frozen-purpose">
          {frozenApply.projected_purpose}
        </span>
      ) : null}
      {frozenApply?.projected_update_policy ? (
        <span className="hidden" data-testid="maintained-edit-frozen-policy">
          {frozenApply.projected_update_policy}
        </span>
      ) : null}
      {outcome ? (
        <p className="text-sm text-green-800 dark:text-green-200" data-testid="maintained-edit-outcome">
          {outcome}
        </p>
      ) : null}
      {error ? (
        <p className="text-sm text-red-700 dark:text-red-300" data-testid="maintained-edit-error">
          {error}
        </p>
      ) : null}
    </div>
  );
}
