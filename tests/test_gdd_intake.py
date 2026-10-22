import base64
import csv
import json
import re
import shutil
import tempfile
import types
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from helpers import load_script, run_main

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "plugins" / "game-server" / "skills" / "gdd-intake"


convert = load_script(SKILL / "scripts" / "convert_office.py")

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
P = "http://schemas.openxmlformats.org/presentationml/2006/main"
S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
XML = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'


def write_zip(path, members):
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in members.items():
            archive.writestr(name, data)


def rels(*items):
    body = "".join(
        f'<Relationship Id="{rid}" Type="{kind}" Target="{target}"/>' for rid, kind, target in items
    )
    return f'{XML}<Relationships xmlns="{PKG_REL}">{body}</Relationships>'


class TempDirCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.inputs = self.tmp / "in"
        self.work = self.tmp / "work"
        self.inputs.mkdir()


def make_docx(path):
    def para(text, style=None, extra=""):
        props = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
        return f"<w:p>{props}<w:r><w:t>{text}</w:t></w:r>{extra}</w:p>"

    def cell(text):
        return f"<w:tc>{para(text)}</w:tc>"

    picture = (
        f'<w:p><w:r><w:drawing><a:graphic xmlns:a="{A}"><a:graphicData>'
        f'<a:blip xmlns:r="{R}" r:embed="rId9"/></a:graphicData></a:graphic></w:drawing></w:r></w:p>'
    )
    bullet = (
        '<w:p><w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr></w:pPr>'
        "<w:r><w:t>Claim once per day</w:t></w:r></w:p>"
    )
    body = (
        para("Weekly challenge", "Title")
        + para("Rewards", "Heading1")
        + para("Day one gives 500 gold.")
        + para("Tiers", "Heading2")
        + bullet
        + f"<w:tbl><w:tr>{cell('Day')}{cell('Gold | coins')}</w:tr><w:tr>{cell('1')}{cell('500')}</w:tr></w:tbl>"
        + picture
    )
    styles = (
        f'{XML}<w:styles xmlns:w="{W}">'
        '<w:style w:styleId="Title"><w:name w:val="Title"/></w:style>'
        '<w:style w:styleId="Heading1"><w:name w:val="heading 1"/></w:style>'
        '<w:style w:styleId="Heading2"><w:name w:val="heading 2"/></w:style></w:styles>'
    )
    write_zip(
        path,
        {
            "[Content_Types].xml": f"{XML}<Types/>",
            "word/document.xml": f'{XML}<w:document xmlns:w="{W}"><w:body>{body}</w:body></w:document>',
            "word/styles.xml": styles,
            "word/_rels/document.xml.rels": rels(
                ("rId9", f"{R}/image", "media/image1.png"),
            ),
            "word/media/image1.png": PNG,
        },
    )


