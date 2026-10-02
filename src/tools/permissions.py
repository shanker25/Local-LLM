"""Permission model for JARVIS tools.

Every tool declares its permission level. The executor consults a
PermissionPolicy before running a tool and refuses to auto-execute
anything above READ_ONLY.

The policy is deliberately simple: READ_ONLY runs unconditionally;
WRITE and DESTRUCTIVE require a confirmation callback, and if no
callback is provided the tool is denied. This guarantees that no
LLM-generated request can bypass the permission check.
"""

from __future__ import annotations

from enum import Enum
from typing import Callable, Optional


class Permission(Enum):
    """Permission levels, ordered from least to most dangerous."""

    READ_ONLY = "read_only"
    WRITE = "write"
    DESTRUCTIVE = "destructive"


#: A confirmation callback receives (tool_name, arguments) and returns
#: True to allow execution or False to deny. It may block on user input.
ConfirmCallback = Callable[[str, dict], bool]


class PermissionError_(Exception):
    """Raised when a tool action is denied by the policy."""


class PermissionPolicy:
    """Decides whether a tool may execute.

    Default behavior:
      - READ_ONLY   -> always allowed
      - WRITE       -> requires a confirm callback that returns True
      - DESTRUCTIVE -> requires a confirm callback that returns True

    If a non-READ_ONLY tool has no callback configured, it is denied.
    This is the safe default: the absence of a confirmation mechanism
    must never be interpreted as consent.
    """

    def __init__(self, confirm_callback: Optional[ConfirmCallback] = None) -> None:
        self._confirm = confirm_callback

    # ---- policy --------------------------------------------------------

    def check(self, tool_name: str, permission: Permission, arguments: dict) -> bool:
        """Return True if the tool may execute, False otherwise.

        Never raises for ordinary denials -- the executor converts a
        False return into a structured error result.
        """
        if not isinstance(permission, Permission):
            return False

        if permission is Permission.READ_ONLY:
            return True

        if self._confirm is None:
            return False

        try:
            return bool(self._confirm(tool_name, arguments))
        except Exception:
            # A misbehaving callback must not crash the executor.
            return False

    # ---- helpers -------------------------------------------------------

    def is_auto_allowed(self, permission: Permission) -> bool:
        """True if this permission level runs without confirmation."""
        return permission is Permission.READ_ONLY