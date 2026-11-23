import type { components } from "./schema";

export type RepoRead = components["schemas"]["RepoRead"];
export type RepoCreate = components["schemas"]["RepoCreate"];
export type NodeRead = components["schemas"]["NodeRead"];
export type EdgeRead = components["schemas"]["EdgeRead"];
export type RepoMap = components["schemas"]["RepoMap"];
export type DeepDiveRead = components["schemas"]["DeepDiveRead"];
export type DeepDiveCreate = components["schemas"]["DeepDiveCreate"];
export type DeepDiveListItem = components["schemas"]["DeepDiveListItem"];
export type NotebookBase = components["schemas"]["NotebookBase"];
export type NotebookJob = components["schemas"]["NotebookJob"];
export type InterviewQuestionListItem = components["schemas"]["InterviewQuestionListItem"];
export type UserRead = components["schemas"]["UserRead"];
export type GitHubRepo = components["schemas"]["GitHubRepo"];
export type AppSettings = components["schemas"]["AppSettings"];
export type AgentRuntime = components["schemas"]["AgentRuntime"];
export type SnapshotBase = components["schemas"]["SnapshotBase"];
export type JobRead = components["schemas"]["JobRead"];
export type JobState = components["schemas"]["JobState"];
export type StepStatus = components["schemas"]["StepStatus"];
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

/** 202 with the HEAD commit the job will index; equal to the repo's commit when it is already current. */
export const reindexRepo = (repoId: number): Promise<SnapshotBase> =>
  request(`/repos/${repoId}/reindex`, { method: "POST" });

/** The logged-in user, or null. Login itself is a plain navigation to /auth/github/login. */
export const me = (): Promise<UserRead | null> => request("/auth/me");

/** 401 (as ApiError) when logged out. */
export const githubRepos = (): Promise<GitHubRepo[]> => request("/auth/github/repos");

/** What a deep dive is about: one node, or the whole repo. The kind is the URL's first segment. */
export type DeepDiveTarget = { kind: "nodes" | "repos"; id: number };

const deepDivePath = ({ kind, id }: DeepDiveTarget): string => `/${kind}/${id}/deep-dive`;

/** 404 (as ApiError) until the worker has written the page. */
export const getDeepDive = (target: DeepDiveTarget): Promise<DeepDiveRead> => request(deepDivePath(target));

/** 202; idempotent, a target already queued or finished is not re-queued. */
export const requestDeepDive = (target: DeepDiveTarget): Promise<DeepDiveCreate> =>
  request(deepDivePath(target), { method: "POST" });

export const deepDiveHtmlUrl = (target: DeepDiveTarget): string => `${deepDivePath(target)}/html`;

/** Any page by its own id, older snapshots' included (the repo route only reaches the current root page). */
export const deepDivePageUrl = (deepDiveId: number): string => `/deep-dives/${deepDiveId}/html`;

/** 404 (as ApiError) when the deep dive has no notebook (`notebook_key` is null). */
export const getNotebook = (deepDiveId: number): Promise<NotebookBase> => request(`/deep-dives/${deepDiveId}/notebook`);

/** 202; idempotent. The worker queues one after every new page, so this is for older pages and failed notebooks. */
export const requestNotebook = (deepDiveId: number): Promise<NotebookJob> =>
  request(`/deep-dives/${deepDiveId}/notebook`, { method: "POST" });

/** Every written deep dive, newest first. */
export const listDeepDives = (): Promise<DeepDiveListItem[]> => request("/deep-dives");

/** The whole interview question bank, each with the area it is about. */
export const listInterviewQuestions = (): Promise<InterviewQuestionListItem[]> => request("/interview-questions");

export const getSettings = (): Promise<AppSettings> => request("/settings");

/** Workers read the setting when each agent starts, so this applies to the next agent, not the next restart. */
export const putSettings = (settings: AppSettings): Promise<AppSettings> =>
  request("/settings", { method: "PUT", body: JSON.stringify(settings) });

/** Both queues' newest jobs, newest first: state from Redis, history (tries, steps, errors) from the workers. */
export const listJobs = (): Promise<JobRead[]> => request("/jobs");
