import { useEffect, useState } from "react";

import { addRepo, ApiError, githubRepos, me, type GitHubRepo, type UserRead } from "./api";

type Props = { onAdded: (normalizedUrl: string) => void };

const UNAUTHORIZED = 401;

/** Login button when logged out; the user's GitHub repos with an Index button each when logged in. */
export function GitHubRepos({ onAdded }: Props) {
  const [user, setUser] = useState<UserRead | null | undefined>(undefined);
  const [repos, setRepos] = useState<GitHubRepo[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  // The session cookie can outlive the GitHub token, so a 401 here must offer a fresh login.
  const [tokenRejected, setTokenRejected] = useState(false);

  useEffect(() => {
    me().then(setUser, (e: Error) => setError(e.message));
  }, []);
  useEffect(() => {
    if (user)
      githubRepos().then(setRepos, (e: Error) => {
        setError(e.message);
        setTokenRejected(e instanceof ApiError && e.status === UNAUTHORIZED);
      });
  }, [user]);

  const index = async (repo: GitHubRepo) => {
    setBusy(repo.html_url);
    setError(null);
    try {
      onAdded((await addRepo(repo.html_url)).url);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not add the repository. Try again.");
    } finally {
      setBusy(null);
    }
  };

  if (user === undefined) return null;
  if (user === null)
    return (
      <>
        <h3 className="section-label">From GitHub</h3>
        <a className="btn btn--secondary" href="/auth/github/login">
          Log in with GitHub
        </a>
      </>
    );
  const needle = query.trim().toLowerCase();
  const shown = repos.filter((r) => r.full_name.toLowerCase().includes(needle));
  return (
    <>
      <h3 className="section-label">From GitHub ({user.login})</h3>
      <input
        type="search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search your repositories"
        aria-label="Search your GitHub repositories"
        className="search-field"
      />
      {error && (
        <p role="alert" className="note note--error">
          {error}{" "}
          {tokenRejected && <a href="/auth/github/login">Log in again</a>}
        </p>
      )}
      <ul className="source-list">
        {shown.map((repo) => (
          <li key={repo.html_url}>
            <button onClick={() => index(repo)} disabled={busy !== null} className="source-list__row">
              <span className="source-list__name">{repo.full_name}</span>
              <span className="source-list__host">{busy === repo.html_url ? "adding…" : repo.private ? "private" : "public"}</span>
            </button>
          </li>
        ))}
      </ul>
      {repos.length > 0 && shown.length === 0 && <p className="note">No repositories match “{query}”.</p>}
    </>
  );
}
