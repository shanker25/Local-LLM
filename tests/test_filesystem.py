"""Unit tests for the filesystem tools.

Every test uses a temporary workspace so nothing touches the real
project or the user's filesystem outside the temp directory.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from src.tools.filesystem import (
    FileMetadataTool,
    ListDirectoryTool,
    ReadFileTool,
    SearchFilesTool,
)


class _WorkspaceCase(unittest.TestCase):
    """Base class that builds a small sandboxed workspace."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name).resolve()

        # A small tree of files.
        (self.ws / "hello.txt").write_text("hi there", encoding="utf-8")
        (self.ws / "data.json").write_text('{"a": 1}', encoding="utf-8")
        (self.ws / "sub").mkdir()
        (self.ws / "sub" / "nested.py").write_text("print('x')", encoding="utf-8")
        (self.ws / "sub" / "other.txt").write_text("more", encoding="utf-8")
        (self.ws / ".env").write_text("SECRET=1", encoding="utf-8")
        (self.ws / "private.pem").write_text("KEYDATA", encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()


# ---- list_directory ----------------------------------------------------

class ListDirectoryTests(_WorkspaceCase):
    def setUp(self) -> None:
        super().setUp()
        self.tool = ListDirectoryTool(workspace=self.ws)

    def test_metadata(self) -> None:
        self.assertEqual(self.tool.name, "list_directory")
        self.assertIn("path", self.tool.schema["properties"])

    def test_lists_root(self) -> None:
        out = self.tool.execute({"path": "."})
        self.assertTrue(out["success"])
        names = {e["name"] for e in out["result"]["entries"]}
        self.assertIn("hello.txt", names)
        self.assertIn("sub", names)

    def test_lists_subdirectory(self) -> None:
        out = self.tool.execute({"path": "sub"})
        self.assertTrue(out["success"])
        names = {e["name"] for e in out["result"]["entries"]}
        self.assertEqual(names, {"nested.py", "other.txt"})

    def test_rejects_traversal(self) -> None:
        out = self.tool.execute({"path": "../"})
        self.assertFalse(out["success"])
        self.assertIn("escape", out["error"].lower())

    def test_rejects_missing(self) -> None:
        out = self.tool.execute({"path": "nope"})
        self.assertFalse(out["success"])

    def test_rejects_file(self) -> None:
        out = self.tool.execute({"path": "hello.txt"})
        self.assertFalse(out["success"])
        self.assertIn("not a directory", out["error"].lower())

    def test_rejects_empty_path(self) -> None:
        out = self.tool.execute({"path": ""})
        self.assertFalse(out["success"])


# ---- search_files ------------------------------------------------------

class SearchFilesTests(_WorkspaceCase):
    def setUp(self) -> None:
        super().setUp()
        self.tool = SearchFilesTool(workspace=self.ws)

    def test_metadata(self) -> None:
        self.assertEqual(self.tool.name, "search_files")

    def test_non_recursive(self) -> None:
        out = self.tool.execute({"path": ".", "pattern": "*.txt"})
        self.assertTrue(out["success"])
        paths = {m["path"] for m in out["result"]["matches"]}
        self.assertIn("hello.txt", paths)
        self.assertNotIn("sub/other.txt", paths)

    def test_recursive(self) -> None:
        out = self.tool.execute({"path": ".", "pattern": "*.txt", "recursive": True})
        self.assertTrue(out["success"])
        paths = {m["path"] for m in out["result"]["matches"]}
        self.assertIn("hello.txt", paths)
        self.assertIn("sub/other.txt", paths)

    def test_glob_subdirectory(self) -> None:
        out = self.tool.execute({"path": "sub", "pattern": "*.py"})
        self.assertTrue(out["success"])
        paths = {m["path"] for m in out["result"]["matches"]}
        self.assertEqual(paths, {"sub/nested.py"})

    def test_rejects_dotdot_in_pattern(self) -> None:
        out = self.tool.execute({"path": ".", "pattern": "../*.py"})
        self.assertFalse(out["success"])

    def test_rejects_empty_pattern(self) -> None:
        out = self.tool.execute({"path": ".", "pattern": ""})
        self.assertFalse(out["success"])

    def test_rejects_traversal_path(self) -> None:
        out = self.tool.execute({"path": "../", "pattern": "*.txt"})
        self.assertFalse(out["success"])

    def test_missing_path(self) -> None:
        out = self.tool.execute({"path": "nope", "pattern": "*.txt"})
        self.assertFalse(out["success"])

    def test_excludes_secrets(self) -> None:
        out = self.tool.execute({"path": ".", "pattern": "*.pem"})
        self.assertTrue(out["success"])
        paths = {m["path"] for m in out["result"]["matches"]}
        self.assertNotIn("private.pem", paths)


# ---- read_file ---------------------------------------------------------

class ReadFileTests(_WorkspaceCase):
    def setUp(self) -> None:
        super().setUp()
        self.tool = ReadFileTool(workspace=self.ws, max_size=1024 * 1024)

    def test_metadata(self) -> None:
        self.assertEqual(self.tool.name, "read_file")

    def test_reads_text(self) -> None:
        out = self.tool.execute({"path": "hello.txt"})
        self.assertTrue(out["success"])
        self.assertEqual(out["result"]["content"], "hi there")
        self.assertFalse(out["result"]["truncated"])

    def test_rejects_traversal(self) -> None:
        out = self.tool.execute({"path": "../anything"})
        self.assertFalse(out["success"])

    def test_rejects_env(self) -> None:
        out = self.tool.execute({"path": ".env"})
        self.assertFalse(out["success"])
        self.assertIn("denylist", out["error"].lower())

    def test_rejects_pem(self) -> None:
        out = self.tool.execute({"path": "private.pem"})
        self.assertFalse(out["success"])

    def test_missing_file(self) -> None:
        out = self.tool.execute({"path": "nope.txt"})
        self.assertFalse(out["success"])

    def test_directory_rejected(self) -> None:
        out = self.tool.execute({"path": "sub"})
        self.assertFalse(out["success"])
        self.assertIn("directory", out["error"].lower())

    def test_binary_rejected(self) -> None:
        (self.ws / "blob.bin").write_bytes(b"\x00\x01\x02")
        out = self.tool.execute({"path": "blob.bin"})
        self.assertFalse(out["success"])
        self.assertIn("binary", out["error"].lower())

    def test_non_utf8_rejected(self) -> None:
        (self.ws / "latin1.txt").write_bytes(b"caf\xe9")
        out = self.tool.execute({"path": "latin1.txt"})
        self.assertFalse(out["success"])
        self.assertIn("utf-8", out["error"].lower())

    def test_truncation(self) -> None:
        small = ReadFileTool(workspace=self.ws, max_size=4)
        out = small.execute({"path": "hello.txt"})
        self.assertTrue(out["success"])
        self.assertTrue(out["result"]["truncated"])
        self.assertEqual(out["result"]["content"], "hi t")
        self.assertEqual(out["result"]["truncated_at"], 4)
        self.assertIn("message", out["result"])

    def test_empty_path_rejected(self) -> None:
        out = self.tool.execute({"path": ""})
        self.assertFalse(out["success"])


# ---- file_metadata -----------------------------------------------------

class FileMetadataTests(_WorkspaceCase):
    def setUp(self) -> None:
        super().setUp()
        self.tool = FileMetadataTool(workspace=self.ws)

    def test_metadata(self) -> None:
        self.assertEqual(self.tool.name, "file_metadata")

    def test_file(self) -> None:
        out = self.tool.execute({"path": "hello.txt"})
        self.assertTrue(out["success"])
        self.assertEqual(out["result"]["type"], "file")
        self.assertEqual(out["result"]["size"], 8)

    def test_directory(self) -> None:
        out = self.tool.execute({"path": "sub"})
        self.assertTrue(out["success"])
        self.assertEqual(out["result"]["type"], "dir")

    def test_rejects_traversal(self) -> None:
        out = self.tool.execute({"path": "../"})
        self.assertFalse(out["success"])

    def test_missing(self) -> None:
        out = self.tool.execute({"path": "nope"})
        self.assertFalse(out["success"])

    def test_env_denied(self) -> None:
        out = self.tool.execute({"path": ".env"})
        self.assertFalse(out["success"])


# ---- sandbox ----------------------------------------------------------

class SandboxTests(_WorkspaceCase):
    def test_absolute_path_outside_workspace_rejected(self) -> None:
        tool = ReadFileTool(workspace=self.ws)
        # A path that definitely exists outside the workspace.
        outside = str(Path(tempfile.gettempdir()) / "whatever.txt")
        out = tool.execute({"path": outside})
        self.assertFalse(out["success"])

    @unittest.skipIf(os.name == "nt", "symlink test is POSIX-specific")
    def test_symlink_escape_rejected(self) -> None:
        outside_dir = tempfile.TemporaryDirectory()
        self.addCleanup(outside_dir.cleanup)
        outside_file = Path(outside_dir.name) / "secret.txt"
        outside_file.write_text("nope", encoding="utf-8")

        link = self.ws / "sneaky.txt"
        try:
            link.symlink_to(outside_file)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks not supported on this platform")

        tool = ReadFileTool(workspace=self.ws)
        out = tool.execute({"path": "sneaky.txt"})
        self.assertFalse(out["success"])


if __name__ == "__main__":
    unittest.main()