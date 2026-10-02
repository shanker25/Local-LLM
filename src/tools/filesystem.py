"""Safe filesystem tools for JARVIS.

Every path passed to these tools is resolved against WORKSPACE_DIR
and rejected if it escapes that root. Symlinks are resolved, so a
link planted inside the workspace that points outside is also
rejected. A denylist refuses sensitive filenames even when they
live inside the workspace.

All four tools are READ_ONLY and never execute file contents.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from src.tools.base import Tool


# ---- constants ---------------------------------------------------------

#: Filenames / suffixes that may never be read, even inside the workspace.
SECRET_DENYLIST: tuple[str, ...] = (
    ".env",
    ".netrc",
    "credentials",
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "known_hosts",
    "authorized_keys",
)

#: Suffix denylist (case-insensitive).
SECRET_SUFFIXES: tuple[str, ...] = (
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    ".jks",
)

#: Directory-name denylist applied to any component of the path.
SECRET_DIRS: tuple[str, ...] = (
    ".ssh",
    ".aws",
    ".gnupg",
    ".kube",
)

#: Default read cap: 1 MiB.
DEFAULT_MAX_FILE_READ_SIZE = 1024 * 1024


# ---- helpers -----------------------------------------------------------

class FilesystemError(Exception):
    """Raised internally for sandbox or I/O failures."""


def _resolve_workspace(workspace: str | os.PathLike) -> Path:
    return Path(workspace).expanduser().resolve()


def _is_secret_path(p: Path) -> bool:
    """True if any component of `p` matches the secret denylist."""
    for part in p.parts:
        low = part.lower()
        if low in SECRET_DIRS:
            return True
        if low in SECRET_DENYLIST or low.startswith(".env"):
            return True
        for suffix in SECRET_SUFFIXES:
            if low.endswith(suffix):
                return True
    return False


def _resolve_inside_workspace(
    user_path: str | os.PathLike,
    workspace: Path,
) -> Path:
    """Resolve `user_path` against `workspace` and enforce the sandbox.

    Raises FilesystemError if the resolved path escapes the workspace,
    hits the secret denylist, or is otherwise invalid.
    """
    if user_path is None or str(user_path).strip() == "":
        raise FilesystemError("Path must be a non-empty string.")

    raw = Path(str(user_path))

    # Absolute paths are allowed only if they end up inside the
    # workspace after resolution. Relative paths are joined to the
    # workspace and then resolved.
    candidate = raw if raw.is_absolute() else (workspace / raw)

    try:
        resolved = candidate.resolve(strict=False)
    except OSError as exc:
        raise FilesystemError(f"Could not resolve path: {exc}")

    # Sandbox check. `is_relative_to` is available on 3.9+.
    try:
        resolved.relative_to(workspace)
    except ValueError:
        raise FilesystemError(
            "Access denied: path escapes the workspace."
        )

    if _is_secret_path(resolved.relative_to(workspace) if resolved != workspace else Path(".")):
        raise FilesystemError("Access denied: path matches the secret denylist.")

    return resolved


def _to_posix_relative(p: Path, workspace: Path) -> str:
    """Return p relative to workspace, always with forward slashes."""
    try:
        rel = p.relative_to(workspace)
    except ValueError:
        return str(p)
    return rel.as_posix() or "."


def _human_size(n: int) -> str:
    """Return a compact human-readable size, e.g. '4.2 MB'."""
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(n)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{n} B"


# ---- tools -------------------------------------------------------------

class ListDirectoryTool(Tool):
    name = "list_directory"
    description = (
        "List the entries in a directory inside the workspace. "
        "Returns names, types (file or dir), sizes, and modification "
        "times. Does not recurse."
    )
    schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Directory path, relative to the workspace.",
            }
        },
        "required": ["path"],
        "additionalProperties": False,
    }

    def __init__(self, workspace: str | os.PathLike = ".") -> None:
        self._workspace = _resolve_workspace(workspace)

    def execute(self, arguments: dict) -> dict:
        try:
            target = _resolve_inside_workspace(arguments.get("path", "."), self._workspace)
        except FilesystemError as exc:
            return {"success": False, "result": None, "error": str(exc)}

        if not target.exists():
            return {"success": False, "result": None, "error": "Path does not exist."}
        if not target.is_dir():
            return {"success": False, "result": None, "error": "Path is not a directory."}

        try:
            entries: list[dict[str, Any]] = []
            for child in sorted(target.iterdir(), key=lambda p: p.name.lower()):
                try:
                    stat = child.stat()
                except OSError:
                    continue
                entries.append({
                    "name": child.name,
                    "type": "dir" if child.is_dir() else "file",
                    "size": stat.st_size if child.is_file() else None,
                    "size_human": _human_size(stat.st_size) if child.is_file() else None,
                    "modified": int(stat.st_mtime),
                })
        except PermissionError:
            return {"success": False, "result": None, "error": "Permission denied."}
        except OSError as exc:
            return {"success": False, "result": None, "error": f"OS error: {exc}"}

        return {
            "success": True,
            "result": {
                "path": _to_posix_relative(target, self._workspace),
                "count": len(entries),
                "entries": entries,
            },
            "error": None,
        }


class SearchFilesTool(Tool):
    name = "search_files"
    description = (
        "Find files under a directory in the workspace whose name "
        "matches a glob pattern (e.g. '*.py'). Non-recursive by default."
    )
    schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Directory to search, relative to the workspace.",
            },
            "pattern": {
                "type": "string",
                "description": "Glob pattern, e.g. '*.py' or 'test_*.py'.",
            },
            "recursive": {
                "type": "boolean",
                "description": "Search subdirectories as well.",
            },
        },
        "required": ["path", "pattern"],
        "additionalProperties": False,
    }

    #: Hard cap on returned matches to avoid pathological results.
    MAX_RESULTS = 500

    def __init__(self, workspace: str | os.PathLike = ".") -> None:
        self._workspace = _resolve_workspace(workspace)

    def execute(self, arguments: dict) -> dict:
        pattern = arguments.get("pattern", "")
        recursive = bool(arguments.get("recursive", False))

        if not isinstance(pattern, str) or not pattern.strip():
            return {"success": False, "result": None, "error": "Pattern must be a non-empty string."}

        # Reject patterns that try to climb directories.
        if ".." in Path(pattern).parts:
            return {"success": False, "result": None, "error": "Pattern may not contain '..'."}

        try:
            base = _resolve_inside_workspace(arguments.get("path", "."), self._workspace)
        except FilesystemError as exc:
            return {"success": False, "result": None, "error": str(exc)}

        if not base.exists():
            return {"success": False, "result": None, "error": "Path does not exist."}
        if not base.is_dir():
            return {"success": False, "result": None, "error": "Path is not a directory."}

        matches: list[dict[str, Any]] = []
        truncated = False

        try:
            iterator = base.rglob(pattern) if recursive else base.glob(pattern)
            for match in iterator:
                # Ignore anything that resolves outside the workspace
                # (e.g. via a symlinked subdirectory).
                try:
                    resolved = match.resolve(strict=False)
                    resolved.relative_to(self._workspace)
                except (OSError, ValueError):
                    continue
                if _is_secret_path(
                    resolved.relative_to(self._workspace)
                    if resolved != self._workspace
                    else Path(".")
                ):
                    continue
                try:
                    stat = match.stat()
                except OSError:
                    continue
                matches.append({
                    "path": _to_posix_relative(match, self._workspace),
                    "type": "dir" if match.is_dir() else "file",
                    "size": stat.st_size if match.is_file() else None,
                })
                if len(matches) >= self.MAX_RESULTS:
                    truncated = True
                    break
        except PermissionError:
            return {"success": False, "result": None, "error": "Permission denied."}
        except OSError as exc:
            return {"success": False, "result": None, "error": f"OS error: {exc}"}

        return {
            "success": True,
            "result": {
                "pattern": pattern,
                "recursive": recursive,
                "count": len(matches),
                "truncated": truncated,
                "matches": matches,
            },
            "error": None,
        }


class ReadFileTool(Tool):
    name = "read_file"
    description = (
        "Read a UTF-8 text file inside the workspace. Files larger "
        "than the configured limit are truncated and the response "
        "will include truncated=true."
    )
    schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "File path, relative to the workspace.",
            }
        },
        "required": ["path"],
        "additionalProperties": False,
    }

    def __init__(
        self,
        workspace: str | os.PathLike = ".",
        max_size: int = DEFAULT_MAX_FILE_READ_SIZE,
    ) -> None:
        self._workspace = _resolve_workspace(workspace)
        self._max_size = int(max_size)

    def execute(self, arguments: dict) -> dict:
        try:
            target = _resolve_inside_workspace(arguments.get("path", ""), self._workspace)
        except FilesystemError as exc:
            return {"success": False, "result": None, "error": str(exc)}

        if not target.exists():
            return {"success": False, "result": None, "error": "File does not exist."}
        if target.is_dir():
            return {"success": False, "result": None, "error": "Path is a directory, not a file."}
        if not target.is_file():
            return {"success": False, "result": None, "error": "Path is not a regular file."}

        try:
            size = target.stat().st_size
        except OSError as exc:
            return {"success": False, "result": None, "error": f"OS error: {exc}"}

        truncated = size > self._max_size
        read_limit = min(size, self._max_size)

        try:
            with open(target, "rb") as fh:
                raw = fh.read(read_limit)
        except PermissionError:
            return {"success": False, "result": None, "error": "Permission denied."}
        except OSError as exc:
            return {"success": False, "result": None, "error": f"OS error: {exc}"}

        # Binary detection: NUL bytes in the first chunk.
        if b"\x00" in raw:
            return {
                "success": False,
                "result": None,
                "error": "File appears to be binary; refusing to return content.",
            }

        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            return {
                "success": False,
                "result": None,
                "error": "File is not valid UTF-8 text.",
            }

        result: dict[str, Any] = {
            "path": _to_posix_relative(target, self._workspace),
            "size": size,
            "size_human": _human_size(size),
            "read": len(raw),
            "truncated": truncated,
            "content": text,
        }
        if truncated:
            result["truncated_at"] = self._max_size
            result["message"] = (
                f"File is larger than {_human_size(self._max_size)}; "
                f"only the first {_human_size(self._max_size)} were returned."
            )

        return {"success": True, "result": result, "error": None}


class FileMetadataTool(Tool):
    name = "file_metadata"
    description = (
        "Return size, modification time, type, and basic permissions "
        "for a file or directory inside the workspace. Does not read "
        "the file contents."
    )
    schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path, relative to the workspace.",
            }
        },
        "required": ["path"],
        "additionalProperties": False,
    }

    def __init__(self, workspace: str | os.PathLike = ".") -> None:
        self._workspace = _resolve_workspace(workspace)

    def execute(self, arguments: dict) -> dict:
        try:
            target = _resolve_inside_workspace(arguments.get("path", ""), self._workspace)
        except FilesystemError as exc:
            return {"success": False, "result": None, "error": str(exc)}

        if not target.exists():
            return {"success": False, "result": None, "error": "Path does not exist."}

        try:
            stat = target.stat()
        except PermissionError:
            return {"success": False, "result": None, "error": "Permission denied."}
        except OSError as exc:
            return {"success": False, "result": None, "error": f"OS error: {exc}"}

        kind = "dir" if target.is_dir() else "file" if target.is_file() else "other"

        result = {
            "path": _to_posix_relative(target, self._workspace),
            "type": kind,
            "size": stat.st_size,
            "size_human": _human_size(stat.st_size),
            "modified": int(stat.st_mtime),
            "created": int(stat.st_ctime),
            "readable": os.access(target, os.R_OK),
            "writable": os.access(target, os.W_OK),
            "executable": os.access(target, os.X_OK),
        }
        return {"success": True, "result": result, "error": None}