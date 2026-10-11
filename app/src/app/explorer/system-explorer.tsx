'use client';

import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  useEdgesState,
  useNodesState,
  type Edge,
  type Node,
} from '@xyflow/react';
import ELK from 'elkjs/lib/elk.bundled.js';
import { Moon, Search, Sun } from 'lucide-react';
import { useTheme } from 'next-themes';
import { useEffect, useMemo, useState } from 'react';

/** Visual-only spotlight: counts Director / Conductor records under each canvas node. Never changes facts. */
const SPOTLIGHT = { director: /director/i, conductor: /conductor/i };
function withSpotlight(bundle: CatalogBundle, nodes: Node[]): Node[] {
  const hit = new Map<string, { d: boolean; c: boolean }>();
  for (const comp of bundle.data.components) {
    const text = `${comp.name ?? ''} ${(comp.aliases ?? []).join(' ')}`;
    const d = SPOTLIGHT.director.test(text);
    const c = SPOTLIGHT.conductor.test(text);
    if (d || c) hit.set(comp.id, { d, c });
  }
  const parentOf = new Map(bundle.overview_memberships.map((m) => [m.component_id, m]));
  const tally = new Map<string, { director: number; conductor: number }>();
  const bump = (key: string, h: { d: boolean; c: boolean }) => {
    const t = tally.get(key) ?? { director: 0, conductor: 0 };
    if (h.d) t.director += 1;
    if (h.c) t.conductor += 1;
    tally.set(key, t);
  };
  for (const [id, h] of hit) {
    const comp = bundle.data.components.find((x) => x.id === id);
    const m = parentOf.get(id);
    const layer = m?.layer_id ?? comp?.layer_id;
    if (layer) bump(layer, h);
    if (m?.parent_id) bump(`group:${m.parent_id}`, h);
    bump(`group:${id}`, h);
    bump(id, h);
  }
  return nodes.map((n) => {
    const t = tally.get(n.id);
    return t ? { ...n, data: { ...n.data, spotlight: t } } : n;
  });
}

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Separator } from '@/components/ui/separator';
import {
  buildOverviewGraph,
  buildSubsystemGraph,
  searchComponents,
  type ExplorerView,
} from '@/lib/graph/build-graph';
import type { CatalogBundle, CatalogComponent, CatalogIssue, CatalogSource } from '@/lib/types/catalog';

import { explorerNodeTypes } from './nodes';
import { SyncStatusBar } from './sync-status-bar';
import { ReliabilityPanel } from './reliability-panel';
import { TracingPanel } from './tracing-panel';
import { LiveSetupPanel } from './live-setup-panel';
import { OrgMapPanel } from './org-map-panel';
import { MaintainedEditPanel } from './maintained-edit-panel';
import { WorkflowPanel } from './workflow-panel';

const elk = new ELK();

async function layoutTopDown(nodes: Node[], edges: { id: string; source: string; target: string }[]) {
  if (!nodes.length) {
    return nodes;
  }
  const graph = {
    id: 'root',
    layoutOptions: {
      'elk.algorithm': 'layered',
      'elk.direction': 'DOWN',
      'elk.spacing.nodeNode': '80',
    },
    children: nodes.map((node) => ({
      id: node.id,
      width: 220,
      height: 90,
    })),
    edges: edges.map((edge) => ({
      id: edge.id,
      sources: [edge.source],
      targets: [edge.target],
    })),
  };
  const layout = await elk.layout(graph);
  const positions = new Map(layout.children?.map((child) => [child.id, child]));
  return nodes.map((node) => {
    const placed = positions.get(node.id);
    if (!placed || placed.x === undefined || placed.y === undefined) {
      return node;
    }
    return { ...node, position: { x: placed.x, y: placed.y } };
  });
}

const VIEW_LABEL: Partial<Record<ExplorerView, string>> = {
  map: 'Map', overview: 'Full Catalog', subsystem: 'Subsystem', files: 'Files', problems: 'Problems', workflows: 'Workflows',
  tracing: 'Tracing', reliability: 'Reliability', maintained: 'Maintained', live: 'Live',
};

