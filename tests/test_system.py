"""Unit tests for the system information tools.

These tests assert on shape, not on specific values, because CPU
counts, memory sizes, and OS versions vary by machine. Nothing here
touches the network, spawns subprocesses, or reads os.environ.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

from src.tools.system import (
    SystemCpuTool,
    SystemDiskTool,
    SystemMemoryTool,
    SystemOsTool,
    SystemPythonTool,
    _human_bytes,
    _memory_info,
)


class HumanBytesTests(unittest.TestCase):
    def test_bytes(self) -> None:
        self.assertEqual(_human_bytes(0), "0 B")
        self.assertEqual(_human_bytes(512), "512 B")

    def test_kilobytes(self) -> None:
        self.assertEqual(_human_bytes(1024), "1.0 KB")

    def test_megabytes(self) -> None:
        self.assertEqual(_human_bytes(1024 * 1024), "1.0 MB")

    def test_gigabytes(self) -> None:
        self.assertEqual(_human_bytes(1024 ** 3), "1.0 GB")


# ---- system_os ---------------------------------------------------------

class SystemOsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tool = SystemOsTool()

    def test_metadata(self) -> None:
        self.assertEqual(self.tool.name, "system_os")
        self.assertEqual(self.tool.schema["type"], "object")
        self.assertEqual(self.tool.schema["properties"], {})

    def test_execute_shape(self) -> None:
        out = self.tool.execute({})
        self.assertTrue(out["success"])
        for key in ("system", "release", "version", "machine", "platform"):
            self.assertIn(key, out["result"])
            self.assertIsInstance(out["result"][key], str)

    def test_no_arguments_needed(self) -> None:
        out = self.tool.execute({})
        self.assertTrue(out["success"])


# ---- system_python -----------------------------------------------------

class SystemPythonTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tool = SystemPythonTool()

    def test_metadata(self) -> None:
        self.assertEqual(self.tool.name, "system_python")

    def test_execute_shape(self) -> None:
        out = self.tool.execute({})
        self.assertTrue(out["success"])
        r = out["result"]
        self.assertRegex(r["version"], r"^\d+\.\d+\.\d+$")
        self.assertEqual(r["version_tuple"][:2], [sys.version_info.major, sys.version_info.minor])
        self.assertIsInstance(r["implementation"], str)
        self.assertIsInstance(r["executable"], str)


# ---- system_cpu --------------------------------------------------------

class SystemCpuTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tool = SystemCpuTool()

    def test_metadata(self) -> None:
        self.assertEqual(self.tool.name, "system_cpu")

    def test_execute_shape(self) -> None:
        out = self.tool.execute({})
        self.assertTrue(out["success"])
        r = out["result"]
        self.assertIn("logical_count", r)
        # os.cpu_count() can be None on exotic platforms; accept either.
        self.assertTrue(r["logical_count"] is None or isinstance(r["logical_count"], int))
        # processor and machine may be empty strings on some platforms;
        # the tool converts those to None.
        self.assertTrue(r["processor"] is None or isinstance(r["processor"], str))
        self.assertTrue(r["machine"] is None or isinstance(r["machine"], str))


# ---- system_memory -----------------------------------------------------

class SystemMemoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tool = SystemMemoryTool()

    def test_metadata(self) -> None:
        self.assertEqual(self.tool.name, "system_memory")

    def test_helper_returns_dict_or_none(self) -> None:
        info = _memory_info()
        if info is not None:
            self.assertIn("total", info)
            self.assertIn("available", info)
            self.assertIsInstance(info["total"], int)
            self.assertIsInstance(info["available"], int)
            self.assertGreater(info["total"], 0)

    def test_execute_shape_when_available(self) -> None:
        info = _memory_info()
        if info is None:
            self.skipTest("memory information unavailable on this platform")
        out = self.tool.execute({})
        self.assertTrue(out["success"])
        r = out["result"]
        for key in ("total", "total_human", "available", "available_human",
                    "used", "used_human", "percent_used"):
            self.assertIn(key, r)
        self.assertGreater(r["total"], 0)
        self.assertGreaterEqual(r["available"], 0)
        self.assertGreaterEqual(r["percent_used"], 0.0)
        self.assertLessEqual(r["percent_used"], 100.0)
        self.assertEqual(r["total"], r["available"] + r["used"])

    def test_execute_returns_failure_when_unavailable(self) -> None:
        # Not directly testable without a mock, but validate the shape
        # the failure path would produce.
        tool = SystemMemoryTool()
        info = _memory_info()
        if info is not None:
            self.skipTest("platform does provide memory info")
        out = tool.execute({})
        self.assertFalse(out["success"])
        self.assertIsNone(out["result"])
        self.assertIsNotNone(out["error"])


# ---- system_disk -------------------------------------------------------

class SystemDiskTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name)
        self.tool = SystemDiskTool(workspace=self.ws)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_metadata(self) -> None:
        self.assertEqual(self.tool.name, "system_disk")

    def test_execute_shape(self) -> None:
        out = self.tool.execute({})
        self.assertTrue(out["success"])
        r = out["result"]
        for key in ("path", "total", "total_human", "used", "used_human",
                    "free", "free_human", "percent_used"):
            self.assertIn(key, r)
        self.assertGreater(r["total"], 0)
        self.assertGreaterEqual(r["free"], 0)
        self.assertEqual(r["total"], r["used"] + r["free"])
        self.assertGreaterEqual(r["percent_used"], 0.0)
        self.assertLessEqual(r["percent_used"], 100.0)

    def test_human_readable_sizes(self) -> None:
        out = self.tool.execute({})
        r = out["result"]
        for key in ("total_human", "used_human", "free_human"):
            self.assertIsInstance(r[key], str)
            self.assertTrue(r[key])


# ---- cross-tool --------------------------------------------------------

class SystemToolsContractTests(unittest.TestCase):
    """Common contract checks across every system tool."""

    def test_all_have_descriptions(self) -> None:
        for cls in (SystemOsTool, SystemPythonTool, SystemCpuTool,
                    SystemMemoryTool, SystemDiskTool):
            self.assertTrue(cls.description.strip())

    def test_all_have_no_properties(self) -> None:
        # Every system tool takes zero arguments.
        for cls in (SystemOsTool, SystemPythonTool, SystemCpuTool,
                    SystemMemoryTool, SystemDiskTool):
            self.assertEqual(cls.schema.get("properties"), {})
            self.assertEqual(cls.schema.get("required"), [])

    def test_execute_returns_standard_shape(self) -> None:
        for cls in (SystemOsTool, SystemPythonTool, SystemCpuTool,
                    SystemMemoryTool, SystemDiskTool):
            tool = cls()
            out = tool.execute({})
            self.assertIn("success", out)
            self.assertIn("result", out)
            self.assertIn("error", out)

    def test_no_os_environ_in_result(self) -> None:
        # Belt-and-braces: dump the result as a string and verify no
        # obvious secret markers leak through.
        import json
        markers = ("SECRET", "TOKEN", "PASSWORD", "API_KEY", "CREDENTIAL")
        for cls in (SystemOsTool, SystemPythonTool, SystemCpuTool,
                    SystemMemoryTool, SystemDiskTool):
            tool = cls()
            out = tool.execute({})
            blob = json.dumps(out).upper()
            for marker in markers:
                self.assertNotIn(marker, blob)


if __name__ == "__main__":
    unittest.main()