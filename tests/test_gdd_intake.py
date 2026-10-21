import base64
import contextlib
import csv
import importlib.util
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "plugins" / "game-server" / "skills" / "gdd-intake"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "gdd"
TEMPLATE = SKILL / "references" / "design-template.md"


def load_script(name):
    path = SKILL / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


convert = load_script("convert_office")
lint_design = load_script("lint_design")
emit_json = load_script("emit_json")

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


def run_main(module, argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = module.main(argv)
    return code, out.getvalue(), err.getvalue()


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

    def test_text_files_pass_through_and_legacy_formats_are_skipped(self):
        (self.inputs / "notes.md").write_text("# Notes\n", encoding="utf-8")
        (self.inputs / "old.ppt").write_bytes(b"x")
        manifest = self.convert()
        self.assertEqual((self.work / "raw" / "notes.md").read_text(encoding="utf-8"), "# Notes\n")
        skipped = {item["file"]: item["reason"] for item in manifest["skipped"]}
        self.assertIn("pptx", skipped["old.ppt"])

    def test_pdf_without_pymupdf_asks_for_an_export(self):
        try:
            import fitz  # noqa: F401
        except ImportError:
            pass
        else:
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


def read_fixture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def issues_of(text):
    return lint_design.lint(text)


def messages(text):
    return [message for _, message in issues_of(text)]


def replace_once(text, old, new):
    assert text.count(old) == 1, f"expected one match for {old!r}, found {text.count(old)}"
    return text.replace(old, new)


def template_skeleton():
    text = TEMPLATE.read_text(encoding="utf-8")
    match = re.search(r"````markdown\n(.*?)\n````", text, re.DOTALL)
    assert match, "design-template.md has no skeleton block"
    skeleton = match.group(1) + "\n"
    skeleton = replace_once(skeleton, "Scope: <server-only, full-stack, or logic-only>", "Scope: server-only")
    return replace_once(skeleton, "- Status: open", "- Status: answered on 2026-01-05: The server day.")


class LintCleanTest(unittest.TestCase):
    def test_clean_design_has_no_issues(self):
        self.assertEqual(issues_of(read_fixture("clean-design.md")), [])

    def test_prompt_only_design_has_no_issues(self):
        self.assertEqual(issues_of(read_fixture("prompt-only-design.md")), [])

    def test_the_template_skeleton_passes(self):
        self.assertEqual(issues_of(template_skeleton()), [])

    def test_headings_inside_code_fences_are_ignored(self):
        text = replace_once(
            read_fixture("clean-design.md"),
            "## Gameplay loop\n",
            "## Gameplay loop\n\n```text\n## Fake section\n#### Q9: not a question\n```\n",
        )
        self.assertEqual(issues_of(text), [])

    def test_tbd_is_allowed_inside_open_questions(self):
        text = replace_once(
            read_fixture("clean-design.md"), "- Interim default: Server time.", "- Interim default: TBD."
        )
        self.assertEqual(issues_of(text), [])


class LintFailureTest(unittest.TestCase):
    def setUp(self):
        self.clean = read_fixture("clean-design.md")

    def assertFlags(self, text, *needles):
        found = messages(text)
        for needle in needles:
            self.assertTrue(
                any(needle in message for message in found), f"no issue mentions {needle!r}: {found}"
            )

    def remove_block(self, start, end):
        i, j = self.clean.index(start), self.clean.index(end)
        return self.clean[:i] + self.clean[j:]

    def test_missing_section(self):
        text = self.remove_block("## Timing\n", "## Edge cases\n")
        self.assertFlags(text, "Timing")

    def test_missing_title(self):
        text = replace_once(self.clean, "# Weekly challenge design\n", "")
        self.assertFlags(text, "title")

    def test_sections_out_of_order(self):
        timing_start, edge_start = self.clean.index("## Timing\n"), self.clean.index("## Edge cases\n")
        rewards_start = self.clean.index("## Rewards\n")
        rewards = self.clean[rewards_start:timing_start]
        timing = self.clean[timing_start:edge_start]
        text = self.clean[:rewards_start] + timing + rewards + self.clean[edge_start:]
        self.assertFlags(text, "order")

    def test_duplicate_section(self):
        text = replace_once(self.clean, "## Glossary\n", "## Timing\n\nNone.\n\n## Glossary\n")
        self.assertFlags(text, "Timing")

    def test_empty_section_needs_none(self):
        text = self.remove_block("| Id | Timing |", "## Edge cases\n")
        self.assertFlags(text, "None.")

    def test_table_without_rows_needs_none(self):
        text = self.remove_block("| TM1 |", "## Edge cases\n")
        self.assertFlags(text, "None.")

    def test_bad_id_format(self):
        text = replace_once(self.clean, "### R1: Points reset each week", "### R01: Points reset each week")
        self.assertFlags(text, "R01")

    def test_id_with_wrong_prefix_for_its_section(self):
        text = replace_once(self.clean, "### F1: Claimable tiers", "### R2: Claimable tiers")
        self.assertFlags(text, "R2", "Formulas")

    def test_duplicate_id_is_reported_at_the_second_use(self):
        text = replace_once(self.clean, "| RW2 | Tier 2 reward", "| RW1 | Tier 2 reward")
        line = text.splitlines().index(next(l for l in text.splitlines() if l.startswith("| RW1 | Tier 2"))) + 1
        found = [(n, m) for n, m in issues_of(text) if "RW1" in m and "duplicate" in m]
        self.assertEqual([n for n, _ in found], [line])

    def test_rule_without_source_line(self):
        text = replace_once(self.clean, "- Source: S1 slide 4.\n\n## Formulas", "\n## Formulas")
        self.assertFlags(text, "R1", "Source")

    def test_rule_without_condition(self):
        text = replace_once(self.clean, "- Condition: A new weekly window starts.\n", "")
        self.assertFlags(text, "R1", "Condition")

    def test_table_row_without_source(self):
        text = replace_once(self.clean, "| The player reaches level 8 | S1 slide 3 |", "| The player reaches level 8 |  |")
        self.assertFlags(text, "ST1", "Source")

    def test_table_row_with_wrong_cell_count(self):
        text = replace_once(self.clean, "| Once per week | S2 Tiers!A2:C2 |", "| S2 Tiers!A2:C2 |")
        self.assertFlags(text, "RW1", "cells")

    def test_unrecognised_citation(self):
        text = replace_once(self.clean, "- Source: S1 slide 4.\n\n## Formulas", "- Source: the deck.\n\n## Formulas")
        self.assertFlags(text, "citation")

    def test_citation_of_unlisted_source(self):
        text = replace_once(self.clean, "- Source: S1 slide 4.\n\n## Formulas", "- Source: S9 slide 4.\n\n## Formulas")
        self.assertFlags(text, "S9")

    def test_answer_citation_needs_an_answered_question(self):
        text = replace_once(self.clean, "- Source: answer Q2.", "- Source: answer Q1.")
        self.assertFlags(text, "Q1", "answered")

    def test_answer_citation_of_unknown_question(self):
        text = replace_once(self.clean, "- Source: answer Q2.", "- Source: answer Q8.")
        self.assertFlags(text, "Q8")

    def test_question_status_must_be_one_of_three_forms(self):
        text = replace_once(self.clean, "- Status: open", "- Status: maybe later")
        self.assertFlags(text, "Q1", "status")

    def test_skipped_status_needs_a_name_and_a_date(self):
        text = replace_once(self.clean, "- Status: skipped by Dana on 2026-03-02", "- Status: skipped")
        self.assertFlags(text, "Q3", "status")

    def test_answered_status_needs_an_answer(self):
        text = replace_once(
            self.clean,
            "- Status: answered on 2026-03-02: The claim counts if the server received it before the boundary.",
            "- Status: answered on 2026-03-02",
        )
        self.assertFlags(text, "Q2", "status")

    def test_question_without_interim_default(self):
        text = replace_once(self.clean, "- Interim default: Hide it.\n", "")
        self.assertFlags(text, "Q3", "Interim default")

    def test_question_without_source(self):
        text = replace_once(self.clean, "- Source: S1 slide 6.\n- Status: skipped", "- Status: skipped")
        self.assertFlags(text, "Q3", "Source")

    def test_question_outside_a_tier(self):
        text = replace_once(self.clean, "### Undefined terms\n\nNone.", "### Undefined terms\n\n#### Q4: Stray question\n\n- Source: prompt.\n- Status: open\n- Interim default: None.\n")
        self.assertFlags(text, "Q4")

    def test_open_questions_need_all_tiers(self):
        text = replace_once(self.clean, "### Minor\n", "### Small\n")
        self.assertFlags(text, "Minor")

    def test_forbidden_tokens_outside_open_questions(self):
        for token in ("TBD", "TODO", "FIXME"):
            with self.subTest(token=token):
                text = replace_once(self.clean, "The feature gives", f"The reward is {token}. The feature gives")
                found = [(n, m) for n, m in issues_of(text) if token in m]
                self.assertEqual(len(found), 1)
                self.assertEqual(text.splitlines()[found[0][0] - 1].count(token), 1)

    def test_scope_is_required_and_limited(self):
        self.assertFlags(replace_once(self.clean, "Scope: server-only\n", ""), "Scope")
        self.assertFlags(replace_once(self.clean, "Scope: server-only", "Scope: client-only"), "Scope")

    def test_config_section_needs_a_draft_path(self):
        text = replace_once(self.clean, "- Draft: `config/weekly-challenge.json`, relative to this file.\n", "")
        self.assertFlags(text, "weekly-challenge.json", "Draft")

    def test_config_table_needs_the_columns_that_the_emitter_reads(self):
        text = replace_once(self.clean, "| Key | Meaning | Type | Example |", "| Key | Meaning | Kind | Example |")
        self.assertFlags(text, "Type")

    def test_other_features_entry_needs_source(self):
        text = replace_once(self.clean, " Source: S1 slide 6.\n\n## States", "\n\n## States")
        self.assertFlags(text, "Source")

    def test_formula_needs_a_code_block(self):
        i = self.clean.index("```text\ninput:")
        j = self.clean.index("```\n", i + 5) + 4
        text = self.clean[:i] + self.clean[j:]
        self.assertFlags(text, "F1", "code block")


class LintCommandLineTest(TempDirCase):
    def run_lint(self, text):
        path = self.tmp / "design.md"
        path.write_text(text, encoding="utf-8")
        return subprocess.run(
            [sys.executable, str(SKILL / "scripts" / "lint_design.py"), str(path)],
            capture_output=True,
            text=True,
        )

    def test_clean_file_exits_zero(self):
        result = self.run_lint(read_fixture("clean-design.md"))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_failures_print_path_line_message_and_exit_one(self):
        text = replace_once(read_fixture("clean-design.md"), "- Condition: A new weekly window starts.\n", "")
        result = self.run_lint(text)
        self.assertEqual(result.returncode, 1)
        lines = [l for l in result.stdout.splitlines() if "Condition" in l]
        self.assertEqual(len(lines), 1)
        self.assertRegex(lines[0], r"design\.md:\d+: .*Condition")


CONFIG_DESIGN = """# Tiny design

## Sources

| Id | Input | Kind | Notes |
| --- | --- | --- | --- |
| S1 | `gdd/tiny.xlsx` | spreadsheet | sheets Tiers, Settings |

Scope: server-only

## Config tables

### `tiny.json`

- Source sheets: S1 Tiers.
- Draft: `config/tiny.json`, relative to this file.
- Shape: an object with `title`, `limits`, and a `tiers` list.

| Key | Meaning | Type | Example | Allowed values | Source |
| --- | --- | --- | --- | --- | --- |
| `title` | Panel title | string | `Weekly` | any text | prompt |
| `unlockLevel` | Level gate | integer | 8 | 1 or more | S1 Settings!B2 |
| `limits.perDay` | Claims per day | integer | 3 | 1 or more | prompt |
| `limits.ratio` | Bonus ratio | number | 1.5 | above 0 | prompt |
| `tiers[].points` | Points needed | integer | 100 | 1 or more | S1 Tiers!A2:A4 |
| `tiers[].reward` | Reward item | string | gold | known items | S1 Tiers!B2:B4 |
| `tiers[].premium` | Needs the pass | boolean | false | true or false | S1 Tiers!C2:C4 |
| `tiers[].items` | Granted items | list of item and amount | 500 gold | known items | S1 Tiers!B2:D4 |
"""


class EmitJsonTest(TempDirCase):
    def write_design(self, text=CONFIG_DESIGN):
        feature = self.tmp / "feature"
        feature.mkdir(exist_ok=True)
        path = feature / "design.md"
        path.write_text(text, encoding="utf-8")
        return path

    def write_sheets(self):
        raw = self.work / "raw"
        raw.mkdir(parents=True)
        (raw / "tiny_Tiers.csv").write_text(
            "points,reward,premium,extra\n100,gold,False,x\n250,chest,false,y\n500,gems,TRUE,z\n",
            encoding="utf-8",
        )
        (raw / "tiny_Settings.csv").write_text("Setting,Value\nunlockLevel,12\n", encoding="utf-8")
        manifest = {
            "files": [
                {
                    "source": "tiny.xlsx",
                    "type": "xlsx",
                    "sheets": [
                        {"sheet": "Tiers", "csv": "tiny_Tiers.csv"},
                        {"sheet": "Settings", "csv": "tiny_Settings.csv"},
                    ],
                }
            ]
        }
        (self.work / "conversion-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    def test_draft_uses_example_values_with_their_types(self):
        design = self.write_design()
        code, out, err = run_main(emit_json, [str(design)])
        self.assertEqual(code, 0, err)
        draft = json.loads((design.parent / "config" / "tiny.json").read_text(encoding="utf-8"))
        self.assertEqual(
            draft,
            {
                "title": "Weekly",
                "unlockLevel": 8,
                "limits": {"perDay": 3, "ratio": 1.5},
                "tiers": [{"points": 100, "reward": "gold", "premium": False, "items": "500 gold"}],
            },
        )
        self.assertIn("tiny.json", out)

    def test_single_column_sources_fill_lists_and_single_cells_fill_scalars(self):
        design = self.write_design()
        self.write_sheets()
        out_dir = self.tmp / "elsewhere"
        code, out, err = run_main(
            emit_json, [str(design), "--sheets", str(self.work), "--out-dir", str(out_dir)]
        )
        self.assertEqual(code, 0, err)
        draft = json.loads((out_dir / "config" / "tiny.json").read_text(encoding="utf-8"))
        self.assertEqual(draft["unlockLevel"], 12)
        self.assertEqual(
            [(t["points"], t["reward"], t["premium"]) for t in draft["tiers"]],
            [(100, "gold", False), (250, "chest", False), (500, "gems", True)],
        )
        self.assertEqual(draft["tiers"][0]["items"], "500 gold")
        self.assertIsNone(draft["tiers"][1]["items"])
        self.assertFalse((design.parent / "config").exists())

    def test_value_that_does_not_match_its_type_becomes_null_with_a_warning(self):
        design = self.write_design(
            CONFIG_DESIGN.replace("| integer | 3 |", "| integer | three |")
        )
        code, out, err = run_main(emit_json, [str(design)])
        self.assertEqual(code, 0)
        draft = json.loads((design.parent / "config" / "tiny.json").read_text(encoding="utf-8"))
        self.assertIsNone(draft["limits"]["perDay"])
        self.assertIn("limits.perDay", err)

    def test_design_without_config_tables_writes_nothing(self):
        design = self.write_design(read_fixture("prompt-only-design.md"))
        code, out, err = run_main(emit_json, [str(design)])
        self.assertEqual(code, 0)
        self.assertFalse((design.parent / "config").exists())

    def test_conflicting_keys_fail(self):
        text = CONFIG_DESIGN.replace(
            "| `limits.perDay` |", "| `limits` | Whole object | string | x | any | prompt |\n| `limits.perDay` |"
        )
        design = self.write_design(text)
        code, out, err = run_main(emit_json, [str(design)])
        self.assertEqual(code, 1)
        self.assertIn("limits", err)

    def test_section_without_a_draft_path_fails(self):
        design = self.write_design(CONFIG_DESIGN.replace("- Draft: `config/tiny.json`, relative to this file.\n", ""))
        code, out, err = run_main(emit_json, [str(design)])
        self.assertEqual(code, 1)
        self.assertIn("Draft", err)

    def test_missing_design_fails(self):
        code, out, err = run_main(emit_json, [str(self.tmp / "absent.md")])
        self.assertEqual(code, 1)

    def test_the_clean_fixture_emits_a_draft(self):
        design = self.write_design(read_fixture("clean-design.md"))
        code, out, err = run_main(emit_json, [str(design)])
        self.assertEqual(code, 0, err)
        draft = json.loads((design.parent / "config" / "weekly-challenge.json").read_text(encoding="utf-8"))
        self.assertEqual(draft["unlockLevel"], 8)
        self.assertEqual(draft["limits"], {"claimsPerWeek": 1})
        self.assertEqual(draft["tiers"], [{"points": 100, "reward": "gold", "premium": False}])


if __name__ == "__main__":
    unittest.main()
