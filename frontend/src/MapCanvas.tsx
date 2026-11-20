import {
  Background,
  BackgroundVariant,
  Controls,
  ReactFlow,
  ReactFlowProvider,
  useNodesInitialized,
  useReactFlow,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useEffect, useMemo, useState } from "react";

import type { RepoMap, RepoRead } from "./api";
import { AreaNode } from "./AreaNode";
import { Breadcrumb } from "./Breadcrumb";
import { AREA_TYPE, layout, NODE_H, NODE_W, REPO_NODE_ID, REPO_TYPE } from "./layout";
import { repoLabel } from "./repoLabel";
import { RepoNode } from "./RepoNode";
import { scopeView } from "./scopeView";

type Props = { repo: RepoRead; map: RepoMap; selectedId: number | null; onSelect: (id: number) => void };

// Module-level so React Flow sees the same object every render (a new one would remount every node).
const NODE_TYPES = { [AREA_TYPE]: AreaNode, [REPO_TYPE]: RepoNode };
const FIT = { padding: 0.2, maxZoom: 1 };
const CAMERA_MS = 400;

/** Mount with `key={repo.id}` so the scope resets when the repo changes. */
export function MapCanvas(props: Props) {
  return (
    <ReactFlowProvider>
      <Canvas {...props} />
    </ReactFlowProvider>
  );
}

function Canvas({ repo, map, selectedId, onSelect }: Props) {
  const [scopeId, setScopeId] = useState<number | null>(null);
  const view = useMemo(() => scopeView(map, scopeId), [map, scopeId]);
  const { nodes, edges } = useMemo(() => layout(view, repo, map.nodes.length, selectedId), [view, repo, map, selectedId]);

  // Ease the camera onto the scope card once the new cards are measured (they start unmeasured). The card sits at
  // the vertical middle of its children, so centering on it centers the whole level; zoom is kept as the user left it.
  const { setCenter, getZoom } = useReactFlow();
  const measured = useNodesInitialized();
  const root = nodes[0]!; // layout puts the scope card first
  const rootX = root.position.x + NODE_W / 2;
  const rootY = root.position.y + NODE_H / 2;
  useEffect(() => {
    if (measured) setCenter(rootX, rootY, { zoom: getZoom(), duration: CAMERA_MS });
  }, [measured, scopeId, rootX, rootY, setCenter, getZoom]);

  const parentId = view.trail.at(-2)?.id ?? null;
  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={NODE_TYPES}
      fitView
      fitViewOptions={FIT}
      minZoom={0.2}
      nodesDraggable={false}
      nodesConnectable={false}
      proOptions={{ hideAttribution: true }}
      onNodeClick={(_, node) => {
        if (node.id === REPO_NODE_ID) return;
        const id = Number(node.id);
        if (id === scopeId) return setScopeId(parentId);
        onSelect(id);
        if (view.children.find((n) => n.id === id)?.childCount) setScopeId(id);
      }}
    >
      <Background variant={BackgroundVariant.Dots} gap={20} size={1} />
      <Controls showInteractive={false} />
      <Breadcrumb repoName={repoLabel(repo.url).name} trail={view.trail} onNavigate={setScopeId} />
    </ReactFlow>
  );
}
