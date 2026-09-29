"""Unit tests for history.trim()."""

from __future__ import annotations

import unittest

from src.history import trim


def _msg(role: str, content: str) -> dict:
    return {"role": role, "content": content}


class TrimTests(unittest.TestCase):
    def test_system_prompt_preserved(self) -> None:
        msgs = [_msg("user", "hi"), _msg("assistant", "yo")]
        out = trim(msgs, "SYS", 10)
        self.assertEqual(out[0], {"role": "system", "content": "SYS"})

    def test_latest_messages_retained(self) -> None:
        msgs = [_msg("user", str(i)) for i in range(5)]
        out = trim(msgs, "SYS", 2)
        self.assertEqual([m["content"] for m in out[1:]], ["3", "4"])

    def test_max_message_count_respected(self) -> None:
        msgs = [_msg("user", str(i)) for i in range(100)]
        out = trim(msgs, "SYS", 40)
        self.assertEqual(len(out), 41)  # system + 40

    def test_original_list_not_modified(self) -> None:
        msgs = [_msg("user", "a"), _msg("assistant", "b")]
        snapshot = [dict(m) for m in msgs]
        trim(msgs, "SYS", 1)
        self.assertEqual(msgs, snapshot)

    def test_max_messages_zero_returns_system_only(self) -> None:
        msgs = [_msg("user", "a")]
        out = trim(msgs, "SYS", 0)
        self.assertEqual(out, [{"role": "system", "content": "SYS"}])

    def test_max_messages_negative_returns_system_only(self) -> None:
        msgs = [_msg("user", "a")]
        out = trim(msgs, "SYS", -5)
        self.assertEqual(out, [{"role": "system", "content": "SYS"}])

    def test_existing_system_messages_are_dropped_and_replaced(self) -> None:
        msgs = [_msg("system", "OLD"), _msg("user", "hi")]
        out = trim(msgs, "NEW", 10)
        self.assertEqual(out[0]["content"], "NEW")
        self.assertNotIn("OLD", [m["content"] for m in out])

    def test_empty_input(self) -> None:
        out = trim([], "SYS", 10)
        self.assertEqual(out, [{"role": "system", "content": "SYS"}])


if __name__ == "__main__":
    unittest.main()