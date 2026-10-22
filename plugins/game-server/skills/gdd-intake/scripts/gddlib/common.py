from __future__ import annotations

import hashlib
import os
import shutil
import stat
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SUPPORTED_SUFFIXES = frozenset({".docx", ".xlsx", ".html", ".htm"})


@dataclass(frozen=True)
class SourceFile:
    root: Path
    absolute: Path
    relative: Path
    suffix: str


@dataclass
class OperationResult:
    source: str
    output: str
    status: str
    source_md5: str
    details: dict[str, Any]


def resolve_source_file(
    gdd_dir: Path,
    source: str,
    allowed_suffixes: frozenset[str] = SUPPORTED_SUFFIXES,
) -> SourceFile:
    if not allowed_suffixes <= SUPPORTED_SUFFIXES:
        raise ValueError("unsupported source extension allowlist")
    root = gdd_dir.resolve(strict=True)
    candidate = (root / source).resolve()
    if not candidate.is_relative_to(root):
        raise ValueError(f"source is outside gdd_dir: {source}")
    if not candidate.is_file():
        raise ValueError(f"source must be a file, not a directory: {source}")
    if candidate.name.startswith("~$"):
        raise ValueError(f"temporary Office file is not allowed: {source}")
    suffix = candidate.suffix.lower()
    if suffix not in allowed_suffixes:
        raise ValueError(f"unsupported source extension: {suffix or '<none>'}")
    return SourceFile(root, candidate, candidate.relative_to(root), suffix)


def output_path_for(source: SourceFile, output_root: Path) -> Path:
    output = output_root.resolve() / source.relative
    return output.with_suffix(".md") if source.suffix in {".docx", ".xlsx"} else output


def validate_output_destination(
    output_root: Path,
    output: Path,
) -> Path:
    if ".." in output_root.parts or ".." in output.parts:
        raise ValueError("ambiguous output path")
    lexical_root = Path(os.path.abspath(output_root))
    lexical_destination = Path(os.path.abspath(output))

    for boundary in (
        *reversed(lexical_root.parents),
        lexical_root,
    ):
        try:
            status = boundary.lstat()
        except FileNotFoundError:
            continue
        if _is_reparse(status):
            raise ValueError(
                "output_root crosses a symlink or reparse point: "
                f"{boundary}"
            )
    try:
        root_status = lexical_root.lstat()
    except FileNotFoundError as error:
        raise ValueError(
            f"output_root does not exist: {output_root}"
        ) from error
    if not stat.S_ISDIR(root_status.st_mode):
        raise ValueError(
            f"output_root must be a real directory: {output_root}"
        )

    for boundary in (
        *reversed(lexical_destination.parents),
        lexical_destination,
    ):
        try:
            status = boundary.lstat()
        except FileNotFoundError:
            continue
        if _is_reparse(status):
            raise ValueError(
                "output crosses a symlink or reparse point: "
                f"{boundary}"
            )

    root = lexical_root.resolve(strict=True)
    destination = lexical_destination.resolve()
    if not destination.is_relative_to(root) or destination == root:
        raise ValueError(
            f"output is outside output_root: {output}"
        )

    current = root
    relative = destination.relative_to(root)
    for index, component in enumerate(relative.parts):
        current /= component
        try:
            status = current.lstat()
        except FileNotFoundError:
            continue
        if _is_reparse(status):
            raise ValueError(
                "output crosses a symlink or reparse point: "
                f"{current}"
            )
        if index < len(relative.parts) - 1:
            if not stat.S_ISDIR(status.st_mode):
                raise ValueError(
                    f"output parent is not a directory: {current}"
                )
        elif not stat.S_ISREG(status.st_mode):
            raise ValueError(
                f"output is not a regular file: {current}"
            )

    resolved_root = root.resolve(strict=True)
    resolved_parent = destination.parent.resolve()
    if not resolved_parent.is_relative_to(resolved_root):
        raise ValueError(
            f"output is outside output_root: {output}"
        )
    return destination


def _is_reparse(status: os.stat_result) -> bool:
    attributes = getattr(status, "st_file_attributes", 0)
    reparse_flag = getattr(
        stat,
        "FILE_ATTRIBUTE_REPARSE_POINT",
        0x400,
    )
    return stat.S_ISLNK(status.st_mode) or bool(
        attributes & reparse_flag
    )


def md5_file(path: Path) -> str:
    return _hash_file(path, hashlib.md5())


def sha256_file(path: Path) -> str:
    return _hash_file(path, hashlib.sha256())


def _hash_file(path: Path, digest: Any) -> str:
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = text.rstrip() + "\n"
    temporary = _temporary_path(path)
    try:
        temporary.write_text(normalized, encoding="utf-8", newline="\n")
        if path.exists():
            path.chmod(stat.S_IREAD | stat.S_IWRITE)
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()


def copy_file_atomic(source: Path, output: Path) -> None:
    expected_source_hash = sha256_file(source)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = _temporary_path(output)
    try:
        shutil.copyfile(source, temporary)
        if sha256_file(temporary) != expected_source_hash or sha256_file(source) != expected_source_hash:
            raise RuntimeError("source changed during copy")
        if output.exists():
            output.chmod(stat.S_IREAD | stat.S_IWRITE)
        temporary.replace(output)
    finally:
        if temporary.exists():
            temporary.unlink()
    if sha256_file(output) != expected_source_hash:
        raise RuntimeError("file hash mismatch after copy")


def _temporary_path(path: Path) -> Path:
    with tempfile.NamedTemporaryFile(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".gdd.tmp",
        delete=False,
    ) as handle:
        return Path(handle.name)


def configure_utf8_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="backslashreplace")
