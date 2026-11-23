import { useEffect, useState } from "react";

import { type DeepDiveListItem, listDeepDives } from "./api";
import { Notebook } from "./Notebook";
import { repoLabel, WHOLE_REPO } from "./repoLabel";

/** Every written notebook, grouped by repo; picking one opens it here, runnable. */
export function NotebookList() {
  const [dives, setDives] = useState<DeepDiveListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<DeepDiveListItem | null>(null);

  useEffect(() => {
    // The deep dive list already carries notebook_key: no route of its own needed.
    listDeepDives().then((all) => setDives(all.filter((dive) => dive.notebook_key)), (e: Error) => setError(e.message));
  }, []);

  if (open)
    return (
      <>
        <button onClick={() => setOpen(null)} className="btn btn--secondary notebooks__back">
          All notebooks
        </button>
        <p className="note">
          {repoLabel(open.repo_url).name} · {open.node_name ?? WHOLE_REPO}
          {open.stale && <span className="badge badge--stale">Older commit</span>}
        </p>
        {/* Unmounted on the way back, which stops its Python worker. */}
        <Notebook key={open.id} deepDiveId={open.id} />
      </>
    );
  if (error)
    return (
      <p role="alert" className="note note--error">
        Could not load notebooks: {error}
      </p>
    );
  if (dives === null) return <p className="note">Loading notebooks…</p>;
  if (dives.length === 0) return <p className="note">No notebooks yet. Open a deep dive and click Write notebook.</p>;

  // The API sorts newest first and a Map keeps insertion order, so each group stays newest first.
  const byRepo = new Map<string, DeepDiveListItem[]>();
  for (const dive of dives) byRepo.set(dive.repo_url, [...(byRepo.get(dive.repo_url) ?? []), dive]);

  return (
    <>
      {[...byRepo].map(([url, group]) => (
        <section key={url}>
          <h2 className="section-label">{repoLabel(url).name}</h2>
          <ul className="source-list">
            {group.map((dive) => (
              <li key={dive.id}>
                <button onClick={() => setOpen(dive)} className="source-list__row">
                  <span className="source-list__name">
                    {dive.node_name ?? WHOLE_REPO}
                    {dive.stale && <span className="badge badge--stale">Older commit</span>}
                  </span>
                  <span className="source-list__host">{new Date(dive.created_at).toLocaleDateString()}</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </>
  );
}