def make_pptx(path):
    def shape(text, placeholder=None):
        ph = f'<p:nvPr><p:ph type="{placeholder}"/></p:nvPr>' if placeholder else "<p:nvPr/>"
        return (
            f'<p:sp><p:nvSpPr><p:cNvPr id="1" name="s"/><p:cNvSpPr/>{ph}</p:nvSpPr>'
            f"<p:txBody><a:bodyPr/><a:p><a:r><a:t>{text}</a:t></a:r></a:p></p:txBody></p:sp>"
        )

    def slide(*shapes):
        return (
            f'{XML}<p:sld xmlns:p="{P}" xmlns:a="{A}" xmlns:r="{R}"><p:cSld><p:spTree>'
            + "".join(shapes)
            + "</p:spTree></p:cSld></p:sld>"
        )

    table = (
        "<p:graphicFrame><a:graphic><a:graphicData><a:tbl>"
        "<a:tr><a:tc><a:txBody><a:p><a:r><a:t>Tier</a:t></a:r></a:p></a:txBody></a:tc>"
        "<a:tc><a:txBody><a:p><a:r><a:t>Points</a:t></a:r></a:p></a:txBody></a:tc></a:tr>"
        "<a:tr><a:tc><a:txBody><a:p><a:r><a:t>1</a:t></a:r></a:p></a:txBody></a:tc>"
        "<a:tc><a:txBody><a:p><a:r><a:t>100</a:t></a:r></a:p></a:txBody></a:tc></a:tr>"
        "</a:tbl></a:graphicData></a:graphic></p:graphicFrame>"
    )
    picture = '<p:pic><p:blipFill><a:blip r:embed="rId7"/></p:blipFill></p:pic>'
    notes = (
        f'{XML}<p:notes xmlns:p="{P}" xmlns:a="{A}"><p:cSld><p:spTree>'
        + shape("1", "sldNum")
        + shape("Say the points slowly.", "body")
        + "</p:spTree></p:cSld></p:notes>"
    )
    presentation = (
        f'{XML}<p:presentation xmlns:p="{P}" xmlns:r="{R}"><p:sldIdLst>'
        '<p:sldId id="256" r:id="rId1"/><p:sldId id="257" r:id="rId2"/></p:sldIdLst></p:presentation>'
    )
    write_zip(
        path,
        {
            "[Content_Types].xml": f"{XML}<Types/>",
            "ppt/presentation.xml": presentation,
            "ppt/_rels/presentation.xml.rels": rels(
                ("rId1", f"{R}/slide", "slides/slide2.xml"),
                ("rId2", f"{R}/slide", "slides/slide1.xml"),
            ),
            "ppt/slides/slide2.xml": slide(shape("Introduction", "title"), shape("Earn points daily.")),
            "ppt/slides/slide1.xml": slide(shape("Rewards", "ctrTitle"), table, picture),
            "ppt/slides/_rels/slide1.xml.rels": rels(
                ("rId7", f"{R}/image", "../media/image1.png"),
                ("rId8", f"{R}/notesSlide", "../notesSlides/notesSlide1.xml"),
            ),
            "ppt/notesSlides/notesSlide1.xml": notes,
            "ppt/media/image1.png": PNG,
        },
    )


def make_xlsx(path):
    shared = (
        f'{XML}<sst xmlns="{S}"><si><r><t>Da</t></r><r><t>y</t></r></si><si><t>Gold</t></si>'
        "<si><t>Setting</t></si><si><t>Value</t></si><si><t>unlockLevel</t></si></sst>"
    )
    rewards = (
        f'{XML}<worksheet xmlns="{S}" xmlns:r="{R}"><sheetData>'
        '<row r="2"><c r="A2" t="s"><v>0</v></c><c r="C2" t="s"><v>1</v></c></row>'
        '<row r="3"><c r="A3"><v>1</v></c><c r="C3"><v>500</v></c><c r="D3"><f>C3*2</f><v>1000</v></c></row>'
        '<row r="4"><c r="A4"><v>2</v></c><c r="C4" t="inlineStr"><is><t>1 rare chest</t></is></c>'
        '<c r="E4" t="b"><v>1</v></c></row>'
        '</sheetData><mergeCells><mergeCell ref="A5:B5"/></mergeCells>'
        '<legacyDrawing r:id="rId1"/></worksheet>'
    )
    settings = (
        f'{XML}<worksheet xmlns="{S}"><sheetData>'
        '<row r="1"><c r="A1" t="s"><v>2</v></c><c r="B1" t="s"><v>3</v></c></row>'
        '<row r="2"><c r="A2" t="s"><v>4</v></c><c r="B2"><v>8</v></c></row>'
        "</sheetData></worksheet>"
    )
    comments = (
        f'{XML}<comments xmlns="{S}"><commentList><comment ref="C3"><text><r><t>Tuned by design</t></r></text>'
        "</comment></commentList></comments>"
    )
    workbook = (
        f'{XML}<workbook xmlns="{S}" xmlns:r="{R}"><sheets>'
        '<sheet name="Rewards" sheetId="1" r:id="rId1"/><sheet name="Settings" sheetId="2" r:id="rId2"/>'
        "</sheets></workbook>"
    )
    write_zip(
        path,
        {
            "[Content_Types].xml": f"{XML}<Types/>",
            "xl/workbook.xml": workbook,
            "xl/_rels/workbook.xml.rels": rels(
                ("rId1", f"{R}/worksheet", "worksheets/sheet1.xml"),
                ("rId2", f"{R}/worksheet", "worksheets/sheet2.xml"),
                ("rId3", f"{R}/sharedStrings", "sharedStrings.xml"),
            ),
            "xl/sharedStrings.xml": shared,
            "xl/worksheets/sheet1.xml": rewards,
            "xl/worksheets/_rels/sheet1.xml.rels": rels(("rId1", f"{R}/comments", "../comments1.xml")),
            "xl/comments1.xml": comments,
            "xl/worksheets/sheet2.xml": settings,
            "xl/media/image1.png": PNG,
        },
    )


