"""Optional-library loader (RAW-00055 option A): works under `python3 -I`, which hides the user site."""
import importlib
import os
import site
import sys

from exam_engine.ingest.schema import IngestError


def user_site():
    """The user site folder if it exists, else None."""
    try:
        path = site.getusersitepackages()
    except Exception:  # noqa: BLE001 - no user site is a normal case
        return None
    return path if isinstance(path, str) and os.path.isdir(path) else None


def load(module, pip):
    """Import `module`; on ImportError retry once with the user site appended (never the cwd)."""
    try:
        return importlib.import_module(module)
    except ImportError:
        pass
    path = user_site()
    if path and path not in sys.path:
        sys.path.append(path)
    try:
        return importlib.import_module(module)
    except ImportError:
        raise IngestError("missing_dependency", "pip install %s" % pip)
