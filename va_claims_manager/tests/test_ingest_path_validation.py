"""
Tests for ingestion pipeline path validation via safe_file_path().

Uses tmp_path to create real files and symlinks so no mocking is needed.
Validates that the pipeline rejects symlinks, normalizes .. traversal,
and rejects non-file paths before any content is read.
"""
from pathlib import Path
import pytest


def _symlinks_available() -> bool:
    try:
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "src"; src.write_bytes(b"x")
            (Path(d) / "lnk").symlink_to(src)
        return True
    except OSError:
        return False

_SYMLINK_SKIP = pytest.mark.skipif(
    not _symlinks_available(),
    reason="Symlink creation requires elevated privileges on this Windows account"
)


# ── _extract_file path validation ─────────────────────────────────────────────

def test_valid_file_resolves_canonical_path(tmp_path):
    """A real file should pass validation and get a resolved canonical path."""
    from app.ingestion.pipeline import _extract_file

    f = tmp_path / "record.pdf"
    f.write_bytes(b"fake pdf")
    result = _extract_file(f)
    assert result.pre_hash_error == ""
    assert result.filepath == f.resolve()


def test_dotdot_path_is_normalized(tmp_path):
    """A path with .. components must resolve to a canonical path."""
    from app.ingestion.pipeline import _extract_file

    f = tmp_path / "record.pdf"
    f.write_bytes(b"fake pdf")
    sub = tmp_path / "subdir"
    sub.mkdir()
    traversal = sub / ".." / "record.pdf"
    result = _extract_file(traversal)
    assert result.pre_hash_error == ""
    assert ".." not in str(result.filepath)
    assert result.filepath == f.resolve()


@_SYMLINK_SKIP
def test_symlink_is_rejected(tmp_path):
    """Symlinks must be rejected before any content is read."""
    from app.ingestion.pipeline import _extract_file

    real = tmp_path / "real.pdf"
    real.write_bytes(b"sensitive content")
    link = tmp_path / "link.pdf"
    link.symlink_to(real)
    result = _extract_file(link)
    assert result.pre_hash_error != ""
    assert "symlink" in result.pre_hash_error.lower()


def test_nonexistent_path_is_rejected(tmp_path):
    from app.ingestion.pipeline import _extract_file

    result = _extract_file(tmp_path / "ghost.pdf")
    assert result.pre_hash_error != ""


def test_directory_is_rejected(tmp_path):
    from app.ingestion.pipeline import _extract_file

    d = tmp_path / "mydir"
    d.mkdir()
    result = _extract_file(d)
    assert result.pre_hash_error != ""


# ── integration: ingest_files end-to-end ──────────────────────────────────────

@_SYMLINK_SKIP
def test_ingest_files_rejects_symlink(tmp_path):
    """ingest_files() must return status='error' for a symlink."""
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
    is_unsupported early-exit — no DB access needed — while the filepath
    is already set to canonical form before the extension check.
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
