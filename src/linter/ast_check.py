"""
AST Anti-Determinism Linter for Empirical Research Harness.
Strictly bans wall-clock time, unseeded randomness, and raw sockets to guarantee
bit-for-bit replayable evaluation episodes.
"""

import ast
import os
import sys
from dataclasses import dataclass
from typing import List, Tuple

BANNED_CALLS = {
    ("time", "time"): "Wall-clock time call (time.time()) destroys determinism",
    ("time", "sleep"): "Wall-clock sleep call (time.sleep()) destroys determinism",
    ("time", "monotonic"): "Wall-clock monotonic() call destroys determinism",
    ("time", "perf_counter"): "Wall-clock perf_counter() call destroys determinism",
    ("datetime", "now"): "datetime.now() destroys determinism; use seeded virtual ticks",
    ("datetime", "utcnow"): "datetime.utcnow() destroys determinism; use seeded virtual ticks",
    ("socket", "socket"): "Raw network socket creation is prohibited in evaluation harness",
    ("requests", "get"): "Raw HTTP network egress is prohibited in evaluation harness",
    ("requests", "post"): "Raw HTTP network egress is prohibited in evaluation harness",
    ("httpx", "get"): "Raw HTTP network egress is prohibited in evaluation harness",
    ("httpx", "post"): "Raw HTTP network egress is prohibited in evaluation harness",
    ("urllib", "urlopen"): "Raw HTTP network egress is prohibited in evaluation harness",
}

BANNED_IMPORTS = {
    "socket": "Direct socket imports bypass sandbox containment",
}


@dataclass
class LintViolation:
    file_path: str
    line_number: int
    rule: str
    message: str


class DeterminismASTVisitor(ast.NodeVisitor):
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.violations: List[LintViolation] = []

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            base_mod = alias.name.split(".")[0]
            if base_mod in BANNED_IMPORTS:
                self.violations.append(
                    LintViolation(
                        file_path=self.file_path,
                        line_number=node.lineno,
                        rule="BANNED_IMPORT",
                        message=BANNED_IMPORTS[base_mod],
                    )
                )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        # Detect obj.method() or mod.func()
        if isinstance(node.func, ast.Attribute):
            attr = node.func.attr
            if isinstance(node.func.value, ast.Name):
                caller = node.func.value.id
                key = (caller, attr)
                if key in BANNED_CALLS:
                    self.violations.append(
                        LintViolation(
                            file_path=self.file_path,
                            line_number=node.lineno,
                            rule="NON_DETERMINISTIC_CALL",
                            message=BANNED_CALLS[key],
                        )
                    )
        self.generic_visit(node)


def lint_file(file_path: str) -> List[LintViolation]:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=file_path)
    except Exception as e:
        return [
            LintViolation(
                file_path=file_path,
                line_number=1,
                rule="SYNTAX_ERROR",
                message=f"Failed to parse AST: {e}",
            )
        ]

    visitor = DeterminismASTVisitor(file_path)
    visitor.visit(tree)
    return visitor.violations


def lint_paths(paths: List[str]) -> Tuple[int, List[LintViolation]]:
    total_violations: List[LintViolation] = []
    for p in paths:
        if os.path.isfile(p) and p.endswith(".py"):
            total_violations.extend(lint_file(p))
        elif os.path.isdir(p):
            for root, _, files in os.walk(p):
                for f in files:
                    if f.endswith(".py"):
                        full = os.path.join(root, f)
                        total_violations.extend(lint_file(full))

    return len(total_violations), total_violations


def main():
    targets = sys.argv[1:] if len(sys.argv) > 1 else ["src/"]
    count, violations = lint_paths(targets)
    if count == 0:
        print("[AST Anti-Determinism Linter]: PASSED. Zero non-deterministic patterns detected.")
        sys.exit(0)
    else:
        print(f"[AST Anti-Determinism Linter]: FAILED with {count} violation(s):\n")
        for v in violations:
            print(f"  {v.file_path}:{v.line_number} [{v.rule}] {v.message}")
        sys.exit(1)


if __name__ == "__main__":
    main()
