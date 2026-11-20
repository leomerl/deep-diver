import type { components } from "./schema";

export type RepoRead = components["schemas"]["RepoRead"];
export type RepoCreate = components["schemas"]["RepoCreate"];
export type NodeRead = components["schemas"]["NodeRead"];
export type EdgeRead = components["schemas"]["EdgeRead"];
export type RepoMap = components["schemas"]["RepoMap"];
export type DeepDiveRead = components["schemas"]["DeepDiveRead"];
export type DeepDiveCreate = components["schemas"]["DeepDiveCreate"];
export type UserRead = components["schemas"]["UserRead"];
export type GitHubRepo = components["schemas"]["GitHubRepo"];
type ValidationError = components["schemas"]["ValidationError"];

const isValidationErrors = (detail: unknown): detail is ValidationError[] =>
  Array.isArray(detail) && detail.every((e: unknown) => typeof e === "object" && e !== null && "msg" in e);

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    detail: string,
  ) {
    super(detail);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, { headers: { "Content-Type": "application/json" }, ...init });
  if (!res.ok) {
    // FastAPI puts its message in `detail`: a string for HTTPException, a list of {loc, msg} for 422.
    const body: unknown = await res.json().catch(() => res.statusText);
    const detail = typeof body === "object" && body !== null && "detail" in body ? body.detail : body;
    const message = isValidationErrors(detail) ? detail.map((e) => e.msg).join("; ") : String(detail);
    throw new ApiError(res.status, message);
  }
  return (await res.json()) as T;
}

export const listRepos = (): Promise<RepoRead[]> => request("/repos");

/** 202 with the normalized URL; the worker creates the row later, so there is no id yet. */
export const addRepo = (url: string): Promise<RepoCreate> =>
  request("/repos", { method: "POST", body: JSON.stringify({ url }) });

export const getMap = (repoId: number): Promise<RepoMap> => request(`/repos/${repoId}/map`);

/** The logged-in user, or null. Login itself is a plain navigation to /auth/github/login. */
export const me = (): Promise<UserRead | null> => request("/auth/me");

/** 401 (as ApiError) when logged out. */
export const githubRepos = (): Promise<GitHubRepo[]> => request("/auth/github/repos");

/** 404 (as ApiError) until the worker has written the page. */
export const getDeepDive = (nodeId: number): Promise<DeepDiveRead> => request(`/nodes/${nodeId}/deep-dive`);

/** 202; idempotent, a node already queued or finished is not re-queued. */
export const requestDeepDive = (nodeId: number): Promise<DeepDiveCreate> =>
  request(`/nodes/${nodeId}/deep-dive`, { method: "POST" });

export const deepDiveHtmlUrl = (nodeId: number): string => `/nodes/${nodeId}/deep-dive/html`;
