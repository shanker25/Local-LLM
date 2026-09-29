"""Persistent conversation storage for JARVIS.

Zero-dependency, standard-library only.

Provides:
    ConversationStore  -- abstract interface
    JsonFileStore      -- JSON-on-disk implementation with atomic writes
"""

from __future__ import annotations

import json
import os
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional


class StoreError(Exception):
    """Raised when the store cannot complete an operation."""


class ConversationStore(ABC):
    """Abstract interface for session persistence."""

    @abstractmethod
    def load(self, session_id: str) -> Optional[dict]:
        ...

    @abstractmethod
    def save(self, session_id: str, data: dict) -> None:
        ...

    @abstractmethod
    def delete(self, session_id: str) -> None:
        ...

    @abstractmethod
    def list_ids(self) -> list[str]:
        ...

    @abstractmethod
    def load_index(self) -> dict:
        ...

    @abstractmethod
    def save_index(self, index: dict) -> None:
        ...


class JsonFileStore(ConversationStore):
    """JSON-file-backed store rooted at `root` (e.g. data/sessions)."""

    INDEX_NAME = "index.json"
    BACKUP_SUFFIX = ".bak"

    def __init__(self, root: str | os.PathLike) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    # ---- paths ---------------------------------------------------------

    def _session_path(self, session_id: str) -> Path:
        return self.root / f"{session_id}.json"

    def _index_path(self) -> Path:
        return self.root / self.INDEX_NAME

    # ---- atomic write --------------------------------------------------

    def _atomic_write_json(self, path: Path, payload: Any) -> None:
        """Write JSON to `path` atomically via tmp file + os.replace."""
        tmp = path.with_suffix(path.suffix + ".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2, ensure_ascii=False)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, path)
        except OSError as exc:
            # Clean up tmp if it still exists
            try:
                if tmp.exists():
                    tmp.unlink()
            except OSError:
                pass
            raise StoreError(f"Failed to write {path}: {exc}") from exc

    # ---- sessions ------------------------------------------------------

    def load(self, session_id: str) -> Optional[dict]:
        path = self._session_path(session_id)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            # Back up the corrupt file and let caller start fresh.
            backup = path.with_suffix(path.suffix + self.BACKUP_SUFFIX)
            try:
                shutil.copy2(path, backup)
            except OSError:
                pass
            raise StoreError(
                f"Corrupt session file {path} (backed up to {backup}): {exc}"
            ) from exc

    def save(self, session_id: str, data: dict) -> None:
        self._atomic_write_json(self._session_path(session_id), data)

    def delete(self, session_id: str) -> None:
        path = self._session_path(session_id)
        try:
            if path.exists():
                path.unlink()
        except OSError as exc:
            raise StoreError(f"Failed to delete {path}: {exc}") from exc

    def list_ids(self) -> list[str]:
        ids: list[str] = []
        for entry in self.root.iterdir():
            if entry.is_file() and entry.suffix == ".json" and entry.name != self.INDEX_NAME:
                ids.append(entry.stem)
        return sorted(ids)

    # ---- index ---------------------------------------------------------

    def load_index(self) -> dict:
        path = self._index_path()
        if not path.exists():
            return {"version": 1, "active_session": None, "sessions": []}
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError):
            # Non-fatal: rebuild a fresh index.
            return {"version": 1, "active_session": None, "sessions": []}

    def save_index(self, index: dict) -> None:
        self._atomic_write_json(self._index_path(), index)