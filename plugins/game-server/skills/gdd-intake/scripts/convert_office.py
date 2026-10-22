#!/usr/bin/env python3
"""Convert the files in a GDD folder to text that an agent can read.

Usage:
    python3 convert_office.py <input_folder> <work_dir>

Reads docx, pptx, and xlsx with the standard library only. PDF needs PyMuPDF
(`pip install pymupdf`), imported as `pymupdf` or, in older releases, `fitz`; without
it the script asks for an export instead. Files in subfolders are not read.

Output under <work_dir>:
    raw/slides_<base>.md       one file per pptx, with "## Slide <n>: <title>" headings; a
                               chart becomes "Chart: <title>" and a table of its cached
                               values, one row per category and one column per series
    raw/doc_<base>.md          one file per docx; a table nested in a cell follows the outer
                               table as its own table, and the cell says "(nested table
                               below)"; then "## Headers and footers" (each distinct text
                               once) and "## Comments" (each with the text it is anchored to)
    raw/pdf_<base>.md          one file per pdf (PyMuPDF only), NFKC-normalized so that
                               ligatures such as U+FB01 read as "fi"
    raw/<base>_<sheet>.csv     one file per xlsx sheet; CSV line n is sheet row n
    raw/<base>_<sheet>.md      sheet notes: merged cells, formulas, comments, preview
    raw/<name>                 md, txt, csv, and json files copied as they are
    images/                    raster images from the files and loose images in the folder,
                               named <kind>_<base>-...img<n> with <kind> doc, slides, sheet, or
                               pdf, so files that share a stem keep apart; loose images are
                               standalone-<base>
    conversion-manifest.json   what was converted, skipped, and needs an export
    conversion-manifest.md     the same for a reader

Sheet values: a number is written in its shortest round-trip form (1.4279999999999999
becomes 1.428), and a whole number stays a whole number. A number whose cell style is a
date or time format (built-in ids 14 to 22 and 45 to 47, or a custom format with d, m, y,
h, or s outside quotes and brackets) is written as ISO 8601: a date, a date and time, or a
time alone when the value is under one day. The 1900 date system keeps Excel's phantom
1900-02-29 (serial 60), and a workbook flagged date1904 counts from 1904-01-01. An
elapsed format such as [h]:mm:ss is written as hours:minutes:seconds, for example 36:00:00.

Sheet formulas: a shared formula block (one formula Excel copies over a range) is listed
as one line, `<range>`: `<formula>`, written as it reads in the range's first cell. When
other formulas overwrite part of the range, each remaining cell is listed with its own
shifted formula. Shifting moves relative cell references, sheet-qualified ones included,
and keeps $-fixed parts; whole-column and whole-row references are kept as written. The
notes list at most 300 formula lines per sheet.

When two inputs would write the same output name, the later one in name order gets `_`
before its extension, so no output overwrites another.

Exit codes: 0 when the run finished (skipped files and warnings are listed in the
manifest), 1 for a bad command line or a missing input folder.
"""
import csv
import json
import posixpath
import re
import shutil
import sys
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path

try:
    import pymupdf as fitz  # optional and used only for .pdf
except ImportError:
    try:
        import fitz  # PyMuPDF before 1.24.3 has only this name
    except ImportError:
        fitz = None
HAS_PYMUPDF = fitz is not None

RASTER = {"png": "png", "jpg": "jpg", "jpeg": "jpg", "gif": "gif", "bmp": "bmp",
          "tif": "tiff", "tiff": "tiff", "webp": "webp"}
TEXT_EXTENSIONS = (".md", ".txt", ".csv", ".json")
LEGACY = {".doc": ".docx", ".ppt": ".pptx", ".xls": ".xlsx"}

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
S = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
C = "{http://schemas.openxmlformats.org/drawingml/2006/chart}"
PKG = "{http://schemas.openxmlformats.org/package/2006/relationships}"

PREVIEW_ROWS = 30
PREVIEW_COLUMNS = 30
FORMULA_LIMIT = 300
DATE_FORMAT_IDS = set(range(14, 23)) | {45, 46, 47}


def safe_name(name):
    return "".join(c if c.isalnum() or c in "._-" else "_" for c in name)


