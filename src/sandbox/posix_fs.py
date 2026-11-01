"""
Deterministic in-memory POSIX-like sandbox with canonical symlink resolution
and SHA-256 state hashing for reproducible research evaluations.
"""

import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from src.sandbox.canonical import (
    PathTraversalEscapeError,
    is_within_boundary,
    normalize_posix_path,
    resolve_canonical_path,
)


@dataclass
class FSEntry:
    path: str
    is_dir: bool = False
    is_symlink: bool = False
    content: str = ""
    symlink_target: str = ""


@dataclass
class FileSystemEvent:
    op: str
    target: str
    details: str = ""
    state_hash_after: str = ""


class DeterministicPOSIXSandbox:
    """
    Zero-disk, in-memory POSIX filesystem model.
    Guarantees bit-for-bit replayability from a seed.
    """

    def __init__(self, root_scope: str = "/project"):
        self.root_scope = normalize_posix_path(root_scope)
        self.entries: Dict[str, FSEntry] = {}
        self.events: List[FileSystemEvent] = []

        # Initialize root and root scope
        self._raw_mkdir("/")
        self._raw_mkdir(self.root_scope)

    def _raw_mkdir(self, path: str):
        norm = normalize_posix_path(path)
        if norm not in self.entries:
            self.entries[norm] = FSEntry(path=norm, is_dir=True)

    def symlink_resolver(self, path: str) -> Optional[str]:
        norm = normalize_posix_path(path)
        entry = self.entries.get(norm)
        if entry and entry.is_symlink:
            return entry.symlink_target
        return None

    def canonical(self, path: str, cwd: str = "/") -> str:
        return resolve_canonical_path(path, symlink_resolver=self.symlink_resolver, cwd=cwd)

    def mkdir(self, path: str, cwd: str = "/"):
        resolved = self.canonical(path, cwd=cwd)
        parts = resolved.strip("/").split("/")
        accum = "/"
        for part in parts:
            if not part:
                continue
            accum = (accum.rstrip("/") + "/" + part).replace("//", "/")
            if accum in self.entries and not self.entries[accum].is_dir:
                raise FileExistsError(f"Path component '{accum}' exists and is not a directory")
            self._raw_mkdir(accum)

        h = self.state_hash()
        self.events.append(FileSystemEvent(op="mkdir", target=resolved, state_hash_after=h))

    def write_file(self, path: str, content: str, cwd: str = "/"):
        resolved = self.canonical(path, cwd=cwd)
        parent = normalize_posix_path(resolved + "/..")
        if parent not in self.entries or not self.entries[parent].is_dir:
            self.mkdir(parent)

        self.entries[resolved] = FSEntry(
            path=resolved,
            is_dir=False,
            is_symlink=False,
            content=content,
        )
        h = self.state_hash()
        self.events.append(FileSystemEvent(op="write", target=resolved, state_hash_after=h))

    def read_file(self, path: str, cwd: str = "/") -> str:
        resolved = self.canonical(path, cwd=cwd)
        entry = self.entries.get(resolved)
        if not entry:
            raise FileNotFoundError(f"No such file: '{resolved}'")
        if entry.is_dir:
            raise IsADirectoryError(f"Path '{resolved}' is a directory")
        return entry.content

    def unlink(self, path: str, cwd: str = "/"):
        resolved = self.canonical(path, cwd=cwd)
        if resolved not in self.entries:
            raise FileNotFoundError(f"No such file to unlink: '{resolved}'")
        del self.entries[resolved]
        h = self.state_hash()
        self.events.append(FileSystemEvent(op="unlink", target=resolved, state_hash_after=h))

    def symlink(self, target: str, link_path: str, cwd: str = "/"):
        norm_link = normalize_posix_path(link_path, cwd=cwd)
        parent = normalize_posix_path(norm_link + "/..")
        if parent not in self.entries or not self.entries[parent].is_dir:
            self.mkdir(parent)

        self.entries[norm_link] = FSEntry(
            path=norm_link,
            is_symlink=True,
            symlink_target=target,
        )
        h = self.state_hash()
        self.events.append(
            FileSystemEvent(
                op="symlink",
                target=norm_link,
                details=f"-> {target}",
                state_hash_after=h,
            )
        )

    def exists(self, path: str, cwd: str = "/") -> bool:
        try:
            resolved = self.canonical(path, cwd=cwd)
            return resolved in self.entries
        except Exception:
            return False

    def list_dir(self, path: str, cwd: str = "/") -> List[str]:
        resolved = self.canonical(path, cwd=cwd)
        entry = self.entries.get(resolved)
        if not entry or not entry.is_dir:
            raise NotADirectoryError(f"Not a directory: '{resolved}'")

        res: Set[str] = set()
        prefix = resolved.rstrip("/") + "/"
        for p in self.entries:
            if p.startswith(prefix) and p != resolved:
                sub = p[len(prefix):].split("/")[0]
                if sub:
                    res.add(sub)
        return sorted(list(res))

    def state_hash(self) -> str:
        """
        Computes SHA-256 fingerprint over sorted filesystem paths and their contents.
        Guarantees bit-for-bit replay verification across test seeds.
        """
        hasher = hashlib.sha256()
        for path in sorted(self.entries.keys()):
            entry = self.entries[path]
            hasher.update(path.encode("utf-8"))
            hasher.update(b":dir:" if entry.is_dir else b":file:")
            if entry.is_symlink:
                hasher.update(b":symlink:" + entry.symlink_target.encode("utf-8"))
            elif not entry.is_dir:
                hasher.update(b":content:" + entry.content.encode("utf-8"))
            hasher.update(b"\n")
        return hasher.hexdigest()
