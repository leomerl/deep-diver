# Deep dive pages run no scripts and load nothing but inline styles and (later) https media.
# Defense in depth on top of autoescaping: if model or repo text ever slipped through, it still can't execute.
HTML_CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src data: https:; media-src https:"

# The notebook runner's Web Worker runs model-written Python, and the model read untrusted repo text. A worker on our
# origin would send the session cookie with any fetch, so it may load scripts from us and fetch only Pyodide's own
# files: it can't call the API. A path needs a full origin in CSP ('self' takes none), so the API fills it in.
NOTEBOOK_WORKER_CSP = "default-src 'none'; script-src 'self' 'wasm-unsafe-eval'; connect-src {origin}/pyodide/"