def claim(used, stem, *suffixes):
    while any(stem + suffix in used for suffix in suffixes):
        stem += "_"
    used.update(stem + suffix for suffix in suffixes)
    return stem


def cell_text(value):
    return " ".join(value.split()).replace("|", "\\|")


def table_md(rows):
    rows = [row for row in rows if row]
    if not rows:
        return ""
    width = max(len(row) for row in rows)
    lines = ["| " + " | ".join(cell_text(c) for c in row + [""] * (width - len(row))) + " |" for row in rows]
    lines.insert(1, "| " + " | ".join("---" for _ in range(width)) + " |")
    return "\n".join(lines)


def parse(archive, member):
    data = archive.read(member)
    if b"<!DOCTYPE" in data or b"<!ENTITY" in data:
        raise ValueError(f"{member} declares a DTD or an entity, which Office files never do")
    return ET.fromstring(data)


def resolve(part, target):
    if target.startswith("/"):
        return target[1:]
    return posixpath.normpath(posixpath.join(posixpath.dirname(part), target))


def related(archive, rels, suffix):
    names = archive.namelist()
    return [member for kind, member in rels.values() if kind.endswith(suffix) and member in names]


def read_rels(archive, part):
    rels_name = posixpath.join(posixpath.dirname(part), "_rels", posixpath.basename(part) + ".rels")
    if rels_name not in archive.namelist():
        return {}
    found = {}
    for rel in parse(archive, rels_name).iter(PKG + "Relationship"):
        if rel.get("TargetMode") == "External":
            continue
        found[rel.get("Id")] = (rel.get("Type", ""), resolve(part, rel.get("Target", "")))
    return found


class ImageSink:

    def __init__(self, archive, images_dir, base, used):
        self.archive, self.images_dir, self.base, self.used = archive, images_dir, base, used
        self.names = {}
        self.counters = {}
        self.skipped = []

    def copy(self, member, label=""):
        if member in self.names:
            return self.names[member]
        extension = RASTER.get(member.rsplit(".", 1)[-1].lower())
        if extension is None or member not in self.archive.namelist():
            self.skipped.append(member)
            return None
        prefix = f"{self.base}-{label}img" if label else f"{self.base}-img"
        self.counters[prefix] = self.counters.get(prefix, 0) + 1
        name = claim(self.used, f"{prefix}{self.counters[prefix]:03d}", f".{extension}") + f".{extension}"
        (self.images_dir / name).write_bytes(self.archive.read(member))
        self.names[member] = name
        return name

    def copy_folder(self, folder):
        for member in self.archive.namelist():
            if member.startswith(folder) and not member.endswith("/"):
                self.copy(member)

    @property
    def count(self):
        return len(self.names)


def image_line(name, alt=""):
    return f"![{alt or name}](../images/{name})"



def docx_style_names(archive):
    if "word/styles.xml" not in archive.namelist():
        return {}
    names = {}
    for style in parse(archive, "word/styles.xml").iter(W + "style"):
        name = style.find(W + "name")
        if name is not None:
            names[style.get(W + "styleId")] = name.get(W + "val", "")
    return names


def heading_level(style_id, names):
    name = names.get(style_id, style_id or "").lower()
    if name == "title":
        return 0
    match = re.fullmatch(r"heading\s*(\d)", name)
    return int(match.group(1)) if match else None


def docx_blocks(parent):
    for child in parent:
        if child.tag in (W + "p", W + "tbl"):
            yield child
        elif child.tag == W + "sdt":
            content = child.find(W + "sdtContent")
            if content is not None:
                yield from docx_blocks(content)


def docx_text(paragraph):
    parts = []
    for element in paragraph.iter():
        if element.tag == W + "t":
            parts.append(element.text or "")
        elif element.tag == W + "tab":
            parts.append("\t")
        elif element.tag in (W + "br", W + "cr"):
            parts.append(" ")
    return "".join(parts).strip()


def docx_table(table):
    rows, nested = [], []
    for r, row in enumerate(table.findall(W + "tr"), start=1):
        cells = []
        for c, cell in enumerate(row.findall(W + "tc"), start=1):
            parts = []
            for block in docx_blocks(cell):
                if block.tag == W + "tbl":
                    nested.append((r, c, block))
                    parts.append("(nested table below)")
                else:
                    parts.append(docx_text(block))
            cells.append(" ".join(filter(None, parts)))
        rows.append(cells)
    lines = [table_md(rows), ""]
    for r, c, block in nested:
        lines += [f"Table nested in row {r}, column {c}:", ""] + docx_table(block)
    return lines


