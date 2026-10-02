"""System information tools for JARVIS.

Read-only introspection of the host machine: OS, Python, CPU, memory,
and disk usage for the workspace filesystem.

Explicitly excluded (privacy):
    - hostname, username, home directory
    - MAC addresses, IP addresses
    - full os.environ contents
    - process list, open ports, running services
    - any credential-shaped value

Memory and disk use only the standard library. On Windows, memory
is read via ctypes + GlobalMemoryStatusEx. On POSIX, via os.sysconf.
No third-party packages.
"""

from __future__ import annotations

import os
import platform
import shutil
import sys
from pathlib import Path
from typing import Any

from src.tools.base import Tool


# ---- helpers -----------------------------------------------------------

def _human_bytes(n: int | float) -> str:
    """Return a compact human-readable byte size."""
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    size = float(n)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{int(n)} B"


def _memory_info() -> dict[str, Any] | None:
    """Return total/available memory in bytes, or None if unavailable."""
    # POSIX: os.sysconf
    if hasattr(os, "sysconf"):
        try:
            page_size = os.sysconf("SC_PAGE_SIZE")
            total_pages = os.sysconf("SC_PHYS_PAGES")
            avail_pages = os.sysconf("SC_AVPHYS_PAGES")
            total = page_size * total_pages
            available = page_size * avail_pages
            return {"total": total, "available": available}
        except (ValueError, OSError, AttributeError):
            pass

    # Windows: ctypes + GlobalMemoryStatusEx
    if sys.platform.startswith("win"):
        try:
            import ctypes

            class _MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            status = _MEMORYSTATUSEX()
            status.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return {
                    "total": int(status.ullTotalPhys),
                    "available": int(status.ullAvailPhys),
                }
        except Exception:  # noqa: BLE001
            pass

    return None


# ---- tools -------------------------------------------------------------

class SystemOsTool(Tool):
    name = "system_os"
    description = (
        "Report basic operating system information: system name, "
        "release, version, machine architecture, and platform string."
    )
    schema = {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    }

    def execute(self, arguments: dict) -> dict:
        result = {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "platform": platform.platform(),
        }
        return {"success": True, "result": result, "error": None}


class SystemPythonTool(Tool):
    name = "system_python"
    description = (
        "Report the Python interpreter version, implementation, "
        "compiler, and executable path."
    )
    schema = {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    }

    def execute(self, arguments: dict) -> dict:
        v = sys.version_info
        result = {
            "version": f"{v.major}.{v.minor}.{v.micro}",
            "version_tuple": [v.major, v.minor, v.micro],
            "implementation": platform.python_implementation(),
            "compiler": platform.python_compiler(),
            "executable": sys.executable,
        }
        return {"success": True, "result": result, "error": None}


class SystemCpuTool(Tool):
    name = "system_cpu"
    description = (
        "Report the number of logical CPUs and a short processor "
        "description, if the platform provides one."
    )
    schema = {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    }

    def execute(self, arguments: dict) -> dict:
        result = {
            "logical_count": os.cpu_count(),
            "processor": platform.processor() or None,
            "machine": platform.machine() or None,
        }
        return {"success": True, "result": result, "error": None}


class SystemMemoryTool(Tool):
    name = "system_memory"
    description = (
        "Report total and available physical memory in bytes and "
        "human-readable form. Returns success=false if the platform "
        "does not expose memory information."
    )
    schema = {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    }

    def execute(self, arguments: dict) -> dict:
        info = _memory_info()
        if info is None:
            return {
                "success": False,
                "result": None,
                "error": "Memory information is not available on this platform.",
            }
        total = info["total"]
        available = info["available"]
        used = total - available
        percent_used = (used / total * 100.0) if total else 0.0
        result = {
            "total": total,
            "total_human": _human_bytes(total),
            "available": available,
            "available_human": _human_bytes(available),
            "used": used,
            "used_human": _human_bytes(used),
            "percent_used": round(percent_used, 1),
        }
        return {"success": True, "result": result, "error": None}


class SystemDiskTool(Tool):
    name = "system_disk"
    description = (
        "Report total, used, and free disk space for the filesystem "
        "that contains the workspace directory."
    )
    schema = {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    }

    def __init__(self, workspace: str | os.PathLike = ".") -> None:
        self._workspace = Path(workspace).expanduser().resolve()

    def execute(self, arguments: dict) -> dict:
        target = self._workspace if self._workspace.exists() else Path(".")
        try:
            usage = shutil.disk_usage(target)
        except OSError as exc:
            return {
                "success": False,
                "result": None,
                "error": f"Could not read disk usage: {exc}",
            }
        used = usage.total - usage.free
        percent_used = (used / usage.total * 100.0) if usage.total else 0.0
        result = {
            "path": str(target),
            "total": usage.total,
            "total_human": _human_bytes(usage.total),
            "used": used,
            "used_human": _human_bytes(used),
            "free": usage.free,
            "free_human": _human_bytes(usage.free),
            "percent_used": round(percent_used, 1),
        }
        return {"success": True, "result": result, "error": None}