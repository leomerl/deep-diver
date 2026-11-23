import { cpSync } from "node:fs";
import { resolve } from "node:path";

import react from "@vitejs/plugin-react";
import { type Plugin } from "vite";
import { defineConfig } from "vitest/config";

// The API is proxied, so the browser sees one origin: no CORS middleware and the deep dive CSP behaves as in prod.
const API = "http://localhost:8000";

// Pyodide is served from our own origin, never a CDN: the notebook worker's CSP lets it fetch only /pyodide/.
// Only the runtime files: packages aren't shipped, and the notebook validator allows no imports beyond the stdlib.
const PYODIDE_FILES = ["pyodide.asm.mjs", "pyodide.asm.wasm", "python_stdlib.zip", "pyodide-lock.json"];

const copyPyodide = (): Plugin => ({
  name: "copy-pyodide",
  apply: "build",
  writeBundle({ dir }) {
    for (const file of PYODIDE_FILES) cpSync(resolve("node_modules/pyodide", file), resolve(dir ?? "dist", "pyodide", file));
  },
});

export default defineConfig({
  plugins: [react(), copyPyodide()],
  server: { proxy: { "/repos": API, "/nodes": API, "/auth": API, "/deep-dives": API, "/jobs": API } },
  // Pyodide finds its own files at run time; pre-bundling would move pyodide.mjs away from them.
  optimizeDeps: { exclude: ["pyodide"] },
  // A fixed name, no content hash: the API matches it to send the worker's CSP (app/api/frontend_files.py).
  worker: { format: "es", rollupOptions: { output: { entryFileNames: "assets/notebook-worker.js" } } },
  test: { include: ["tests/**/*.test.ts"] },
});
