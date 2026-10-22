from __future__ import annotations

from bisect import bisect_right
import hashlib
from html import unescape as unescape_html
import os
import re
import stat
import struct
import unicodedata
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Any, Iterator, Sequence
from urllib.parse import unquote


HEADING_RE = re.compile(r"^\s*(#{1,6})\s+(.+?)\s*$")
HTML_ANCHOR_RE = re.compile(
    r"<a\s+[^>]*\b(?:id|name)\s*=\s*"
    r"(?:\"([^\"]+)\"|'([^']+)'|([^\s>]+))[^>]*>",
    re.IGNORECASE,
)
WORD_TOC_ANCHOR_RE = re.compile(
    r"<a\s+[^>]*\b(?:id|name)\s*=\s*"
    r"(?:\"_Toc\d+\"|'_Toc\d+'|_Toc\d+)[^>]*>",
    re.IGNORECASE,
)
STYLE_DELIMITER_ARTIFACT_RE = re.compile(
    r"\*{4,}|~{4,}|\*\*\s+\*\*|~~\s+~~"
)
FENCE_RE = re.compile(
    r"^(?P<quotes>(?: {0,3}>[ \t]?)*?)"
    r"(?P<list> {0,3}(?:[-+*]|\d{1,9}[.)])[ \t]+)?"
    r"(?P<indent>[ \t]*)"
    r"(?P<marker>`{3,}|~{3,})(?P<trailing>.*)$"
)
LIST_ITEM_RE = re.compile(
    r"^(?P<quotes>(?: {0,3}>[ \t]?)*?)"
    r"(?P<indent> {0,3})"
    r"(?P<marker>[-+*]|\d{1,9}[.)])"
    r"(?P<spacing>[ \t]+)"
)
CONTAINER_INDENT_RE = re.compile(
    r"^(?P<quotes>(?: {0,3}>[ \t]?)*)(?P<indent>[ \t]*)"
)
REFERENCE_DEFINITION_RE = re.compile(
    r"^[ \t]{0,3}\[(?P<label>(?:\\.|[^\]])+)\]:"
    r"[ \t]*(?P<destination>.+?)\s*$"
)
HTML_IMAGE_RE = re.compile(
    r"<img\b(?:[^>\"']|\"[^\"]*\"|'[^']*')*>",
    re.IGNORECASE | re.DOTALL,
)
HTML_ATTRIBUTE_RE = re.compile(
    r"(?<![\w:-])(?P<name>src|alt)\s*=\s*"
    r"(?P<value>\"[^\"]*\"|'[^']*'|[^\s>]+)",
    re.IGNORECASE | re.DOTALL,
)
URI_SCHEME_RE = re.compile(r"^(?P<scheme>[a-z][a-z0-9+.-]*):", re.IGNORECASE)
REMOTE_LINK_SCHEMES = frozenset({"http", "https", "mailto"})
TABLE_SEPARATOR_CELL_RE = re.compile(r"^:?-{3,}:?$")
GROUP_DESCRIPTION_RE = re.compile(
    r"^\*\*Mô tả trực quan(?: theo [^*:]+)?:\*\*$"
)
STANDALONE_DESCRIPTION = "**Mô tả trực quan:**"
WINDOWS_DEVICES = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        "CLOCK$",
        "CONIN$",
        "CONOUT$",
        *(f"COM{suffix}" for suffix in "123456789¹²³"),
        *(f"LPT{suffix}" for suffix in "123456789¹²³"),
    }
)


def github_heading_slug(value: str) -> str:
    normalized = value.lower().strip()
    visible = "".join(
        character
        for character in normalized
        if (
            character in {"-", "_"}
            or character.isspace()
            or unicodedata.category(character)[0] in {"L", "M", "N"}
        )
    )
    return re.sub(r"\s", "-", visible) or "section"


def markdown_heading_anchors(text: str) -> frozenset[str]:
    _, visible_lines, _ = _markdown_scan_lines(text)
    anchors = {
        match.group(1) or match.group(2) or match.group(3)
        for match in HTML_ANCHOR_RE.finditer(text)
    }
    used: set[str] = set(anchors)
    for line in visible_lines:
        match = HEADING_RE.match(line)
        if match is None:
            continue
        heading = re.sub(r"\s+#+\s*$", "", match.group(2))
        heading = re.sub(
            r"!?\[([^\]]*)]\([^)]*\)",
            r"\1",
            heading,
        )
        heading = re.sub(r"<[^>]+>", "", heading)
        heading = unescape_html(heading)
        heading = re.sub(r"\\(.)", r"\1", heading)
        heading = heading.replace("`", "").replace("*", "").replace("~", "")
        base = github_heading_slug(heading)
        anchor = base
        duplicate = 0
        while anchor in used:
            duplicate += 1
            anchor = f"{base}-{duplicate}"
        used.add(anchor)
        anchors.add(anchor)
    return frozenset(anchors)


@dataclass(frozen=True)
class ImageOccurrence:
    markdown: str
    line: int
    alt: str
    target: str
    resolved_path: str | None
    exists: bool
    sha256: str | None
    width: int | None
    height: int | None
    heading: str | None
    grouped_row: bool
    description_present: bool
    duplicate_of: str | None = None


@dataclass(frozen=True)
class VisualUnit:
    order: int
    heading: str | None
    grouped: bool
    anchor_start: int
    anchor_end: int
    hashes: tuple[str, ...]
    description_start: int | None
    description_end: int | None
    description: str | None


@dataclass(frozen=True)
class _MarkdownTarget:
    label: str
    target: str
    start: int
    error: str | None = None


@dataclass(frozen=True)
class _ListContainer:
    quote_depth: int
    content_indent: int


@dataclass(frozen=True)
class _FenceState:
    character: str
    length: int
    quote_depth: int
    list_indent: int | None


@dataclass(frozen=True)
class _ResolvedMarkdown:
    root: Path
    lexical_root: Path
    markdown: Path
    relative: Path


@dataclass(frozen=True)
class _ParsedImage:
    line_index: int
    image: _MarkdownTarget
    heading: str | None
    group: tuple[int, int]
    grouped: bool


@dataclass(frozen=True)
class _DescriptionScan:
    present: bool
    errors: tuple[str, ...]
    start: int | None = None
    end: int | None = None
    text: str | None = None


