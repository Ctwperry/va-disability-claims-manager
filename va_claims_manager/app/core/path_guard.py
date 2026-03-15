"""
Path validation utilities for document filepaths loaded from the database.

Filepaths are user-supplied strings stored in SQLite. Before passing them to
OS APIs (os.startfile, shutil.copy2) we must verify they refer to a real,
non-symlinked file or directory. Symlinks are rejected outright: a database
row modified by an attacker could point a symlink at /etc/passwd or any other
sensitive path, causing it to be copied into an export package.
"""
from pathlib import Path


def safe_file_path(path: Path) -> Path | None:
    """
    Validate a document filepath before reading or copying it.

    Returns the resolved (canonical) Path if the path is a regular file
    and is not a symlink. Returns None if the path is missing, is a
    directory, or is a symlink.

    Args:
        path: Absolute path to validate (typically from Document.filepath).

    Returns:
        Resolved Path on success, None on any validation failure.
    """
    try:
        if path.is_symlink():
            return None
        resolved = path.resolve()
        if not resolved.is_file():
            return None
        return resolved
    except (OSError, ValueError):
        return None


def safe_dir_path(path: Path) -> Path | None:
    """
    Validate a directory path before passing it to the OS file browser.

    Returns the resolved (canonical) Path if the path is a real directory
    and is not a symlink. Returns None otherwise.

    Args:
        path: Absolute path to a directory to validate.

    Returns:
        Resolved Path on success, None on any validation failure.
    """
    try:
        if path.is_symlink():
            return None
        resolved = path.resolve()
        if not resolved.is_dir():
            return None
        return resolved
    except (OSError, ValueError):
        return None
