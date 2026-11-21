/** Shown in place of an area name for a deep dive about the whole repo. */
export const WHOLE_REPO = "Whole repository";

/** Splits a normalized repo URL into the "owner/name" shown in the list and the host shown under it. */
export function repoLabel(url: string): { name: string; host: string } {
  const { pathname, host } = new URL(url);
  return { name: pathname.replace(/^\/|\/$/g, "").replace(/\.git$/, ""), host };
}
