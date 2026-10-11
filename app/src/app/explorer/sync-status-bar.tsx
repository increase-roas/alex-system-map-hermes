'use client';

import { useEffect, useMemo, useState } from 'react';

type SyncFile = {
  path: string;
  sha256?: string | null;
  readable?: number | boolean;
  error?: string | null;
  observed_at?: string;
};

type SyncStatus = {
  last_observation?: string;
  unreadable_count?: number;
  files?: SyncFile[];
};

function fingerprint(files: SyncFile[]): string | null {
  const hashes = files
    .filter((file) => file.sha256)
    .map((file) => file.sha256 as string)
    .sort();
  if (!hashes.length) {
    return null;
  }
  let acc = 0;
  for (const hash of hashes) {
    for (let i = 0; i < hash.length; i += 2) {
      acc = (acc + Number.parseInt(hash.slice(i, i + 2), 16)) % 0xffff_ffff;
    }
  }
  return acc.toString(16).padStart(8, '0');
}

export function SyncStatusBar() {
  const [status, setStatus] = useState<SyncStatus | null>(null);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    async function load() {
      const payload = await fetch('/api/sync/status').then((r) => r.json());
      setStatus(payload);
    }
    void load();
    const timer = setInterval(() => void load(), 15000);
    return () => clearInterval(timer);
  }, []);

  const staleFiles = useMemo(() => {
    if (!status?.files) {
      return [] as SyncFile[];
    }
    return status.files.filter(
      (file) => file.readable === 0 || file.readable === false || Boolean(file.error),
    );
  }, [status]);

  const catalogHash = useMemo(
    () => (status?.files ? fingerprint(status.files) : null),
    [status],
  );

  if (!status) {
    return null;
  }

  return (
    <div className="text-muted-foreground border-b px-4 py-1.5 text-xs">
      <button type="button" className="hover:text-foreground text-left" onClick={() => setExpanded((v) => !v)}>
        Catalog sync: last observation {status.last_observation ?? 'unknown'}
        {catalogHash ? ` · fingerprint ${catalogHash}` : null}
        {staleFiles.length ? (
          <span className="text-amber-700 dark:text-amber-300">
            {' '}
            · {staleFiles.length} stale/unreadable file(s)
          </span>
        ) : (
          <span> · allowlisted files readable</span>
        )}
        {expanded ? ' (hide)' : ' (details)'}
      </button>
      {expanded && status.files && (
        <ul className="mt-1 max-h-28 space-y-0.5 overflow-auto">
          {status.files.map((file) => (
            <li key={file.path} className={staleFiles.includes(file) ? 'text-amber-800 dark:text-amber-200' : ''}>
              {file.path}
              {file.sha256 ? ` · ${file.sha256.slice(0, 12)}…` : ''}
              {file.error ? ` · ${file.error}` : ''}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
