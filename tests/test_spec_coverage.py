"""Keep ``spec-coverage.json`` honest about the code.

CI checks the file against the spec. These tests check it against the SDK:
every supported ``method`` is a real callable on a client, and the supported
paths are exactly the paths the per-operation builders in
``usesmileid.generated.operations`` send.
"""

from __future__ import annotations

import inspect
import json
import re
from pathlib import Path
from typing import Any, Dict, Set

from tests.conftest import make_client
from usesmileid.generated import operations

MANIFEST = Path(__file__).resolve().parent.parent / "spec-coverage.json"

# A string argument the builders put in a path segment shows up as this value.
_PARAM = "__param__"
_BINARY = ("a.jpg", b"x", "image/jpeg")
# A dummy value for each required parameter type the builders take.
_DUMMIES: Dict[str, Any] = {
    "str": _PARAM,
    "bool": True,
    "dict": {},
    "List[str]": [_PARAM],
    "List[dict]": [{}],
    "BinaryPart": _BINARY,
    "List[BinaryPart]": [_BINARY],
}


def _entries() -> Dict[str, Dict[str, Any]]:
    return json.loads(MANIFEST.read_text())["operations"]


def _supported() -> Dict[str, Dict[str, Any]]:
    return {op_id: e for op_id, e in _entries().items() if "unsupported" not in e}


def _normalize(path: str) -> str:
    """``POST /v3/status/{jobId}`` and ``POST /v3/status/__param__`` -> ``POST /v3/status/{}``."""
    return re.sub(r"\{[^}]*\}", "{}", path).replace(_PARAM, "{}")


def _builder_paths() -> Set[str]:
    """``METHOD /path`` for every public builder in the operations module."""
    paths = set()
    for name, builder in inspect.getmembers(operations, inspect.isfunction):
        if name.startswith("_") or builder.__module__ != operations.__name__:
            continue
        kwargs = {
            p.name: _DUMMIES[p.annotation]
            for p in inspect.signature(builder).parameters.values()
            if p.default is p.empty
        }
        request = builder(**kwargs)
        paths.add(_normalize(f"{request.method} {request.path}"))
    return paths


def test_every_supported_method_is_a_callable_on_the_client() -> None:
    client = make_client()
    for op_id, entry in _supported().items():
        root, *names = entry["method"].split(".")
        assert root == "client", f"{op_id}: method must start with 'client.'"
        target: Any = client
        for name in names:
            assert hasattr(target, name), f"{op_id}: {entry['method']} doesn't exist"
            target = getattr(target, name)
        assert callable(target), f"{op_id}: {entry['method']} isn't callable"


def test_supported_paths_are_the_operation_builders_paths() -> None:
    supported = {_normalize(e["path"]) for e in _supported().values()}
    assert supported == _builder_paths()

