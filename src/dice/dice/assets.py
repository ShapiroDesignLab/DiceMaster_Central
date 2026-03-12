"""Asset access — resolve paths in the filesystem."""
from __future__ import annotations
import os

_assets_root: str = "/assets"


def configure(root: str) -> None:
    global _assets_root
    _assets_root = root


def get(name: str) -> str:
    return os.path.join(_assets_root, name)


def list_all() -> list[str]:
    result = []
    for dirpath, _, filenames in os.walk(_assets_root):
        for f in filenames:
            full = os.path.join(dirpath, f)
            rel = os.path.relpath(full, _assets_root)
            result.append(rel)
    return sorted(result)


def _reset() -> None:
    global _assets_root
    _assets_root = "/assets"
