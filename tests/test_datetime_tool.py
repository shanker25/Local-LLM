"""Unit tests for the date/time tool."""

from __future__ import annotations

import re
import unittest
from datetime import datetime, timezone

from src.tools.datetime_tool import DateTimeTool


_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ISO_DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")


class DateTimeToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tool = DateTimeTool()

    # ---- metadata ------------------------------------------------------

    def test_metadata(self) -> None:
        self.assertEqual(self.tool.name, "get_datetime")
        self.assertTrue(self.tool.description)
        self.assertEqual(self.tool.schema["type"], "object")
        self.assertIn("mode", self.tool.schema["properties"])
        self.assertEqual(self.tool.schema["required"], ["mode"])

    # ---- local_time ----------------------------------------------------

    def test_local_time_returns_iso_datetime(self) -> None:
        out = self.tool.execute({"mode": "local_time"})
        self.assertTrue(out["success"])
        self.assertRegex(out["result"], _ISO_DATETIME_RE)

    def test_local_time_is_close_to_now(self) -> None:
        before = datetime.now().astimezone().replace(microsecond=0)
        out = self.tool.execute({"mode": "local_time"})
        after = datetime.now().astimezone().replace(microsecond=0)
        result = datetime.fromisoformat(out["result"])
        self.assertLessEqual(before, result)
        self.assertLessEqual(result, after)

    # ---- local_date ----------------------------------------------------

    def test_local_date_returns_iso_date(self) -> None:
        out = self.tool.execute({"mode": "local_date"})
        self.assertTrue(out["success"])
        self.assertRegex(out["result"], _ISO_DATE_RE)

    def test_local_date_matches_today(self) -> None:
        out = self.tool.execute({"mode": "local_date"})
        self.assertEqual(out["result"], datetime.now().date().isoformat())

    # ---- utc -----------------------------------------------------------

    def test_utc_returns_iso_datetime_with_offset(self) -> None:
        out = self.tool.execute({"mode": "utc"})
        self.assertTrue(out["success"])
        self.assertIn("+00:00", out["result"])

    def test_utc_is_close_to_now(self) -> None:
        before = datetime.now(timezone.utc).replace(microsecond=0)
        out = self.tool.execute({"mode": "utc"})
        after = datetime.now(timezone.utc).replace(microsecond=0)
        result = datetime.fromisoformat(out["result"])
        self.assertLessEqual(before, result)
        self.assertLessEqual(result, after)

    # ---- errors --------------------------------------------------------

    def test_invalid_mode(self) -> None:
        out = self.tool.execute({"mode": "yesterday"})
        self.assertFalse(out["success"])
        self.assertIn("Invalid mode", out["error"])

    def test_missing_mode(self) -> None:
        out = self.tool.execute({})
        self.assertFalse(out["success"])
        self.assertIn("Invalid mode", out["error"])

    def test_non_string_mode(self) -> None:
        out = self.tool.execute({"mode": 42})
        self.assertFalse(out["success"])

    # ---- purity --------------------------------------------------------

    def test_repeated_calls_do_not_share_state(self) -> None:
        a = self.tool.execute({"mode": "local_date"})
        b = self.tool.execute({"mode": "local_date"})
        self.assertEqual(a["result"], b["result"])


if __name__ == "__main__":
    unittest.main()