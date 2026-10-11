'use client';

import type { NodeProps } from '@xyflow/react';
import { Handle, Position } from '@xyflow/react';

import { BaseNode, BaseNodeContent, BaseNodeHeader, BaseNodeHeaderTitle } from '@/components/base-node';

type LayerData = {
  label: string;
  count: number;
  groupCount?: number;
  groupedChildren?: number;
  standalone?: number;
  layerId: string;
  layerOrder?: number;
};
type ComponentData = {
  label: string;
  kind: string;
  category: string;
  evidence_level: string;
  observed_condition: string;
  componentId?: string;
  isGroup?: boolean;
  childCount?: number;
  layerTotal?: number;
};


type Spot = { director: number; conductor: number } | undefined;
function SpotlightBadge({ spot }: { spot: Spot }) {
  if (!spot) return null;
  return (
    <div className="flex flex-wrap gap-1" data-testid="director-conductor-spotlight">
      {spot.director > 0 ? (
        <span className="rounded-full bg-[#ff0071] px-2 py-0.5 text-xs font-semibold text-white">
          ★ Director {spot.director}
        </span>
      ) : null}
      {spot.conductor > 0 ? (
        <span className="rounded-full border border-[#ff0071] px-2 py-0.5 text-xs font-semibold text-[#ff4d9a]">
          ◆ Conductor {spot.conductor}
        </span>
      ) : null}
    </div>
  );
}
const spotRing = (spot: Spot) => (spot ? ' ring-2 ring-[#ff0071] shadow-[0_0_24px_rgba(255,0,113,0.35)]' : '');

function Badge({ children }: { children: React.ReactNode }) {
  return (
    <span className="bg-muted text-muted-foreground rounded px-1.5 py-0.5 text-sm font-medium">
      {children}
    </span>
  );
}

export function LayerNode({ data }: NodeProps) {
  const node = data as LayerData;
  return (
    <BaseNode
      className={`w-[240px]${spotRing((data as { spotlight?: Spot }).spotlight)}`}
      data-testid={node.layerOrder ? `layer-order-${node.layerOrder}` : undefined}
    >
      <Handle type="target" position={Position.Top} className="opacity-0" />
      <BaseNodeHeader>
        <BaseNodeHeaderTitle className="whitespace-normal break-words text-base font-semibold">{node.label}</BaseNodeHeaderTitle>
      </BaseNodeHeader>
      <BaseNodeContent className="gap-1 text-sm">
        <SpotlightBadge spot={(data as { spotlight?: Spot }).spotlight} />
        <Badge>{node.count} records in layer</Badge>
        <div
          className="text-muted-foreground leading-snug"
          title="Every record in this layer is counted once: group cards + records inside groups + standalone records"
        >
          {node.groupCount ?? 0} groups + {node.groupedChildren ?? 0} grouped + {node.standalone ?? 0} standalone
        </div>
      </BaseNodeContent>
      <Handle type="source" position={Position.Bottom} className="opacity-0" />
    </BaseNode>
  );
}

export function GroupNode({ data }: NodeProps) {
  const node = data as ComponentData;
  return (
    <BaseNode className={`h-[156px] w-[260px] overflow-hidden border-dashed${spotRing((data as { spotlight?: Spot }).spotlight)}`}>
      <Handle type="target" position={Position.Top} />
      <BaseNodeHeader>
        <BaseNodeHeaderTitle className="line-clamp-2 whitespace-normal break-words text-base font-semibold" title={node.label}>
          {node.label}
        </BaseNodeHeaderTitle>
      </BaseNodeHeader>
      <BaseNodeContent className="gap-1 text-sm">
        <SpotlightBadge spot={(data as { spotlight?: Spot }).spotlight} />
        <Badge>
          {node.childCount ?? 0} inside{node.layerTotal ? ` · of ${node.layerTotal} in layer` : ''}
        </Badge>
        <div className="text-muted-foreground text-sm">Click to expand</div>
      </BaseNodeContent>
      <Handle type="source" position={Position.Bottom} />
    </BaseNode>
  );
}

export function ComponentNode({ data }: NodeProps) {
  const node = data as ComponentData;
  return (
    <BaseNode className={`max-w-[260px]${spotRing((data as { spotlight?: Spot }).spotlight)}`}>
      <Handle type="target" position={Position.Top} />
      <BaseNodeHeader>
        <BaseNodeHeaderTitle className="text-base font-semibold">{node.label}</BaseNodeHeaderTitle>
      </BaseNodeHeader>
      <BaseNodeContent className="gap-1 text-sm">
        <SpotlightBadge spot={(data as { spotlight?: Spot }).spotlight} />
        <div className="flex flex-wrap gap-1">
          <Badge>{node.kind}</Badge>
          <Badge>{node.category}</Badge>
          {node.isGroup ? <Badge>{node.childCount ?? 0} children</Badge> : null}
        </div>
        <div className="text-muted-foreground flex flex-wrap gap-1">
          <Badge>evidence: {node.evidence_level}</Badge>
          <Badge>condition: {node.observed_condition}</Badge>
        </div>
      </BaseNodeContent>
      <Handle type="source" position={Position.Bottom} />
    </BaseNode>
  );
}

export const explorerNodeTypes = {
  layerNode: LayerNode,
  componentNode: ComponentNode,
  groupNode: GroupNode,
};