def make_sheet_xlsx(path, rows, styles=None, workbook_pr="", sheet="Data"):
    members = {
        "[Content_Types].xml": f"{XML}<Types/>",
        "xl/workbook.xml": f'{XML}<workbook xmlns="{S}" xmlns:r="{R}">{workbook_pr}<sheets>'
        f'<sheet name="{sheet}" sheetId="1" r:id="rId1"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels": rels(
            ("rId1", f"{R}/worksheet", "worksheets/sheet1.xml"),
            ("rId2", f"{R}/styles", "styles.xml"),
        ),
        "xl/worksheets/sheet1.xml": f'{XML}<worksheet xmlns="{S}"><sheetData>{rows}</sheetData></worksheet>',
    }
    if styles is not None:
        members["xl/styles.xml"] = f'{XML}<styleSheet xmlns="{S}">{styles}</styleSheet>'
    write_zip(path, members)


def make_one_sheet_xlsx(path, sheet, value):
    make_sheet_xlsx(path, f'<row r="1"><c r="A1" t="inlineStr"><is><t>{value}</t></is></c></row>', sheet=sheet)


C = "http://schemas.openxmlformats.org/drawingml/2006/chart"


def make_docx_with_parts(path):
    def para(text):
        return f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>"

    def part(tag, text):
        return f'{XML}<w:{tag} xmlns:w="{W}">{para(text)}</w:{tag}>'

    inner = f"<w:tbl><w:tr><w:tc>{para('Inner A')}</w:tc><w:tc>{para('Inner B')}</w:tc></w:tr></w:tbl>"
    body = (
        "<w:p><w:r><w:t>Before </w:t></w:r><w:commentRangeStart w:id=\"7\"/>"
        "<w:r><w:t>the reset hour</w:t></w:r><w:commentRangeEnd w:id=\"7\"/>"
        '<w:r><w:commentReference w:id="7"/></w:r></w:p>'
        f"<w:tbl><w:tr><w:tc>{para('Outer')}</w:tc><w:tc>{para('Has a table')}{inner}</w:tc></w:tr></w:tbl>"
    )
    comments = (
        f'{XML}<w:comments xmlns:w="{W}"><w:comment w:id="7" w:author="Dana">'
        f"{para('Use server time.')}</w:comment></w:comments>"
    )
    write_zip(
        path,
        {
            "[Content_Types].xml": f"{XML}<Types/>",
            "word/document.xml": f'{XML}<w:document xmlns:w="{W}"><w:body>{body}</w:body></w:document>',
            "word/_rels/document.xml.rels": rels(
                ("rId1", f"{R}/header", "header1.xml"),
                ("rId2", f"{R}/header", "header2.xml"),
                ("rId3", f"{R}/footer", "footer1.xml"),
                ("rId4", f"{R}/comments", "comments.xml"),
            ),
            "word/header1.xml": part("hdr", "Design draft"),
            "word/header2.xml": part("hdr", "Design draft"),
            "word/footer1.xml": part("ftr", "Page 1"),
            "word/comments.xml": comments,
        },
    )


