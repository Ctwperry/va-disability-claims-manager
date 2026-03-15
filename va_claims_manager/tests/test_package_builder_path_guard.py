"""
Tests that _copy_doc() rejects symlinks and missing files.
"""
from pathlib import Path
from unittest.mock import MagicMock
import pytest


def _make_doc(filepath: str):
    doc = MagicMock()
    doc.filepath = filepath
    doc.filename = Path(filepath).name
    return doc


def test_copy_doc_copies_real_file(tmp_path):
    """A real file is copied to the destination directory."""
    from app.export.package_builder import _copy_doc

    src = tmp_path / "src" / "record.pdf"
    src.parent.mkdir()
    src.write_bytes(b"pdf content")
    dest = tmp_path / "dest"
    dest.mkdir()

    _copy_doc(_make_doc(str(src)), dest)

    assert (dest / "record.pdf").exists()


def test_copy_doc_skips_symlink(tmp_path):
    """A symlink is silently skipped — nothing is copied to dest."""
    from app.export.package_builder import _copy_doc

    real = tmp_path / "real.pdf"
    real.write_bytes(b"data")
    link = tmp_path / "link.pdf"
    link.symlink_to(real)
    dest = tmp_path / "dest"
    dest.mkdir()

    _copy_doc(_make_doc(str(link)), dest)

    assert not (dest / "link.pdf").exists(), "Symlink target must not be copied"


def test_copy_doc_skips_missing_file(tmp_path):
    """A missing filepath is silently skipped."""
    from app.export.package_builder import _copy_doc

    dest = tmp_path / "dest"
    dest.mkdir()

    _copy_doc(_make_doc(str(tmp_path / "ghost.pdf")), dest)

    assert list(dest.iterdir()) == []
