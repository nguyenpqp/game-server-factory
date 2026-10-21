#!/usr/bin/env python3
"""Check a design.md against the conventions in references/design-template.md.

Usage:
    python3 lint_design.py <design.md>...

Prints `path:line: message` for each problem and exits 1 if there is any.

Checks:
  - the title and the sixteen `##` sections, once each and in order
  - `None.` under every empty section, and no table without rows
  - requirement ids: format, one prefix per section, never repeated
  - a `Source:` citation on every requirement, in one of the allowed formats,
    naming a source that the Sources table lists
  - the fields that each rule, formula, edge case, and open question must carry
  - open question status: open, skipped by <name> on <date>, or answered on <date>: <answer>
  - the columns and the Draft path that emit_json.py reads in each config table
  - TBD, TODO, and FIXME outside the Open questions section

Glossary coverage is left to the self-reviewer prompt, because a regex check for it
reported mostly false positives.
"""
import re
import sys
from pathlib import Path

SECTIONS = [
    "Sources", "Overview", "Gameplay loop", "Parts", "Worked example", "Other features", "States",
    "Rules", "Formulas", "Rewards", "Timing", "Edge cases", "Config tables", "UI touchpoints",
    "Glossary", "Open questions",
]
TIERS = ["Blocker", "Important", "Minor"]
QUESTION_PARTS = TIERS + ["Undefined terms"]
SCOPES = ("server-only", "full-stack", "logic-only")
TABLE_SECTIONS = {"States": "ST", "Rewards": "RW", "Timing": "TM", "UI touchpoints": "UI"}
HEADING_SECTIONS = {
    "Rules": ("R", ["Description", "Condition", "Effect", "Edge cases", "Example", "Source"]),
    "Formulas": ("F", ["Edge cases", "Example", "Source"]),
    "Edge cases": ("EC", ["Scenario", "Handling", "Source"]),
}
CONFIG_COLUMNS = ["Key", "Type", "Example", "Source"]
FORBIDDEN = re.compile(r"\b(TBD|TODO|FIXME)\b")
STATUS = re.compile(
    r"open|skipped by .+ on \d{4}-\d{2}-\d{2}|answered on \d{4}-\d{2}-\d{2}: \S.*", re.DOTALL)
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
FIELD = re.compile(r"^- ([A-Za-z][A-Za-z ]*?):\s*(.*)$")
SPLIT_CITATIONS = re.compile(r"\s*;\s*|\s*,\s*(?=(?:S\d+\b|prompt\b|answer Q\d))")
SOURCE_TOKEN = re.compile(r"\bS\d+\b|\bprompt\b|\banswer Q\d+\b")
SHEET_RANGE = re.compile(r".+!\$?[A-Z]+\$?\d+(?::\$?[A-Z]+\$?\d+)?")
CITATION_FORMATS = "S<n> slide <k>, S<n> § <heading>, S<n> <sheet>!<range>, S<n>, prompt, or answer Q<n>"


class Line:
    def __init__(self, number, text, fenced):
        self.number, self.text, self.fenced = number, text, fenced


class Node:
    def __init__(self, level, text, number, parent):
        self.level, self.text, self.number, self.parent = level, text, number, parent
        self.body, self.children = [], []

    def content(self):
        return [line for line in self.body if line.text.strip()]

    def is_none(self):
        return [line.text.strip() for line in self.content()] == ["None."]


def parse_document(text):
    root = Node(0, "", 0, None)
    nodes, lines = [], []
    current, fenced = root, False
    for number, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.lstrip()
        if stripped.startswith(("```", "~~~")):
            lines.append(Line(number, raw, True))
            current.body.append(lines[-1])
            fenced = not fenced
            continue
        match = None if fenced else HEADING.match(raw)
        lines.append(Line(number, raw, fenced))
        if match:
            level = len(match.group(1))
            parent = current
            while parent.level >= level:
                parent = parent.parent
            current = Node(level, match.group(2).strip("` "), number, parent)
            parent.children.append(current)
            nodes.append(current)
        else:
            current.body.append(lines[-1])
    return root, nodes, lines


def split_row(text):
    cells = re.split(r"(?<!\\)\|", text.strip())
    if cells and cells[0].strip() == "":
        cells = cells[1:]
    if cells and cells[-1].strip() == "":
        cells = cells[:-1]
    return [cell.strip().replace("\\|", "|") for cell in cells]


