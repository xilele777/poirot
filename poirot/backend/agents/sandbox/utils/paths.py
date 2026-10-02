"""Portable path validation for sandbox exports and host destinations."""
from pathlib import Path

VIRTUAL_ROOT = "/mnt/poirot/user-data"
_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def virtual_relative(path: str, *, allow_root: bool = False) -> str:
    if path == VIRTUAL_ROOT and allow_root:
        return ""
    if not isinstance(path, str) or not path.startswith(VIRTUAL_ROOT + "/"):
        raise ValueError("path must be under " + VIRTUAL_ROOT)
    relative = path[len(VIRTUAL_ROOT) + 1:]
    if not relative and allow_root:
        return ""
    for part in relative.split("/"):
        if (not part or part in (".", "..") or part.endswith((".", " "))
                or any(c in part for c in '\\:*?"<>|')
                or any(ord(c) < 32 for c in part)
                or part.split(".")[0].upper() in _RESERVED):
            raise ValueError("invalid sandbox path component")
    return relative


def contained_path(root: Path, relative: str) -> Path:
    """Resolve symlinks before checking containment; reject the root itself."""
    root = root.resolve()
    candidate = (root / relative).resolve()
    if candidate == root or not candidate.is_relative_to(root):
        raise ValueError("path escapes its allowed root")
    return candidate
