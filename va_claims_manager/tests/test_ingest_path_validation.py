"""
Tests for _validate_path() in app.ingestion.pipeline.

Uses tmp_path to create real files and symlinks so no mocking is needed.
The function is private but tested directly because it is the sole guard
for all filesystem operations in the ingestion pipeline.
"""
from pathlib import Path


def _vp(filepath):
    """Thin wrapper to import _validate_path each call (avoids module-cache issues)."""
    from app.ingestion.pipeline import _validate_path
    return _validate_path(filepath)


# ── happy path ────────────────────────────────────────────────────────────────

def test_valid_file_returns_resolved_path(tmp_path):
    f = tmp_path / "record.pdf"
    f.write_bytes(b"fake pdf")
    resolved, err = _vp(f)
    assert err == ""
    assert resolved == f.resolve()
    assert resolved.is_file()


def test_dotdot_path_is_normalized(tmp_path):
    """A path with .. components must resolve to a canonical path with no traversal."""
    f = tmp_path / "record.pdf"
    f.write_bytes(b"fake pdf")
    sub = tmp_path / "subdir"
    sub.mkdir()
    traversal = sub / ".." / "record.pdf"   # same file, ugly path
    resolved, err = _vp(traversal)
    assert err == ""
    assert resolved == f.resolve()
    assert ".." not in str(resolved)


# ── rejection cases ────────────────────────────────────────────────────────────

def test_symlink_is_rejected(tmp_path):
    """Symlinks must be rejected before any content is read."""
    real = tmp_path / "real.pdf"
    real.write_bytes(b"sensitive content")
    link = tmp_path / "link.pdf"
    link.symlink_to(real)
    resolved, err = _vp(link)
    assert resolved is None
    assert "symlink" in err.lower()


def test_nonexistent_path_is_rejected(tmp_path):
    missing = tmp_path / "ghost.pdf"
    resolved, err = _vp(missing)
    assert resolved is None
    assert err != ""


def test_directory_is_rejected(tmp_path):
    d = tmp_path / "mydir"
    d.mkdir()
    resolved, err = _vp(d)
    assert resolved is None
    assert err != ""


# ── integration: ingest_files rejects symlinks end-to-end ────────────────────

def test_ingest_files_rejects_symlink(tmp_path):
    """
    End-to-end: ingest_files() must return status='error' for a symlink,
    not read its content or create any DB record.
    """
    from app.ingestion.pipeline import ingest_files

    real = tmp_path / "real.pdf"
    real.write_bytes(b"sensitive")
    link = tmp_path / "link.pdf"
    link.symlink_to(real)

    results = ingest_files([str(link)], veteran_id=1)

    assert len(results) == 1
    assert results[0]["status"] == "error"
    assert "symlink" in results[0]["message"].lower()


def test_ingest_files_stores_canonical_path(tmp_path):
    """
    ingest_files() must store the resolved canonical path, not the
    raw path with .. components.

    Uses an unsupported extension (.xyz) so the pipeline returns at the
    is_unsupported early-exit — no DB access, no real extractor needed —
    while the filepath field is already set to the canonical form by
    _validate_path() before the extension check runs.
    """
    from app.ingestion.pipeline import ingest_files

    real = tmp_path / "record.xyz"
    real.write_bytes(b"fake content")
    sub = tmp_path / "subdir"
    sub.mkdir()
    traversal = sub / ".." / "record.xyz"

    results = ingest_files([str(traversal)], veteran_id=1)

    assert len(results) == 1
    returned_path = results[0]["filepath"]
    assert ".." not in returned_path
    assert returned_path == str(real.resolve())
