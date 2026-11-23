from app.deep_dive.page_text import page_text


def test_keeps_headings_prose_and_code_without_line_numbers_styles_or_diagrams() -> None:
    html = (
        "<html><head><title>T</title><style>.a{}</style></head><body>"
        "<h2>How a job moves</h2><p>One <code>XADD</code> per job.</p>"
        '<figure><svg viewBox="0 0 1 1"><text>node a</text><path d="M0"/></svg></figure>'
        '<figcaption><code>app/queue.py<span class="lines">:1-2</span></code></figcaption>'
        '<pre><code><span class="ln">1</span><span class="k">def</span> enqueue():\n<span class="ln">2</span>    pass\n</code></pre>'
        "</body></html>"
    )
    assert page_text(html) == "How a job moves\n\nOne XADD per job.\n\napp/queue.py:1-2\n\ndef enqueue():\n    pass"
