import { useEffect, useState } from "react";

import { ApiError, deepDiveHtmlUrl, getDeepDive, type NodeRead, requestDeepDive } from "./api";
import { GIVE_UP_MS, POLL_MS } from "./polling";

// checking: one GET on mount. missing: 404, offer to generate. waiting: POSTed, poll until a row exists.
type Status = "checking" | "missing" | "waiting" | "ready" | "gave_up";

/** Mount with `key={node.id}` so the status resets when the selection changes. */
export function NodePanel({ node }: { node: NodeRead }) {
  const [status, setStatus] = useState<Status>("checking");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (status !== "checking" && status !== "waiting") return;
    const started = Date.now();
    const check = () =>
      getDeepDive(node.id).then(
        () => setStatus("ready"),
        (e: unknown) => {
          if (!(e instanceof ApiError && e.status === 404)) return setError(String(e));
          if (status === "checking") setStatus("missing");
          else if (Date.now() - started >= GIVE_UP_MS) setStatus("gave_up");
        },
      );
    check();
    if (status !== "waiting") return;
    const timer = setInterval(check, POLL_MS);
    return () => clearInterval(timer);
  }, [node.id, status]);

  const generate = async () => {
    setError(null);
    try {
      await requestDeepDive(node.id);
      setStatus("waiting");
    } catch (e) {
      setError(e instanceof ApiError && e.status === 503 ? "Queue unavailable, try again" : String(e));
    }
  };

  return (
    <div className="node-panel">
      <div className="node-panel__header">
        <h2 className="node-panel__title">{node.name}</h2>
        {node.grouping === "fallback" ? (
          <span className="badge badge--folder">Folder</span>
        ) : (
          <span className="badge badge--llm">LLM</span>
        )}
      </div>
      <div className="node-panel__body">
        {node.description && <p className="node-panel__description">{node.description}</p>}
        <ul className="path-list">
          {node.paths.map((p) => (
            <li key={p}>{p}</li>
          ))}
        </ul>
        {status === "checking" && <p className="note">Checking for a deep dive…</p>}
        {(status === "missing" || status === "gave_up") && (
          <button onClick={generate} className="btn">
            Generate deep dive
          </button>
        )}
        {status === "waiting" && <p className="note">Generating… this takes a few minutes.</p>}
        {status === "gave_up" && (
          <p role="alert" className="note note--error">
            No deep dive after 15 minutes; the job may have failed. Try again.
          </p>
        )}
        {error && (
          <p role="alert" className="note note--error">
            {error}
          </p>
        )}
      </div>
      {status === "ready" && (
        // The page's own CSP forbids scripts; `sandbox` says the same from the embedding side.
        <iframe src={deepDiveHtmlUrl(node.id)} title={`Deep dive: ${node.name}`} sandbox="" className="node-panel__frame" />
      )}
    </div>
  );
}
