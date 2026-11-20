import type { Edge, Node } from "@xyflow/react";

import type { RepoRead } from "./api";
import type { ScopeNode, ScopeView } from "./scopeView";

// A screen is a star: the scope card on the left, its children in a column on the right. No layout engine needed.
export const NODE_W = 240;
export const NODE_H = 76;
const GAP_X = 96;
const GAP_Y = 16;
export const REPO_NODE_ID = "repo";
export const AREA_TYPE = "area";
export const REPO_TYPE = "repo";

export type AreaData = { node: ScopeNode; selected: boolean; isScope: boolean };
export type RepoData = { repo: RepoRead; areaCount: number };
export type AreaNode = Node<AreaData, typeof AREA_TYPE>;
export type RepoNode = Node<RepoData, typeof REPO_TYPE>;

export function layout(
  view: ScopeView,
  repo: RepoRead,
  areaCount: number,
  selectedId: number | null,
): { nodes: (AreaNode | RepoNode)[]; edges: Edge[] } {
  const size = { width: NODE_W, height: NODE_H }; // the DOM box must match these coordinates, so size stays here, not in CSS
  const columnHeight = view.children.length * NODE_H + Math.max(0, view.children.length - 1) * GAP_Y;
  const rootPosition = { x: 0, y: (columnHeight - NODE_H) / 2 };
  const scope = view.trail.at(-1);
  // The scope card keeps the id it had as a child, so React Flow moves the same element and the CSS transition animates it.
  const root: AreaNode | RepoNode =
    scope === undefined
      ? { id: REPO_NODE_ID, type: REPO_TYPE, position: rootPosition, data: { repo, areaCount }, selectable: false, style: size }
      : {
          id: String(scope.id),
          type: AREA_TYPE,
          position: rootPosition,
          data: { node: scope, selected: scope.id === selectedId, isScope: true },
          style: size,
        };
  const children = view.children.map(
    (n, i): AreaNode => ({
      id: String(n.id),
      type: AREA_TYPE,
      position: { x: NODE_W + GAP_X, y: i * (NODE_H + GAP_Y) },
      data: { node: n, selected: n.id === selectedId, isScope: false },
      style: size,
    }),
  );
  const edges = children.map((c): Edge => ({ id: `${root.id}-${c.id}`, source: root.id, target: c.id, type: "smoothstep" }));
  return { nodes: [root, ...children], edges };
}
