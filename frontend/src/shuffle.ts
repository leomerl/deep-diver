/** Sorts a copy by one random key per item: every order is equally likely. A comparator that returns
 * Math.random() - 0.5 is not uniform, because the sort sees inconsistent answers. */
export function shuffle<T>(items: readonly T[], random: () => number = Math.random): T[] {
  return items
    .map((item) => ({ item, key: random() }))
    .sort((a, b) => a.key - b.key)
    .map(({ item }) => item);
}