def docx_headers_and_footers(archive, rels):
    lines, seen = [], []
    for kind in ("header", "footer"):
        for member in sorted(related(archive, rels, "/" + kind)):
            text = []
            for block in docx_blocks(parse(archive, member)):
                if block.tag == W + "tbl":
                    text += docx_table(block)
                elif docx_text(block):
                    text += [docx_text(block), ""]
            if text and text not in seen:
                seen.append(text)
                lines += [f"{kind.title()}:", ""] + text
    return ["## Headers and footers", ""] + lines if lines else []


def docx_comments(archive, rels, body):
    members = related(archive, rels, "/comments")
    if not members:
        return []
    anchors, open_ids = {}, set()
    for element in body.iter():
        if element.tag == W + "commentRangeStart":
            open_ids.add(element.get(W + "id"))
        elif element.tag == W + "commentRangeEnd":
            open_ids.discard(element.get(W + "id"))
        elif element.tag == W + "t":
            for comment_id in open_ids:
                anchors.setdefault(comment_id, []).append(element.text or "")
    lines = []
    for comment in parse(archive, members[0]).iter(W + "comment"):
        text = " ".join(filter(None, (docx_text(p) for p in comment.iter(W + "p"))))
        anchor = " ".join("".join(anchors.get(comment.get(W + "id"), [])).split())
        lines.append(f'- On "{anchor}": {text}' if anchor else f"- {text}")
    return ["## Comments", ""] + lines + [""] if lines else []


def convert_docx(path, raw_dir, images_dir, used):
    stem = claim(used, f"doc_{safe_name(path.stem)}", ".md")
    out = raw_dir / f"{stem}.md"
    with zipfile.ZipFile(path) as archive:
        names = docx_style_names(archive)
        rels = read_rels(archive, "word/document.xml")
        sink = ImageSink(archive, images_dir, stem, used)
        body = parse(archive, "word/document.xml").find(W + "body")
        lines = [f"# Document: {path.name}", ""]
        tables = paragraphs = 0
        placed = set()
        for block in docx_blocks(body):
            if block.tag == W + "tbl":
                tables += 1
                lines += docx_table(block)
                continue
            paragraphs += 1
            text = docx_text(block)
            style = block.find(f"{W}pPr/{W}pStyle")
            level = heading_level(style.get(W + "val") if style is not None else None, names)
            numbering = block.find(f"{W}pPr/{W}numPr")
            if text and level is not None:
                lines += ["#" * min(level + 1, 6) + " " + text, ""]
            elif text and numbering is not None:
                ilvl = numbering.find(W + "ilvl")
                depth = int(ilvl.get(W + "val", "0")) if ilvl is not None else 0
                lines.append("  " * depth + "- " + text)
            elif text:
                lines += [text, ""]
            for blip in block.iter(A + "blip"):
                target = rels.get(blip.get(R + "embed"))
                name = sink.copy(target[1]) if target else None
                if name:
                    placed.add(name)
                    lines += [image_line(name), ""]
        lines += docx_headers_and_footers(archive, rels) + docx_comments(archive, rels, body)
        sink.copy_folder("word/media/")
        remaining = [n for n in sink.names.values() if n not in placed]
        if remaining:
            lines += ["## Other images in the document", ""] + [image_line(n) for n in remaining] + [""]
    out.write_text("\n".join(lines), encoding="utf-8")
    return {"source": path.name, "type": "docx", "output": f"raw/{out.name}", "paragraphs": paragraphs,
            "tables": tables, "images_extracted": sink.count, "images_skipped": sink.skipped}



def drawing_paragraph(paragraph):
    parts = []
    for child in paragraph:
        if child.tag in (A + "r", A + "fld"):
            parts.append("".join(t.text or "" for t in child.findall(A + "t")))
        elif child.tag == A + "br":
            parts.append(" ")
    text = "".join(parts).strip()
    properties = paragraph.find(A + "pPr")
    level = int(properties.get("lvl", "0")) if properties is not None else 0
    return "  " * level + "- " + text if text and level else text


