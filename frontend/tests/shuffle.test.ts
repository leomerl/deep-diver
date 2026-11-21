import { expect, test } from "vitest";

import { shuffle } from "../src/shuffle";

test("keeps every item and leaves the input untouched", () => {
  const input = [1, 2, 3, 4, 5];
  expect([...shuffle(input)].sort()).toEqual(input);
  expect(input).toEqual([1, 2, 3, 4, 5]);
});

test("orders items by their random keys", () => {
  const keys = [0.3, 0.1, 0.2];
  expect(shuffle(["a", "b", "c"], () => keys.shift() ?? 0)).toEqual(["b", "c", "a"]);
});
