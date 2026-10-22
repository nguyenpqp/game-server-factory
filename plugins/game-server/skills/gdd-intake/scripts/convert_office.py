#!/usr/bin/env python3
"""Convert the files in a GDD folder to text that an agent can read.

Usage:
    python3 convert_office.py <input_folder> <work_dir>

Reads pptx with the standard library. docx and xlsx go through `gddlib`, which needs
python-docx and openpyxl (`pip install -r requirements.txt`); without them those files
are skipped with the install command. PDF needs PyMuPDF (`pip install pymupdf`), imported
as `pymupdf` or, in older releases, `fitz`; without it the script asks for an export
instead. Files in subfolders are not read.

Output under <work_dir>:
    raw/slides_<base>.md       one file per pptx, with "## Slide <n>: <title>" headings; a
                               chart becomes "Chart: <title>" and a table of its cached
                               values, one row per category and one column per series
    raw/<name>.md              one file per docx or xlsx, named after the source file; a
                               docx keeps headings, inline styles, lists, tables, hyperlinks,
                               and images, which go to raw/assets/<slug>/; an xlsx has one
                               "## Sheet: <name>" section per sheet with its range and one
                               table, and a cell with a formula shows the formula
    raw/pdf_<base>.md          one file per pdf (PyMuPDF only), NFKC-normalized so that
                               ligatures such as U+FB01 read as "fi"
    raw/<name>                 md, txt, csv, and json files copied as they are
    images/                    raster images from pptx, xlsx, and pdf files and loose images in
                               the folder, named <kind>_<base>-...img<n> with <kind> slides,
                               sheet, or pdf, so files that share a stem keep apart; loose
                               images are standalone-<base>
    conversion-manifest.json   what was converted, skipped, and needs an export
    conversion-manifest.md     the same for a reader

docx and xlsx files convert first. When another input would write the same output name,
it gets `_` before its extension, so no output overwrites another. A docx and an xlsx that
share a name cannot both convert, so the second one is reported to be renamed.

Exit codes: 0 when the run finished (skipped files and warnings are listed in the
manifest), 1 for a bad command line or a missing input folder.
"""
import importlib.util
import json
import posixpath
import re
import shutil
import sys
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gddlib.docx import convert_docx_file
from gddlib.xlsx import convert_xlsx_file

try:
    import pymupdf as fitz  # optional and used only for .pdf
except ImportError:
    try:
        import fitz  # PyMuPDF before 1.24.3 has only this name
    except ImportError:
        fitz = None
HAS_PYMUPDF = fitz is not None
HAS_GDDLIB = all(importlib.util.find_spec(name) for name in ("docx", "openpyxl"))

RASTER = {"png": "png", "jpg": "jpg", "jpeg": "jpg", "gif": "gif", "bmp": "bmp",
          "tif": "tiff", "tiff": "tiff", "webp": "webp"}
TEXT_EXTENSIONS = (".md", ".txt", ".csv", ".json")
OFFICE = (".docx", ".xlsx")
LEGACY = {".doc": ".docx", ".ppt": ".pptx", ".xls": ".xlsx"}

A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
C = "{http://schemas.openxmlformats.org/drawingml/2006/chart}"
PKG = "{http://schemas.openxmlformats.org/package/2006/relationships}"

def safe_name(name):
    return "".join(c if c.isalnum() or c in "._-" else "_" for c in name)


def claim(used, stem, *suffixes):
    while any((stem + suffix).lower() in used for suffix in suffixes):
        stem += "_"
    used.update((stem + suffix).lower() for suffix in suffixes)
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


def number_text(text):
    if re.fullmatch(r"-?\d+", text):
        return text
    try:
        number = float(text)
    except ValueError:
        return text
    return str(int(number)) if number.is_integer() else repr(number)


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


def convert_office_file(path, raw_dir, images_dir, used):
    source = path.resolve()
    name = source.stem + ".md"
    if name.lower() in used:
        raise ValueError(f"raw/{name} is taken by another input with the same name; rename one of them")
    if source.suffix.lower() == ".docx":
        result = convert_docx_file(source.parent, source.name, raw_dir)
        details = result.details
        entry = {"type": "docx", "paragraphs": details["paragraphs"], "tables": details["tables"],
                 "hyperlinks": details["hyperlinks"], "image_occurrences": details["image_occurrences"],
                 "images_extracted": details["unique_media"]}
    else:
        result = convert_xlsx_file(source.parent, source.name, raw_dir)
        with zipfile.ZipFile(source) as archive:
            sink = ImageSink(archive, images_dir, f"sheet_{safe_name(source.stem)}", used)
            sink.copy_folder("xl/media/")
        sheets = [{"sheet": s["name"], "range": s["range"], "formulas": s["formulas"],
                   "merged_ranges": len(s["merged_ranges"])} for s in result.details["sheets"]]
        entry = {"type": "xlsx", "sheets": sheets, "images_extracted": sink.count,
                 "images_skipped": sink.skipped}
    used.add(name.lower())
    return {"source": path.name, "output": f"raw/{result.output}", **entry}


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
    for path in sorted(input_folder.iterdir(), key=lambda p: (p.suffix.lower() not in OFFICE, p.name)):
        extension = path.suffix.lower()
        if path.name.startswith(("~$", ".")):
            continue
        if path.is_dir():
            manifest["skipped"].append({"file": path.name, "reason": "folder; move its files up one level"})
            continue
        try:
            if extension in OFFICE and HAS_GDDLIB:
                manifest["files"].append(convert_office_file(path, raw_dir, images_dir, used))
            elif extension in OFFICE:
                manifest["skipped"].append({
                    "file": path.name,
                    "reason": "python-docx or openpyxl is not installed; run "
                              "`python3 -m pip install python-docx openpyxl` and run again",
                })
            elif extension == ".pptx":
                manifest["files"].append(convert_pptx(path, raw_dir, images_dir, used))
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
    "docx comments, headers, and footers are not converted.",
    "A merged sheet range repeats its label in each of its cells, and the sheet lists the range. "
    "A sheet cell with a formula shows the formula, not its last saved value. "
    "A date cell shows as `2026-01-05 00:00:00`, and a duration cell of 36 hours as `1 day, 12:00:00`.",
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
                lines += [f"  - `{s['sheet']}`: range `{s['range']}`, {s['merged_ranges']} merged ranges, "
                          f"{s['formulas']} formulas" for s in value]
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
