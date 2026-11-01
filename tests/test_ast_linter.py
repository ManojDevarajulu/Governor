import os
import tempfile
import unittest

from src.linter import lint_file, lint_paths


class TestASTAntiDeterminismLinter(unittest.TestCase):
    def test_flags_wall_clock_calls(self):
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write("import time\ndef get_t(): return time.time()\n")
            tmp_name = f.name

        try:
            violations = lint_file(tmp_name)
            self.assertTrue(any(v.rule == "NON_DETERMINISTIC_CALL" for v in violations))
        finally:
            os.remove(tmp_name)

    def test_flags_raw_socket_imports(self):
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write("import socket\ns = socket.socket()\n")
            tmp_name = f.name

        try:
            violations = lint_file(tmp_name)
            self.assertTrue(any(v.rule == "BANNED_IMPORT" for v in violations))
        finally:
            os.remove(tmp_name)

    def test_governor_codebase_clean(self):
        # Governor's own evaluation codebase must pass the anti-determinism linter with 0 violations
        count, violations = lint_paths(["src/"])
        self.assertEqual(count, 0, f"Governor codebase has non-deterministic violations: {violations}")


if __name__ == "__main__":
    unittest.main()
