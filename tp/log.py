# log.py
# -------------------------------------------------------------------
# tiny unified logging helper for the project
# prints to stdout immediately, qt-safe, no weird formatting
# -------------------------------------------------------------------

import sys
import threading

class Logger:
    _lock = threading.Lock()

    def _write(self, level: str, msg: str):
        with self._lock:
            sys.stdout.write(f"[{level}] {msg}\n")
            sys.stdout.flush()

    def info(self, msg: str):
        self._write("INFO", msg)

    def warn(self, msg: str):
        self._write("WARN", msg)

    def error(self, msg: str):
        self._write("ERROR", msg)

log = Logger()
