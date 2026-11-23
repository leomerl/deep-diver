import { type ReactNode, useEffect, useMemo, useState } from "react";

import { ApiError, getNotebook, type NotebookBase } from "./api";
import { createRunner } from "./notebookRunner";
import { tokenize } from "./pythonTokens";

type CellRun = { status: "running" } | { status: "done"; ok: boolean; output: string };

/** Backticks become <code>, the page's own convention. React escapes the rest, so model text stays text. */
const withCode = (text: string): ReactNode[] =>
  text.split(/(`[^`]+`)/).map((part, i) => (part.startsWith("`") && part.endsWith("`") && part.length > 1 ? <code key={i}>{part.slice(1, -1)}</code> : part));

/** The deep dive's runnable notebook: each cell's explanation, its editable code, and its output. */
export function Notebook({ deepDiveId }: { deepDiveId: number }) {
  const [notebook, setNotebook] = useState<NotebookBase | null>(null);
  const [codes, setCodes] = useState<string[]>([]);
  const [runs, setRuns] = useState<Record<number, CellRun>>({});
  const [error, setError] = useState<string | null>(null);
  const runner = useMemo(createRunner, []);

  useEffect(() => () => runner.reset(), [runner]); // the worker dies with the panel
  useEffect(() => {
    getNotebook(deepDiveId).then(
      (loaded) => {
        setNotebook(loaded);
        setCodes(loaded.cells.map((cell) => cell.code));
      },
      (e: unknown) => setError(e instanceof ApiError ? e.message : "Could not load the notebook."),
    );
  }, [deepDiveId]);

  // One cell at a time: the worker shares one output buffer (notebookRunner.ts).
  const busy = Object.values(runs).some((run) => run.status === "running");

  const runCell = async (index: number): Promise<boolean> => {
    setRuns((prev) => ({ ...prev, [index]: { status: "running" } }));
    const { ok, output } = await runner.run(codes[index] ?? "");
    setRuns((prev) => ({ ...prev, [index]: { status: "done", ok, output } }));
    return ok;
  };

  const runAll = async () => {
    for (const index of codes.keys()) if (!(await runCell(index))) return; // later cells depend on earlier ones
  };

  const restart = () => {
    runner.reset();
    setRuns({});
  };

  if (error) return <p role="alert" className="note note--error notebook__status">{error}</p>;
  if (!notebook) return <p className="note notebook__status"><span className="spinner" aria-hidden="true" />Loading the notebook…</p>;

  return (
    <div className="notebook">
      <div className="notebook__toolbar">
        <h3 className="notebook__title">{withCode(notebook.title)}</h3>
        <button onClick={runAll} disabled={busy} className="btn">Run all</button>
        <button onClick={restart} disabled={busy} className="btn btn--secondary">Restart</button>
      </div>
      <p className="note notebook__hint">Python runs in your browser. Cells share one interpreter, so run them in order. Edit any code and run it again.</p>
      {notebook.cells.map((cell, index) => {
        const run = runs[index];
        return (
          <section key={index} className="notebook__cell" aria-label={`Step ${index + 1}`}>
            {cell.explanation.split(/\n\s*\n/).map((paragraph, i) => <p key={i} className="notebook__explanation">{withCode(paragraph)}</p>)}
            {cell.mirrors && <p className="notebook__mirrors">Rebuilds <code>{cell.mirrors}</code></p>}
            <div className="notebook__editor">
              <pre aria-hidden="true" className="notebook__highlight">
                {tokenize(codes[index] ?? "").map((token, i) => (token.kind ? <span key={i} className={`tok--${token.kind}`}>{token.text}</span> : token.text))}
                {"\n"}
              </pre>
              <textarea
                value={codes[index] ?? ""}
                onChange={(e) => setCodes((prev) => prev.map((code, i) => (i === index ? e.target.value : code)))}
                spellCheck={false}
                aria-label={`Code for step ${index + 1}`}
                className="notebook__code"
              />
            </div>
            <button onClick={() => runCell(index)} disabled={busy} className="btn btn--secondary notebook__run">
              {run?.status === "running" ? "Running…" : "Run"}
            </button>
            {run?.status === "done" && (
              <output className={run.ok ? "notebook__output" : "notebook__output notebook__output--error"}>{run.output || "(no output)"}</output>
            )}
          </section>
        );
      })}
    </div>
  );
}
