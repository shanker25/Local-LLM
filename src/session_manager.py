"""Session lifecycle management for JARVIS."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional

from src.store import ConversationStore, StoreError


SESSION_ID_RE = re.compile(r"^[a-z0-9_-]+$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class SessionError(Exception):
    """Raised for invalid session operations."""


class SessionManager:
    def __init__(
        self,
        store: ConversationStore,
        *,
        default_session: str = "default",
        model: str = "llama3.2:1b",
        system_prompt: str = "You are JARVIS, a helpful local assistant.",
        auto_resume: bool = True,
    ) -> None:
        self.store = store
        self.default_session = default_session
        self.model = model
        self.system_prompt_text = system_prompt
        self.auto_resume = auto_resume

        self._active_id: str = ""
        self._current: dict = {}
        self._index: dict = {}

        self._bootstrap()

    # ---- bootstrap -----------------------------------------------------

    def _bootstrap(self) -> None:
        self._index = self.store.load_index()
        candidate: Optional[str] = None
        if self.auto_resume:
            candidate = self._index.get("active_session")

        if not candidate or not self._session_exists(candidate):
            candidate = self.default_session

        if not self._session_exists(candidate):
            self.create(candidate, switch=True)
        else:
            self.switch(candidate)

    def _session_exists(self, session_id: str) -> bool:
        """True only if a loadable session file exists.

        Corrupt files are treated as 'not loadable' so bootstrap
        can recreate a fresh session instead of crashing.
        """
        try:
            return self.store.load(session_id) is not None
        except StoreError as exc:
            print(f"[warn] {exc}")
            return False

    # ---- validation ----------------------------------------------------

    @staticmethod
    def _validate_id(session_id: str) -> None:
        if not SESSION_ID_RE.match(session_id):
            raise SessionError(
                f"Invalid session id {session_id!r}. "
                "Use only [a-z0-9_-]+."
            )

    # ---- properties ----------------------------------------------------

    @property
    def active_id(self) -> str:
        return self._active_id

    def messages(self) -> list[dict]:
        return list(self._current.get("messages", []))

    def system_prompt(self) -> str:
        return self._current.get("system_prompt", self.system_prompt_text)

    # ---- lifecycle -----------------------------------------------------

    def create(self, session_id: str, *, switch: bool = True) -> None:
        self._validate_id(session_id)
        if self._session_exists(session_id):
            raise SessionError(f"Session {session_id!r} already exists.")

        now = _now()
        data = {
            "session_id": session_id,
            "created_at": now,
            "updated_at": now,
            "model": self.model,
            "system_prompt": self.system_prompt_text,
            "messages": [],
        }
        self.store.save(session_id, data)
        self._refresh_index_entry(session_id, data)
        if switch:
            self.switch(session_id)

    def load(self, session_id: str) -> None:
        self.switch(session_id)

    def switch(self, session_id: str) -> None:
        self._validate_id(session_id)

        corrupt = False
        try:
            data = self.store.load(session_id)
        except StoreError as exc:
            # Corrupt file: warn, back up, and recreate a fresh session
            # under the same id. This is a recovery path, not an error.
            print(f"[warn] {exc}")
            corrupt = True
            data = None

        if data is None and not corrupt:
            # File simply does not exist -> this is a real error.
            raise SessionError(f"Session {session_id!r} does not exist.")

        if corrupt:
            # Recreate cleanly under the same id.
            now = _now()
            data = {
                "session_id": session_id,
                "created_at": now,
                "updated_at": now,
                "model": self.model,
                "system_prompt": self.system_prompt_text,
                "messages": [],
            }
            self.store.save(session_id, data)

        self._active_id = session_id
        self._current = data
        self._refresh_index_entry(session_id, data)
        self._index["active_session"] = session_id
        self.store.save_index(self._index)

    def delete(self, session_id: str) -> None:
        self._validate_id(session_id)
        self.store.delete(session_id)
        self._index["sessions"] = [
            s for s in self._index.get("sessions", []) if s.get("id") != session_id
        ]
        if self._index.get("active_session") == session_id:
            self._index["active_session"] = None
        self.store.save_index(self._index)
        if self._active_id == session_id:
            # Fall back to default (create if needed).
            if not self._session_exists(self.default_session):
                self.create(self.default_session, switch=True)
            else:
                self.switch(self.default_session)

    def list(self) -> list[dict]:
        out: list[dict] = []
        for sid in self.store.list_ids():
            data = self.store.load(sid) or {}
            out.append(
                {
                    "id": sid,
                    "message_count": len(data.get("messages", [])),
                    "updated_at": data.get("updated_at", ""),
                    "active": sid == self._active_id,
                }
            )
        return out

    # ---- messaging -----------------------------------------------------

    def append(self, role: str, content: str) -> None:
        if not self._active_id:
            raise SessionError("No active session.")
        ts = _now()
        self._current.setdefault("messages", []).append(
            {"role": role, "content": content, "ts": ts}
        )
        self._current["updated_at"] = ts
        self.store.save(self._active_id, self._current)
        self._refresh_index_entry(self._active_id, self._current)

    def clear(self) -> None:
        if not self._active_id:
            raise SessionError("No active session.")
        self._current["messages"] = []
        self._current["updated_at"] = _now()
        self.store.save(self._active_id, self._current)
        self._refresh_index_entry(self._active_id, self._current)

    # ---- index helpers -------------------------------------------------

    def _refresh_index_entry(self, session_id: str, data: dict) -> None:
        sessions = self._index.setdefault("sessions", [])
        entry = {
            "id": session_id,
            "updated_at": data.get("updated_at", ""),
            "message_count": len(data.get("messages", [])),
        }
        for i, existing in enumerate(sessions):
            if existing.get("id") == session_id:
                sessions[i] = entry
                break
        else:
            sessions.append(entry)
        self.store.save_index(self._index)