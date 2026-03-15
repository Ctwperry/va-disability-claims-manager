"""
Tests for app.core.path_guard — safe_file_path() and safe_dir_path().
"""
from pathlib import Path
import pytest


# Creating symlinks on Windows requires SeCreateSymbolicLinkPrivilege
# (Administrator or Developer Mode). Skip symlink tests when unavailable.
def _symlinks_available() -> bool:
    try:
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "src"
            src.write_bytes(b"x")
            (Path(d) / "lnk").symlink_to(src)
        return True
    except OSError:
        return False

_SYMLINK_SKIP = pytest.mark.skipif(
    not _symlinks_available(),
    reason="Symlink creation requires elevated privileges on this Windows account"
)


# ── safe_file_path ────────────────────────────────────────────────────────────

def test_safe_file_path_returns_resolved_for_regular_file(tmp_path):
    from app.core.path_guard import safe_file_path
    f = tmp_path / "doc.pdf"
    f.write_bytes(b"data")
    result = safe_file_path(f)
    assert result == f.resolve()


def test_safe_file_path_returns_none_for_missing_file(tmp_path):
    from app.core.path_guard import safe_file_path
    result = safe_file_path(tmp_path / "nonexistent.pdf")
    assert result is None


def test_safe_file_path_returns_none_for_directory(tmp_path):
    from app.core.path_guard import safe_file_path
    result = safe_file_path(tmp_path)
    assert result is None


@_SYMLINK_SKIP
def test_safe_file_path_returns_none_for_symlink_to_file(tmp_path):
    from app.core.path_guard import safe_file_path
    real = tmp_path / "real.pdf"
    real.write_bytes(b"data")
    link = tmp_path / "link.pdf"
    link.symlink_to(real)
    result = safe_file_path(link)
    assert result is None, "Symlinks must be rejected even when the target exists"


@_SYMLINK_SKIP
def test_safe_file_path_returns_none_for_symlink_to_sensitive_dir(tmp_path):
    from app.core.path_guard import safe_file_path
    link = tmp_path / "system_link"
    link.symlink_to("/etc")
    result = safe_file_path(link)
    assert result is None


# ── safe_dir_path ─────────────────────────────────────────────────────────────

def test_safe_dir_path_returns_resolved_for_real_dir(tmp_path):
    from app.core.path_guard import safe_dir_path
    d = tmp_path / "subdir"
    d.mkdir()
    result = safe_dir_path(d)
    assert result == d.resolve()


def test_safe_dir_path_returns_none_for_missing_dir(tmp_path):
    from app.core.path_guard import safe_dir_path
    result = safe_dir_path(tmp_path / "ghost")
    assert result is None


def test_safe_dir_path_returns_none_for_file(tmp_path):
    from app.core.path_guard import safe_dir_path
    f = tmp_path / "file.pdf"
    f.write_bytes(b"x")
    result = safe_dir_path(f)
    assert result is None


@_SYMLINK_SKIP
def test_safe_dir_path_returns_none_for_symlink_to_dir(tmp_path):
    from app.core.path_guard import safe_dir_path
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    link = tmp_path / "link_dir"
    link.symlink_to(real_dir)
    result = safe_dir_path(link)
    assert result is None, "Symlinked directories must be rejected"
