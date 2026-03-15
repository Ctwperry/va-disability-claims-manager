"""
Tests that DocumentPanel._open_file_location uses safe_dir_path.
"""
from pathlib import Path
from unittest.mock import patch, MagicMock
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


def _make_panel_and_doc(doc_filepath: str):
    """Instantiate a bare DocumentPanel and a mock Document."""
    import app.ui.panels.document_panel as mod

    panel = mod.DocumentPanel.__new__(mod.DocumentPanel)
    panel._veteran_id = 1

    mock_doc = MagicMock()
    mock_doc.filepath = doc_filepath

    return panel, mock_doc


def test_open_file_location_calls_startfile_for_real_file(tmp_path):
    """os.startfile is called with the resolved parent dir of a real file."""
    import app.ui.panels.document_panel as mod

    real_file = tmp_path / "record.pdf"
    real_file.write_bytes(b"x")
    panel, mock_doc = _make_panel_and_doc(str(real_file))

    with patch.object(mod.doc_repo, "get_by_id", return_value=mock_doc), \
         patch.object(mod, "os") as mock_os:
        panel._open_file_location(1)

    mock_os.startfile.assert_called_once_with(str(real_file.parent.resolve()))


@_SYMLINK_SKIP
def test_open_file_location_skips_symlinked_file(tmp_path):
    """os.startfile is NOT called when the filepath is a symlink."""
    import app.ui.panels.document_panel as mod

    real_file = tmp_path / "real.pdf"
    real_file.write_bytes(b"x")
    link = tmp_path / "link.pdf"
    link.symlink_to(real_file)
    panel, mock_doc = _make_panel_and_doc(str(link))

    with patch.object(mod.doc_repo, "get_by_id", return_value=mock_doc), \
         patch.object(mod, "os") as mock_os:
        panel._open_file_location(1)

    mock_os.startfile.assert_not_called()


def test_open_file_location_skips_missing_file(tmp_path):
    """os.startfile is NOT called when the file doesn't exist."""
    import app.ui.panels.document_panel as mod

    panel, mock_doc = _make_panel_and_doc(str(tmp_path / "ghost.pdf"))

    with patch.object(mod.doc_repo, "get_by_id", return_value=mock_doc), \
         patch.object(mod, "os") as mock_os:
        panel._open_file_location(1)

    mock_os.startfile.assert_not_called()