@dataclass(frozen=True)
class _DescriptionTable:
    row_count: int
    non_empty_rows: int
    identifiers: tuple[str, ...]
    grouped_non_empty_rows: int


@dataclass(frozen=True)
class _VisualGroup:
    order: int
    heading: str | None
    grouped: bool
    anchor_start: int
    anchor_end: int
    occurrence_indexes: tuple[int, ...]
    description: _DescriptionScan


@dataclass(frozen=True)
class _ImageScan:
    occurrences: tuple[ImageOccurrence, ...]
    groups: tuple[_VisualGroup, ...]
    image_errors: tuple[str, ...]
    invalid_occurrences: frozenset[int]
    description_errors: tuple[str, ...]


def build_image_manifest(
    markdown: Path,
    output_root: Path,
) -> tuple[ImageOccurrence, ...]:
    resolved = _resolve_markdown(markdown, output_root)
    text = _read_markdown(resolved.markdown)
    _reject_invalid_text(text, resolved.relative)
    raw_lines, visible_lines, _ = _markdown_scan_lines(text)
    scan = _scan_images(resolved, raw_lines, visible_lines)
    if scan.image_errors:
        raise ValueError(scan.image_errors[0])
    return scan.occurrences


def build_visual_units(
    markdown: Path,
    output_root: Path,
) -> tuple[VisualUnit, ...]:
    resolved = _resolve_markdown(markdown, output_root)
    text = _read_markdown(resolved.markdown)
    _reject_invalid_text(text, resolved.relative)
    raw_lines, visible_lines, _ = _markdown_scan_lines(text)
    scan = _scan_images(resolved, raw_lines, visible_lines)
    if scan.image_errors:
        raise ValueError(scan.image_errors[0])

    units: list[VisualUnit] = []
    for group in scan.groups:
        occurrences = tuple(
            scan.occurrences[index]
            for index in group.occurrence_indexes
        )
        missing = next(
            (
                occurrence
                for occurrence in occurrences
                if occurrence.sha256 is None
            ),
            None,
        )
        if missing is not None:
            raise ValueError(
                f"{missing.markdown}:{missing.line}: "
                f"missing image: {missing.target}"
            )
        units.append(
            VisualUnit(
                order=group.order,
                heading=group.heading,
                grouped=group.grouped,
                anchor_start=group.anchor_start,
                anchor_end=group.anchor_end,
                hashes=tuple(
                    occurrence.sha256
                    for occurrence in occurrences
                    if occurrence.sha256 is not None
                ),
                description_start=group.description.start,
                description_end=group.description.end,
                description=group.description.text,
            )
        )
    return tuple(units)


def verify_docx_markdown(
    markdown: Path,
    output_root: Path,
) -> tuple[dict[str, Any], list[str]]:
    resolved = _resolve_markdown(markdown, output_root)
    summary = _empty_summary(resolved)
    try:
        text = _read_markdown(resolved.markdown)
    except UnicodeDecodeError as error:
        errors = [
            f"{resolved.relative.as_posix()}: invalid UTF-8: {error}"
        ]
        summary["utf8_errors"] = 1
        summary["errors"] = 1
        return summary, errors

    errors: list[str] = []
    if "\x00" in text:
        summary["utf8_errors"] += 1
        errors.append(
            f"{resolved.relative.as_posix()}: contains NUL character"
        )
    if "\ufffd" in text:
        summary["utf8_errors"] += 1
        errors.append(
            f"{resolved.relative.as_posix()}: contains U+FFFD "
            "replacement character"
        )

    raw_lines, visible_lines, fences_balanced = _markdown_scan_lines(text)
    if not fences_balanced:
        summary["fence_errors"] = 1
        errors.append(
            f"{resolved.relative.as_posix()}: "
            "unbalanced fenced code block"
        )

    errors.extend(
        _verify_docx_markdown_artifacts(
            resolved.relative,
            visible_lines,
        )
    )

    scan = _scan_images(resolved, raw_lines, visible_lines)
    errors.extend(scan.image_errors)
    errors.extend(scan.description_errors)
    for index, occurrence in enumerate(scan.occurrences):
        if not occurrence.exists and index not in scan.invalid_occurrences:
            errors.append(
                f"{occurrence.markdown}:{occurrence.line}: "
                f"missing image: {occurrence.target}"
            )

    link_errors, broken_links = _verify_local_links(
        resolved,
        visible_lines,
    )
    errors.extend(link_errors)

    occurrences = scan.occurrences
    summary.update(
        {
            "image_occurrences": len(occurrences),
            "unique_local_images": len(
                {
                    occurrence.sha256
                    for occurrence in occurrences
                    if occurrence.sha256 is not None
                }
            ),
            "described_occurrences": sum(
                occurrence.description_present
                for occurrence in occurrences
            ),
            "broken_images": sum(
                not occurrence.exists for occurrence in occurrences
            ),
            "broken_links": broken_links,
            "errors": len(errors),
        }
    )
    return summary, errors


def _verify_docx_markdown_artifacts(
    relative: Path,
    visible_lines: Sequence[str],
) -> list[str]:
    errors: list[str] = []
    label = relative.as_posix()
    for line_index, line in enumerate(visible_lines, start=1):
        if WORD_TOC_ANCHOR_RE.search(line) is not None:
            errors.append(
                f"{label}:{line_index}: raw Word TOC bookmark"
            )
        if (
            STYLE_DELIMITER_ARTIFACT_RE.search(line) is not None
            or line.strip() in {"**", "~~"}
        ):
            errors.append(
                f"{label}:{line_index}: degenerate style delimiter"
            )
    return errors


def _empty_summary(resolved: _ResolvedMarkdown) -> dict[str, Any]:
    return {
        "markdown": resolved.relative.as_posix(),
        "output_root": str(resolved.root),
        "image_occurrences": 0,
        "unique_local_images": 0,
        "described_occurrences": 0,
        "broken_images": 0,
        "broken_links": 0,
        "utf8_errors": 0,
        "fence_errors": 0,
        "errors": 0,
    }


