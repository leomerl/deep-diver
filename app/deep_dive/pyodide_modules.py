import sys

# Modules a notebook cell may import: what runs in Pyodide, the browser Python the notebook executes in.
# Pyodide ships the standard library minus what needs an OS the browser doesn't have (processes, threads, sockets,
# a terminal, a GUI). asyncio works, so a cell that would use a thread can use a task instead.
# No third-party packages: Pyodide fetches their wheels from a CDN, and the runner's worker may only fetch Pyodide's
# own files from our origin.
UNAVAILABLE_IN_PYODIDE = frozenset({
    "_thread", "concurrent", "curses", "dbm", "ensurepip", "idlelib", "lib2to3", "multiprocessing", "pydoc_data",
    "readline", "socket", "subprocess", "threading", "tkinter", "turtle", "turtledemo", "venv", "webbrowser",
})

# shortcut: the worker's stdlib list stands in for Pyodide's (CPython 3.14); pin a list if a module ever differs.
ALLOWED_MODULES = frozenset(sys.stdlib_module_names) - UNAVAILABLE_IN_PYODIDE
