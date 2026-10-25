"""Ask before the native window closes, but only while a job is running.

Closing the window ends MDMT, so a running job would be lost.  pywebview can
ask "Quit anyway?" (its window's confirm_close flag), but asking on every
close would be a nuisance; this switches the flag on while jobs run.
"""
import threading
import time

QUESTION = "MDMT is still working on a job. Quit anyway? Unfinished work will be lost."


def install(jobs, send):
    """Call send(True/False) whenever the 'any job running' state changes."""
    state = {"on": False}
    lock = threading.Lock()   # jobs end in their own threads: two may report at once

    def sync():
        with lock:
            on = bool(jobs.running())
            if on != state["on"]:
                state["on"] = on
                send(on)

    jobs.on_change(sync)
    return sync


class _NativeSender:
    """Sends the latest wanted confirm_close value to the window, one call at a time.

    NiceGUI runs each queued window call in a thread of its own, so two calls
    in quick succession (a job that fails at once: True, then False) could be
    applied in either order.  Calls go out from one thread, at most every
    SPACING seconds, and only when the value differs from the last one sent.
    """

    SPACING = 0.5

    def __init__(self, put):
        self._put = put
        self._wanted = self._sent = False
        self._changed = threading.Event()
        threading.Thread(target=self._run, name="close-guard", daemon=True).start()

    def want(self, on: bool):
        self._wanted = on
        self._changed.set()

    def _run(self):
        while True:
            self._changed.wait()
            self._changed.clear()
            on = self._wanted
            if on != self._sent:
                self._put(on)
                self._sent = on
                time.sleep(self.SPACING)


_sender = None


def send_to_native_window(on: bool):
    """Set confirm_close on the pywebview window, which lives in NiceGUI's window process.

    Uses NiceGUI's queue of window method calls (its window proxy does not
    expose attributes); pinned NiceGUI 3.18.  pywebview reads the flag when
    the window is about to close, on Windows and macOS alike.
    """
    global _sender
    from nicegui.native import native
    if getattr(native, "method_queue", None) is None:
        return
    if _sender is None:
        _sender = _NativeSender(lambda value: native.method_queue.put(("__setattr__", ("confirm_close", value), {})))
    _sender.want(on)