def _resolve_markdown(
    markdown: Path,
    output_root: Path,
) -> _ResolvedMarkdown:
    if _contains_parent_traversal(output_root):
        raise ValueError(f"ambiguous output_root path: {output_root}")
    lexical_root = _absolute_path(output_root)
    if not lexical_root.exists():
        raise ValueError(f"missing output root: {output_root}")
    if not lexical_root.is_dir():
        raise ValueError(
            f"output_root must be a directory: {output_root}"
        )
    _assert_no_reparse(lexical_root)
    root = lexical_root.resolve(strict=True)

    if _contains_parent_traversal(markdown):
        raise ValueError(f"ambiguous Markdown path: {markdown}")
    lexical_markdown = _absolute_path(markdown)
    if not lexical_markdown.is_relative_to(lexical_root):
        raise ValueError(
            f"Markdown is outside output_root: {markdown}"
        )
    _assert_no_reparse(lexical_markdown)
    if not lexical_markdown.exists():
        raise ValueError(f"missing Markdown file: {markdown}")
    if not lexical_markdown.is_file():
        raise ValueError(f"Markdown must be a file: {markdown}")
    if lexical_markdown.suffix.lower() != ".md":
        raise ValueError(f"Markdown file must use .md: {markdown}")

    resolved_markdown = lexical_markdown.resolve(strict=True)
    if not resolved_markdown.is_relative_to(root):
        raise ValueError(
            f"Markdown is outside output_root: {markdown}"
        )
    return _ResolvedMarkdown(
        root=root,
        lexical_root=lexical_root,
        markdown=resolved_markdown,
        relative=resolved_markdown.relative_to(root),
    )


def _contains_parent_traversal(path: Path) -> bool:
    return ".." in path.parts


def _absolute_path(path: Path) -> Path:
    return Path(os.path.abspath(path))


