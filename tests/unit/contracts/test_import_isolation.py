"""Ensure contracts do not depend on FastAPI, LiveKit, or vendor SDKs."""

import ast
from pathlib import Path

import xymphony_contracts as contracts


def test_public_exports_exist() -> None:
    assert contracts.AgentVersion is not None
    assert contracts.Event is not None
    assert contracts.Session is not None
    assert contracts.LLMBinding is not None


def test_no_framework_imports() -> None:
    forbidden = {"fastapi", "livekit", "openai", "anthropic", "elevenlabs"}
    root = Path(contracts.__file__).resolve().parent
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] not in forbidden, alias.name
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[0] not in forbidden, node.module
