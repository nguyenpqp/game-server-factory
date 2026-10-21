#!/usr/bin/env python3
"""Convert the files in a GDD folder to text that an agent can read.

Usage:
    python3 convert_office.py <input_folder> <work_dir>

Reads docx, pptx, and xlsx with the standard library only. PDF needs PyMuPDF;
without it the script asks for an export instead. Files in subfolders are not read.

Output under <work_dir>:
    raw/slides_<base>.md       one file per pptx, with "## Slide <n>: <title>" headings
    raw/doc_<base>.md          one file per docx
    raw/pdf_<base>.md          one file per pdf (PyMuPDF only)
    raw/<base>_<sheet>.csv     one file per xlsx sheet; CSV line n is sheet row n
    raw/<base>_<sheet>.md      sheet notes: merged cells, formulas, comments, preview
    raw/<name>                 md, txt, csv, and json files copied as they are
    images/                    raster images from the files and loose images in the folder,
                               named <kind>_<base>-...img<n> with <kind> doc, slides, sheet, or
                               pdf, so files that share a stem keep apart; loose images are
                               standalone-<base>
    conversion-manifest.json   what was converted, skipped, and needs an export
    conversion-manifest.md     the same for a reader

Exit codes: 0 when the run finished (skipped files and warnings are listed in the
manifest), 1 for a bad command line or a missing input folder.
"""
import csv
import json
import posixpath
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime
from pathlib import Path

try:
    import fitz  # PyMuPDF, optional and used only for .pdf

    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

RASTER = {"png": "png", "jpg": "jpg", "jpeg": "jpg", "gif": "gif", "bmp": "bmp",
          "tif": "tiff", "tiff": "tiff", "webp": "webp"}
TEXT_EXTENSIONS = (".md", ".txt", ".csv", ".json")
LEGACY = {".doc": ".docx", ".ppt": ".pptx", ".xls": ".xlsx"}

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
S = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PKG = "{http://schemas.openxmlformats.org/package/2006/relationships}"

PREVIEW_ROWS = 30
PREVIEW_COLUMNS = 30
FORMULA_LIMIT = 80


def safe_name(name):
    return "".join(c if c.isalnum() or c in "._-" else "_" for c in name)


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

    def __init__(self, archive, images_dir, base):
        self.archive, self.images_dir, self.base = archive, images_dir, base
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
        name = f"{prefix}{self.counters[prefix]:03d}.{extension}"
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


def convert_docx(path, raw_dir, images_dir):
    base = safe_name(path.stem)
    out = raw_dir / f"doc_{base}.md"
    with zipfile.ZipFile(path) as archive:
        names = docx_style_names(archive)
        rels = read_rels(archive, "word/document.xml")
        sink = ImageSink(archive, images_dir, f"doc_{base}")
        body = parse(archive, "word/document.xml").find(W + "body")
        lines = [f"# Document: {path.name}", ""]
        tables = paragraphs = 0
        placed = set()
        for block in docx_blocks(body):
            if block.tag == W + "tbl":
                rows = []
                for row in block.findall(W + "tr"):
                    rows.append([
                        " ".join(filter(None, (docx_text(p) for p in cell.iter(W + "p"))))
                        for cell in row.findall(W + "tc")
                    ])
                tables += 1
                lines += [table_md(rows), ""]
                continue
            paragraphs += 1
            text = docx_text(block)
            properties = block.find(W + "pPr")
            style = properties.find(W + "pStyle") if properties is not None else None
            level = heading_level(style.get(W + "val") if style is not None else None, names)
            if text and level is not None:
                lines += ["#" * min(level + 1, 6) + " " + text if level else "# " + text, ""]
            elif text:
                numbered = properties is not None and properties.find(W + "numPr") is not None
                if numbered:
                    ilvl = properties.find(W + "numPr").find(W + "ilvl")
                    depth = int(ilvl.get(W + "val", "0")) if ilvl is not None else 0
                    lines.append("  " * depth + "- " + text)
                else:
                    lines += [text, ""]
            for blip in block.iter(A + "blip"):
                target = rels.get(blip.get(R + "embed"))
                name = sink.copy(target[1]) if target else None
                if name:
                    placed.add(name)
                    lines += [image_line(name), ""]
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


def convert_pptx(path, raw_dir, images_dir):
    base = safe_name(path.stem)
    out = raw_dir / f"slides_{base}.md"
    lines = [f"# Slides: {path.name}", ""]
    tables = notes_slides = 0
    with zipfile.ZipFile(path) as archive:
        sink = ImageSink(archive, images_dir, f"slides_{base}")
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
            "tables": tables, "images_extracted": sink.count, "speaker_notes_slides": notes_slides,
            "images_skipped": sink.skipped}



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


def cell_value(cell, strings):
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
    return value.text


def read_sheet(archive, member, strings):
    root = parse(archive, member)
    values, formulas = {}, {}
    row_number = 0
    for row in root.iter(S + "row"):
        row_number = int(row.get("r", row_number + 1))
        column = 0
        for cell in row.findall(S + "c"):
            match = re.fullmatch(r"([A-Z]+)(\d+)", cell.get("r", ""))
            column = column_number(match.group(1)) if match else column + 1
            value = cell_value(cell, strings)
            if value != "":
                values[(row_number, column)] = value
            formula = cell.find(S + "f")
            if formula is not None and (formula.text or "").strip():
                formulas[f"{column_letters(column)}{row_number}"] = formula.text.strip()
    merges = [m.get("ref") for m in root.iter(S + "mergeCell")]
    comments = {}
    for kind, target in read_rels(archive, member).values():
        if kind.endswith("/comments") and target in archive.namelist():
            for comment in parse(archive, target).iter(S + "comment"):
                comments[comment.get("ref")] = "".join(t.text or "" for t in comment.iter(S + "t"))
    return values, formulas, merges, comments


