'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Separator } from '@/components/ui/separator';
import { Textarea } from '@/components/ui/textarea';

type WorkflowTemplate = {
  name: string;
  document: {
    kind: string;
    instructions?: string[];
    required_inputs?: string[];
    job: {
      id: string;
      goal: string;
      scope: string[];
      constraints: string[];
      owner: string;
      acceptance: string[];
    };
    tasks: {
      id: string;
      goal: string;
      owner: string;
      deps: string[];
      acceptance: string[];
      next_action?: string;
    }[];
  };
};

type JobRow = { job_id: string; revision: number; goal: Record<string, unknown> };

type TaskState = {
  id: string;
  goal: string;
  owner: string;
  status: string;
  deps: string[];
  acceptance: string[];
  next_action?: string | null;
  evidence?: string[];
};

type RecoverPacket = {
  job_id: string;
  current_revision: number;
  synthetic_only?: boolean;
  goal: { goal?: string; owner?: string; scope?: string[] };
  tasks: Record<string, TaskState>;
  next_permitted_action?: { task_id: string; action: string; source?: string; actionable?: boolean } | null;
  superseded_next_permitted_action?: { task_id: string; action: string; source?: string; actionable?: boolean } | null;
  governing_next_action?: string;
  pending_dependencies?: Record<string, string[]>;
  active_corrections?: {
    id: string;
    reason?: string;
    active?: boolean;
    superseded_next_action?: string;
    preserved_attempts?: unknown[];
  }[];
  affected_outputs_needing_recheck?: { task_id: string; output?: string; reason?: string }[];
  blocked_corrected_tasks?: {
    task_id: string;
    correction_id?: string;
    reason?: string;
    action?: string;
    blockers?: string[];
  }[];
  reliability_recovery?: {
    governing_applied?: boolean;
    superseded_notes?: { note: string; superseded_by_correction?: string }[];
    correction_history?: { correction_id?: string; superseded_next_action?: string }[];
  };
};

const ACTION_LABELS: Record<string, string> = {
  create: 'Create job',
  add_task: 'Add task',
  update: 'Update task progress',
  verify: 'Independent verification',
  dependencies: 'Change dependencies',
  correct: 'Record correction',
  checkpoint: 'Checkpoint',
};

const STATUS_LABELS: Record<string, string> = {
  pending: 'Pending',
  in_progress: 'In progress',
  verified: 'Verified',
  needs_rechecking: 'Needs rechecking',
  blocked: 'Blocked',
};

function statusLabel(status: string) {
  return STATUS_LABELS[status] ?? status;
}

