"""Unit tests for SessionManager."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.session_manager import SessionManager, SessionError
from src.store import JsonFileStore


class SessionManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "sessions"
        self.store = JsonFileStore(self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _manager(self, **kw):
        return SessionManager(self.store, **kw)

    # ---- bootstrap -----------------------------------------------------

    def test_default_session_created_on_first_run(self) -> None:
        sm = self._manager()
        self.assertEqual(sm.active_id, "default")

    # ---- create / load / switch ---------------------------------------

    def test_create_and_switch(self) -> None:
        sm = self._manager()
        sm.create("work")
        self.assertEqual(sm.active_id, "work")

    def test_create_duplicate_raises(self) -> None:
        sm = self._manager()
        sm.create("work")
        with self.assertRaises(SessionError):
            sm.create("work")

    def test_invalid_id_raises(self) -> None:
        sm = self._manager()
        with self.assertRaises(SessionError):
            sm.create("Bad ID!")

    def test_switch_to_missing_raises(self) -> None:
        sm = self._manager()
        with self.assertRaises(SessionError):
            sm.switch("ghost")

    # ---- list ----------------------------------------------------------

    def test_list_reports_counts_and_active(self) -> None:
        sm = self._manager()
        sm.create("work")
        sm.append("user", "hi")
        sm.append("assistant", "hello")
        rows = {r["id"]: r for r in sm.list()}
        self.assertTrue(rows["work"]["active"])
        self.assertEqual(rows["work"]["message_count"], 2)
        self.assertFalse(rows["default"]["active"])

    # ---- delete --------------------------------------------------------

    def test_delete_falls_back_to_default(self) -> None:
        sm = self._manager()
        sm.create("work")
        sm.delete("work")
        self.assertEqual(sm.active_id, "default")

    # ---- append / clear ------------------------------------------------

    def test_append_persists_across_manager_instances(self) -> None:
        sm = self._manager()
        sm.append("user", "hello")
        sm2 = self._manager()
        self.assertEqual(sm2.active_id, "default")
        self.assertEqual(sm2.messages()[0]["content"], "hello")

    def test_clear_keeps_session(self) -> None:
        sm = self._manager()
        sm.append("user", "hello")
        sm.clear()
        self.assertEqual(sm.messages(), [])
        self.assertEqual(sm.active_id, "default")

    # ---- active-session persistence -----------------------------------

    def test_active_session_resumed_after_restart(self) -> None:
        sm = self._manager()
        sm.create("work")
        sm.append("user", "persisted")

        sm2 = self._manager()
        self.assertEqual(sm2.active_id, "work")
        self.assertEqual(sm2.messages()[0]["content"], "persisted")

    def test_auto_resume_false_starts_on_default(self) -> None:
        sm = self._manager()
        sm.create("work")

        sm2 = self._manager(auto_resume=False)
        # Default is created/found on bootstrap.
        self.assertEqual(sm2.active_id, "default")

    # ---- corrupt file --------------------------------------------------

    def test_corrupt_session_falls_back(self) -> None:
        (self.root / "default.json").write_text("not json", encoding="utf-8")
        # Bootstrap should recreate default cleanly.
        sm = self._manager()
        self.assertEqual(sm.active_id, "default")
        self.assertEqual(sm.messages(), [])


if __name__ == "__main__":
    unittest.main()