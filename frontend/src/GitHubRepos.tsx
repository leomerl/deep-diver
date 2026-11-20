import { useEffect, useState } from "react";

import { addRepo, ApiError, githubRepos, me, type GitHubRepo, type UserRead } from "./api";

type Props = { onAdded: (normalizedUrl: string) => void };

/** Login button when logged out; the user's GitHub repos with an Index button each when logged in. */
export function GitHubRepos({ onAdded }: Props) {
  const [user, setUser] = useState<UserRead | null | undefined>(undefined);
  const [repos, setRepos] = useState<GitHubRepo[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    me().then(setUser, (e: Error) => setError(e.message));
  }, []);
  useEffect(() => {
    if (user) githubRepos().then(setRepos, (e: Error) => setError(e.message));
  }, [user]);

  const index = async (repo: GitHubRepo) => {
    setBusy(repo.html_url);
    setError(null);
    try {
      onAdded((await addRepo(repo.html_url)).url);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  };

  if (user === undefined) return null;
  if (user === null)
    return (
      <a className="btn" href="/auth/github/login">
        Log in with GitHub
      </a>
    );
  return (
    <>
      <h2 className="section-label">Your GitHub repositories ({user.login})</h2>
      {error && (
        <p role="alert" className="note note--error">
          {error}
        </p>
      )}
      <ul className="source-list">
        {repos.map((repo) => (
          <li key={repo.html_url}>
            <button onClick={() => index(repo)} disabled={busy !== null} className="source-list__row">
              <span className="source-list__name">{repo.full_name}</span>
              <span className="source-list__host">{busy === repo.html_url ? "adding…" : repo.private ? "private" : "public"}</span>
            </button>
          </li>
        ))}
      </ul>
    </>
  );
}
