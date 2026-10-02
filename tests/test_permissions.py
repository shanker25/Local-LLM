"""Unit tests for the permission model."""

from __future__ import annotations

import unittest

from src.tools.permissions import Permission, PermissionPolicy


class PermissionTests(unittest.TestCase):
    def test_enum_values(self) -> None:
        self.assertEqual(Permission.READ_ONLY.value, "read_only")
        self.assertEqual(Permission.WRITE.value, "write")
        self.assertEqual(Permission.DESTRUCTIVE.value, "destructive")

    def test_read_only_always_allowed(self) -> None:
        policy = PermissionPolicy()
        self.assertTrue(policy.check("t", Permission.READ_ONLY, {}))

    def test_write_denied_without_callback(self) -> None:
        policy = PermissionPolicy()
        self.assertFalse(policy.check("t", Permission.WRITE, {}))

    def test_destructive_denied_without_callback(self) -> None:
        policy = PermissionPolicy()
        self.assertFalse(policy.check("t", Permission.DESTRUCTIVE, {}))

    def test_write_allowed_with_approving_callback(self) -> None:
        policy = PermissionPolicy(confirm_callback=lambda name, args: True)
        self.assertTrue(policy.check("t", Permission.WRITE, {}))

    def test_write_denied_with_rejecting_callback(self) -> None:
        policy = PermissionPolicy(confirm_callback=lambda name, args: False)
        self.assertFalse(policy.check("t", Permission.WRITE, {}))

    def test_destructive_allowed_with_approving_callback(self) -> None:
        policy = PermissionPolicy(confirm_callback=lambda name, args: True)
        self.assertTrue(policy.check("t", Permission.DESTRUCTIVE, {}))

    def test_callback_receives_tool_name_and_arguments(self) -> None:
        seen: dict = {}

        def cb(name: str, args: dict) -> bool:
            seen["name"] = name
            seen["args"] = args
            return True

        PermissionPolicy(confirm_callback=cb).check("danger", Permission.WRITE, {"x": 1})
        self.assertEqual(seen, {"name": "danger", "args": {"x": 1}})

    def test_callback_exception_is_denial(self) -> None:
        def boom(name: str, args: dict) -> bool:
            raise RuntimeError("callback blew up")

        policy = PermissionPolicy(confirm_callback=boom)
        self.assertFalse(policy.check("t", Permission.WRITE, {}))

    def test_invalid_permission_value_is_denial(self) -> None:
        policy = PermissionPolicy(confirm_callback=lambda n, a: True)
        self.assertFalse(policy.check("t", "read_only", {}))  # not an enum

    def test_is_auto_allowed(self) -> None:
        policy = PermissionPolicy()
        self.assertTrue(policy.is_auto_allowed(Permission.READ_ONLY))
        self.assertFalse(policy.is_auto_allowed(Permission.WRITE))
        self.assertFalse(policy.is_auto_allowed(Permission.DESTRUCTIVE))


if __name__ == "__main__":
    unittest.main()