def shape_lines(shape):
    return [t for t in (drawing_paragraph(p) for p in shape.iter(A + "p")) if t]


def placeholder_type(shape):
    placeholder = shape.find(f".//{P}ph")
    return placeholder.get("type", "body") if placeholder is not None else None


def slide_members(archive):
    rels = read_rels(archive, "ppt/presentation.xml")
    members = []
    for slide_id in parse(archive, "ppt/presentation.xml").iter(P + "sldId"):
        target = rels.get(slide_id.get(R + "id"))
        if target:
            members.append(target[1])
    return members


def notes_text(archive, rels):
    for kind, member in rels.values():
        if kind.endswith("/notesSlide") and member in archive.namelist():
            shapes = [s for s in parse(archive, member).iter(P + "sp") if placeholder_type(s) == "body"]
            return "\n".join(line for s in shapes for line in shape_lines(s))
    return ""


def chart_points(series, tag):
    return {int(pt.get("idx", "0")): pt.findtext(C + "v", "") for pt in series.iterfind(f"{C}{tag}//{C}pt")}


def chart_text(element):
    if element is None:
        return ""
    return "".join(e.text or "" for e in element.iter() if e.tag in (A + "t", C + "v")).strip()


def chart_lines(root):
    categories, series = {}, []
    for ser in root.iter(C + "ser"):
        name = chart_text(ser.find(C + "tx"))
        for idx, label in (chart_points(ser, "cat") or chart_points(ser, "xVal")).items():
            categories.setdefault(idx, label)
        values = chart_points(ser, "val") or chart_points(ser, "yVal")
        series.append((name or f"Series {len(series) + 1}", values))
    rows = [["Category"] + [name for name, _ in series]]
    for idx in sorted(set(categories).union(*(values for _, values in series))):
        rows.append([categories.get(idx, str(idx + 1))]
                    + [number_text(values.get(idx, "")) for _, values in series])
    title = chart_text(root.find(f"{C}chart/{C}title"))
    return [f"Chart: {title or '(no title)'}", "", table_md(rows), ""]


def convert_pptx(path, raw_dir, images_dir, used):
    stem = claim(used, f"slides_{safe_name(path.stem)}", ".md")
    out = raw_dir / f"{stem}.md"
    lines = [f"# Slides: {path.name}", ""]
    tables = notes_slides = charts = 0
    with zipfile.ZipFile(path) as archive:
        sink = ImageSink(archive, images_dir, stem, used)
        members = slide_members(archive)
        for number, member in enumerate(members, start=1):
            root = parse(archive, member)
            rels = read_rels(archive, member)
            title, body = "", []
            for element in root.iter():
                if element.tag == P + "sp":
                    kind = placeholder_type(element)
                    if kind in ("sldNum", "ftr", "dt"):
                        continue
                    text = shape_lines(element)
                    if kind in ("title", "ctrTitle") and not title:
                        title = " ".join(text)
                    elif text:
                        body += text + [""]
                elif element.tag == P + "graphicFrame":
                    rows = [[" ".join(shape_lines(cell)) for cell in row.findall(A + "tc")]
                            for row in element.iter(A + "tr")]
                    if rows:
                        tables += 1
                        body += [table_md(rows), ""]
                    chart = element.find(f".//{C}chart")
                    target = rels.get(chart.get(R + "id")) if chart is not None else None
                    if target and target[1] in archive.namelist():
                        charts += 1
                        body += chart_lines(parse(archive, target[1]))
                elif element.tag == P + "pic":
                    blip = element.find(f".//{A}blip")
                    target = rels.get(blip.get(R + "embed")) if blip is not None else None
                    name = sink.copy(target[1], f"slide{number:03d}-") if target else None
                    description = element.find(f".//{P}cNvPr")
                    alt = description.get("descr", "") if description is not None else ""
                    body += [image_line(name, alt), ""] if name else []
            lines += [f"## Slide {number}: {title or '(no title)'}", ""] + body
            notes = notes_text(archive, rels)
            if notes:
                notes_slides += 1
                lines += ["Speaker notes:", "", notes, ""]
    out.write_text("\n".join(lines), encoding="utf-8")
    return {"source": path.name, "type": "pptx", "output": f"raw/{out.name}", "slides": len(members),
            "tables": tables, "charts": charts, "images_extracted": sink.count,
            "speaker_notes_slides": notes_slides, "images_skipped": sink.skipped}



