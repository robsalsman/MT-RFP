"""Keep the local machine awake while long automated work runs.

This asks the operating system's power manager to stay awake — Windows
SetThreadExecutionState, macOS `caffeinate`. It does NOT move the mouse,
press keys, or simulate any user activity; it only prevents the system and
display from sleeping so an assistant-driven job (USAC sync, document
download, response generation) can finish without the machine dozing off.

Deliberately NOT an activity/presence simulator — see the README note.

Uses a hold set so multiple callers (the manual UI toggle plus automatic
holds during sync/generation) compose: the OS is kept awake while any hold
is active, and released when the last one clears.
"""
import ctypes
import logging
import platform
import subprocess
import threading

log = logging.getLogger(__name__)

# Windows SetThreadExecutionState flags
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002

_lock = threading.Lock()
_holds: set[str] = set()
_keep_display = True
_win_thread: threading.Thread | None = None
_win_wake = threading.Event()
_mac_proc: subprocess.Popen | None = None


def status() -> dict:
    with _lock:
        return {"on": bool(_holds), "holds": sorted(_holds),
                "platform": platform.system(),
                "supported": platform.system() in ("Windows", "Darwin")}


def acquire(reason: str, keep_display: bool = True) -> dict:
    """Add a keep-awake hold. Idempotent per reason."""
    global _keep_display
    with _lock:
        was_active = bool(_holds)
        _holds.add(reason)
        _keep_display = keep_display
        if not was_active:
            _start_locked()
        elif platform.system() == "Windows":
            _win_wake.set()  # re-assert flags (display pref may have changed)
    return status()


def release(reason: str) -> dict:
    """Remove a hold; stops keep-awake when the last hold clears."""
    with _lock:
        _holds.discard(reason)
        if not _holds:
            _stop_locked()
    return status()


def set_manual(on: bool) -> dict:
    return acquire("manual") if on else release("manual")


class hold:
    """Context manager for an automatic hold around a long operation."""

    def __init__(self, reason: str):
        self.reason = reason

    def __enter__(self):
        acquire(self.reason)
        return self

    def __exit__(self, *exc):
        release(self.reason)
        return False


# --- platform backends (call with _lock held) ---------------------------

def _start_locked() -> None:
    system = platform.system()
    if system == "Windows":
        global _win_thread
        _win_wake.clear()
        _win_thread = threading.Thread(target=_win_loop, daemon=True,
                                       name="keepawake")
        _win_thread.start()
    elif system == "Darwin":
        global _mac_proc
        args = ["caffeinate", "-i"] + (["-d"] if _keep_display else [])
        try:
            _mac_proc = subprocess.Popen(args)
        except Exception as e:
            log.warning("caffeinate failed: %s", e)
    else:
        log.info("keep-awake not supported on %s; toggle is a no-op", system)


def _stop_locked() -> None:
    system = platform.system()
    if system == "Windows":
        _win_wake.set()  # loop clears state on its thread and exits
    elif system == "Darwin":
        global _mac_proc
        if _mac_proc:
            _mac_proc.terminate()
            _mac_proc = None


def _win_loop() -> None:
    k = ctypes.windll.kernel32
    while True:
        with _lock:
            active = bool(_holds)
            flags = ES_CONTINUOUS
            if active:
                flags |= ES_SYSTEM_REQUIRED
                if _keep_display:
                    flags |= ES_DISPLAY_REQUIRED
        k.SetThreadExecutionState(flags)
        if not active:
            return  # ES_CONTINUOUS alone cleared the request; exit thread
        _win_wake.wait(30)  # re-assert periodically; wake early on change
        _win_wake.clear()