def make_pptx_with_chart(path):
    def slide(title, extra=""):
        return (
            f'{XML}<p:sld xmlns:p="{P}" xmlns:a="{A}" xmlns:r="{R}"><p:cSld><p:spTree>'
            f'<p:sp><p:nvSpPr><p:cNvPr id="1" name="t"/><p:cNvSpPr/><p:nvPr><p:ph type="title"/></p:nvPr></p:nvSpPr>'
            f"<p:txBody><a:bodyPr/><a:p><a:r><a:t>{title}</a:t></a:r></a:p></p:txBody></p:sp>{extra}"
            "</p:spTree></p:cSld></p:sld>"
        )

    frame = (
        f'<p:graphicFrame><a:graphic><a:graphicData uri="{C}">'
        f'<c:chart xmlns:c="{C}" r:id="rId3"/></a:graphicData></a:graphic></p:graphicFrame>'
    )

    def series(name, values):
        points = "".join(f'<c:pt idx="{i}"><c:v>{v}</c:v></c:pt>' for i, v in enumerate(values))
        categories = "".join(f'<c:pt idx="{i}"><c:v>Week {i + 1}</c:v></c:pt>' for i in range(len(values)))
        return (
            f"<c:ser><c:tx><c:strRef><c:strCache><c:pt idx=\"0\"><c:v>{name}</c:v></c:pt></c:strCache></c:strRef></c:tx>"
            f"<c:cat><c:strRef><c:strCache>{categories}</c:strCache></c:strRef></c:cat>"
            f"<c:val><c:numRef><c:numCache>{points}</c:numCache></c:numRef></c:val></c:ser>"
        )

    chart = (
        f'{XML}<c:chartSpace xmlns:c="{C}" xmlns:a="{A}"><c:chart>'
        "<c:title><c:tx><c:rich><a:p><a:r><a:t>Weekly players</a:t></a:r></a:p></c:rich></c:tx></c:title>"
        "<c:plotArea><c:barChart>"
        + series("Free", ["120", "0.28999999999999998"])
        + series("Paid", ["30", "45"])
        + "</c:barChart></c:plotArea></c:chart></c:chartSpace>"
    )
    presentation = (
        f'{XML}<p:presentation xmlns:p="{P}" xmlns:r="{R}"><p:sldIdLst>'
        '<p:sldId id="256" r:id="rId1"/><p:sldId id="257" r:id="rId2"/></p:sldIdLst></p:presentation>'
    )
    write_zip(
        path,
        {
            "[Content_Types].xml": f"{XML}<Types/>",
            "ppt/presentation.xml": presentation,
            "ppt/_rels/presentation.xml.rels": rels(
                ("rId1", f"{R}/slide", "slides/slide1.xml"),
                ("rId2", f"{R}/slide", "slides/slide2.xml"),
            ),
            "ppt/slides/slide1.xml": slide("Players", frame),
            "ppt/slides/_rels/slide1.xml.rels": rels(("rId3", f"{R}/chart", "../charts/chart1.xml")),
            "ppt/charts/chart1.xml": chart,
            "ppt/slides/slide2.xml": slide("Next"),
        },
    )


