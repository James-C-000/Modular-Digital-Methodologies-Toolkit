"""Ask before the native window closes, but only while a job is running.

Closing the window ends MDMT, so a running job would be lost.  pywebview can
ask "Quit anyway?" (its window's confirm_close flag), but asking on every
close would be a nuisance; this switches the flag on while jobs run.
"""

QUESTION = "MDMT is still working on a job. Quit anyway? Unfinished work will be lost."


def install(jobs, send):
    """Call send(True/False) whenever the 'any job running' state changes."""
    state = {"on": False}

    def sync():
        on = bool(jobs.running())
        if on != state["on"]:
            state["on"] = on
            send(on)

    jobs.on_change(sync)
    return sync


def send_to_native_window(on: bool):
    """Set confirm_close on the pywebview window, which lives in NiceGUI's window process.

    Uses NiceGUI's queue of window method calls (its window proxy does not
    expose attributes); pinned NiceGUI 3.18.  pywebview reads the flag when
    the window is about to close, on Windows and macOS alike.
    """
    from nicegui.native import native
    if getattr(native, "method_queue", None) is not None:
        native.method_queue.put(("__setattr__", ("confirm_close", on), {}))
