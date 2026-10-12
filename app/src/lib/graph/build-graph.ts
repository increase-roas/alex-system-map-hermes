import type { Edge, Node } from '@xyflow/react';

import type { CatalogBundle, CatalogComponent } from '@/lib/types/catalog';

export type ExplorerView =
  | 'map'
  | 'pro'
  | 'overview'
  | 'subsystem'
  | 'problems'
  | 'workflows'
  | 'files'
  | 'tracing'
  | 'reliability'
  | 'maintained'
  | 'live';

export function layerCounts(bundle: CatalogBundle): Map<string, number> {
  const counts = new Map<string, number>();
  for (const layer of bundle.data.layers) {
    counts.set(layer.id, 0);
  }
  for (const component of bundle.data.components) {
    counts.set(component.layer_id, (counts.get(component.layer_id) ?? 0) + 1);
  }
  return counts;
}

function membershipByComponent(bundle: CatalogBundle) {
  return new Map(bundle.overview_memberships.map((item) => [item.component_id, item]));
}

function childCount(bundle: CatalogBundle, parentId: string): number {
  return bundle.overview_memberships.filter((item) => item.parent_id === parentId).length;
}

function componentLayer(bundle: CatalogBundle, componentId: string): string | null {
  const component = bundle.data.components.find((item) => item.id === componentId);
  return component?.layer_id ?? null;
}

/** Map a component to a layer node or expandable group node on the overview canvas. */
function overviewAnchor(bundle: CatalogBundle, componentId: string): string | null {
  const membership = membershipByComponent(bundle).get(componentId);
  const layerId = membership?.layer_id ?? componentLayer(bundle, componentId);
  if (!layerId) {
    return null;
  }
  if (membership?.parent_id) {
    return `group:${membership.parent_id}`;
  }
  if (childCount(bundle, componentId) > 0) {
    return `group:${componentId}`;
  }
  return layerId;
}

/** Per-layer breakdown: total = groupRoots + groupedChildren + standalone. Every membership is counted once. */
export type LayerBreakdown = {
  total: number;
  groups: { componentId: string; childCount: number }[];
  groupedChildren: number;
  standalone: number;
};

export function layerBreakdown(bundle: CatalogBundle): Map<string, LayerBreakdown> {
  const children = new Map<string, number>();
  for (const member of bundle.overview_memberships) {
    if (member.parent_id) {
      children.set(member.parent_id, (children.get(member.parent_id) ?? 0) + 1);
    }
  }
  const out = new Map<string, LayerBreakdown>();
  for (const layer of bundle.data.layers) {
    out.set(layer.id, { total: 0, groups: [], groupedChildren: 0, standalone: 0 });
  }
  for (const member of bundle.overview_memberships) {
    const entry = out.get(member.layer_id);
    if (!entry) {
      continue;
    }
    entry.total += 1;
    if (member.parent_id) {
      entry.groupedChildren += 1;
    } else if (children.has(member.component_id)) {
      entry.groups.push({ componentId: member.component_id, childCount: children.get(member.component_id) ?? 0 });
    } else {
      entry.standalone += 1;
    }
  }
  for (const entry of out.values()) {
    entry.groups.sort((a, b) => b.childCount - a.childCount);
  }
  return out;
}

export const OVERVIEW_LAYOUT = {
  layerX: 40,
  layerWidth: 240,
  groupX: 320,
  groupWidth: 260,
  groupHeight: 156,
  gapX: 24,
  gapY: 20,
  groupsPerRow: 4,
  rowGap: 48,
};