class ConvertTest(TempDirCase):
    def convert(self):
        code, out, err = run_main(convert, [str(self.inputs), str(self.work)])
        self.assertEqual(code, 0, err)
        return json.loads((self.work / "conversion-manifest.json").read_text(encoding="utf-8"))

    def test_docx_keeps_headings_lists_tables_and_images(self):
        make_docx(self.inputs / "challenge.docx")
        manifest = self.convert()
        text = (self.work / "raw" / "doc_challenge.md").read_text(encoding="utf-8")
        self.assertIn("# Weekly challenge", text)
        self.assertIn("\n## Rewards\n", text)
        self.assertIn("\n### Tiers\n", text)
        self.assertIn("Day one gives 500 gold.", text)
        self.assertIn("- Claim once per day", text)
        self.assertIn("| Day | Gold \\| coins |", text)
        self.assertIn("| 1 | 500 |", text)
        images = list((self.work / "images").iterdir())
        self.assertEqual([p.read_bytes() for p in images], [PNG])
        self.assertIn(f"](../images/{images[0].name})", text)
        self.assertEqual(manifest["files"][0]["type"], "docx")

    def test_pptx_follows_deck_order_and_keeps_tables_notes_and_pictures(self):
        make_pptx(self.inputs / "deck.pptx")
        self.convert()
        text = (self.work / "raw" / "slides_deck.md").read_text(encoding="utf-8")
        first = text.index("## Slide 1: Introduction")
        second = text.index("## Slide 2: Rewards")
        self.assertLess(first, second)
        self.assertIn("Earn points daily.", text)
        self.assertIn("| Tier | Points |", text)
        self.assertIn("| 1 | 100 |", text)
        self.assertIn("Say the points slowly.", text[second:])
        self.assertNotIn("Say the points slowly.", text[:second])
        self.assertEqual([p.read_bytes() for p in (self.work / "images").iterdir()], [PNG])

    def test_xlsx_keeps_cell_positions_formulas_merges_and_comments(self):
        make_xlsx(self.inputs / "balance.xlsx")
        manifest = self.convert()
        with (self.work / "raw" / "balance_Rewards.csv").open(newline="", encoding="utf-8") as handle:
            rows = list(csv.reader(handle))
        self.assertEqual(rows[0], [""] * 5)
        self.assertEqual(rows[1], ["Day", "", "Gold", "", ""])
        self.assertEqual(rows[2], ["1", "", "500", "1000", ""])
        self.assertEqual(rows[3], ["2", "", "1 rare chest", "", "TRUE"])
        with (self.work / "raw" / "balance_Settings.csv").open(newline="", encoding="utf-8") as handle:
            settings = list(csv.reader(handle))
        self.assertEqual(settings[1], ["unlockLevel", "8"])
        notes = (self.work / "raw" / "balance_Rewards.md").read_text(encoding="utf-8")
        self.assertIn("`D3`: `C3*2`", notes)
        self.assertIn("`A5:B5`", notes)
        self.assertIn("`C3`: Tuned by design", notes)
        self.assertIn("| 3 | 1 |", notes)
        entry = manifest["files"][0]
        self.assertEqual([s["sheet"] for s in entry["sheets"]], ["Rewards", "Settings"])
        self.assertEqual(entry["sheets"][0]["csv"], "balance_Rewards.csv")
        self.assertEqual([p.read_bytes() for p in (self.work / "images").iterdir()], [PNG])

    def test_images_from_inputs_with_the_same_stem_do_not_collide(self):
        make_docx(self.inputs / "challenge.docx")
        make_xlsx(self.inputs / "challenge.xlsx")
        make_pptx(self.inputs / "challenge.pptx")
        manifest = self.convert()
        images = sorted(p.name for p in (self.work / "images").iterdir())
        self.assertEqual(len(images), 3, images)
        self.assertEqual(sum(f["images_extracted"] for f in manifest["files"]), 3)
        for name in ("doc_challenge.md", "slides_challenge.md"):
            text = (self.work / "raw" / name).read_text(encoding="utf-8")
            linked = re.findall(r"\]\(\.\./images/([^)]+)\)", text)
            self.assertEqual(len(linked), 1, text)
            self.assertIn(linked[0], images)

    def test_loose_images_that_share_a_stem_get_their_own_names(self):
        (self.inputs / "a.jpeg").write_bytes(b"jpeg bytes")
        (self.inputs / "a.jpg").write_bytes(b"jpg bytes")
        manifest = self.convert()
        outputs = {f["source"]: f["output"] for f in manifest["files"]}
        self.assertEqual(outputs, {"a.jpeg": "images/standalone-a.jpg", "a.jpg": "images/standalone-a_.jpg"})
        for source, output in outputs.items():
            self.assertEqual((self.work / output).read_bytes(), (self.inputs / source).read_bytes())

    def test_sheets_whose_names_join_to_the_same_stem_get_their_own_files(self):
        make_one_sheet_xlsx(self.inputs / "a.xlsx", "b_c", "from a")
        make_one_sheet_xlsx(self.inputs / "a_b.xlsx", "c", "from a_b")
        manifest = self.convert()
        csvs = {f["source"]: (f["sheets"][0]["csv"], f["sheets"][0]["md"]) for f in manifest["files"]}
        self.assertEqual(csvs, {"a.xlsx": ("a_b_c.csv", "a_b_c.md"), "a_b.xlsx": ("a_b_c_.csv", "a_b_c_.md")})
        self.assertEqual((self.work / "raw" / "a_b_c.csv").read_text(encoding="utf-8"), "from a\n")
        self.assertEqual((self.work / "raw" / "a_b_c_.csv").read_text(encoding="utf-8"), "from a_b\n")
        self.assertIn("(file: a_b.xlsx)", (self.work / "raw" / "a_b_c_.md").read_text(encoding="utf-8"))

    def test_a_copied_text_file_does_not_overwrite_a_sheet_csv(self):
        make_one_sheet_xlsx(self.inputs / "a.xlsx", "b", "sheet value")
        (self.inputs / "a_b.csv").write_text("text,file\n", encoding="utf-8")
        manifest = self.convert()
        by_source = {f["source"]: f for f in manifest["files"]}
        self.assertEqual(by_source["a.xlsx"]["sheets"][0]["csv"], "a_b.csv")
        self.assertEqual(by_source["a_b.csv"]["output"], "raw/a_b_.csv")
        self.assertEqual((self.work / "raw" / "a_b.csv").read_text(encoding="utf-8"), "sheet value\n")
        self.assertEqual((self.work / "raw" / "a_b_.csv").read_text(encoding="utf-8"), "text,file\n")

    def test_text_files_pass_through_and_legacy_formats_are_skipped(self):
        (self.inputs / "notes.md").write_text("# Notes\n", encoding="utf-8")
        (self.inputs / "old.ppt").write_bytes(b"x")
        manifest = self.convert()
        self.assertEqual((self.work / "raw" / "notes.md").read_text(encoding="utf-8"), "# Notes\n")
        skipped = {item["file"]: item["reason"] for item in manifest["skipped"]}
        self.assertIn("pptx", skipped["old.ppt"])

    def test_pdf_without_pymupdf_asks_for_an_export(self):
        if convert.HAS_PYMUPDF:
            self.skipTest("PyMuPDF is installed")
        (self.inputs / "spec.pdf").write_bytes(b"%PDF-1.4\n")
        code, out, err = run_main(convert, [str(self.inputs), str(self.work)])
        self.assertEqual(code, 0)
        manifest = json.loads((self.work / "conversion-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual([r["file"] for r in manifest["export_requests"]], ["spec.pdf"])
        self.assertIn("spec.pdf", out)
        self.assertIn("docx or Markdown", out)
        self.assertEqual(manifest["files"], [])

    def test_a_broken_file_is_reported_without_stopping_the_rest(self):
        (self.inputs / "broken.docx").write_bytes(b"not a zip")
        (self.inputs / "notes.txt").write_text("hello", encoding="utf-8")
        manifest = self.convert()
        self.assertEqual([w["file"] for w in manifest["warnings"]], ["broken.docx"])
        self.assertTrue((self.work / "raw" / "notes.txt").exists())

    def test_missing_input_folder_fails(self):
        code, _, _ = run_main(convert, [str(self.tmp / "absent"), str(self.work)])
        self.assertEqual(code, 1)

    def read_csv(self, name):
        with (self.work / "raw" / name).open(newline="", encoding="utf-8") as handle:
            return list(csv.reader(handle))

    def test_docx_lists_headers_footers_once_and_comments_with_their_anchor(self):
        make_docx_with_parts(self.inputs / "spec.docx")
        self.convert()
        text = (self.work / "raw" / "doc_spec.md").read_text(encoding="utf-8")
        headers = text.split("## Headers and footers\n", 1)[1].split("\n## ", 1)[0]
        self.assertEqual(headers.count("Design draft"), 1, headers)
        self.assertIn("Page 1", headers)
        comments = text.split("## Comments\n", 1)[1]
        self.assertIn('"the reset hour"', comments)
        self.assertIn("Use server time.", comments)
        self.assertNotIn("Design draft", text.split("## Headers and footers")[0])

    def test_docx_nested_table_stays_a_table_of_its_own(self):
        make_docx_with_parts(self.inputs / "spec.docx")
        self.convert()
        text = (self.work / "raw" / "doc_spec.md").read_text(encoding="utf-8")
        outer = next(line for line in text.splitlines() if line.startswith("| Outer |"))
        self.assertNotIn("Inner A", outer)
        self.assertIn("| Inner A | Inner B |", text)
        self.assertLess(text.index(outer), text.index("| Inner A | Inner B |"))

    def test_pptx_chart_title_categories_and_series_land_under_their_slide(self):
        make_pptx_with_chart(self.inputs / "deck.pptx")
        self.convert()
        text = (self.work / "raw" / "slides_deck.md").read_text(encoding="utf-8")
        slide = text.split("## Slide 1: Players", 1)[1].split("## Slide 2", 1)[0]
        self.assertIn("Weekly players", slide)
        self.assertIn("| Category | Free | Paid |", slide)
        self.assertIn("| Week 1 | 120 | 30 |", slide)
        self.assertIn("| Week 2 | 0.29 | 45 |", slide)

    def test_xlsx_shared_formula_block_is_listed_once_relative_to_its_first_cell(self):
        rows = "".join(
            f'<row r="{r}"><c r="C{r}"><v>{r}</v></c><c r="D{r}">'
            + ('<f t="shared" ref="D3:D147" si="0">C3*$B$1</f>'
               if r == 3 else '<f t="shared" si="0"/>')
            + f"<v>{r * 2}</v></c></row>"
            for r in range(3, 148)
        )
        make_sheet_xlsx(self.inputs / "book.xlsx", rows)
        manifest = self.convert()
        notes = (self.work / "raw" / "book_Data.md").read_text(encoding="utf-8")
        self.assertIn("`D3:D147`: `C3*$B$1`", notes)
        self.assertNotIn("more in the workbook", notes)
        self.assertEqual(manifest["files"][0]["sheets"][0]["formulas"], 145)
        self.assertEqual(self.read_csv("book_Data.csv")[4], ["", "", "5", "10"])

    def test_xlsx_shared_formula_cells_outside_a_full_block_get_shifted_text(self):
        rows = (
            '<row r="3"><c r="E3"><f t="shared" ref="E3:G4" si="4">E2+$E2+E$2+Other!E2+SUM(E2:E3)+LOG10(E2)&amp;"E2"</f><v>1</v></c>'
            '<c r="F3"><f t="shared" si="4"/><v>1</v></c><c r="G3"><f>1+1</f><v>2</v></c></row>'
            '<row r="4"><c r="F4"><f t="shared" si="4"/><v>1</v></c></row>'
        )
        make_sheet_xlsx(self.inputs / "book.xlsx", rows)
        self.convert()
        notes = (self.work / "raw" / "book_Data.md").read_text(encoding="utf-8")
        self.assertIn('`E3`: `E2+$E2+E$2+Other!E2+SUM(E2:E3)+LOG10(E2)&"E2"`', notes)
        self.assertIn('`F3`: `F2+$E2+F$2+Other!F2+SUM(F2:F3)+LOG10(F2)&"E2"`', notes)
        self.assertIn('`F4`: `F3+$E3+F$2+Other!F3+SUM(F3:F4)+LOG10(F3)&"E2"`', notes)
        self.assertIn("`G3`: `1+1`", notes)

    def test_xlsx_numbers_are_written_in_their_shortest_form(self):
        rows = (
            '<row r="1"><c r="A1"><v>1.4279999999999999</v></c><c r="B1"><v>0.28999999999999998</v></c>'
            '<c r="C1"><v>1000</v></c><c r="D1"><v>1E+3</v></c><c r="E1" t="n"><v>-2.5</v></c>'
            '<c r="F1" t="str"><f>"0.10"</f><v>0.10</v></c><c r="G1" t="e"><v>#DIV/0!</v></c></row>'
        )
        make_sheet_xlsx(self.inputs / "book.xlsx", rows)
        self.convert()
        self.assertEqual(self.read_csv("book_Data.csv")[0], ["1.428", "0.29", "1000", "1000", "-2.5", "0.10", "#DIV/0!"])

    DATE_STYLES = (
        '<numFmts><numFmt numFmtId="164" formatCode="yyyy-mm-dd hh:mm"/>'
        '<numFmt numFmtId="165" formatCode="0 &quot;days&quot;"/>'
        '<numFmt numFmtId="166" formatCode="[h]:mm:ss"/><numFmt numFmtId="167" formatCode="[Red]0.00"/></numFmts>'
        '<cellXfs><xf numFmtId="0"/><xf numFmtId="14"/><xf numFmtId="164"/><xf numFmtId="165"/>'
        '<xf numFmtId="20"/><xf numFmtId="166"/><xf numFmtId="167"/></cellXfs>'
    )

    def test_xlsx_dates_are_iso_with_the_1900_leap_year_bug(self):
        cells = [("1", "45000"), ("1", "59"), ("1", "60"), ("1", "61"), ("2", "45000.5"), ("3", "5"),
                 ("4", "0.75"), ("5", "1.5"), ("6", "3"), ("0", "45000")]
        rows = "".join(f'<row r="{n}"><c r="A{n}" s="{s}"><v>{v}</v></c></row>' for n, (s, v) in enumerate(cells, 1))
        make_sheet_xlsx(self.inputs / "book.xlsx", rows, self.DATE_STYLES)
        self.convert()
        self.assertEqual([row[0] for row in self.read_csv("book_Data.csv")], [
            "2023-03-15", "1900-02-28", "1900-02-29", "1900-03-01", "2023-03-15T12:00:00", "5",
            "18:00:00", "36:00:00", "3", "45000",
        ])

    def test_xlsx_dates_follow_the_1904_date_system(self):
        rows = '<row r="1"><c r="A1" s="1"><v>43538</v></c><c r="B1" s="2"><v>1.5</v></c></row>'
        make_sheet_xlsx(self.inputs / "book.xlsx", rows, self.DATE_STYLES, '<workbookPr date1904="1"/>')
        self.convert()
        self.assertEqual(self.read_csv("book_Data.csv")[0], ["2023-03-15", "1904-01-02T12:00:00"])

    def test_pdf_text_is_nfkc_normalized(self):
        class Page:
            def get_text(self, kind):
                return "Proﬁt per ﬁsh"

            def get_images(self, full):
                return []

        class Document:
            page_count = 1

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def __iter__(self):
                return iter([Page()])

        fake = types.SimpleNamespace(open=lambda path: Document())
        (self.inputs / "spec.pdf").write_bytes(b"%PDF-1.4\n")
        with mock.patch.multiple(convert, fitz=fake, HAS_PYMUPDF=True):
            self.convert()
        text = (self.work / "raw" / "pdf_spec.md").read_text(encoding="utf-8")
        self.assertIn("Profit per fish", text)


if __name__ == "__main__":
    unittest.main()
