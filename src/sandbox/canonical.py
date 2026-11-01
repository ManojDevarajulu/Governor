"""
Canonical path normalization and boundary verification primitives.
Ensures symlinks, traversal dots ('..'), and indirection cannot escape permitted boundaries.
"""

from typing import Callable, Optional, Set


class PathTraversalEscapeError(Exception):
    """Raised when a resolved path escapes outside the canonical root boundary."""
    pass


class SymlinkLoopError(Exception):
    """Raised when circular symlinks are encountered during path resolution."""
    pass


def normalize_posix_path(raw_path: str, cwd: str = "/") -> str:
    """Normalizes a raw path string into an absolute POSIX path without resolving symlinks."""
    cleaned = raw_path.replace("\\", "/").strip()
    if not cleaned.startswith("/"):
        base = cwd.rstrip("/")
        cleaned = f"{base}/{cleaned}"

    segments = []
    for part in cleaned.split("/"):
        if not part or part == ".":
            continue
        elif part == "..":
            if segments:
                segments.pop()
        else:
            segments.append(part)

    return "/" + "/".join(segments)


def resolve_canonical_path(
    path: str,
    symlink_resolver: Optional[Callable[[str], Optional[str]]] = None,
    cwd: str = "/",
    max_symlink_depth: int = 16,
) -> str:
    """
    Deterministically resolves a path to its canonical form, following symlinks iteratively.
    Guarantees termination against circular symlinks up to max_symlink_depth.
    """
    current = normalize_posix_path(path, cwd=cwd)
    if symlink_resolver is None:
        return current

    seen_symlinks: Set[str] = set()
    depth = 0

    while depth < max_symlink_depth:
        parts = current.strip("/").split("/")
        resolved_prefix = "/"
        target_found = False

        for i, part in enumerate(parts):
            if not part:
                continue
            cand = (resolved_prefix.rstrip("/") + "/" + part).replace("//", "/")
            link_target = symlink_resolver(cand)
            if link_target is not None:
                if cand in seen_symlinks:
                    raise SymlinkLoopError(f"Circular symlink loop detected at '{cand}' -> '{link_target}'")
                seen_symlinks.add(cand)

                # Reconstruct remaining path
                remaining = "/".join(parts[i + 1:])
                if link_target.startswith("/"):
                    new_path = link_target + ("/" + remaining if remaining else "")
                else:
                    new_path = resolved_prefix.rstrip("/") + "/" + link_target + ("/" + remaining if remaining else "")
                current = normalize_posix_path(new_path, cwd=cwd)
                target_found = True
                depth += 1
                break
            else:
                resolved_prefix = cand

        if not target_found:
            return current

    raise SymlinkLoopError(f"Exceeded maximum symlink resolution depth ({max_symlink_depth}) for '{path}'")


def is_within_boundary(path: str, allowed_root: str) -> bool:
    """
    Checks whether canonical `path` is contained within `allowed_root`.
    Both paths should be normalized canonical paths.
    """
    norm_path = normalize_posix_path(path)
    norm_root = normalize_posix_path(allowed_root).rstrip("/")

    if norm_root == "":
        return True
    if norm_path == norm_root:
        return True
    return norm_path.startswith(norm_root + "/")
