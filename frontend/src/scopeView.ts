import type { NodeRead, RepoMap } from "./api";

export type ScopeNode = NodeRead & { childCount: number };
/** `trail`: ancestors from the top level down to the scope itself (empty at repo level). `children`: what the screen shows. */
export type ScopeView = { trail: ScopeNode[]; children: ScopeNode[] };

const CONTAINS = "contains";

/**
 * One screen shows one scope: the repo's top-level areas, or the children of one area (DESIGN §1: drawn
 * top-level first, click to go deeper). An unknown scope id falls back to the repo level.
 */
export function scopeView(map: RepoMap, scopeId: number | null): ScopeView {
  const contains = map.edges.filter((e) => e.kind === CONTAINS);
  const parentOf = new Map(contains.map((e) => [e.target_id, e.source_id]));
  const childCount = new Map<number, number>();
  for (const e of contains) childCount.set(e.source_id, (childCount.get(e.source_id) ?? 0) + 1);
  const withCount = (n: NodeRead): ScopeNode => ({ ...n, childCount: childCount.get(n.id) ?? 0 });
  const byId = new Map(map.nodes.map((n) => [n.id, withCount(n)]));

  const trail: ScopeNode[] = [];
  for (let id = scopeId; id !== null; id = parentOf.get(id) ?? null) {
    const node = byId.get(id);
    if (node === undefined) return { trail: [], children: roots() };
    trail.unshift(node);
  }
  const scope = trail.at(-1);
  const children = scope === undefined ? roots() : [...byId.values()].filter((n) => parentOf.get(n.id) === scope.id);
  return { trail, children };

  function roots(): ScopeNode[] {
    return [...byId.values()].filter((n) => !parentOf.has(n.id));
  }
}
