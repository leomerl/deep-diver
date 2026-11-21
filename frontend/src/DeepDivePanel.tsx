import { type ReactNode, useEffect, useRef, useState } from "react";

import { ApiError, deepDiveHtmlUrl, type DeepDiveTarget, getDeepDive, requestDeepDive } from "./api";
import { GIVE_UP_MS, POLL_MS } from "./polling";

// checking: one GET on mount. missing: 404, offer to generate. waiting: POSTed, poll until a row exists.
type Status = "checking" | "missing" | "waiting" | "ready" | "gave_up";

type Props = { target: DeepDiveTarget; title: string; badge?: ReactNode; children?: ReactNode };

/** Mount with a key per target so the status resets when the selection changes. `children` describe the target. */
export function DeepDivePanel({ target, title, badge, children }: Props) {
  const { kind, id } = target;
  const [status, setStatus] = useState<Status>("checking");
  const [error, setError] = useState<string | null>(null);
  const frame = useRef<HTMLIFrameElement>(null);

  useEffect(() => {
    if (status !== "checking" && status !== "waiting") return;
    const started = Date.now();
    const check = () =>
      getDeepDive({ kind, id }).then(
        () => setStatus("ready"),
        (e: unknown) => {
          if (!(e instanceof ApiError && e.status === 404)) return setError(e instanceof ApiError ? e.message : "Could not reach the server.");
          if (status === "checking") setStatus("missing");
          else if (Date.now() - started >= GIVE_UP_MS) setStatus("gave_up");
        },
      );
    check();
    if (status !== "waiting") return;
    const timer = setInterval(check, POLL_MS);
    return () => clearInterval(timer);
  }, [kind, id, status]);

  const generate = async () => {
    setError(null);
    try {
      await requestDeepDive(target);
      setStatus("waiting");
    } catch (e) {
      setError(
        e instanceof ApiError && e.status === 503
          ? "The generation queue is down. Try again in a minute."
          : e instanceof ApiError
            ? e.message
            : "Could not start the deep dive. Try again.",
      );
    }
  };

  return (
    <div className="node-panel">
      <div className="node-panel__header">
        <h2 className="node-panel__title">{title}</h2>
        {badge}
        {status === "ready" && (
          <button onClick={() => frame.current?.requestFullscreen()} className="btn btn--secondary node-panel__fullscreen">
            Full screen
          </button>
        )}
      </div>
      <div className="node-panel__body">
        {children}
        {status === "checking" && <p className="note"><span className="spinner" aria-hidden="true" />Checking for a deep dive…</p>}
        {(status === "missing" || status === "gave_up") && (
          <button onClick={generate} className="btn">
            Generate deep dive
          </button>
        )}
        {status === "waiting" && <p className="note" role="status"><span className="spinner" aria-hidden="true" />Generating… this takes a few minutes.</p>}
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
        <iframe ref={frame} src={deepDiveHtmlUrl(target)} title={`Deep dive: ${title}`} sandbox="" className="node-panel__frame" />
      )}
    </div>
  );
}