export function SystemExplorer() {
  const { theme, setTheme, resolvedTheme } = useTheme();
  const [bundle, setBundle] = useState<CatalogBundle | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [view, setView] = useState<ExplorerView>('map');
  const [selectedLayer, setSelectedLayer] = useState<string>('layer_01');
  const [expandedGroupId, setExpandedGroupId] = useState<string | null>(null);
  const [selectedComponent, setSelectedComponent] = useState<CatalogComponent | null>(null);
  const [selectedSource, setSelectedSource] = useState<CatalogSource | null>(null);
  const [sourcePreview, setSourcePreview] = useState<Record<string, unknown> | null>(null);
  const [search, setSearch] = useState('');
  const [spotOnly, setSpotOnly] = useState(false);
  const [localToken, setLocalToken] = useState('');
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  useEffect(() => {
    async function load() {
      try {
        const [health, catalog] = await Promise.all([
          fetch('/api/health').then((r) => r.json()),
          fetch('/api/catalog').then((r) => r.json()),
        ]);
        setLocalToken(String(health.token ?? ''));
        setBundle(catalog as CatalogBundle);
      } catch (error) {
        setLoadError(error instanceof Error ? error.message : 'load failed');
      }
    }
    void load();
  }, []);

  useEffect(() => {
    async function renderGraph() {
      if (
        !bundle ||
        view === 'problems' ||
        view === 'workflows' ||
        view === 'files' ||
        view === 'tracing' ||
        view === 'maintained' ||
        view === 'live' ||
        view === 'map'
      ) {
        return;
      }
      const graph =
        view === 'overview'
          ? buildOverviewGraph(bundle)
          : buildSubsystemGraph(bundle, selectedLayer, expandedGroupId);
      const layouted =
        view === 'overview' ? graph.nodes : await layoutTopDown(graph.nodes, graph.edges);
      const lit = withSpotlight(bundle, layouted);
      if (spotOnly) {
        const kept = lit.filter((n) => (n.data as { spotlight?: unknown }).spotlight);
        const ids = new Set(kept.map((n) => n.id));
        const keptEdges = graph.edges.filter((e) => ids.has(e.source) && ids.has(e.target));
        // Compact grid: one row per layer, layer card first, its lit groups beside it.
        const order: string[] = [];
        const rows = new Map<string, Node[]>();
        for (const n of [...kept].sort((a, b) => a.position.y - b.position.y || a.position.x - b.position.x)) {
          const key = String((n.data as { layerId?: string }).layerId ?? n.id);
          if (!rows.has(key)) {
            rows.set(key, []);
            order.push(key);
          }
          rows.get(key)!.push(n);
        }
        const placed: Node[] = [];
        order.forEach((key, r) => {
          const row = rows.get(key)!.sort((a, b) => (a.type === 'layerNode' ? -1 : b.type === 'layerNode' ? 1 : 0));
          row.forEach((n, i) => placed.push({ ...n, position: { x: 40 + i * 290, y: r * 200 } }));
        });
        setNodes(view === 'overview' ? placed : await layoutTopDown(kept, keptEdges));
        setEdges(keptEdges);
      } else {
        setNodes(lit);
        setEdges(graph.edges);
      }
    }
    void renderGraph();
  }, [bundle, view, selectedLayer, expandedGroupId, spotOnly, setNodes, setEdges]);

  const searchResults = useMemo(
    () => (bundle ? searchComponents(bundle, search) : []),
    [bundle, search],
  );

  const filteredIssues = useMemo(() => {
    if (!bundle) {
      return [] as CatalogIssue[];
    }
    const q = search.trim().toLowerCase();
    if (!q) {
      return bundle.data.issues.slice(0, 200);
    }
    return bundle.data.issues.filter(
      (issue) =>
        (issue.summary ?? '').toLowerCase().includes(q) ||
        (issue.id ?? '').toLowerCase().includes(q) ||
        (issue.category ?? '').toLowerCase().includes(q),
    );
  }, [bundle, search]);

  const filteredSources = useMemo(() => {
    if (!bundle) {
      return [] as CatalogSource[];
    }
    const q = search.trim().toLowerCase();
    const rows = bundle.data.sources;
    if (!q) {
      return rows.slice(0, 200);
    }
    return rows
      .filter(
        (source) =>
          source.id.toLowerCase().includes(q) ||
          (source.relative_path ?? '').toLowerCase().includes(q) ||
          (source.original_path ?? '').toLowerCase().includes(q),
      )
      .slice(0, 200);
  }, [bundle, search]);

  async function openSource(source: CatalogSource) {
    setSelectedSource(source);
    const payload = await fetch(`/api/sources/${source.id}`).then((r) => r.json());
    setSourcePreview(payload);
  }

  async function persistLayout() {
    if (!localToken) {
      return;
    }
    await fetch('/api/presentation', {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'X-Local-Token': localToken,
      },
      body: JSON.stringify({
        scope: 'explorer',
        key: 'node-positions',
        value: nodes.map((node) => ({ id: node.id, position: node.position })),
      }),
    });
  }

  if (loadError) {
    return (
      <main className="p-6">
        <h1 className="text-lg font-medium">System map failed to load</h1>
        <p className="text-muted-foreground mt-2">{loadError}</p>
      </main>
    );
  }

  if (!bundle) {
    return <main className="text-muted-foreground p-6">Loading foundation catalog…</main>;
  }

  return (
    <div className="flex h-screen flex-col">
      <header className="flex flex-wrap items-center gap-3 border-b px-4 py-3">
        <div>
          <h1 className="text-base font-medium">Alex system map</h1>
          <p className="text-muted-foreground text-xs" data-testid="catalog-stats">
            Snapshot {bundle.loaded_at} · {bundle.data.components.length} components ·{' '}
            {bundle.data.relationships.length} relationships ·{' '}
            {bundle.completeness?.complete ? 'catalog complete' : 'catalog incomplete'}
          </p>
        </div>
        <div className="flex flex-1 flex-wrap items-center gap-2">
          <div className="relative min-w-[220px] flex-1">
            <Search className="text-muted-foreground absolute top-2.5 left-2 size-4" />
            <Input
              className="pl-8"
              placeholder="Search IDs, names, files, issues"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>
          {(
            [
              'map',
              'overview',
              'subsystem',
              'files',
              'problems',
              'workflows',
              'tracing',
              'reliability',
              'maintained',
              'live',
            ] as ExplorerView[]
          ).map(
            (item) => (
              <Button
                key={item}
                size="sm"
                variant={view === item ? 'default' : 'outline'}
                onClick={() => setView(item)}
              >
                {VIEW_LABEL[item] ?? item}
              </Button>
            ),
          )}
          <Button
            size="sm"
            variant="outline"
            onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
            aria-label="Toggle theme"
          >
            {theme === 'dark' ? <Sun className="size-4" /> : <Moon className="size-4" />}
          </Button>
          <Button
            size="sm"
            variant={spotOnly ? 'default' : 'outline'}
            aria-pressed={spotOnly}
            onClick={() => setSpotOnly((v) => !v)}
            title="Show only cards that contain Director or Conductor records (visual filter only)"
          >
            {spotOnly ? '★ Director & Conductor only (on)' : '★ Director & Conductor only'}
          </Button>
        </div>
      </header>

      <SyncStatusBar />

      {bundle.load_gaps.length > 0 && (
        <div className="border-b bg-amber-50 px-4 py-2 text-sm text-amber-950 dark:bg-amber-950/30 dark:text-amber-100">
          Catalog load gaps (local files unavailable until downloaded):{' '}
          {bundle.load_gaps.map((gap) => gap.file).join(', ')}
        </div>
      )}

      {/* The map and live views have their own detail panels, so the side column is dropped there. */}
      <div className={`grid min-h-0 flex-1 grid-cols-1 ${view === 'map' || view === 'live' ? '' : 'lg:grid-cols-[1fr_360px]'}`}>
        <section className={`min-h-0 border-b lg:h-auto lg:border-b-0 ${view === 'map' || view === 'live' ? 'h-[85vh]' : 'h-[72vh] lg:border-r'}`}>
          {view === 'files' ? (
            <div className="h-full overflow-auto p-4">
              <h2 className="mb-3 font-medium">Files</h2>
              <ul className="space-y-2">
                {filteredSources.map((source) => (
                  <li key={source.id}>
                    <button
                      type="button"
                      className="hover:bg-muted w-full rounded border px-3 py-2 text-left"
                      onClick={() => void openSource(source)}
                    >
                      <div className="font-medium">{source.relative_path ?? source.id}</div>
                      <div className="text-muted-foreground text-xs">{source.kind}</div>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ) : view === 'problems' ? (
            <div className="h-full overflow-auto p-4">
              <h2 className="mb-3 font-medium">Problems</h2>
              <ul className="space-y-2">
                {filteredIssues.map((issue) => (
                  <li key={issue.id}>
                    <button
                      type="button"
                      className="hover:bg-muted w-full rounded border px-3 py-2 text-left"
                      onClick={() => {
                        const subject = bundle.data.components.find(
                          (item) => item.id === issue.subject_id,
                        );
                        if (subject) {
                          setSelectedComponent(subject);
                          setView('subsystem');
                          setSelectedLayer(subject.layer_id);
                        }
                      }}
                    >
                      <div className="font-medium">{issue.summary}</div>
                      <div className="text-muted-foreground text-xs">
                        {issue.severity} · {issue.status} · {issue.category}
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ) : view === 'workflows' ? (
            <WorkflowPanel localToken={localToken} />
          ) : view === 'tracing' ? (
            <TracingPanel />
          ) : view === 'reliability' ? (
            <ReliabilityPanel />
          ) : view === 'map' ? (
            <OrgMapPanel />
          ) : view === 'live' ? (
            <LiveSetupPanel />
          ) : view === 'maintained' ? (
            <MaintainedEditPanel localToken={localToken} />
          ) : (
            <div className="flex h-full min-h-0 flex-col">
              {view === 'subsystem' && (
                <div className="flex flex-wrap items-center gap-2 border-b p-3">
                  {bundle.data.layers.map((layer) => (
                    <Button
                      key={layer.id}
                      size="sm"
                      variant={selectedLayer === layer.id ? 'default' : 'outline'}
                      onClick={() => {
                        setSelectedLayer(layer.id);
                        setExpandedGroupId(null);
                      }}
                    >
                      {layer.name}
                    </Button>
                  ))}
                  {expandedGroupId ? (
                    <Button size="sm" variant="outline" onClick={() => setExpandedGroupId(null)}>
                      Collapse group view
                    </Button>
                  ) : null}
                </div>
              )}
              <ReactFlow
                nodes={nodes}
                edges={edges}
                nodeTypes={explorerNodeTypes}
                colorMode={resolvedTheme === 'dark' ? 'dark' : 'light'}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                key={`${view}-${selectedLayer ?? ''}-${expandedGroupId ?? ''}-${spotOnly ? 'spot' : 'all'}`}
                fitView
                fitViewOptions={{ padding: 0.08 }}
                minZoom={0.1}
                proOptions={{ hideAttribution: true }}
                className="min-h-0 flex-1"
                onNodeClick={(_, node) => {
                  if (view === 'overview' && node.type === 'layerNode') {
                    setSelectedLayer(String(node.data.layerId));
                    setExpandedGroupId(null);
                    setView('subsystem');
                    return;
                  }
                  if (view === 'overview' && node.type === 'groupNode') {
                    const data = node.data as { layerId?: string; componentId?: string };
                    if (data.layerId && data.componentId) {
                      setSelectedLayer(data.layerId);
                      setExpandedGroupId(data.componentId);
                      setView('subsystem');
                    }
                    return;
                  }
                  const component = bundle.data.components.find((item) => item.id === node.id);
                  if (component) {
                    setSelectedComponent(component);
                  }
                  if (view === 'subsystem' && node.data && (node.data as { isGroup?: boolean }).isGroup) {
                    setExpandedGroupId(node.id);
                  }
                }}
              >
                <Background />
                <Controls />
                <MiniMap
                  pannable
                  zoomable
                  bgColor={resolvedTheme === 'dark' ? '#111113' : '#ffffff'}
                  nodeColor={resolvedTheme === 'dark' ? '#3f3f46' : '#d4d4d8'}
                  maskColor={resolvedTheme === 'dark' ? 'rgba(0,0,0,0.6)' : 'rgba(240,240,240,0.6)'}
                />
              </ReactFlow>
              <div className="flex gap-2 border-t p-2">
                <Button size="sm" variant="outline" onClick={() => void persistLayout()}>
                  Save layout (visual only)
                </Button>
              </div>
            </div>
          )}
        </section>

        {view !== 'map' && view !== 'live' && (
        <aside className="overflow-auto p-4">
          <h2 className="font-medium">Detail and provenance</h2>
          <Separator className="my-3" />
          {searchResults.length > 0 && (
            <div className="mb-4">
              <h3 className="text-sm font-medium">Search matches</h3>
              <ul className="mt-2 space-y-1">
                {searchResults.slice(0, 8).map((item) => (
                  <li key={item.id}>
                    <button
                      type="button"
                      className="text-left text-sm underline-offset-2 hover:underline"
                      onClick={() => {
                        setSelectedComponent(item);
                        setSelectedLayer(item.layer_id);
                      }}
                    >
                      {item.name}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {selectedComponent ? (
            <div className="space-y-2 text-sm">
              <div className="text-base font-medium">{selectedComponent.name}</div>
              <p>{selectedComponent.purpose}</p>
              <p className="text-muted-foreground">{selectedComponent.boundary}</p>
              <div className="flex flex-wrap gap-1 text-xs">
                <span className="bg-muted rounded px-1.5 py-0.5">{selectedComponent.category}</span>
                <span className="bg-muted rounded px-1.5 py-0.5">
                  evidence: {selectedComponent.evidence_level}
                </span>
                <span className="bg-muted rounded px-1.5 py-0.5">
                  condition: {selectedComponent.observed_condition}
                </span>
              </div>
              <div>
                <div className="font-medium">Evidence IDs</div>
                <ul className="list-disc pl-5">
                  {selectedComponent.evidence_ids.map((id) => (
                    <li key={id}>{id}</li>
                  ))}
                </ul>
              </div>
              <div>
                <div className="font-medium">Relationships</div>
                <ul className="list-disc pl-5">
                  {bundle.data.relationships
                    .filter(
                      (rel) =>
                        rel.source_id === selectedComponent.id ||
                        rel.target_id === selectedComponent.id,
                    )
                    .map((rel) => {
                      const peerId =
                        rel.source_id === selectedComponent.id ? rel.target_id : rel.source_id;
                      const peer = bundle.data.components.find((c) => c.id === peerId);
                      return (
                        <li key={rel.id}>
                          <button
                            type="button"
                            className="text-left underline-offset-2 hover:underline"
                            onClick={() => {
                              if (peer) {
                                setSelectedComponent(peer);
                                setSelectedLayer(peer.layer_id);
                                setView('subsystem');
                              }
                            }}
                          >
                            {rel.label} ({rel.type}) → {peer?.name ?? peerId}
                          </button>
                        </li>
                      );
                    })}
                </ul>
              </div>
            </div>
          ) : (
            <p className="text-muted-foreground text-sm">Select a component or issue.</p>
          )}

          {selectedSource && sourcePreview && (
            <div className="mt-6 space-y-2 text-sm">
              <h3 className="font-medium">File contents</h3>
              <div className="text-muted-foreground text-xs">
                {String(sourcePreview.label)} · {String(sourcePreview.path)}
              </div>
              <pre className="bg-muted max-h-[320px] overflow-auto rounded p-3 text-xs whitespace-pre-wrap">
                {String(sourcePreview.content ?? sourcePreview.error ?? 'No content')}
              </pre>
            </div>
          )}
        </aside>
        )}
      </div>
    </div>
  );
}
