import re
from pathlib import Path

import usesmileid

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


def test_version_matches_pyproject():
    # tomllib is 3.11+, and the SDK still supports 3.8, so read the line directly.
    match = re.search(r'^version = "([^"]+)"$', PYPROJECT.read_text(), re.MULTILINE)
    assert match is not None
    assert usesmileid.__version__ == match.group(1)
