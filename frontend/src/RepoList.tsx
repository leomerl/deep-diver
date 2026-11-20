import { useEffect, useState } from "react";

import { listRepos, type RepoRead } from "./api";
import { GIVE_UP_MS, POLL_MS } from "./polling";
import { repoLabel } from "./repoLabel";

type Props = {
  selected: number | null;
  onSelect: (repo: RepoRead) => void;
  /** A URL just POSTed: the list polls until it shows up (indexed) or the give-up passes. */
  pendingUrl: string | null;
  onIndexed: (repo: RepoRead) => void;
};

// Deep link: #repo=<id> selects that repo once the list has loaded.
const HASH_REPO = /^#repo=(\d+)$/;

export function RepoList({ selected, onSelect, pendingUrl, onIndexed }: Props) {
  const [repos, setRepos] = useState<RepoRead[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [gaveUp, setGaveUp] = useState(false);

  useEffect(() => {
    const load = () => listRepos().then(setRepos, (e: Error) => setError(e.message));
    load();
    setGaveUp(false);
    if (pendingUrl === null) return;
    const started = Date.now();
    const timer = setInterval(() => {
      if (Date.now() - started < GIVE_UP_MS) return load();
      clearInterval(timer);
      setGaveUp(true);
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [pendingUrl]);

  useEffect(() => {
    const indexed = repos.find((r) => r.url === pendingUrl);
    if (indexed) onIndexed(indexed);
  }, [repos, pendingUrl, onIndexed]);

  useEffect(() => {
    const wanted = Number(HASH_REPO.exec(location.hash)?.[1]);
    const linked = repos.find((r) => r.id === wanted);
    if (selected === null && linked) onSelect(linked);
  }, [repos, selected, onSelect]);

  const select = (repo: RepoRead) => {
    location.hash = `repo=${repo.id}`;
    onSelect(repo);
  };

  if (error)
    return (
      <p role="alert" className="note note--error">
        Could not load repos: {error}
      </p>
    );
  return (
    <>
      <ul className="source-list">
        {repos.map((repo) => {
          const { name, host } = repoLabel(repo.url);
          return (
            <li key={repo.id}>
              <button onClick={() => select(repo)} aria-pressed={repo.id === selected} className="source-list__row">
                <span className="source-list__name">{name}</span>
                <span className="source-list__host">{host}</span>
              </button>
            </li>
          );
        })}
      </ul>
      {pendingUrl && !gaveUp && <p className="note">Indexing {pendingUrl}…</p>}
      {pendingUrl && gaveUp && (
        <p role="alert" className="note note--error">
          {pendingUrl} is still not indexed after 15 minutes; the job may have failed. Add it again to retry.
        </p>
      )}
    </>
  );
}
