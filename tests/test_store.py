"""Unit tests for JsonFileStore."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from src.store import JsonFileStore, StoreError


class JsonFileStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "sessions"
        self.store = JsonFileStore(self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    # ---- basics --------------------------------------------------------

    def test_root_created_automatically(self) -> None:
        self.assertTrue(self.root.is_dir())

    def test_save_load_round_trip(self) -> None:
        payload = {
            "session_id": "default",
            "messages": [{"role": "user", "content": "hi", "ts": "t"}],
        }
        self.store.save("default", payload)
        loaded = self.store.load("default")
        self.assertEqual(loaded, payload)

    def test_missing_file_returns_none(self) -> None:
        self.assertIsNone(self.store.load("nope"))

    # ---- atomicity -----------------------------------------------------

    def test_atomic_save_leaves_no_tmp(self) -> None:
        self.store.save("default", {"a": 1})
        leftovers = [p.name for p in self.root.iterdir() if p.suffix == ".tmp"]
        self.assertEqual(leftovers, [])

    def test_save_overwrites_existing(self) -> None:
        self.store.save("default", {"v": 1})
        self.store.save("default", {"v": 2})
        self.assertEqual(self.store.load("default"), {"v": 2})

    # ---- corruption ----------------------------------------------------

    def test_corrupt_json_raises_and_backs_up(self) -> None:
        path = self.root / "broken.json"
        path.write_text("{not json", encoding="utf-8")
        with self.assertRaises(StoreError):
            self.store.load("broken")
        backup = self.root / "broken.json.bak"
        self.assertTrue(backup.exists())

    # ---- delete --------------------------------------------------------

    def test_delete_removes_file(self) -> None:
        self.store.save("gone", {"x": 1})
        self.store.delete("gone")
        self.assertIsNone(self.store.load("gone"))

    def test_delete_missing_is_noop(self) -> None:
        # Should not raise.
        self.store.delete("never-existed")

    # ---- listing -------------------------------------------------------

    def test_list_ids_excludes_index(self) -> None:
        self.store.save("a", {})
        self.store.save("b", {})
        self.store.save_index({"version": 1})
        self.assertEqual(self.store.list_ids(), ["a", "b"])

    # ---- index ---------------------------------------------------------

    def test_index_persistence_round_trip(self) -> None:
        index = {"version": 1, "active_session": "work", "sessions": []}
        self.store.save_index(index)
        self.assertEqual(self.store.load_index(), index)

    def test_missing_index_returns_default(self) -> None:
        self.assertEqual(
            self.store.load_index(),
            {"version": 1, "active_session": None, "sessions": []},
        )

    def test_corrupt_index_returns_default(self) -> None:
        (self.root / "index.json").write_text("!!!", encoding="utf-8")
        self.assertEqual(
            self.store.load_index(),
            {"version": 1, "active_session": None, "sessions": []},
        )


if __name__ == "__main__":
    unittest.main()