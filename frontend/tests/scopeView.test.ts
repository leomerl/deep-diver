import { expect, test } from "vitest";

import type { RepoMap } from "../src/api";
import { scopeView } from "../src/scopeView";

const node = (id: number, name: string) => ({ id, name, description: null, paths: [name], grouping: "llm" as const });
const contains = (id: number, source_id: number, target_id: number) => ({ id, source_id, target_id, kind: "contains" as const, label: null });

// API(1) ─ Auth(2) ─ Tokens(4); API(1) ─ Routes(3); Worker(5)
const MAP: RepoMap = {
  nodes: [node(1, "API"), node(2, "Auth"), node(3, "Routes"), node(4, "Tokens"), node(5, "Worker")],
  edges: [contains(10, 1, 2), contains(11, 1, 3), contains(12, 2, 4)],
};
const ids = (nodes: { id: number }[]) => nodes.map((n) => n.id);

test("repo level: top-level areas with their child counts, empty trail", () => {
  const view = scopeView(MAP, null);
  expect(view.trail).toEqual([]);
  expect(ids(view.children)).toEqual([1, 5]);
  expect(view.children.map((n) => n.childCount)).toEqual([2, 0]);
});

test("an area as scope: its direct children only, trail from the top", () => {
  const view = scopeView(MAP, 2);
  expect(ids(view.trail)).toEqual([1, 2]);
  expect(ids(view.children)).toEqual([4]);
});

test("a leaf as scope has no children", () => {
  expect(scopeView(MAP, 5).children).toEqual([]);
});

test("an unknown scope falls back to the repo level", () => {
  expect(scopeView(MAP, 99)).toEqual(scopeView(MAP, null));
});
