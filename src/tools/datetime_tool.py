"""Date and time tools for JARVIS.

Reports the current local time, current local date, or current UTC
time. All output is ISO-8601. Uses only the standard library.
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.tools.base import Tool


_VALID_MODES = ("local_time", "local_date", "utc")


class DateTimeTool(Tool):
    name = "get_datetime"
    description = (
        "Return the current date or time. Modes: 'local_time' for local "
        "time, 'local_date' for local date, 'utc' for UTC time. Output "
        "is ISO-8601."
    )
    schema = {
        "type": "object",
        "properties": {
            "mode": {
                "type": "string",
                "description": "One of: local_time, local_date, utc.",
            }
        },
        "required": ["mode"],
        "additionalProperties": False,
    }

    def execute(self, arguments: dict) -> dict:
        mode = arguments.get("mode", "")
        if mode not in _VALID_MODES:
            return {
                "success": False,
                "result": None,
                "error": (
                    f"Invalid mode {mode!r}. "
                    f"Expected one of: {', '.join(_VALID_MODES)}."
                ),
            }

        now = datetime.now()

        if mode == "local_time":
            value = now.astimezone().isoformat(timespec="seconds")
        elif mode == "local_date":
            value = now.date().isoformat()
        else:  # "utc"
            value = datetime.now(timezone.utc).isoformat(timespec="seconds")

        return {"success": True, "result": value, "error": None}