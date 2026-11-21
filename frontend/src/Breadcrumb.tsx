import { Panel } from "@xyflow/react";

import type { ScopeNode } from "./scopeView";

type Props = { repoName: string; trail: ScopeNode[]; onNavigate: (scopeId: number | null) => void };

/** Repo › area › sub-area, floating over the canvas; the last crumb is the current scope. */
export function Breadcrumb({ repoName, trail, onNavigate }: Props) {
  const crumbs = [{ id: null, name: repoName }, ...trail.map((n) => ({ id: n.id, name: n.name }))];
  return (
    <Panel position="top-left">
      <nav className="crumbs" aria-label="Area scope">
        <span className="crumbs__depth">Depth {trail.length}</span>
        {crumbs.map((c, i) => (
          <span key={c.id ?? REPO_CRUMB_KEY} className="crumbs__item">
            {i > 0 && <span className="crumbs__sep">›</span>}
            <button
              className="crumbs__link"
              onClick={() => onNavigate(c.id)}
              disabled={i === crumbs.length - 1}
              aria-current={i === crumbs.length - 1 ? "location" : undefined}
            >
              {c.name}
            </button>
          </span>
        ))}
      </nav>
    </Panel>
  );
}

const REPO_CRUMB_KEY = "repo";
