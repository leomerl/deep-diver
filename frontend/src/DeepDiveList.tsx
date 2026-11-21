import { useEffect, useState } from "react";

import { type DeepDiveListItem, deepDivePageUrl, listDeepDives } from "./api";
import { repoLabel, WHOLE_REPO } from "./repoLabel";

export function DeepDiveList() {
  const [dives, setDives] = useState<DeepDiveListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listDeepDives().then(setDives, (e: Error) => setError(e.message));
  }, []);

  if (error)
    return (
      <p role="alert" className="note note--error">
        Could not load deep dives: {error}
      </p>
    );
  if (dives === null) return <p className="note">Loading deep dives…</p>;
  if (dives.length === 0) return <p className="note">No deep dives yet. Generate one from a node or the repo card on the map.</p>;

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
                {/* A new tab still gets the page's CSP header from the API. */}
                <a href={deepDivePageUrl(dive.id)} target="_blank" rel="noopener" className="source-list__row">
                  <span className="source-list__name">
                    {dive.node_name ?? WHOLE_REPO}
                    {dive.stale && <span className="badge badge--stale">Older commit</span>}
                  </span>
                  <span className="source-list__host">{new Date(dive.created_at).toLocaleDateString()}</span>
                </a>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </>
  );
}
