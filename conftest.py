"""Test setup: isolated temp database and NO real Gemini key (so no network calls)."""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_tmp = tempfile.mkdtemp(prefix="pocketsmart_test_")
os.environ["DB_PATH"] = str(Path(_tmp) / "test.db")
os.environ["GEMINI_API_KEY"] = ""
os.environ["GOOGLE_API_KEY"] = ""
os.environ["SECRET_KEY"] = "test-secret-key-for-pytest-only-0123456789"

import pytest  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _cleanup_uploads():
    upload_dir = ROOT / "static" / "uploads"
    before = set(upload_dir.glob("*")) if upload_dir.exists() else set()
    yield
    for f in set(upload_dir.glob("*")) - before:
        f.unlink(missing_ok=True)
