// Runs notebook cells in Pyodide, off the main thread. Loaded only through notebookRunner.ts.
// Isolation lives in this file's response header (NOTEBOOK_WORKER_CSP): it can't fetch the API, so model-written
// code can't act with the reader's session.
import { loadPyodide, type PyodideAPI } from "pyodide";

import type { RunRequest, RunResult } from "./notebookRunner";

// Dev serves the package straight from node_modules; the build copies it to /pyodide/ (vite.config.ts).
const INDEX_URL = import.meta.env.DEV ? "/node_modules/pyodide/" : "/pyodide/";

let output: string[] = [];
const ready: Promise<PyodideAPI> = loadPyodide({ indexURL: INDEX_URL }).then((pyodide) => {
  const collect = { batched: (line: string) => output.push(line) };
  pyodide.setStdout(collect);
  pyodide.setStderr(collect);
  return pyodide;
});

const run = async ({ id, code }: RunRequest): Promise<RunResult> => {
  output = [];
  try {
    await (await ready).runPythonAsync(code);
    return { id, ok: true, output: output.join("\n") };
  } catch (e) {
    // A PythonError's message is the full traceback.
    return { id, ok: false, output: [...output, e instanceof Error ? e.message : String(e)].join("\n") };
  }
};

self.onmessage = async ({ data }: MessageEvent<RunRequest>) => postMessage(await run(data));