export function WorkflowPanel({ localToken }: { localToken: string }) {
  const [templates, setTemplates] = useState<WorkflowTemplate[]>([]);
  const [selectedKind, setSelectedKind] = useState('investigate');
  const [jobs, setJobs] = useState<JobRow[]>([]);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [recover, setRecover] = useState<RecoverPacket | null>(null);
  const [events, setEvents] = useState<unknown[]>([]);
  const [tab, setTab] = useState<'run' | 'history' | 'tasks'>('run');
  const [goal, setGoal] = useState('');
  const [owner, setOwner] = useState('alex');
  const [scope, setScope] = useState('local foundation catalog');
  const [verifier, setVerifier] = useState('reviewer-b');
  const [message, setMessage] = useState<string | null>(null);
  const [acceptanceChecks, setAcceptanceChecks] = useState<Record<string, Record<string, boolean>>>(
    {},
  );

  const template = useMemo(
    () => templates.find((item) => item.name === selectedKind),
    [templates, selectedKind],
  );

  const taskList = useMemo(() => {
    if (!recover?.tasks) {
      return [] as TaskState[];
    }
    return Object.values(recover.tasks);
  }, [recover]);

  const actionableNext =
    recover?.next_permitted_action?.actionable !== false ? recover?.next_permitted_action ?? null : null;
  const staleNext = recover?.superseded_next_permitted_action ?? null;
  const blockedCorrection = (
    recover as RecoverPacket & {
      correction_governed_task?: { task_id: string; action: string; blockers?: string[] };
    }
  )?.correction_governed_task;

  const refreshJobs = useCallback(async () => {
    const payload = await fetch('/api/workflow').then((r) => r.json());
    const rows = (payload.jobs ?? []) as JobRow[];
    setJobs(rows);
    if (!activeJobId && rows[0]) {
      setActiveJobId(rows[0].job_id);
    }
  }, [activeJobId]);

  const refreshJobDetail = useCallback(async (jobId: string) => {
    const [packet, history] = await Promise.all([
      fetch(`/api/workflow/recover/${jobId}`).then((r) => r.json()),
      fetch(`/api/workflow/events/${jobId}`).then((r) => r.json()),
    ]);
    setRecover(packet as RecoverPacket);
    setEvents(history.events ?? []);
  }, []);

  useEffect(() => {
    fetch('/api/workflow/templates')
      .then((r) => r.json())
      .then((payload) => setTemplates(payload.templates ?? []));
    void refreshJobs();
  }, [refreshJobs]);

  useEffect(() => {
    if (activeJobId) {
      void refreshJobDetail(activeJobId);
    }
  }, [activeJobId, refreshJobDetail]);

  async function mutate(body: Record<string, unknown>): Promise<{ revision: number } | null> {
    if (!localToken) {
      setMessage('Missing local mutation token');
      return null;
    }
    const jobId = typeof body.job_id === 'string' ? body.job_id : recover?.job_id;
    const envelope = {
      ...body,
      actor_owner: owner,
      ...(jobId ? { handoff_operation_id: `${jobId}-handoff` } : {}),
    };
    const response = await fetch('/api/workflow', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Local-Token': localToken },
      body: JSON.stringify(envelope),
    });
    const payload = await response.json();
    if (!response.ok || payload.error) {
      setMessage(String(payload.error ?? 'mutation failed'));
      return null;
    }
    setMessage(`Committed revision ${payload.revision} (${payload.operation_id})`);
    await refreshJobs();
    if (typeof body.job_id === 'string') {
      setActiveJobId(body.job_id);
      await refreshJobDetail(body.job_id);
    }
    return { revision: Number(payload.revision) };
  }

  function validateStartFields(): boolean {
    if (!goal.trim()) {
      setMessage('Goal is required');
      return false;
    }
    if (!owner.trim()) {
      setMessage('Owner is required');
      return false;
    }
    if (!scope.trim()) {
      setMessage('Scope is required');
      return false;
    }
    return true;
  }

  async function startFromTemplate() {
    if (!template || !validateStartFields()) {
      return;
    }
    const jobId = `${selectedKind}-${Date.now()}`;
    const created = await mutate({
      job_id: jobId,
      expected_revision: 0,
      operation_id: `${jobId}-create`,
      action: 'create',
      payload: {
        goal,
        scope: [scope],
        constraints: ['no external services', 'no dispatch'],
        owner,
        acceptance: template.document.job.acceptance.map((item) =>
          item.replace('REQUIRED', 'catalog snapshot loaded'),
        ),
        account_or_local_only: 'local-only',
      },
    });
    if (!created) {
      return;
    }
    let revision = created.revision;
    const taskIds: string[] = [];
    for (const [index, task] of template.document.tasks.entries()) {
      const taskId = `${jobId}-t${index}`;
      taskIds.push(taskId);
      const added = await mutate({
        job_id: jobId,
        expected_revision: revision,
        operation_id: `${jobId}-task-${index}`,
        action: 'add_task',
        payload: {
          id: taskId,
          goal: task.goal,
          owner,
          acceptance: task.acceptance.map((item) => item.replace('REQUIRED', 'bounded evidence attached')),
          deps: index === 0 ? [] : [taskIds[index - 1]],
          next_action: task.next_action ?? task.goal,
        },
      });
      if (!added) {
        return;
      }
      revision = added.revision;
    }
    setTab('tasks');
  }

  async function markInProgress(taskId: string) {
    if (!recover) {
      return;
    }
    await mutate({
      job_id: recover.job_id,
      expected_revision: recover.current_revision,
      operation_id: `${recover.job_id}-update-${taskId}-${Date.now()}`,
      action: 'update',
      payload: {
        task_id: taskId,
        status: 'in_progress',
        attempt: 'local explorer update',
      },
    });
  }

  async function verifyTask(task: TaskState) {
    if (!recover) {
      return;
    }
    if (!verifier.trim() || verifier === task.owner) {
      setMessage('Verifier must differ from task owner');
      return;
    }
    const checks = Object.fromEntries(
      task.acceptance.map((item) => [item, acceptanceChecks[task.id]?.[item] === true]),
    );
    if (!Object.values(checks).every(Boolean)) {
      setMessage('Mark every acceptance criterion before independent verification');
      return;
    }
    setMessage(
      'Independent verification requires gate-bound requirement_claims and proof_path evidence via local_service apply; configure claims before verify.',
    );
  }

  function toggleAcceptance(taskId: string, criterion: string, checked: boolean) {
    setAcceptanceChecks((prev) => ({
      ...prev,
      [taskId]: { ...(prev[taskId] ?? {}), [criterion]: checked },
    }));
  }

  async function addAdHocTask() {
    if (!recover || !goal.trim()) {
      setMessage('Select a job and enter a goal for the new task');
      return;
    }
    const taskId = `${recover.job_id}-adhoc-${Date.now()}`;
    await mutate({
      job_id: recover.job_id,
      expected_revision: recover.current_revision,
      operation_id: `${recover.job_id}-add-${taskId}`,
      action: 'add_task',
      payload: {
        id: taskId,
        goal,
        owner,
        acceptance: ['adhoc-check'],
        deps: [],
        next_action: goal,
      },
    });
  }

  return (
    <div className="space-y-4 overflow-auto p-4 text-sm">
      <div className="flex flex-wrap gap-2">
        {['investigate', 'build', 'repair'].map((kind) => (
          <Button
            key={kind}
            size="sm"
            variant={selectedKind === kind ? 'default' : 'outline'}
            onClick={() => setSelectedKind(kind)}
          >
            {kind}
          </Button>
        ))}
        {(['run', 'tasks', 'history'] as const).map((name) => (
          <Button key={name} size="sm" variant={tab === name ? 'default' : 'outline'} onClick={() => setTab(name)}>
            {name === 'run' ? 'Guided start' : name === 'tasks' ? 'Tasks & actions' : 'History'}
          </Button>
        ))}
      </div>

      <div className="flex flex-wrap gap-2">
        {jobs.map((job) => (
          <Button
            key={job.job_id}
            size="sm"
            variant={job.job_id === activeJobId ? 'default' : 'outline'}
            onClick={() => setActiveJobId(job.job_id)}
          >
            {job.job_id} (r{job.revision})
          </Button>
        ))}
      </div>

      {tab === 'run' ? (
        <>
          <div className="space-y-2">
            <label className="font-medium">Goal</label>
            <Textarea value={goal} onChange={(e) => setGoal(e.target.value)} rows={2} />
            <label className="font-medium">Owner</label>
            <Input value={owner} onChange={(e) => setOwner(e.target.value)} />
            <label className="font-medium">Scope</label>
            <Input value={scope} onChange={(e) => setScope(e.target.value)} />
          </div>
          {template && (
            <div className="bg-muted space-y-2 rounded p-3 text-xs">
              <div className="font-medium">Guided template: {template.document.kind}</div>
              {template.document.instructions && (
                <ul className="list-disc pl-5">
                  {template.document.instructions.map((line) => (
                    <li key={line}>{line}</li>
                  ))}
                </ul>
              )}
              <div className="font-medium">Steps ({template.document.tasks.length})</div>
              <ol className="list-decimal pl-5">
                {template.document.tasks.map((task) => (
                  <li key={task.id}>{task.goal}</li>
                ))}
              </ol>
            </div>
          )}
          <Button onClick={() => void startFromTemplate()}>Start guided job</Button>
        </>
      ) : null}

      {tab === 'tasks' ? (
        <>
          {recover ? (
            <div className="space-y-3 rounded border p-3">
              <div className="font-medium">Recover packet (human-readable)</div>
              <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-xs">
                <dt className="text-muted-foreground">Job</dt>
                <dd>{recover.job_id}</dd>
                <dt className="text-muted-foreground">Revision</dt>
                <dd>{recover.current_revision}</dd>
                <dt className="text-muted-foreground">Goal</dt>
                <dd>{recover.goal?.goal ?? '—'}</dd>
                <dt className="text-muted-foreground">Owner</dt>
                <dd>{recover.goal?.owner ?? '—'}</dd>
                <dt className="text-muted-foreground">Engine mode</dt>
                <dd>{recover.synthetic_only ? 'Synthetic reference engine' : 'Local reference engine'}</dd>
                {actionableNext ? (
                  <>
                    <dt className="text-muted-foreground">Actionable next</dt>
                    <dd data-testid="workflow-actionable-next">
                      {actionableNext.action} on {actionableNext.task_id}
                      {actionableNext.source ? ` (${actionableNext.source})` : ''}
                    </dd>
                  </>
                ) : null}
                {staleNext && staleNext.actionable === false ? (
                  <>
                    <dt className="text-muted-foreground">Superseded (history only)</dt>
                    <dd className="text-muted-foreground line-through" data-testid="workflow-stale-next">
                      {staleNext.action} on {staleNext.task_id}
                    </dd>
                  </>
                ) : null}
              </dl>
              {recover.active_corrections && recover.active_corrections.length > 0 && (
                <div className="text-amber-800 dark:text-amber-200 text-xs">
                  Active corrections:{' '}
                  {recover.active_corrections.map((item) => item.reason ?? item.id).join('; ')}
                </div>
              )}
              {recover.reliability_recovery?.correction_history &&
                recover.reliability_recovery.correction_history.length > 0 && (
                  <div className="text-muted-foreground text-xs" data-testid="workflow-correction-history">
                    Prior decisions retained:{' '}
                    {recover.reliability_recovery.correction_history
                      .map((row) => row.superseded_next_action || row.correction_id)
                      .filter(Boolean)
                      .join(' · ')}
                  </div>
                )}
              {(recover.affected_outputs_needing_recheck?.length ?? 0) > 0 && (
                <div className="text-xs" data-testid="workflow-affected-recheck">
                  <div>Affected outputs needing recheck: {recover.affected_outputs_needing_recheck?.length}</div>
                  {recover.affected_outputs_needing_recheck?.map((row) => (
                    <div key={`${row.task_id}-${row.output ?? row.reason}`} data-testid="workflow-affected-output-record">
                      {row.task_id}: {row.output ?? row.reason ?? '—'}
                    </div>
                  ))}
                </div>
              )}
              {(recover.blocked_corrected_tasks?.length ?? 0) > 0 ? (
                <div className="text-xs text-amber-800 dark:text-amber-200" data-testid="workflow-correction-blocked">
                  {recover.blocked_corrected_tasks?.map((row) => (
                    <div key={row.correction_id ?? row.task_id}>
                      Corrected task {row.task_id} blocked ({(row.blockers ?? []).join(', ')}):{' '}
                      {row.reason ?? row.action}
                      {row.correction_id ? ` [${row.correction_id}]` : ''}
                    </div>
                  ))}
                </div>
              ) : blockedCorrection && blockedCorrection.blockers && blockedCorrection.blockers.length > 0 ? (
                <div className="text-xs text-amber-800 dark:text-amber-200" data-testid="workflow-correction-blocked">
                  Corrected task {blockedCorrection.task_id} blocked ({blockedCorrection.blockers.join(', ')}):{' '}
                  {blockedCorrection.action}
                </div>
              ) : null}
            </div>
          ) : null}

          <div className="space-y-2">
            <div className="flex flex-wrap items-end gap-2">
              <div className="min-w-[180px] flex-1">
                <label className="font-medium">Independent verifier</label>
                <Input value={verifier} onChange={(e) => setVerifier(e.target.value)} />
              </div>
              <Button size="sm" variant="outline" onClick={() => void addAdHocTask()}>
                Add task
              </Button>
            </div>
            <ul className="space-y-2">
              {taskList.map((task) => (
                <li key={task.id} className="rounded border p-3">
                  <div className="font-medium">{task.goal}</div>
                  <div className="text-muted-foreground text-xs">
                    {task.id} · {statusLabel(task.status)} · owner {task.owner}
                  </div>
                  {task.next_action && (
                    <div className="text-xs">Next: {task.next_action}</div>
                  )}
                  {task.acceptance.length > 0 && (
                    <ul className="mt-2 space-y-1 text-xs">
                      {task.acceptance.map((criterion) => (
                        <li key={criterion} className="flex items-start gap-2">
                          <input
                            type="checkbox"
                            checked={acceptanceChecks[task.id]?.[criterion] === true}
                            onChange={(e) => toggleAcceptance(task.id, criterion, e.target.checked)}
                          />
                          <span>{criterion}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                  <div className="mt-2 flex flex-wrap gap-2">
                    <Button size="sm" variant="outline" onClick={() => void markInProgress(task.id)}>
                      Mark in progress
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => void verifyTask(task)}>
                      Verify (revision-aware)
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </>
      ) : null}

      {tab === 'history' ? (
        <div>
          <div className="font-medium">Event history</div>
          <ul className="mt-2 space-y-2">
            {events.map((event) => {
              const row = event as {
                sequence: number;
                revision: number;
                request: { action: string; operation_id: string };
              };
              return (
                <li key={row.sequence} className="rounded border px-2 py-1 text-xs">
                  #{row.sequence} revision {row.revision} · {ACTION_LABELS[row.request.action] ?? row.request.action}{' '}
                  · {row.request.operation_id}
                </li>
              );
            })}
          </ul>
          {recover && (
            <details className="mt-3">
              <summary className="cursor-pointer text-xs">Raw recover packet</summary>
              <pre className="bg-muted mt-2 max-h-48 overflow-auto rounded p-2 text-xs">
                {JSON.stringify(recover, null, 2)}
              </pre>
            </details>
          )}
        </div>
      ) : null}

      {message && <p className="text-muted-foreground text-xs">{message}</p>}
      <Separator />
      <p className="text-muted-foreground text-xs">
        Mutations use expected_revision from the latest recover packet. Verification requires a verifier distinct from
        the task owner and passing acceptance checks.
      </p>
    </div>
  );
}