def column_number(letters):
    number = 0
    for letter in letters:
        number = number * 26 + ord(letter) - 64
    return number


def column_letters(number):
    letters = ""
    while number:
        number, rest = divmod(number - 1, 26)
        letters = chr(65 + rest) + letters
    return letters


def shared_strings(archive):
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    strings = []
    for item in parse(archive, "xl/sharedStrings.xml").iter(S + "si"):
        text = [t.text or "" for t in item.findall(S + "t")]
        for run in item.findall(S + "r"):
            text += [t.text or "" for t in run.findall(S + "t")]
        strings.append("".join(text))
    return strings


def number_text(text):
    if re.fullmatch(r"-?\d+", text):
        return text
    try:
        number = float(text)
    except ValueError:
        return text
    return str(int(number)) if number.is_integer() else repr(number)


def date_styles(archive, rels):
    members = related(archive, rels, "/styles")
    if not members:
        return {}
    root = parse(archive, members[0])
    codes = {f.get("numFmtId"): f.get("formatCode", "") for f in root.iter(S + "numFmt")}
    styles = {}
    for index, xf in enumerate(root.iterfind(f"{S}cellXfs/{S}xf")):
        fmt = xf.get("numFmtId", "0")
        if fmt in codes:
            code = re.sub(r'"[^"]*"|\[[^\]]*\]|\\.|[_*].', "", codes[fmt])
            is_date = re.search(r"[dmyhs]", code, re.I) is not None
        else:
            is_date = int(fmt) in DATE_FORMAT_IDS
        if is_date:
            styles[str(index)] = fmt == "46" or re.search(r"\[(h+|m+|s+)\]", codes.get(fmt, ""), re.I) is not None
    return styles


