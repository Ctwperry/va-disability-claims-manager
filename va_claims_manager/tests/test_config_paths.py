"""
Tests for app.config path construction safety.

TESSERACT_DEFAULT_PATHS must not derive any entry from the USERNAME
environment variable, which can be spoofed or contain path traversal.
"""
from pathlib import Path


def test_tesseract_user_path_derived_from_home_not_username(monkeypatch):
    """
    The user-profile Tesseract path must come from Path.home(),
    not os.getenv("USERNAME"). Poisoning USERNAME must have no effect.
    """
    import importlib
    import sys

    # Set a malicious USERNAME that would inject path traversal
    monkeypatch.setenv("USERNAME", "../../evil")

    # Force reimport of app.config with the poisoned env
    sys.modules.pop("app.config", None)
    import app.config as cfg
    importlib.reload(cfg)

    user_path = Path(cfg.TESSERACT_DEFAULT_PATHS[2])

    # Must start inside the real home directory — not anywhere else
    home = Path.home()
    assert user_path.is_relative_to(home), (
        f"Expected path inside {home}, got {user_path}. "
        "TESSERACT_DEFAULT_PATHS must not use os.getenv('USERNAME')."
    )


def test_tesseract_user_path_starts_with_home():
    """The user-specific Tesseract path must be rooted in the real home directory."""
    from app.config import TESSERACT_DEFAULT_PATHS

    home = str(Path.home())
    user_path = TESSERACT_DEFAULT_PATHS[2]
    assert user_path.startswith(home), (
        f"Expected user path to start with {home!r}, got {user_path!r}"
    )