export function buildOverviewGraph(bundle: CatalogBundle): { nodes: Node[]; edges: Edge[] } {
  const breakdown = layerBreakdown(bundle);
  const sortedLayers = [...bundle.data.layers].sort((a, b) => a.order - b.order);
  const L = OVERVIEW_LAYOUT;
  const nodes: Node[] = [];
  const groupsByLayer = new Map<string, string[]>();

  let y = 0;
  for (const layer of sortedLayers) {
    const info = breakdown.get(layer.id) ?? { total: 0, groups: [], groupedChildren: 0, standalone: 0 };
    const rows = Math.max(1, Math.ceil(info.groups.length / L.groupsPerRow));
    const bandHeight = rows * L.groupHeight + (rows - 1) * L.gapY;
    nodes.push({
      id: layer.id,
      type: 'layerNode',
      position: { x: L.layerX, y },
      data: {
        label: layer.name,
        count: info.total,
        groupCount: info.groups.length,
        groupedChildren: info.groupedChildren,
        standalone: info.standalone,
        layerId: layer.id,
        layerOrder: layer.order,
      },
    });
    groupsByLayer.set(layer.id, info.groups.map((g) => g.componentId));
    info.groups.forEach((group, index) => {
      const component = bundle.data.components.find((item) => item.id === group.componentId);
      nodes.push({
        id: `group:${group.componentId}`,
        type: 'groupNode',
        position: {
          x: L.groupX + (index % L.groupsPerRow) * (L.groupWidth + L.gapX),
          y: y + Math.floor(index / L.groupsPerRow) * (L.groupHeight + L.gapY),
        },
        data: {
          ...componentData(component),
          isGroup: true,
          childCount: group.childCount,
          layerTotal: info.total,
          layerId: layer.id,
          componentId: group.componentId,
        },
      });
    });
    y += bandHeight + L.rowGap;
  }

  const edges: Edge[] = [];
  for (let i = 0; i < sortedLayers.length - 1; i += 1) {
    const from = sortedLayers[i];
    const to = sortedLayers[i + 1];
    edges.push({
      id: `layer-flow-${from.id}-${to.id}`,
      source: from.id,
      target: to.id,
      label: 'layer order',
      data: { kind: 'layer_navigation' },
    });
  }
  for (const layer of sortedLayers) {
    for (const componentId of groupsByLayer.get(layer.id) ?? []) {
      edges.push({
        id: `layer-group-${layer.id}-${componentId}`,
        source: layer.id,
        target: `group:${componentId}`,
        label: 'navigation group',
        data: { kind: 'membership' },
      });
    }
  }

  const seen = new Set<string>();
  for (const rel of bundle.data.relationships) {
    const source = overviewAnchor(bundle, rel.source_id);
    const target = overviewAnchor(bundle, rel.target_id);
    if (!source || !target || source === target) {
      continue;
    }
    const key = `${source}->${target}:${rel.label}`;
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    edges.push({
      id: rel.id,
      source,
      target,
      label: rel.label,
      data: { relationshipId: rel.id, kind: 'configured' },
    });
    if (edges.length >= 32) {
      break;
    }
  }
  return { nodes, edges };
}

export function buildSubsystemGraph(
  bundle: CatalogBundle,
  layerId: string,
  expandedGroupId: string | null,
  limit = 120,
): { nodes: Node[]; edges: Edge[] } {
  const inLayer = bundle.overview_memberships.filter((item) => item.layer_id === layerId);
  const roots = inLayer.filter((item) => !item.parent_id);
  const groups = roots.slice(0, 40);
  const nodes: Node[] = [];
  const memberIds = new Set<string>();

  if (!expandedGroupId) {
    for (const [index, group] of groups.entries()) {
      const childCount = inLayer.filter((item) => item.parent_id === group.component_id).length;
      const self = bundle.data.components.find((c) => c.id === group.component_id);
      nodes.push({
        id: group.component_id,
        type: 'componentNode',
        position: { x: (index % 6) * 200, y: Math.floor(index / 6) * 110 },
        data: {
          ...componentData(self),
          isGroup: childCount > 0,
          childCount,
        },
      });
      memberIds.add(group.component_id);
    }
  } else {
    const children = inLayer
      .filter((item) => item.parent_id === expandedGroupId || item.component_id === expandedGroupId)
      .slice(0, limit);
    for (const [index, member] of children.entries()) {
      const component = bundle.data.components.find((item) => item.id === member.component_id);
      nodes.push({
        id: member.component_id,
        type: 'componentNode',
        position: { x: (index % 8) * 180, y: Math.floor(index / 8) * 100 },
        data: componentData(component),
      });
      memberIds.add(member.component_id);
    }
  }

  const edges: Edge[] = bundle.data.relationships
    .filter((rel) => memberIds.has(rel.source_id) && memberIds.has(rel.target_id))
    .map((rel) => ({
      id: rel.id,
      source: rel.source_id,
      target: rel.target_id,
      label: rel.label,
      data: { relationshipId: rel.id, kind: 'configured' },
    }));

  return { nodes, edges };
}

export function componentData(component?: CatalogComponent) {
  if (!component) {
    return {
      label: 'Unresolved reference',
      kind: 'unknown',
      category: 'unresolved',
      evidence_level: 'unverified',
      observed_condition: 'unknown',
    };
  }
  return {
    label: component.name,
    kind: component.kind,
    category: component.category,
    evidence_level: component.evidence_level,
    observed_condition: component.observed_condition,
    componentId: component.id,
  };
}

export function searchComponents(
  bundle: CatalogBundle,
  query: string,
): CatalogComponent[] {
  const q = query.trim().toLowerCase();
  if (!q) {
    return [];
  }
  const exact = bundle.data.components.filter((item) => item.id.toLowerCase() === q);
  if (exact.length) {
    return exact;
  }
  return bundle.data.components
    .filter((item) => {
      const name = (item.name ?? '').toLowerCase();
      const id = (item.id ?? '').toLowerCase();
      const aliases = item.aliases ?? [];
      return (
        name.includes(q) ||
        id.includes(q) ||
        aliases.some((alias) => String(alias).toLowerCase().includes(q))
      );
    })
    .slice(0, 40);
}