def date_text(serial, date1904, elapsed):
    days, seconds = divmod(round(serial * 86400), 86400)
    hours, minutes = divmod(seconds // 60, 60)
    if elapsed:
        return f"{days * 24 + hours}:{minutes:02d}:{seconds % 60:02d}"
    clock = f"{hours:02d}:{minutes:02d}:{seconds % 60:02d}"
    if days == 0:
        return clock
    base = date(1904, 1, 1) if date1904 else date(1899, 12, 31 if days < 60 else 30)
    day = "1900-02-29" if days == 60 and not date1904 else (base + timedelta(days)).isoformat()
    return f"{day}T{clock}" if seconds else day


def cell_value(cell, strings, dates, date1904):
    kind = cell.get("t")
    if kind == "inlineStr":
        return "".join(t.text or "" for t in cell.iter(S + "t"))
    value = cell.find(S + "v")
    if value is None or value.text is None:
        return ""
    if kind == "s":
        index = int(value.text)
        return strings[index] if index < len(strings) else ""
    if kind == "b":
        return "TRUE" if value.text.strip() == "1" else "FALSE"
    if kind not in (None, "n"):
        return value.text
    style = cell.get("s", "0")
    if style in dates and 0 <= (serial := float(value.text)) < 2958466:
        return date_text(serial, date1904, dates[style])
    return number_text(value.text)


REFERENCE = re.compile(r"\"[^\"]*\"|'[^']*'|(?<![A-Za-z0-9_.])(\$?)([A-Z]{1,3})(\$?)(\d+)(?![A-Za-z0-9_(])")


def shift_formula(formula, rows, columns):
    def move(match):
        if match.group(2) is None:
            return match.group(0)
        column_fixed, letters, row_fixed, number = match.groups()
        column = column_number(letters) + (0 if column_fixed else columns)
        row = int(number) + (0 if row_fixed else rows)
        return f"{column_fixed}{column_letters(column)}{row_fixed}{row}"
    return REFERENCE.sub(move, formula)


def range_size(ref):
    corners = [re.fullmatch(r"([A-Z]+)(\d+)", part).groups() for part in ref.split(":")]
    rows = [int(number) for _, number in corners]
    columns = [column_number(letters) for letters, _ in corners]
    return (max(rows) - min(rows) + 1) * (max(columns) - min(columns) + 1)


def formula_lines(entries):
    """Excel writes a shared formula's text and range on its top-left cell, so a block
    whose every cell still carries the shared index is listed once as `<range>`: `<text>`."""
    masters = {si: (row, column, text, ref) for row, column, si, text, ref in entries if si is not None and text}
    sizes = {}
    for _, _, si, _, _ in entries:
        if si is not None:
            sizes[si] = sizes.get(si, 0) + 1
    whole = {si for si, (_, _, _, ref) in masters.items() if ref and range_size(ref) == sizes[si]}
    lines = []
    for row, column, si, text, ref in entries:
        if si in whole:
            if text:
                lines.append((ref, text))
        elif si in masters:
            master_row, master_column, master_text, _ = masters[si]
            lines.append((f"{column_letters(column)}{row}",
                          shift_formula(master_text, row - master_row, column - master_column)))
        elif text:
            lines.append((f"{column_letters(column)}{row}", text))
    return lines


def read_sheet(archive, member, strings, dates, date1904):
    root = parse(archive, member)
    values, entries = {}, []
    row_number = 0
    for row in root.iter(S + "row"):
        row_number = int(row.get("r", row_number + 1))
        column = 0
        for cell in row.findall(S + "c"):
            match = re.fullmatch(r"([A-Z]+)(\d+)", cell.get("r", ""))
            column = column_number(match.group(1)) if match else column + 1
            value = cell_value(cell, strings, dates, date1904)
            if value != "":
                values[(row_number, column)] = value
            formula = cell.find(S + "f")
            if formula is not None:
                si = formula.get("si") if formula.get("t") == "shared" else None
                entries.append((row_number, column, si, (formula.text or "").strip(), formula.get("ref")))
    merges = [m.get("ref") for m in root.iter(S + "mergeCell")]
    comments = {}
    for kind, target in read_rels(archive, member).values():
        if kind.endswith("/comments") and target in archive.namelist():
            for comment in parse(archive, target).iter(S + "comment"):
                comments[comment.get("ref")] = "".join(t.text or "" for t in comment.iter(S + "t"))
    return values, entries, merges, comments


def convert_xlsx(path, raw_dir, images_dir, used):
    base = safe_name(path.stem)
    sheets = []
    with zipfile.ZipFile(path) as archive:
        strings = shared_strings(archive)
        rels = read_rels(archive, "xl/workbook.xml")
        workbook = parse(archive, "xl/workbook.xml")
        dates = date_styles(archive, rels)
        properties = workbook.find(S + "workbookPr")
        date1904 = properties is not None and properties.get("date1904") in ("1", "true")
        for sheet in workbook.iter(S + "sheet"):
            name = sheet.get("name", "")
            target = rels.get(sheet.get(R + "id"))
            if not target:
                continue
            values, entries, merges, comments = read_sheet(archive, target[1], strings, dates, date1904)
            formulas = formula_lines(entries)
            rows = max((r for r, _ in values), default=0)
            columns = max((c for _, c in values), default=0)
            stem = claim(used, f"{base}_{safe_name(name)}", ".csv", ".md")
            with (raw_dir / f"{stem}.csv").open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle, lineterminator="\n")
                for r in range(1, rows + 1):
                    writer.writerow([values.get((r, c), "") for c in range(1, columns + 1)])
            notes = [f"# Sheet: {name} (file: {path.name})", "",
                     f"- Rows: {rows}, columns: {columns}",
                     f"- Cell values: `{stem}.csv`. Line n of the CSV is sheet row n, and column 1 is column A."]
            if sheet.get("state") in ("hidden", "veryHidden"):
                notes.append(f"- State: {sheet.get('state')}")
            if merges:
                notes += ["", "## Merged cell ranges"] + [f"- `{m}`" for m in merges]
            if formulas:
                notes += ["", "## Formula cells"]
                if any(":" in ref for ref, _ in formulas):
                    notes.append("A range is one shared formula, written as it reads in the range's first cell. "
                                 "Each other cell shifts its relative references by its offset.")
                notes += [f"- `{ref}`: `{text}`" for ref, text in formulas[:FORMULA_LIMIT]]
                if len(formulas) > FORMULA_LIMIT:
                    notes.append(f"- {len(formulas) - FORMULA_LIMIT} more lines in the workbook")
            if comments:
                notes += ["", "## Comments"] + [f"- `{ref}`: {text}" for ref, text in comments.items()]
            shown = min(columns, PREVIEW_COLUMNS)
            notes += ["", f"## Preview of the first {PREVIEW_ROWS} rows", ""]
            preview = [["Row"] + [column_letters(c) for c in range(1, shown + 1)]]
            for r in range(1, min(rows, PREVIEW_ROWS) + 1):
                preview.append([str(r)] + [values.get((r, c), "") for c in range(1, shown + 1)])
            notes.append(table_md(preview) if rows else "The sheet has no values.")
            (raw_dir / f"{stem}.md").write_text("\n".join(notes) + "\n", encoding="utf-8")
            sheets.append({"sheet": name, "csv": f"{stem}.csv", "md": f"{stem}.md", "rows": rows,
                           "cols": columns, "merged_ranges": len(merges), "formulas": len(entries),
                           "comments": len(comments)})
        sink = ImageSink(archive, images_dir, f"sheet_{base}", used)
        sink.copy_folder("xl/media/")
    return {"source": path.name, "type": "xlsx", "sheets": sheets, "images_extracted": sink.count,
            "images_skipped": sink.skipped}



