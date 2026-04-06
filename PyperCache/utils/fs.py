"""Filesystem helpers: directory creation and platform file-explorer launcher."""

import os
import sys
import subprocess
from pathlib import Path


def ensure_dirs_exist(path: str) -> None:
    """Create all intermediate directories required for *path* if they don't exist.

    If the final component of *path* contains a ``.`` it is treated as a
    filename and only its parent directories are created; otherwise the full
    path is treated as a directory tree and created in its entirety.

    Args:
        path: A file or directory path whose parent directories should exist.
    """
    p = Path(path)

    if len(p.parts) <= 1:
        return  # Nothing to create for a bare filename/single component

    # Determine whether the last part looks like a file (has an extension).
    if "." in p.parts[-1]:
        dir_path = Path(*p.parts[:-1])
    else:
        dir_path = p

    if not dir_path.exists():
        os.makedirs(dir_path)


def open_folder(path: Path) -> None:
    """Open *path* in the system file explorer, cross-platform.

    Args:
        path: Directory to open.
    """
    path = path.resolve()
    if sys.platform == "win32":
        os.startfile(str(path))
    elif sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
    else:
        subprocess.run(["xdg-open", str(path)], check=False)
