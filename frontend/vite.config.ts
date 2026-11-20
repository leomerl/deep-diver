import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// The API is proxied, so the browser sees one origin: no CORS middleware and the deep dive CSP behaves as in prod.
const API = "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/repos": API, "/nodes": API, "/auth": API } },
  test: { include: ["tests/**/*.test.ts"] },
});
