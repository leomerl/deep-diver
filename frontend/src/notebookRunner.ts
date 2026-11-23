export type RunRequest = { id: number; code: string };
export type RunResult = { id: number; ok: boolean; output: string };
export type Runner = { run: (code: string) => Promise<RunResult>; reset: () => void };

// Covers the first run's Pyodide start-up too. Past it the worker is killed: Python can't be interrupted from outside
// without SharedArrayBuffer, which needs cross-origin isolation headers on the whole app.
export const TIMEOUT_MS = 30_000;

/** One Python interpreter shared by every cell, started on the first run. The caller runs one cell at a time:
 * the worker shares one output buffer, so overlapping runs would mix their output. */
export function createRunner(): Runner {
  let worker: Worker | null = null;
  let nextId = 0;

  const reset = () => {
    worker?.terminate();
    worker = null;
  };

  const run = (code: string) =>
    new Promise<RunResult>((resolve) => {
      const current = (worker ??= new Worker(new URL("./notebookWorker.ts", import.meta.url), { type: "module" }));
      const id = nextId++;
      const finish = (result: RunResult) => {
        clearTimeout(timer);
        current.removeEventListener("message", onMessage);
        current.removeEventListener("error", onError);
        resolve(result);
      };
      const onMessage = ({ data }: MessageEvent<RunResult>) => data.id === id && finish(data);
      // Fires when the worker script or Pyodide itself fails to load, which never produces a message.
      const onError = () => {
        reset();
        finish({ id, ok: false, output: "The Python runtime failed to start. Reload the page and try again." });
      };
      const timer = setTimeout(() => {
        reset();
        finish({ id, ok: false, output: `Stopped after ${TIMEOUT_MS / 1000} s. Python restarted, so run the cells above again first.` });
      }, TIMEOUT_MS);
      current.addEventListener("message", onMessage);
      current.addEventListener("error", onError);
      current.postMessage({ id, code } satisfies RunRequest);
    });

  return { run, reset };
}