def convert_pdf(path, raw_dir, images_dir, used):
    stem = claim(used, f"pdf_{safe_name(path.stem)}", ".md")
    out = raw_dir / f"{stem}.md"
    images = tables = 0
    with fitz.open(str(path)) as document:
        pages = document.page_count
        lines = [f"# PDF: {path.name}", "", f"- Pages: {pages}", ""]
        for number, page in enumerate(document, start=1):
            lines += [f"## Page {number}", ""]
            text = unicodedata.normalize("NFKC", page.get_text("text")).strip()
            if text:
                lines += [text, ""]
            if hasattr(page, "find_tables"):
                try:
                    found = page.find_tables()
                    for table in getattr(found, "tables", found):
                        rows = [["" if c is None else unicodedata.normalize("NFKC", str(c)) for c in row]
                                for row in table.extract()]
                        if rows:
                            tables += 1
                            lines += [table_md(rows), ""]
                except Exception:
                    pass
            for info in page.get_images(full=True):
                try:
                    pixmap = fitz.Pixmap(document, info[0])
                    if pixmap.n - pixmap.alpha >= 4:
                        pixmap = fitz.Pixmap(fitz.csRGB, pixmap)
                    images += 1
                    name = claim(used, f"{stem}-page{number:03d}-img{images:03d}", ".png") + ".png"
                    pixmap.save(str(images_dir / name))
                    lines += [image_line(name), ""]
                except Exception:
                    continue
    out.write_text("\n".join(lines), encoding="utf-8")
    return {"source": path.name, "type": "pdf", "output": f"raw/{out.name}", "pages": pages,
            "tables": tables, "images_extracted": images}



def copy_loose_image(path, images_dir, used):
    extension = "." + RASTER[path.suffix.lower().lstrip(".")]
    name = claim(used, f"standalone-{safe_name(path.stem)}", extension) + extension
    shutil.copyfile(path, images_dir / name)
    return {"source": path.name, "type": "standalone-image", "output": f"images/{name}"}


