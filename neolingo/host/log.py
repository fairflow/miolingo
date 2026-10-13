import threading
import time

from . import paths

_lock = threading.Lock()


def log(msg):
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + msg
    with _lock:
        try:
            with open(paths.LOG, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass
