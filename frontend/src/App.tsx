import { useCallback, useEffect, useState } from "react";

import { AddRepoSheet } from "./AddRepoSheet";
import { getMap, type RepoMap, type RepoRead } from "./api";
import { DeepDiveList } from "./DeepDiveList";
import { DeepDivePanel } from "./DeepDivePanel";
import { REPO_NODE_ID, type Selection } from "./layout";
import { MapCanvas } from "./MapCanvas";
import { Practice } from "./Practice";
import { Reindex } from "./Reindex";
import { repoLabel } from "./repoLabel";
import { RepoList } from "./RepoList";
import { Settings } from "./Settings";

const VIEWS = { map: "Map", deepDives: "Deep dives", practice: "Practice", settings: "Settings" } as const;
type View = keyof typeof VIEWS;

export function App() {
  const [view, setView] = useState<View>("map");
  const [repo, setRepo] = useState<RepoRead | null>(null);
  const [pendingUrl, setPendingUrl] = useState<string | null>(null);
  const [map, setMap] = useState<RepoMap | null>(null);
  const [selected, setSelected] = useState<Selection>(null);
  const [sidebarHidden, setSidebarHidden] = useState(false);
  const [adding, setAdding] = useState(false);
  const onIndexed = useCallback((indexed: RepoRead) => {
    setPendingUrl(null);
    setRepo(indexed);
  }, []);
  // A repo only shows on the map, so picking one from another view switches to it.
  const openRepo = useCallback((picked: RepoRead) => {
    setRepo(picked);
    setView("map");
  }, []);

  useEffect(() => {
    setMap(null);
    setSelected(null);
    if (repo !== null) getMap(repo.id).then(setMap);
  }, [repo]);

  const node = view === "map" ? map?.nodes.find((n) => n.id === selected) : undefined;
  const rootRepo = view === "map" && map && selected === REPO_NODE_ID ? repo : null;

  const classes = ["app", (node || rootRepo) && "app--panel", sidebarHidden && "app--sidebar-hidden"];
  return (
    <main className={classes.filter(Boolean).join(" ")}>
      <aside className="sidebar">
        <div className="sidebar__header">
          {!sidebarHidden && <h1 className="sidebar__title">deep-diver</h1>}
          <button
            onClick={() => setSidebarHidden(!sidebarHidden)}
            aria-label={sidebarHidden ? "Show sidebar" : "Hide sidebar"}
            aria-expanded={!sidebarHidden}
            title={sidebarHidden ? "Show sidebar" : "Hide sidebar"}
            className="icon-btn"
          >
            <SidebarIcon />
          </button>
        </div>
        <nav hidden={sidebarHidden}>
          <ul className="source-list">
            {(Object.keys(VIEWS) as View[]).map((v) => (
              <li key={v}>
                <button onClick={() => setView(v)} aria-pressed={v === view} className="source-list__row">
                  <span className="source-list__name">{VIEWS[v]}</span>
                </button>
              </li>
            ))}
          </ul>
        </nav>
        <div hidden={sidebarHidden}>
          <h2 className="section-label">Repositories</h2>
          <RepoList selected={repo?.id ?? null} onSelect={openRepo} pendingUrl={pendingUrl} onIndexed={onIndexed} />
          <button onClick={() => setAdding(true)} className="btn btn--secondary sidebar__add">
            Add Repository…
          </button>
        </div>
      </aside>
      <AddRepoSheet open={adding} onClose={() => setAdding(false)} onAdded={setPendingUrl} />
      {view === "deepDives" && (
        <section className="page">
          <div className="page__inner">
            <DeepDiveList />
          </div>
        </section>
      )}
      {view === "practice" && (
        <section className="page">
          <div className="page__inner">
            <Practice />
          </div>
        </section>
      )}
      {view === "settings" && (
        <section className="page">
          <div className="page__inner">
            <Settings />
          </div>
        </section>
      )}
      <section className="canvas" hidden={view !== "map"}>
        {map && repo !== null && (
          <MapCanvas key={repo.id} repo={repo} map={map} selectedId={selected} onSelect={setSelected} />
        )}
        {!map && <p className="note canvas__empty">{repo === null ? "Select a repository to see its map" : "Loading map…"}</p>}
      </section>
      {node && (
        <aside className="panel">
          <DeepDivePanel
            key={node.id}
            target={{ kind: "nodes", id: node.id }}
            title={node.name}
            badge={
              node.grouping === "fallback" ? (
                <span className="badge badge--folder">Folder</span>
              ) : (
                <span className="badge badge--llm">AI-grouped</span>
              )
            }
          >
            {node.description && <p className="node-panel__description">{node.description}</p>}
            <ul className="path-list">
              {node.paths.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          </DeepDivePanel>
        </aside>
      )}
      {rootRepo && (
        <aside className="panel">
          <DeepDivePanel key={REPO_NODE_ID} target={{ kind: "repos", id: rootRepo.id }} title={repoLabel(rootRepo.url).name}>
            <p className="node-panel__description">The whole repository: how its top-level areas fit together.</p>
            {/* A new repo object reloads the map (the effect on `repo`), which also closes this panel. */}
            <Reindex repo={rootRepo} onReindexed={setRepo} />
          </DeepDivePanel>
        </aside>
      )}
    </main>
  );
}

/** Outline in the style of SF Symbols' sidebar.left; decorative, the button carries the label. */
function SidebarIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.4" aria-hidden="true">
      <rect x="1.5" y="3" width="15" height="12" rx="2.5" />
      <path d="M6.5 3v12" />
    </svg>
  );
}