def find_tables(node):
    tables, run = [], []
    for line in node.body + [Line(0, "", False)]:
        if line.text.lstrip().startswith("|") and not line.fenced:
            run.append(line)
            continue
        if len(run) >= 2 and re.fullmatch(r"[\s|:-]+", run[1].text) and "-" in run[1].text:
            tables.append((run[0].number, split_row(run[0].text),
                           [(r.number, split_row(r.text)) for r in run[2:]]))
        run = []
    return tables


def fields_of(node):
    found = {}
    for line in node.body:
        match = None if line.fenced else FIELD.match(line.text)
        if match and match.group(1) not in found:
            found[match.group(1)] = (line.number, match.group(2).strip())
    return found


class Linter:
    def __init__(self, text):
        self.issues = []
        self.root, self.nodes, self.lines = parse_document(text)
        self.source_ids = set()
        self.seen_ids = {}
        self.questions = {}
        self.answer_refs = []

    def add(self, line, message):
        self.issues.append((line, message))

    def section(self, name):
        return next((n for n in self.nodes if n.level == 2 and n.text == name), None)


    def check_id(self, raw, prefix, line, section_name):
        match = re.fullmatch(r"([A-Z]+)(\d+)", raw)
        if match and match.group(1) != prefix:
            self.add(line, f"id {raw} belongs in another section; {section_name} uses {prefix}<n>")
        elif not re.fullmatch(rf"{prefix}[1-9]\d*", raw):
            self.add(line, f"bad id '{raw}'; use {prefix}<n>, numbered from 1 with no leading zero")
        elif raw in self.seen_ids:
            self.add(line, f"duplicate id {raw}, first used on line {self.seen_ids[raw]}")
        else:
            self.seen_ids[raw] = line

    def check_sources(self, value, line, label=""):
        prefix = f"{label}: " if label else ""
        value = value.strip().rstrip(".").strip()
        if not value:
            self.add(line, f"{prefix}Source has no value; cite S<n>, prompt, or answer Q<n>")
            return
        for item in SPLIT_CITATIONS.split(value):
            item = item.strip()
            if item == "prompt":
                continue
            answer = re.fullmatch(r"answer Q(\d+)", item)
            if answer:
                self.answer_refs.append((line, int(answer.group(1))))
                continue
            match = re.fullmatch(r"(S\d+)(?: (.+))?", item)
            rest = match.group(2) if match else None
            valid = match and (rest is None or re.fullmatch(r"slides? \d+(?:-\d+)?", rest)
                               or rest.startswith("§ ") and len(rest) > 2 or SHEET_RANGE.fullmatch(rest))
            if not valid:
                self.add(line, f"{prefix}unrecognised citation '{item}'; use {CITATION_FORMATS}")
            elif match.group(1) not in self.source_ids:
                self.add(line, f"{prefix}{match.group(1)} is not in the Sources table")

    def check_source_mentions(self, value, line):
        tokens = SOURCE_TOKEN.findall(value)
        if not tokens:
            self.add(line, "Source names no input; cite S<n>, prompt, or answer Q<n>")
        for token in tokens:
            answer = re.fullmatch(r"answer Q(\d+)", token)
            if answer:
                self.answer_refs.append((line, int(answer.group(1))))
            elif token != "prompt" and token not in self.source_ids:
                self.add(line, f"{token} is not in the Sources table")


    def check_title_and_order(self):
        titles = [n for n in self.nodes if n.level == 1]
        if not titles or not titles[0].text.endswith(" design"):
            self.add(1, "missing title; start with '# <Feature name> design'")
        positions = {}
        highest = -1
        for node in self.nodes:
            if node.level != 2 or node.text not in SECTIONS:
                continue
            index = SECTIONS.index(node.text)
            if node.text in positions:
                self.add(node.number, f"duplicate section '## {node.text}'")
                continue
            positions[node.text] = node.number
            if index < highest:
                self.add(node.number, f"section '## {node.text}' is out of order; "
                         f"follow the order in the template, which puts it before '## {SECTIONS[highest]}'")
            highest = max(highest, index)
        for name in SECTIONS:
            if name not in positions:
                self.add(1, f"missing section '## {name}'")

    def check_empty(self):
        for node in self.nodes:
            if node.level < 2:
                continue
            if not node.content() and not node.children:
                self.add(node.number, f"section '{node.text}' is empty; write None.")

    def check_forbidden_tokens(self):
        in_questions = False
        for line in self.lines:
            match = None if line.fenced else HEADING.match(line.text)
            if match and len(match.group(1)) <= 2:
                in_questions = len(match.group(1)) == 2 and match.group(2).strip() == "Open questions"
            found = FORBIDDEN.search(line.text)
            if found and not in_questions:
                self.add(line.number, f"'{found.group(1)}' outside Open questions; "
                         "settle it or move it to an open question")

    def check_sources_section(self):
        node = self.section("Sources")
        if node is None:
            return
        scope = fields_of_free(node, "Scope")
        if scope is None:
            self.add(node.number, "Sources has no 'Scope:' line")
        elif scope[1] not in SCOPES:
            self.add(scope[0], f"Scope must be one of {', '.join(SCOPES)}")
        for header_line, headers, rows in find_tables(node):
            if not rows:
                self.add(header_line, "table has no rows; write None. instead")
            for number, cells in rows:
                if len(cells) != len(headers):
                    self.add(number, f"row '{cells[0]}' has {len(cells)} cells, header has {len(headers)}")
                elif not re.fullmatch(r"S[1-9]\d*", cells[0]):
                    self.add(number, f"bad source id '{cells[0]}'; use S<n>")
                elif cells[0] in self.source_ids:
                    self.add(number, f"duplicate id {cells[0]}")
                else:
                    self.source_ids.add(cells[0])

    def check_overview(self):
        node = self.section("Overview")
        if node is None:
            return
        measures = next((c for c in node.children if c.text == "Success measures"), None)
        if measures is None:
            self.add(node.number, "Overview has no '### Success measures'")
            return
        self.check_bullets(measures, "SM", "Success measures", need_id=True)

    def check_bullets(self, node, prefix, section_name, need_id):
        if node.is_none():
            return
        for line in node.content():
            if not line.text.startswith("- "):
                continue
            body = line.text[2:]
            if need_id:
                match = re.match(r"(\S+?):\s", body)
                self.check_id(match.group(1) if match else (body.split() or [""])[0], prefix, line.number, section_name)
            source = re.search(r"\bSource:\s*(.*)$", body)
            label = body.split(":")[0] if need_id else ""
            if source is None:
                self.add(line.number, f"entry {label or 'in ' + section_name} has no 'Source:'")
            else:
                self.check_sources(source.group(1), line.number, label)

    def check_other_features(self):
        node = self.section("Other features")
        if node is not None:
            self.check_bullets(node, "", "Other features", need_id=False)

    def check_table_sections(self):
        for name, prefix in TABLE_SECTIONS.items():
            node = self.section(name)
            if node is None or node.is_none():
                continue
            tables = find_tables(node)
            if not tables:
                self.add(node.number, f"section '{name}' needs a table with an Id column, or None.")
            for header_line, headers, rows in tables:
                if "Id" not in headers or "Source" not in headers:
                    self.add(header_line, f"table in '{name}' needs the columns Id and Source")
                    continue
                if not rows:
                    self.add(header_line, "table has no rows; write None. instead")
                for number, cells in rows:
                    if len(cells) != len(headers):
                        self.add(number, f"row '{cells[0]}' has {len(cells)} cells, header has {len(headers)}")
                        continue
                    row_id = cells[headers.index("Id")]
                    self.check_id(row_id, prefix, number, name)
                    self.check_sources(cells[headers.index("Source")], number, row_id)

    def check_heading_sections(self):
        for name, (prefix, required) in HEADING_SECTIONS.items():
            node = self.section(name)
            if node is None or node.is_none():
                continue
            if not node.children:
                self.add(node.number, f"section '{name}' needs entries like '### {prefix}1: <title>', or None.")
            for entry in node.children:
                match = re.match(r"(\S+?):\s+\S", entry.text)
                if not match:
                    self.add(entry.number, f"heading '{entry.text}' must read '### {prefix}<n>: <title>'")
                    continue
                entry_id = match.group(1)
                self.check_id(entry_id, prefix, entry.number, name)
                fields = fields_of(entry)
                for field in required:
                    if field not in fields:
                        self.add(entry.number, f"{entry_id} is missing '- {field}:'")
                    elif not fields[field][1]:
                        self.add(fields[field][0], f"{entry_id} '- {field}:' has no value; write None.")
                if "Source" in fields and fields["Source"][1]:
                    self.check_sources(fields["Source"][1], fields["Source"][0], entry_id)
                if name == "Formulas" and not any(line.fenced for line in entry.body):
                    self.add(entry.number, f"{entry_id} has no code block with input, output, and formula")

    def check_config_tables(self):
        node = self.section("Config tables")
        if node is None or node.is_none():
            return
        if not node.children:
            self.add(node.number, "section 'Config tables' needs one '### `file.json`' entry per file, or None.")
        for entry in node.children:
            fields = fields_of(entry)
            for field in ("Source sheets", "Draft", "Shape"):
                if field not in fields or not fields[field][1]:
                    self.add(entry.number, f"config '{entry.text}' is missing '- {field}:'")
            draft = fields.get("Draft")
            if draft and not re.search(r"`[^`]+\.json`", draft[1]):
                self.add(draft[0], f"config '{entry.text}' Draft line must name a path in backticks that ends in .json")
            tables = find_tables(entry)
            if not tables:
                self.add(entry.number, f"config '{entry.text}' has no key table")
            for header_line, headers, rows in tables:
                missing = [c for c in CONFIG_COLUMNS if c not in headers]
                if missing:
                    self.add(header_line, f"config '{entry.text}' table is missing column '{missing[0]}'")
                    continue
                if not rows:
                    self.add(header_line, "table has no rows; write None. instead")
                keys = {}
                for number, cells in rows:
                    if len(cells) != len(headers):
                        self.add(number, f"row '{cells[0]}' has {len(cells)} cells, header has {len(headers)}")
                        continue
                    key = cells[headers.index("Key")].strip("`")
                    if key in keys:
                        self.add(number, f"duplicate key {key}, first used on line {keys[key]}")
                    keys[key] = number
                    self.check_sources(cells[headers.index("Source")], number, key)

    def check_open_questions(self):
        node = self.section("Open questions")
        if node is None:
            return
        parts = {child.text: child for child in node.children}
        for name in QUESTION_PARTS:
            if name not in parts:
                self.add(node.number, f"Open questions is missing '### {name}'")
        for name in QUESTION_PARTS:
            part = parts.get(name)
            if part is None or part.is_none():
                continue
            if name == "Undefined terms":
                for child in part.children:
                    if re.match(r"Q\d+:", child.text):
                        self.add(child.number, f"question {child.text.split(':')[0]} must sit under Blocker, Important, or Minor")
                continue
            if not part.children:
                self.add(part.number, f"'{name}' needs questions like '#### Q1: <question>', or None.")
            for question in part.children:
                self.check_question(question)

    def check_question(self, node):
        match = re.match(r"(\S+?):\s+\S", node.text)
        if not match:
            self.add(node.number, f"heading '{node.text}' must read '#### Q<n>: <question>'")
            return
        qid = match.group(1)
        self.check_id(qid, "Q", node.number, "Open questions")
        fields = fields_of(node)
        for field in ("Source", "Status", "Interim default"):
            if field not in fields or not fields[field][1]:
                self.add(node.number, f"{qid} is missing '- {field}:'")
        if "Source" in fields and fields["Source"][1]:
            self.check_source_mentions(fields["Source"][1], fields["Source"][0])
        if "Status" in fields and fields["Status"][1]:
            line, status = fields["Status"]
            if not STATUS.fullmatch(status):
                self.add(line, f"{qid} status '{status}' must be open, 'skipped by <name> on <date>', "
                         "or 'answered on <date>: <answer>', with dates as YYYY-MM-DD")
            elif re.fullmatch(r"Q[1-9]\d*", qid):
                self.questions[int(qid[1:])] = status

    def check_answer_refs(self):
        for line, number in self.answer_refs:
            status = self.questions.get(number)
            if status is None:
                self.add(line, f"answer Q{number} cites a question that does not exist")
            elif not status.startswith("answered on"):
                self.add(line, f"answer Q{number} cites a question that is not answered")

    def run(self):
        self.check_title_and_order()
        self.check_sources_section()
        self.check_empty()
        self.check_overview()
        self.check_other_features()
        self.check_table_sections()
        self.check_heading_sections()
        self.check_config_tables()
        self.check_open_questions()
        self.check_answer_refs()
        self.check_forbidden_tokens()
        return sorted(set(self.issues))


def fields_of_free(node, name):
    for line in node.body:
        if line.text.startswith(f"{name}:") and not line.fenced:
            return line.number, line.text.split(":", 1)[1].strip()
    return None


def lint(text):
    return Linter(text).run()


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print("Usage: lint_design.py <design.md>...", file=sys.stderr)
        return 1
    failed = False
    for name in argv:
        path = Path(name)
        if not path.is_file():
            print(f"{name}:1: file not found")
            failed = True
            continue
        issues = lint(path.read_text(encoding="utf-8"))
        for line, message in issues:
            print(f"{name}:{line}: {message}")
        if issues:
            failed = True
        else:
            print(f"{name}: ok")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
