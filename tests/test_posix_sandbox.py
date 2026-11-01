import unittest

from src.sandbox import (
    DeterministicPOSIXSandbox,
    PathTraversalEscapeError,
    SymlinkLoopError,
    is_within_boundary,
    normalize_posix_path,
    resolve_canonical_path,
)


class TestPOSIXSandbox(unittest.TestCase):
    def setUp(self):
        self.sb = DeterministicPOSIXSandbox(root_scope="/project")

    def test_basic_file_lifecycle(self):
        self.sb.write_file("/project/src/app.py", "print('hello')\n")
        self.assertTrue(self.sb.exists("/project/src/app.py"))
        self.assertEqual(self.sb.read_file("/project/src/app.py"), "print('hello')\n")

        self.sb.unlink("/project/src/app.py")
        self.assertFalse(self.sb.exists("/project/src/app.py"))

    def test_canonical_path_normalization(self):
        self.assertEqual(normalize_posix_path("/project/../project/src/./file.py"), "/project/src/file.py")
        self.assertEqual(normalize_posix_path("relative/path", cwd="/project"), "/project/relative/path")
        self.assertEqual(normalize_posix_path("/a/b/c/../../d"), "/a/d")

    def test_boundary_containment(self):
        self.assertTrue(is_within_boundary("/project/src/app.py", "/project"))
        self.assertTrue(is_within_boundary("/project", "/project"))
        self.assertFalse(is_within_boundary("/etc/passwd", "/project"))
        self.assertFalse(is_within_boundary("/project_other/file.py", "/project"))

    def test_symlink_resolution_and_traversal(self):
        # Create a symlink pointing inside project
        self.sb.write_file("/project/real.txt", "real_content")
        self.sb.symlink("/project/real.txt", "/project/link.txt")
        self.assertEqual(self.sb.read_file("/project/link.txt"), "real_content")

    def test_symlink_loop_detection(self):
        # A points to B, B points to A
        self.sb.symlink("/project/b.txt", "/project/a.txt")
        self.sb.symlink("/project/a.txt", "/project/b.txt")
        with self.assertRaises(SymlinkLoopError):
            self.sb.canonical("/project/a.txt")

    def test_state_hashing_determinism(self):
        # Two sandboxes initialized with identical commands must have identical state hashes
        sb1 = DeterministicPOSIXSandbox(root_scope="/project")
        sb2 = DeterministicPOSIXSandbox(root_scope="/project")

        sb1.write_file("/project/a.py", "x = 1\n")
        sb1.write_file("/project/b.py", "y = 2\n")

        sb2.write_file("/project/a.py", "x = 1\n")
        sb2.write_file("/project/b.py", "y = 2\n")

        self.assertEqual(sb1.state_hash(), sb2.state_hash())


if __name__ == "__main__":
    unittest.main()