def _is_reparse_point(path: Path) -> bool:
    try:
        metadata = os.lstat(path)
    except FileNotFoundError:
        return False
    attributes = getattr(metadata, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return stat.S_ISLNK(metadata.st_mode) or bool(
        attributes & reparse_flag
    )


def _assert_no_reparse(path: Path) -> None:
    absolute = _absolute_path(path)
    for candidate in (*reversed(absolute.parents), absolute):
        if _is_reparse_point(candidate):
            raise ValueError(
                "path contains a symlink or reparse point: "
                f"{candidate}"
            )


def _read_markdown(markdown: Path) -> str:
    with markdown.open(
        "r",
        encoding="utf-8",
        errors="strict",
        newline="",
    ) as stream:
        return stream.read()


def _reject_invalid_text(text: str, relative: Path) -> None:
    if "\x00" in text:
        raise ValueError(
            f"{relative.as_posix()}: contains NUL character"
        )
    if "\ufffd" in text:
        raise ValueError(
            f"{relative.as_posix()}: contains U+FFFD replacement character"
        )


def _markdown_scan_lines(
    text: str,
) -> tuple[list[str], list[str], bool]:
    raw_lines = text.splitlines()
    visible: list[str] = []
    fence: _FenceState | None = None
    list_container: _ListContainer | None = None
    html_comment = False
    code_ticks = 0
    for line_index, line in enumerate(raw_lines):
        if fence is None and not html_comment and not code_ticks:
            current_list = _list_container(line)
            if current_list is not None:
                list_container = current_list
            elif (
                list_container is not None
                and _container_line_content(line)
                and not _continues_list_container(line, list_container)
            ):
                list_container = None
        marker_match = (
            None
            if html_comment or code_ticks
            else FENCE_RE.match(line)
        )
        if fence is None:
            opening_fence = (
                _opening_fence(marker_match, list_container)
                if marker_match is not None
                else None
            )
            if opening_fence is not None:
                fence = opening_fence
                visible.append("")
                continue
            masked, html_comment, code_ticks = (
                _mask_inline_code_and_comments(
                    raw_lines,
                    line_index,
                    html_comment,
                    code_ticks,
                )
            )
            visible.append(masked)
            continue

        visible.append("")
        if marker_match is None:
            continue
        if _matches_fence_close(marker_match, fence):
            fence = None
    return raw_lines, visible, fence is None


def _is_opening_fence(match: re.Match[str]) -> bool:
    return _opening_fence(match) is not None


def _opening_fence(
    match: re.Match[str],
    list_container: _ListContainer | None = None,
) -> _FenceState | None:
    marker = match.group("marker")
    trailing = match.group("trailing")
    if marker[0] == "`" and "`" in trailing:
        return None
    indent = _indent_width(match.group("indent"))
    list_prefix = match.group("list")
    if list_prefix is None:
        if indent <= 3:
            list_indent = None
        elif (
            list_container is not None
            and match.group("quotes").count(">")
            == list_container.quote_depth
            and list_container.content_indent
            <= indent
            <= list_container.content_indent + 3
        ):
            list_indent = list_container.content_indent
        else:
            return None
    else:
        list_indent = _indent_width(list_prefix) + indent
    return _FenceState(
        character=marker[0],
        length=len(marker),
        quote_depth=match.group("quotes").count(">"),
        list_indent=list_indent,
    )


def _matches_fence_close(
    match: re.Match[str],
    fence: _FenceState,
) -> bool:
    marker = match.group("marker")
    if (
        marker[0] != fence.character
        or len(marker) < fence.length
        or match.group("trailing").strip()
        or match.group("quotes").count(">") != fence.quote_depth
        or match.group("list") is not None
    ):
        return False
    indent = _indent_width(match.group("indent"))
    if fence.list_indent is None:
        return indent <= 3
    return fence.list_indent <= indent <= fence.list_indent + 3


def _indent_width(value: str) -> int:
    return len(value.expandtabs(4))


def _list_container(line: str) -> _ListContainer | None:
    match = LIST_ITEM_RE.match(line)
    if match is None:
        return None
    spacing = _indent_width(match.group("spacing"))
    content_indent = (
        _indent_width(match.group("indent"))
        + len(match.group("marker"))
        + (spacing if spacing <= 4 else 1)
    )
    return _ListContainer(
        quote_depth=match.group("quotes").count(">"),
        content_indent=content_indent,
    )


def _continues_list_container(
    line: str,
    container: _ListContainer,
) -> bool:
    match = CONTAINER_INDENT_RE.match(line)
    if match is None:
        return False
    return (
        match.group("quotes").count(">") == container.quote_depth
        and _indent_width(match.group("indent"))
        >= container.content_indent
    )


def _mask_inline_code_and_comments(
    lines: Sequence[str],
    line_index: int,
    html_comment: bool,
    code_ticks: int,
) -> tuple[str, bool, int]:
    line = lines[line_index]
    visible = list(line)
    cursor = 0
    while cursor < len(line):
        if html_comment:
            end = line.find("-->", cursor)
            stop = len(line) if end < 0 else end + 3
            visible[cursor:stop] = " " * (stop - cursor)
            if end < 0:
                return "".join(visible), True, code_ticks
            html_comment = False
            cursor = stop
            continue

        if code_ticks:
            run_start = line.find("`", cursor)
            if run_start < 0:
                visible[cursor:] = " " * (len(line) - cursor)
                return "".join(visible), html_comment, code_ticks
            run_end = _tick_run_end(line, run_start)
            visible[cursor:run_end] = " " * (run_end - cursor)
            if run_end - run_start == code_ticks:
                code_ticks = 0
            cursor = run_end
            continue

        if line.startswith("<!--", cursor):
            html_comment = True
            continue
        if line[cursor] == "`" and not _character_is_escaped(
            line,
            cursor,
        ):
            run_end = _tick_run_end(line, cursor)
            opening_ticks = run_end - cursor
            if not _has_closing_tick_run(
                lines,
                line_index,
                run_end,
                opening_ticks,
            ):
                cursor = run_end
                continue
            code_ticks = opening_ticks
            visible[cursor:run_end] = " " * opening_ticks
            cursor = run_end
            continue
        cursor += 1
    return "".join(visible), html_comment, code_ticks


def _tick_run_end(line: str, start: int) -> int:
    end = start
    while end < len(line) and line[end] == "`":
        end += 1
    return end


def _has_closing_tick_run(
    lines: Sequence[str],
    line_index: int,
    start: int,
    ticks: int,
) -> bool:
    for candidate_index in range(line_index, len(lines)):
        line = lines[candidate_index]
        if candidate_index > line_index:
            if not line.strip():
                return False
            fence_match = FENCE_RE.match(line)
            if (
                fence_match is not None
                and _is_opening_fence(fence_match)
            ):
                return False
        cursor = start if candidate_index == line_index else 0
        while cursor < len(line):
            run_start = line.find("`", cursor)
            if run_start < 0:
                break
            run_end = _tick_run_end(line, run_start)
            if run_end - run_start == ticks:
                return True
            cursor = run_end
    return False


def _character_is_escaped(text: str, index: int) -> bool:
    backslashes = 0
    cursor = index - 1
    while cursor >= 0 and text[cursor] == "\\":
        backslashes += 1
        cursor -= 1
    return bool(backslashes % 2)


def _bare_markdown_destination(value: str) -> str:
    depth = 0
    for index, character in enumerate(value):
        if _character_is_escaped(value, index):
            continue
        if character == "(":
            depth += 1
        elif character == ")" and depth:
            depth -= 1
        elif character.isspace() and depth == 0:
            return value[:index]
    return value


def _iter_inline_markdown_targets(
    line: str,
    *,
    images: bool,
) -> Iterator[_MarkdownTarget]:
    marker = "![" if images else "["
    cursor = 0
    while cursor < len(line):
        start = line.find(marker, cursor)
        if start < 0:
            return
        if _character_is_escaped(line, start):
            cursor = start + len(marker)
            continue
        if (
            not images
            and start > 0
            and line[start - 1] == "!"
            and not _character_is_escaped(line, start - 1)
        ):
            cursor = start + 1
            continue

        depth = 1
        label_start = start + len(marker)
        label_end = label_start
        while label_end < len(line):
            character = line[label_end]
            if not _character_is_escaped(line, label_end):
                if character == "[":
                    depth += 1
                elif character == "]":
                    depth -= 1
                    if depth == 0:
                        break
            label_end += 1
        if depth:
            return

        open_parenthesis = label_end + 1
        while (
            open_parenthesis < len(line)
            and line[open_parenthesis].isspace()
        ):
            open_parenthesis += 1
        if (
            open_parenthesis >= len(line)
            or line[open_parenthesis] != "("
        ):
            cursor = label_end + 1
            continue

        close_parenthesis = _closing_parenthesis(
            line,
            open_parenthesis,
        )
        if close_parenthesis is None:
            return

        inside = line[
            open_parenthesis + 1 : close_parenthesis
        ].strip()
        if inside.startswith("<"):
            destination_end = 1
            while destination_end < len(inside):
                if (
                    inside[destination_end] == ">"
                    and not _character_is_escaped(
                        inside,
                        destination_end,
                    )
                ):
                    destination_end += 1
                    break
                destination_end += 1
            target = inside[:destination_end]
        else:
            target = _bare_markdown_destination(inside)
        yield _MarkdownTarget(
            label=line[label_start:label_end],
            target=target,
            start=start,
        )
        cursor = close_parenthesis + 1


def _reference_definitions(
    lines: Sequence[str],
) -> dict[str, str]:
    definitions: dict[str, str] = {}
    for line in lines:
        match = REFERENCE_DEFINITION_RE.match(line)
        if match is None:
            continue
        label = _normalize_reference_label(match.group("label"))
        if not label or label in definitions:
            continue
        destination = _markdown_destination(match.group("destination"))
        if destination:
            definitions[label] = destination
    return definitions


def _normalize_reference_label(label: str) -> str:
    return " ".join(_markdown_unescape(label).split()).casefold()


def _markdown_destination(value: str) -> str:
    inside = value.strip()
    if inside.startswith("<"):
        destination_end = 1
        while destination_end < len(inside):
            if (
                inside[destination_end] == ">"
                and not _character_is_escaped(
                    inside,
                    destination_end,
                )
            ):
                return inside[: destination_end + 1]
            destination_end += 1
        return inside
    return _bare_markdown_destination(inside)


def _iter_reference_markdown_targets(
    line: str,
    *,
    images: bool,
    definitions: dict[str, str],
) -> Iterator[_MarkdownTarget]:
    if REFERENCE_DEFINITION_RE.match(line) is not None:
        return
    marker = "![" if images else "["
    cursor = 0
    while cursor < len(line):
        start = line.find(marker, cursor)
        if start < 0:
            return
        if _character_is_escaped(line, start):
            cursor = start + len(marker)
            continue
        label_start = start + len(marker)
        label_end = _closing_square_bracket(line, label_start)
        if label_end is None:
            return
        reference_start = label_end + 1
        while (
            reference_start < len(line)
            and line[reference_start].isspace()
        ):
            reference_start += 1
        if (
            not images
            and start > 0
            and line[start - 1] == "!"
            and not _character_is_escaped(line, start - 1)
        ):
            if (
                reference_start < len(line)
                and line[reference_start] == "["
            ):
                reference_end = _closing_square_bracket(
                    line,
                    reference_start + 1,
                )
                cursor = (
                    reference_end + 1
                    if reference_end is not None
                    else label_end + 1
                )
            elif (
                reference_start < len(line)
                and line[reference_start] == "("
            ):
                destination_end = _closing_parenthesis(
                    line,
                    reference_start,
                )
                cursor = (
                    destination_end + 1
                    if destination_end is not None
                    else label_end + 1
                )
            else:
                cursor = label_end + 1
            continue
        label = line[label_start:label_end]
        if (
            reference_start >= len(line)
            or line[reference_start] != "["
        ):
            if (
                reference_start < len(line)
                and line[reference_start] == "("
            ):
                cursor = label_end + 1
                continue
            normalized = _normalize_reference_label(label)
            target = definitions.get(normalized)
            if target is not None:
                yield _MarkdownTarget(
                    label=label,
                    target=target,
                    start=start,
                )
            elif images:
                yield _MarkdownTarget(
                    label=label,
                    target=f"[{label}]",
                    start=start,
                    error=f"undefined image reference: {label!r}",
                )
            cursor = label_end + 1
            continue
        reference_end = _closing_square_bracket(
            line,
            reference_start + 1,
        )
        if reference_end is None:
            return

        reference = line[reference_start + 1 : reference_end]
        normalized = _normalize_reference_label(reference or label)
        target = definitions.get(normalized)
        error = None
        if target is None:
            target = f"[{reference or label}]"
            error = (
                f"undefined {'image' if images else 'link'} "
                f"reference: {reference or label!r}"
            )
        yield _MarkdownTarget(
            label=label,
            target=target,
            start=start,
            error=error,
        )
        cursor = reference_end + 1


def _closing_square_bracket(
    line: str,
    start: int,
) -> int | None:
    depth = 1
    cursor = start
    while cursor < len(line):
        character = line[cursor]
        if not _character_is_escaped(line, cursor):
            if character == "[":
                depth += 1
            elif character == "]":
                depth -= 1
                if depth == 0:
                    return cursor
        cursor += 1
    return None


def _targets_by_line(
    visible_lines: Sequence[str],
    *,
    images: bool,
) -> dict[int, tuple[_MarkdownTarget, ...]]:
    definitions = _reference_definitions(visible_lines)
    collected: dict[int, list[_MarkdownTarget]] = {}
    content_lines: list[str] = []
    for line_index, line in enumerate(visible_lines):
        if REFERENCE_DEFINITION_RE.match(line) is not None:
            content_lines.append(" " * len(line))
            continue
        content_lines.append(line)
        targets = [
            *_iter_inline_markdown_targets(line, images=images),
            *_iter_reference_markdown_targets(
                line,
                images=images,
                definitions=definitions,
            ),
        ]
        if targets:
            collected[line_index] = targets
    if images:
        for line_index, target in _iter_html_image_targets(content_lines):
            collected.setdefault(line_index, []).append(target)
    return {
        line_index: tuple(sorted(targets, key=lambda target: target.start))
        for line_index, targets in collected.items()
    }


def _iter_html_image_targets(
    visible_lines: Sequence[str],
) -> Iterator[tuple[int, _MarkdownTarget]]:
    visible_text = "\n".join(visible_lines)
    line_starts = [0]
    for line in visible_lines[:-1]:
        line_starts.append(line_starts[-1] + len(line) + 1)
    for match in HTML_IMAGE_RE.finditer(visible_text):
        attributes: dict[str, str] = {}
        for attribute in HTML_ATTRIBUTE_RE.finditer(match.group()):
            value = attribute.group("value")
            if value[:1] in {'"', "'"}:
                value = value[1:-1]
            attributes.setdefault(
                attribute.group("name").casefold(),
                value,
            )
        line_index = bisect_right(line_starts, match.start()) - 1
        error = None
        target = attributes.get("src", "")
        if not target:
            error = "HTML image is missing src attribute"
        yield line_index, _MarkdownTarget(
            label=unescape_html(attributes.get("alt", "")),
            target=target,
            start=match.start() - line_starts[line_index],
            error=error,
        )


def _closing_parenthesis(
    line: str,
    open_parenthesis: int,
) -> int | None:
    depth = 1
    angle_target = False
    quote: str | None = None
    cursor = open_parenthesis + 1
    while cursor < len(line):
        character = line[cursor]
        if _character_is_escaped(line, cursor):
            cursor += 1
            continue
        if quote is not None:
            if character == quote:
                quote = None
        elif (
            character in {'"', "'"}
            and cursor > open_parenthesis + 1
            and line[cursor - 1].isspace()
        ):
            quote = character
        elif character == "<":
            angle_target = True
        elif character == ">":
            angle_target = False
        elif not angle_target and character == "(":
            depth += 1
        elif not angle_target and character == ")":
            depth -= 1
            if depth == 0:
                return cursor
        cursor += 1
    return None


def _scan_images(
    resolved: _ResolvedMarkdown,
    raw_lines: Sequence[str],
    visible_lines: Sequence[str],
) -> _ImageScan:
    targets_by_line = _targets_by_line(
        visible_lines,
        images=True,
    )

    parsed: list[_ParsedImage] = []
    heading: str | None = None
    for line_index, line in enumerate(visible_lines):
        heading_match = HEADING_RE.match(line)
        if heading_match is not None:
            heading = heading_match.group(2)
        images = targets_by_line.get(line_index, ())
        if not images:
            continue
        if line.lstrip().startswith("|"):
            group = _markdown_table_span(visible_lines, line_index)
        else:
            group = (line_index, line_index)
        group_count = sum(
            len(targets_by_line.get(group_line, ()))
            for group_line in range(group[0], group[1] + 1)
        )
        grouped = line.lstrip().startswith("|") or group_count > 1
        parsed.extend(
            _ParsedImage(
                line_index=line_index,
                image=image,
                heading=heading,
                group=group,
                grouped=grouped,
            )
            for image in images
        )

    group_counts: dict[tuple[int, int], int] = {}
    group_first_lines: dict[tuple[int, int], int] = {}
    for item in parsed:
        group_counts[item.group] = group_counts.get(item.group, 0) + 1
        group_first_lines.setdefault(item.group, item.line_index)

    description_scans: dict[tuple[int, int], _DescriptionScan] = {}
    description_errors: list[str] = []
    relative = resolved.relative.as_posix()
    for group, count in group_counts.items():
        grouped = count > 1 or visible_lines[group[0]].lstrip().startswith(
            "|"
        )
        description = _description_status(
            raw_lines,
            visible_lines,
            group[1],
            grouped,
            count,
        )
        description_scans[group] = description
        location = f"{relative}:{group_first_lines[group] + 1}"
        description_errors.extend(
            f"{location}: {error}" for error in description.errors
        )

    occurrences: list[ImageOccurrence] = []
    image_errors: list[str] = []
    invalid_occurrences: set[int] = set()
    first_hash_occurrence: dict[str, str] = {}
    for item in parsed:
        target = item.image.target.strip()
        resolved_path: Path | None = None
        exists = False
        digest: str | None = None
        width: int | None = None
        height: int | None = None
        duplicate_of: str | None = None
        try:
            if item.image.error is not None:
                raise ValueError(item.image.error)
            target = _normalize_link_target(item.image.target)
            relative_target = _local_target(
                item.image.target,
                kind="image",
            )
            if relative_target is None:
                raise ValueError("empty image target")
            resolved_path = _resolve_local_target(
                resolved,
                relative_target,
                kind="image",
            )
            exists = (
                resolved_path.exists() and resolved_path.is_file()
            )
            if exists:
                digest = _sha256_file(resolved_path)
                width, height = _image_dimensions(resolved_path)
                duplicate_of = first_hash_occurrence.get(digest)
                if duplicate_of is None:
                    first_hash_occurrence[digest] = (
                        f"{relative}:{item.line_index + 1}"
                    )
        except (OSError, UnicodeError, ValueError) as error:
            occurrence_index = len(occurrences)
            invalid_occurrences.add(occurrence_index)
            image_errors.append(
                f"{relative}:{item.line_index + 1}: "
                f"unsafe image target {target!r}: {error}"
            )

        occurrences.append(
            ImageOccurrence(
                markdown=relative,
                line=item.line_index + 1,
                alt=item.image.label,
                target=target,
                resolved_path=(
                    str(resolved_path)
                    if resolved_path is not None
                    else None
                ),
                exists=exists,
                sha256=digest,
                width=width,
                height=height,
                heading=item.heading,
                grouped_row=item.grouped,
                description_present=description_scans[
                    item.group
                ].present,
                duplicate_of=duplicate_of,
            )
        )

    occurrence_indexes: dict[tuple[int, int], list[int]] = {}
    group_headings: dict[tuple[int, int], str | None] = {}
    group_shapes: dict[tuple[int, int], bool] = {}
    for index, item in enumerate(parsed):
        occurrence_indexes.setdefault(item.group, []).append(index)
        group_headings.setdefault(item.group, item.heading)
        group_shapes.setdefault(item.group, item.grouped)
    groups = tuple(
        _VisualGroup(
            order=order,
            heading=group_headings[group],
            grouped=group_shapes[group],
            anchor_start=group[0],
            anchor_end=group[1],
            occurrence_indexes=tuple(occurrence_indexes[group]),
            description=description_scans[group],
        )
        for order, group in enumerate(group_counts)
    )
    return _ImageScan(
        occurrences=tuple(occurrences),
        groups=groups,
        image_errors=tuple(image_errors),
        invalid_occurrences=frozenset(invalid_occurrences),
        description_errors=tuple(description_errors),
    )


def _markdown_table_span(
    lines: Sequence[str],
    line_index: int,
) -> tuple[int, int]:
    start = line_index
    while start > 0 and lines[start - 1].lstrip().startswith("|"):
        start -= 1
    end = line_index
    while (
        end + 1 < len(lines)
        and lines[end + 1].lstrip().startswith("|")
    ):
        end += 1
    return start, end


def _description_status(
    raw_lines: Sequence[str],
    visible_lines: Sequence[str],
    anchor_end: int,
    grouped: bool,
    image_count: int,
) -> _DescriptionScan:
    blank_before = anchor_end + 1
    marker_index = anchor_end + 2
    if (
        blank_before >= len(raw_lines)
        or raw_lines[blank_before].strip()
    ):
        return _DescriptionScan(
            False,
            (
                "visual description requires a blank line before its marker",
            ),
        )
    if marker_index >= len(visible_lines):
        return _DescriptionScan(
            False,
            ("missing immediate structured visual description",),
        )

    marker = visible_lines[marker_index].strip()
    marker_matches = (
        GROUP_DESCRIPTION_RE.fullmatch(marker) is not None
        if grouped
        else marker == STANDALONE_DESCRIPTION
    )
    if not marker_matches:
        return _DescriptionScan(
            False,
            ("missing immediate structured visual description",),
        )

    blank_after = marker_index + 1
    body_start = marker_index + 2
    if (
        blank_after >= len(raw_lines)
        or raw_lines[blank_after].strip()
    ):
        return _DescriptionScan(
            False,
            (
                "visual description requires a blank line after its marker",
            ),
        )
    if body_start >= len(raw_lines):
        return _DescriptionScan(
            False,
            ("missing structured visual description body",),
        )

    table_rows = _description_table_rows(raw_lines, body_start)
    if grouped:
        if table_rows is None:
            return _DescriptionScan(
                False,
                (
                    "grouped visual description must use a comparison table",
                ),
            )
        if table_rows.row_count != image_count:
            return _DescriptionScan(
                False,
                (
                    "grouped visual description requires exactly "
                    f"{image_count} data rows; found "
                    f"{table_rows.row_count}",
                ),
            )
        if any(not identifier for identifier in table_rows.identifiers):
            return _DescriptionScan(
                False,
                (
                    "grouped visual description requires a nonempty "
                    "identifier for every image occurrence",
                ),
            )
        if len(set(table_rows.identifiers)) != image_count:
            return _DescriptionScan(
                False,
                (
                    "grouped visual description identifiers must be "
                    "unique",
                ),
            )
        if table_rows.grouped_non_empty_rows != image_count:
            return _DescriptionScan(
                False,
                (
                    "grouped visual description requires "
                    f"{image_count} non-empty description rows; "
                    "found "
                    f"{table_rows.grouped_non_empty_rows}",
                ),
            )
        table_end = _description_table_end(raw_lines, body_start)
        return _DescriptionScan(
            True,
            (),
            marker_index,
            table_end,
            "\n".join(raw_lines[marker_index : table_end + 1]),
        )

    if table_rows is not None and table_rows.non_empty_rows >= 1:
        table_end = _description_table_end(raw_lines, body_start)
        return _DescriptionScan(
            True,
            (),
            marker_index,
            table_end,
            "\n".join(raw_lines[marker_index : table_end + 1]),
        )
    fence_match = FENCE_RE.match(raw_lines[body_start])
    if fence_match is not None and _is_opening_fence(fence_match):
        if _fenced_description_has_content(
            raw_lines,
            body_start,
            fence_match,
        ):
            fence_end = _description_fence_end(
                raw_lines,
                body_start,
                fence_match,
            )
            if fence_end is not None:
                return _DescriptionScan(
                    True,
                    (),
                    marker_index,
                    fence_end,
                    "\n".join(
                        raw_lines[marker_index : fence_end + 1]
                    ),
                )
        return _DescriptionScan(
            False,
            (
                "visual description requires non-empty structured visual "
                "description content",
            ),
        )
    return _DescriptionScan(
        False,
        ("missing structured visual description body",),
    )


def _description_table_rows(
    lines: Sequence[str],
    start: int,
) -> _DescriptionTable | None:
    table: list[str] = []
    cursor = start
    while (
        cursor < len(lines)
        and lines[cursor].lstrip().startswith("|")
    ):
        table.append(lines[cursor])
        cursor += 1
    if len(table) < 3 or not _is_table_separator(table[1]):
        return None
    data_rows = _mask_html_comments(table[2:])
    non_empty_rows = sum(
        _row_has_description(row) for row in data_rows
    )
    cells = tuple(_table_cells(row) for row in data_rows)
    identifiers = tuple(
        row[0] if row else ""
        for row in cells
    )
    grouped_non_empty_rows = sum(
        any(cell for cell in row[1:])
        for row in cells
    )
    return _DescriptionTable(
        row_count=len(data_rows),
        non_empty_rows=non_empty_rows,
        identifiers=identifiers,
        grouped_non_empty_rows=grouped_non_empty_rows,
    )


def _description_table_end(
    lines: Sequence[str],
    start: int,
) -> int:
    cursor = start
    while (
        cursor + 1 < len(lines)
        and lines[cursor + 1].lstrip().startswith("|")
    ):
        cursor += 1
    return cursor


def _mask_html_comments(lines: Sequence[str]) -> list[str]:
    masked_lines: list[str] = []
    in_comment = False
    for line in lines:
        visible = list(line)
        cursor = 0
        while cursor < len(line):
            if in_comment:
                end = line.find("-->", cursor)
                stop = len(line) if end < 0 else end + 3
                visible[cursor:stop] = " " * (stop - cursor)
                if end < 0:
                    break
                in_comment = False
                cursor = stop
                continue
            start = line.find("<!--", cursor)
            if start < 0:
                break
            in_comment = True
            cursor = start
        masked_lines.append("".join(visible))
    return masked_lines


def _row_has_description(row: str) -> bool:
    cells = _table_cells(row)
    descriptive_cells = cells[1:] if len(cells) > 1 else cells
    return any(descriptive_cells)


def _table_cells(row: str) -> list[str]:
    return [
        cell.strip()
        for cell in row.strip().strip("|").split("|")
    ]


def _fenced_description_has_content(
    lines: Sequence[str],
    start: int,
    opening: re.Match[str],
) -> bool:
    fence = _opening_fence(opening)
    if fence is None:
        return False
    has_content = False
    for line in lines[start + 1 :]:
        candidate = FENCE_RE.match(line)
        if (
            candidate is not None
            and _matches_fence_close(candidate, fence)
        ):
            return has_content
        if _container_line_content(line):
            has_content = True
    return False


def _description_fence_end(
    lines: Sequence[str],
    start: int,
    opening: re.Match[str],
) -> int | None:
    fence = _opening_fence(opening)
    if fence is None:
        return None
    for index, line in enumerate(lines[start + 1 :], start=start + 1):
        candidate = FENCE_RE.match(line)
        if (
            candidate is not None
            and _matches_fence_close(candidate, fence)
        ):
            return index
    return None


def _container_line_content(line: str) -> str:
    content = line.lstrip()
    while content.startswith(">"):
        content = content[1:].lstrip()
    return content.strip()


def _is_table_separator(line: str) -> bool:
    cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
    return bool(cells) and all(
        TABLE_SEPARATOR_CELL_RE.fullmatch(cell) is not None
        for cell in cells
    )


def _verify_local_links(
    resolved: _ResolvedMarkdown,
    visible_lines: Sequence[str],
) -> tuple[list[str], int]:
    errors: list[str] = []
    broken = 0
    relative = resolved.relative.as_posix()
    links_by_line = _targets_by_line(
        visible_lines,
        images=False,
    )
    anchors_by_path: dict[Path, frozenset[str]] = {}
    for line_index, links in links_by_line.items():
        line_number = line_index + 1
        for link in links:
            target = link.target.strip()
            try:
                if link.error is not None:
                    raise ValueError(link.error)
                target = _normalize_link_target(link.target)
                target_text = _markdown_target_text(link.target)
                if target_text.startswith("#"):
                    path = resolved.markdown
                else:
                    relative_target = _local_target(
                        link.target,
                        kind="link",
                    )
                    if relative_target is None:
                        continue
                    path = _resolve_local_target(
                        resolved,
                        relative_target,
                        kind="link",
                    )
            except (OSError, UnicodeError, ValueError) as error:
                broken += 1
                errors.append(
                    f"{relative}:{line_number}: "
                    f"unsafe local link {target!r}: {error}"
                )
                continue
            if not path.exists():
                broken += 1
                errors.append(
                    f"{relative}:{line_number}: "
                    f"missing local link: {target}"
                )
                continue

            try:
                fragment = _link_fragment(target_text)
                if fragment is None:
                    continue
                anchors = anchors_by_path.get(path)
                if anchors is None:
                    anchors = markdown_heading_anchors(
                        path.read_text(encoding="utf-8")
                    )
                    anchors_by_path[path] = anchors
            except (OSError, UnicodeError, ValueError) as error:
                broken += 1
                errors.append(
                    f"{relative}:{line_number}: "
                    f"unsafe local link fragment {target!r}: {error}"
                )
                continue
            if fragment not in anchors:
                broken += 1
                errors.append(
                    f"{relative}:{line_number}: "
                    f"missing local link fragment: {target}"
                )
    return errors, broken


def _link_fragment(target: str) -> str | None:
    split_at = target.find("#")
    if split_at < 0:
        return None
    encoded = target[split_at + 1 :]
    if not encoded:
        raise ValueError("empty fragment")
    if re.search(r"%(?![0-9A-Fa-f]{2})", encoded):
        raise ValueError("invalid percent escape in fragment")
    return unquote(encoded, encoding="utf-8", errors="strict")


def _normalize_link_target(raw_target: str) -> str:
    target = _markdown_target_text(raw_target)
    path_text, suffix = _split_literal_suffix(target)
    return _percent_decode_path(path_text) + suffix


def _markdown_target_text(raw_target: str) -> str:
    target = raw_target.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    return unescape_html(_markdown_unescape(target))


def _markdown_unescape(value: str) -> str:
    return re.sub(
        r"""\\([!\"#$%&'()*+,\-./:;<=>?@\[\]\\^_`{|}~])""",
        r"\1",
        value,
    )


def _split_literal_suffix(target: str) -> tuple[str, str]:
    delimiters = [
        index
        for delimiter in ("?", "#")
        if (index := target.find(delimiter)) >= 0
    ]
    if not delimiters:
        return target, ""
    split_at = min(delimiters)
    return target[:split_at], target[split_at:]


def _percent_decode_path(path_text: str) -> str:
    if re.search(r"%(?![0-9A-Fa-f]{2})", path_text):
        raise ValueError("invalid percent escape in target")
    return unquote(
        path_text,
        encoding="utf-8",
        errors="strict",
    )


def _local_target(raw_target: str, *, kind: str) -> Path | None:
    target = _markdown_target_text(raw_target)
    if not target:
        raise ValueError(f"empty {kind} target")
    if target.startswith("#"):
        if kind == "link":
            return None
        raise ValueError("fragment-only image target")
    encoded_path, _ = _split_literal_suffix(target)
    path_text = _percent_decode_path(encoded_path)
    lowered = path_text.casefold()
    if (
        re.match(r"^[a-z]:", lowered)
        or lowered.startswith(
            ("\\\\?\\", "\\\\.\\", "\\??\\", "//?/", "//./")
        )
    ):
        raise ValueError("rooted or device path is not allowed")
    scheme_match = URI_SCHEME_RE.match(path_text)
    if scheme_match is not None:
        scheme = scheme_match.group("scheme").casefold()
        if scheme not in REMOTE_LINK_SCHEMES:
            raise ValueError(f"URI scheme is not allowed: {scheme}")
    if _is_remote_target(raw_target):
        if kind == "image":
            raise ValueError("remote image target is not allowed")
        return None
    if not path_text:
        if kind == "link" and target != path_text:
            return None
        raise ValueError(f"empty {kind} target")
    windows = PureWindowsPath(path_text)
    if (
        "\\" in path_text
        or path_text.startswith("/")
        or windows.drive
        or windows.root
        or re.match(r"^[A-Za-z]:", path_text)
    ):
        raise ValueError("rooted or device path is not allowed")

    parts = tuple(path_text.split("/"))
    for part in parts:
        device = part.split(".", 1)[0].rstrip(" ").upper()
        if (
            part in {"", ".", ".."}
            or part != part.rstrip(" .")
            or any(ord(character) < 32 for character in part)
            or any(character in '<>:"|?*' for character in part)
            or device in WINDOWS_DEVICES
        ):
            raise ValueError(f"unsafe path component: {part!r}")
    return Path(*parts)


def _is_remote_target(target: str) -> bool:
    target_text = _markdown_target_text(target)
    path_text, _ = _split_literal_suffix(target_text)
    decoded = _percent_decode_path(path_text)
    scheme = URI_SCHEME_RE.match(decoded)
    return (
        path_text.startswith("//")
        or (
            scheme is not None
            and scheme.group("scheme").casefold()
            in REMOTE_LINK_SCHEMES
        )
    )


def _resolve_local_target(
    resolved: _ResolvedMarkdown,
    relative_target: Path,
    *,
    kind: str,
) -> Path:
    lexical = _absolute_path(
        resolved.markdown.parent / relative_target
    )
    if not lexical.is_relative_to(resolved.root):
        raise ValueError(f"{kind} target escapes output_root")

    current = resolved.root
    relative_from_root = lexical.relative_to(resolved.root)
    for part in relative_from_root.parts:
        current /= part
        if _is_reparse_point(current):
            raise ValueError(
                f"{kind} target contains a symlink or reparse point: "
                f"{current}"
            )

    if not lexical.exists():
        return lexical
    target = lexical.resolve(strict=True)
    if not target.is_relative_to(resolved.root):
        raise ValueError(f"{kind} target escapes output_root")
    if kind == "image" and not target.is_file():
        raise ValueError("image target is not a file")
    return target


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _image_dimensions(path: Path) -> tuple[int | None, int | None]:
    try:
        with path.open("rb") as stream:
            signature = stream.read(24)
        if (
            signature.startswith(b"\x89PNG\r\n\x1a\n")
            and len(signature) >= 24
        ):
            return struct.unpack(">II", signature[16:24])
        if (
            signature[:6] in {b"GIF87a", b"GIF89a"}
            and len(signature) >= 10
        ):
            return struct.unpack("<HH", signature[6:10])
    except OSError:
        pass
    return None, None
