import { useEffect, useState } from "react";

import { listRepos, reindexRepo, type RepoRead } from "./api";
import { GIVE_UP_MS, POLL_MS } from "./polling";

// idle: the button. current: HEAD is already the indexed commit. waiting: queued, poll until the commit changes.
type Status = "idle" | "current" | "waiting" | "gaveUp";

type Props = { repo: RepoRead; onReindexed: (repo: RepoRead) => void };

export function Reindex({ repo, onReindexed }: Props) {
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (status !== "waiting") return;
    const started = Date.now();
    const timer = setInterval(() => {
      if (Date.now() - started > GIVE_UP_MS) {
        clearInterval(timer);
        setStatus("gaveUp");
        return;
      }
      listRepos().then((repos) => {
        const latest = repos.find((r) => r.id === repo.id);
        // Any new commit, not only the one the API named: HEAD can move again before the worker clones.
        if (latest && latest.commit_sha !== repo.commit_sha) onReindexed(latest);
      }, (e: Error) => setError(e.message));
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [status, repo, onReindexed]);

  const start = () => {
    setError(null);
    reindexRepo(repo.id).then(
      (target) => setStatus(target.commit_sha === repo.commit_sha ? "current" : "waiting"),
      (e: Error) => setError(e.message),
    );
  };

  return (
    <div className="reindex">
      {status === "waiting" ? (
        <p className="note" role="status"><span className="spinner" aria-hidden="true" />Re-indexing at the latest commit…</p>
      ) : (
        <button onClick={start} className="btn btn--secondary">
          Re-index
        </button>
      )}
      {status === "current" && <p className="note">Already at the latest commit ({repo.commit_sha?.slice(0, 7)}).</p>}
      {status === "gaveUp" && (
        <p role="alert" className="note note--error">
          Still not re-indexed after 15 minutes; the job may have failed.
        </p>
      )}
      {error && (
        <p role="alert" className="note note--error">
          {error}
        </p>
      )}
    </div>
  );
}