def convert_xlsx(path, raw_dir, images_dir):
    base = safe_name(path.stem)
    sheets = []
    with zipfile.ZipFile(path) as archive:
        strings = shared_strings(archive)
        rels = read_rels(archive, "xl/workbook.xml")
        used = set()
        for sheet in parse(archive, "xl/workbook.xml").iter(S + "sheet"):
            name = sheet.get("name", "")
            target = rels.get(sheet.get(R + "id"))
            if not target:
                continue
            values, formulas, merges, comments = read_sheet(archive, target[1], strings)
            rows = max((r for r, _ in values), default=0)
            columns = max((c for _, c in values), default=0)
            stem = f"{base}_{safe_name(name)}"
            while stem in used:
                stem += "_"
            used.add(stem)
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
                notes += [f"- `{ref}`: `{text}`" for ref, text in list(formulas.items())[:FORMULA_LIMIT]]
                if len(formulas) > FORMULA_LIMIT:
                    notes.append(f"- {len(formulas) - FORMULA_LIMIT} more in the workbook")
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
                           "cols": columns, "merged_ranges": len(merges), "formulas": len(formulas),
                           "comments": len(comments)})
        sink = ImageSink(archive, images_dir, f"sheet_{base}")
        sink.copy_folder("xl/media/")
    return {"source": path.name, "type": "xlsx", "sheets": sheets, "images_extracted": sink.count,
            "images_skipped": sink.skipped}



def convert_pdf(path, raw_dir, images_dir):
    base = safe_name(path.stem)
    out = raw_dir / f"pdf_{base}.md"
    images = tables = 0
    with fitz.open(str(path)) as document:
        pages = document.page_count
        lines = [f"# PDF: {path.name}", "", f"- Pages: {pages}", ""]
        for number, page in enumerate(document, start=1):
            lines += [f"## Page {number}", ""]
            text = page.get_text("text").strip()
            if text:
                lines += [text, ""]
            if hasattr(page, "find_tables"):
                try:
                    found = page.find_tables()
                    for table in getattr(found, "tables", found):
                        rows = [["" if c is None else str(c) for c in row] for row in table.extract()]
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
                    name = f"pdf_{base}-page{number:03d}-img{images:03d}.png"
                    pixmap.save(str(images_dir / name))
                    lines += [image_line(name), ""]
                except Exception:
                    continue
    out.write_text("\n".join(lines), encoding="utf-8")
    return {"source": path.name, "type": "pdf", "output": f"raw/{out.name}", "pages": pages,
            "tables": tables, "images_extracted": images}



def copy_loose_image(path, images_dir):
    name = f"standalone-{safe_name(path.stem)}.{RASTER[path.suffix.lower().lstrip('.')]}"
    (images_dir / name).write_bytes(path.read_bytes())
    return {"source": path.name, "type": "standalone-image", "output": f"images/{name}"}


def convert_folder(input_folder, work_dir):
    raw_dir, images_dir = work_dir / "raw", work_dir / "images"
    raw_dir.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"input_folder": str(input_folder), "work_dir": str(work_dir),
                "converted_at": datetime.now().isoformat(timespec="seconds"),
                "files": [], "skipped": [], "export_requests": [], "warnings": []}
    for path in sorted(input_folder.iterdir()):
        extension = path.suffix.lower()
        if path.name.startswith(("~$", ".")):
            continue
        if path.is_dir():
            manifest["skipped"].append({"file": path.name, "reason": "folder; move its files up one level"})
            continue
        try:
            if extension == ".docx":
                manifest["files"].append(convert_docx(path, raw_dir, images_dir))
            elif extension == ".pptx":
                manifest["files"].append(convert_pptx(path, raw_dir, images_dir))
            elif extension == ".xlsx":
                manifest["files"].append(convert_xlsx(path, raw_dir, images_dir))
            elif extension == ".pdf" and HAS_PYMUPDF:
                manifest["files"].append(convert_pdf(path, raw_dir, images_dir))
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
                (raw_dir / path.name).write_bytes(path.read_bytes())
                manifest["files"].append({"source": path.name, "type": "text", "output": f"raw/{path.name}"})
            elif extension.lstrip(".") in RASTER:
                manifest["files"].append(copy_loose_image(path, images_dir))
            else:
                manifest["skipped"].append({"file": path.name, "reason": f"unsupported extension {extension}"})
        except Exception as error:
            manifest["warnings"].append({"file": path.name, "error": f"{type(error).__name__}: {error}"})
    return manifest


LOSSES = [
    "Charts, SmartArt, shapes, and vector drawings are not converted. Only raster images are copied out. "
    "If one of them carries rules or numbers, export it as a PNG into the images folder.",
    "Merged table cells are flattened. Check the merged ranges in each sheet note.",
    "Spreadsheet formulas are listed as written, and the CSV holds their last saved values. "
    "Dates appear as serial numbers.",
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
