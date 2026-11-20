import { useCallback, useEffect, useState } from "react";

import { AddRepo } from "./AddRepo";
import { getMap, type RepoMap, type RepoRead } from "./api";
import { GitHubRepos } from "./GitHubRepos";
import { MapCanvas } from "./MapCanvas";
import { NodePanel } from "./NodePanel";
import { RepoList } from "./RepoList";

export function App() {
  const [repo, setRepo] = useState<RepoRead | null>(null);
  const [pendingUrl, setPendingUrl] = useState<string | null>(null);
  const [map, setMap] = useState<RepoMap | null>(null);
  const [nodeId, setNodeId] = useState<number | null>(null);
  const onIndexed = useCallback((indexed: RepoRead) => {
    setPendingUrl(null);
    setRepo(indexed);
  }, []);

  useEffect(() => {
    setMap(null);
    setNodeId(null);
    if (repo !== null) getMap(repo.id).then(setMap);
  }, [repo]);

  const node = map?.nodes.find((n) => n.id === nodeId);

  return (
    <main className={node ? "app app--panel" : "app"}>
      <aside className="sidebar">
        <h1 className="sidebar__title">deep-diver</h1>
        <AddRepo onAdded={setPendingUrl} />
        <GitHubRepos onAdded={setPendingUrl} />
        <h2 className="section-label">Repositories</h2>
        <RepoList selected={repo?.id ?? null} onSelect={setRepo} pendingUrl={pendingUrl} onIndexed={onIndexed} />
      </aside>
      <section className="canvas">
        {map && repo !== null && (
          <MapCanvas key={repo.id} repo={repo} map={map} selectedId={nodeId} onSelect={setNodeId} />
        )}
        {!map && <p className="note canvas__empty">{repo === null ? "Select a repository to see its map" : "Loading map…"}</p>}
      </section>
      {node && (
        <aside className="panel">
          <NodePanel key={node.id} node={node} />
        </aside>
      )}
    </main>
  );
}
