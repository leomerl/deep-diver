import { expect, test } from "vitest";

import { repoLabel } from "../src/repoLabel";

test("owner/name without the leading slash, trailing slash or .git", () => {
  expect(repoLabel("https://github.com/owner/repo")).toEqual({ name: "owner/repo", host: "github.com" });
  expect(repoLabel("https://github.com/owner/repo.git/")).toEqual({ name: "owner/repo", host: "github.com" });
});
