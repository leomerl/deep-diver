# Deep dive pages run no scripts and load nothing but inline styles and (later) https media.
# Defense in depth on top of autoescaping: if model or repo text ever slipped through, it still can't execute.
HTML_CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src data: https:; media-src https:"