def convert_folder(input_folder, work_dir):
    raw_dir, images_dir = work_dir / "raw", work_dir / "images"
    raw_dir.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"input_folder": str(input_folder), "work_dir": str(work_dir),
                "converted_at": datetime.now().isoformat(timespec="seconds"),
                "files": [], "skipped": [], "export_requests": [], "warnings": []}
    used = set()
    for path in sorted(input_folder.iterdir()):
        extension = path.suffix.lower()
        if path.name.startswith(("~$", ".")):
            continue
        if path.is_dir():
            manifest["skipped"].append({"file": path.name, "reason": "folder; move its files up one level"})
            continue
        try:
            if extension == ".docx":
                manifest["files"].append(convert_docx(path, raw_dir, images_dir, used))
            elif extension == ".pptx":
                manifest["files"].append(convert_pptx(path, raw_dir, images_dir, used))
            elif extension == ".xlsx":
                manifest["files"].append(convert_xlsx(path, raw_dir, images_dir, used))
            elif extension == ".pdf" and HAS_PYMUPDF:
                manifest["files"].append(convert_pdf(path, raw_dir, images_dir, used))
            elif extension == ".pdf":
                manifest["export_requests"].append({
                    "file": path.name,
                    "reason": "PyMuPDF is not installed, so the PDF cannot be read",
                    "ask": "Export it to docx or Markdown, put the export in the input folder, and run again.",
                })
            elif extension in LEGACY:
                manifest["skipped"].append({
                    "file": path.name,
                    "reason": f"legacy {extension} format; save it as {LEGACY[extension]} and run again",
                })
            elif extension in TEXT_EXTENSIONS:
                name = claim(used, path.stem, path.suffix) + path.suffix
                shutil.copyfile(path, raw_dir / name)
                manifest["files"].append({"source": path.name, "type": "text", "output": f"raw/{name}"})
            elif extension.lstrip(".") in RASTER:
                manifest["files"].append(copy_loose_image(path, images_dir, used))
            else:
                manifest["skipped"].append({"file": path.name, "reason": f"unsupported extension {extension}"})
        except Exception as error:
            manifest["warnings"].append({"file": path.name, "error": f"{type(error).__name__}: {error}"})
    return manifest


LOSSES = [
    "SmartArt, shapes, vector drawings, and charts outside slides are not converted. Slide charts are "
    "read as tables of their cached values. Only raster images are copied out. "
    "If one of them carries rules or numbers, export it as a PNG into the images folder.",
    "Merged table cells are flattened. Check the merged ranges in each sheet note.",
    "Spreadsheet formulas are listed as written, and the CSV holds their last saved values. "
    "A cell with a date or time format appears in ISO 8601.",
    "A scanned PDF has no text layer and reads as empty.",
]


def manifest_markdown(manifest):
    lines = ["# Conversion manifest", "", f"- Input: `{manifest['input_folder']}`",
             f"- Converted at: {manifest['converted_at']}", "", "## Converted", ""]
    for entry in manifest["files"]:
        lines.append(f"### {entry['source']} ({entry['type']})")
        for key, value in entry.items():
            if key in ("source", "type"):
                continue
            if key == "sheets":
                lines.append("- sheets:")
                lines += [f"  - `{s['sheet']}`: `{s['csv']}`, {s['rows']} rows, {s['cols']} columns, "
                          f"{s['merged_ranges']} merged ranges, {s['formulas']} formulas, "
                          f"{s['comments']} comments" for s in value]
            elif value or value == 0:
                lines.append(f"- {key}: {value}")
        lines.append("")
    for title, key, template in (
        ("Needs an export", "export_requests", "- `{file}`: {reason}. {ask}"),
        ("Skipped", "skipped", "- `{file}`: {reason}"),
        ("Warnings", "warnings", "- `{file}`: {error}"),
    ):
        if manifest[key]:
            lines += [f"## {title}", ""] + [template.format(**item) for item in manifest[key]] + [""]
    lines += ["## What conversion loses", ""] + [f"- {text}" for text in LOSSES] + [""]
    return "\n".join(lines)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print("Usage: convert_office.py <input_folder> <work_dir>", file=sys.stderr)
        return 1
    input_folder, work_dir = Path(argv[0]).resolve(), Path(argv[1]).resolve()
    if not input_folder.is_dir():
        print(f"Input folder not found: {input_folder}", file=sys.stderr)
        return 1
    manifest = convert_folder(input_folder, work_dir)
    (work_dir / "conversion-manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    (work_dir / "conversion-manifest.md").write_text(manifest_markdown(manifest), encoding="utf-8")
    print(f"Converted {len(manifest['files'])} file(s), skipped {len(manifest['skipped'])}, "
          f"{len(manifest['export_requests'])} need an export, {len(manifest['warnings'])} warning(s).")
    for request in manifest["export_requests"]:
        print(f"Export request: {request['file']}. {request['reason']}. {request['ask']}")
    for item in manifest["skipped"]:
        print(f"Skipped: {item['file']}. {item['reason']}.")
    for item in manifest["warnings"]:
        print(f"Warning: {item['file']}. {item['error']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
