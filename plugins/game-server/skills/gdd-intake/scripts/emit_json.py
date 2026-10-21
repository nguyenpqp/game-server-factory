#!/usr/bin/env python3
"""Write draft config JSON from the Config tables section of a design.md.

Usage:
    python3 emit_json.py <design.md> [--sheets <work_dir>] [--out-dir <dir>]

Each `### \\`file.json\\`` entry under `## Config tables` becomes one JSON file at the path
on its Draft line, relative to the design file (or to --out-dir). The key table drives the shape:

  - A key path joins object fields with dots: `limits.perDay`.
  - `[]` marks a list of objects (`tiers[].points`) or, at the end, a list of values (`tags[]`).
  - The Type column picks the JSON type: integer, number, boolean, or string. Any other type,
    such as "list of item and amount", keeps the cell text as a string.
  - A value comes from the Example column. With --sheets, a key whose Source cites a sheet
    range takes its values from the converted CSV instead: a single cell for a plain key, or a
    single column for a list key. A list gets one element per row of its longest column.
    Keys with no sheet values keep their Example in the first element and null after it.

--sheets takes the work directory that convert_office.py wrote. The output is a draft, so the
developer or feature-spec checks it against the design before it becomes a config file.

Exit codes: 0 when the run finished (warnings go to stderr), 1 for a missing design or a config
entry that cannot be built.
"""
import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from convert_office import column_number  # noqa: E402
from lint_design import SPLIT_CITATIONS, fields_of, find_tables, parse_document  # noqa: E402

SHEET_CITATION = re.compile(
    r"(S\d+) (.+)!\$?([A-Z]+)\$?(\d+)(?::\$?([A-Z]+)\$?(\d+))?")
KEY_PART = re.compile(r"([A-Za-z_][\w-]*)(\[\])?")
TRUE_WORDS, FALSE_WORDS = {"true", "yes", "1"}, {"false", "no", "0"}


class DesignError(Exception):
    pass


def source_files(nodes):
    files = {}
    for node in nodes:
        if node.level == 2 and node.text == "Sources":
            for _, headers, rows in find_tables(node):
                if "Id" in headers and "Input" in headers:
                    for _, cells in rows:
                        if len(cells) == len(headers):
                            name = cells[headers.index("Input")].strip("`")
                            files[cells[headers.index("Id")]] = Path(name).name
    return files


def config_entries(nodes):
    entries, inside = [], False
    for node in nodes:
        if node.level == 2:
            inside = node.text == "Config tables"
        elif inside and node.level == 3:
            fields = {name: value for name, (_, value) in fields_of(node).items()}
            tables = [(headers, [cells for _, cells in rows]) for _, headers, rows in find_tables(node)]
            entries.append({"title": node.text, "fields": fields, "tables": tables})
    return entries



class Sheets:
    def __init__(self, work_dir):
        self.raw = work_dir / "raw"
        manifest = work_dir / "conversion-manifest.json"
        if not manifest.is_file():
            raise DesignError(f"no conversion-manifest.json in {work_dir}")
        self.csv_names = {}
        for entry in json.loads(manifest.read_text(encoding="utf-8")).get("files", []):
            for sheet in entry.get("sheets", []):
                self.csv_names[(entry["source"], sheet["sheet"])] = sheet["csv"]
        self.cache = {}

    def rows(self, file_name, sheet):
        name = self.csv_names.get((file_name, sheet))
        if name is None:
            return None
        if name not in self.cache:
            with (self.raw / name).open(newline="", encoding="utf-8-sig") as handle:
                self.cache[name] = list(csv.reader(handle))
        return self.cache[name]


def sheet_values(source, files, sheets, shape, warn, label):
    for item in SPLIT_CITATIONS.split(source.strip().rstrip(".")):
        match = SHEET_CITATION.fullmatch(item.strip())
        if not match:
            continue
        source_id, sheet, c1, r1, c2, r2 = match.groups()
        c2, r2 = c2 or c1, r2 or r1
        if (shape == "cell" and (c1, r1) != (c2, r2)) or (shape == "column" and c1 != c2):
            warn(f"{label}: {item.strip()} is not a single {shape}; using the Example")
            return None
        rows = sheets.rows(files.get(source_id, ""), sheet.strip("'"))
        if rows is None:
            warn(f"{label}: {source_id} {sheet} is not in the converted sheets; using the Example")
            return None
        column = column_number(c1) - 1
        return [rows[r - 1][column] if r - 1 < len(rows) and column < len(rows[r - 1]) else ""
                for r in range(int(r1), int(r2) + 1)]
    return None



class Node:
    def __init__(self, kind):
        self.kind = kind
        self.children = {}
        self.item = None
        self.leaf = None


def coerce(raw, type_name, warn, label):
    raw = raw.strip().strip("`")
    kind = type_name.strip().lower()
    if raw == "":
        return "" if kind == "string" else None
    try:
        if kind in ("integer", "int"):
            if re.fullmatch(r"[+-]?\d+", raw):
                return int(raw)
            number = float(raw)
            if not number.is_integer():
                raise ValueError
            return int(number)
        if kind in ("number", "float", "decimal"):
            return float(raw)
    except ValueError:
        warn(f"{label}: '{raw}' is not {kind}; wrote null")
        return None
    if kind in ("boolean", "bool"):
        if raw.lower() in TRUE_WORDS:
            return True
        if raw.lower() in FALSE_WORDS:
            return False
        warn(f"{label}: '{raw}' is not boolean; wrote null")
        return None
    return raw


def add_key(root, key, leaf):
    node = root
    parts = key.split(".")
    for number, part in enumerate(parts):
        match = KEY_PART.fullmatch(part)
        if not match:
            raise DesignError(f"key '{key}' is not a path like 'a.b' or 'list[].field'")
        name, is_list = match.groups()
        last = number == len(parts) - 1
        if node.kind != "object":
            raise DesignError(f"key '{key}' conflicts with another key")
        child = node.children.get(name)
        wanted = "list" if is_list else ("leaf" if last else "object")
        if child is None:
            child = node.children[name] = Node(wanted)
        elif child.kind != wanted or (last and not is_list):
            raise DesignError(f"key '{key}' conflicts with another key")
        if is_list:
            if child.item is None:
                child.item = Node("leaf" if last else "object")
            if last:
                if child.item.leaf is not None:
                    raise DesignError(f"key '{key}' is listed twice")
                child.item.leaf = leaf
                return
            node = child.item
        elif last:
            child.leaf = leaf
        else:
            node = child


def list_length(node):
    lengths = []

    def walk(current):
        if current.kind == "leaf" and current.leaf and current.leaf["fill"]:
            lengths.append(len(current.leaf["fill"]))
        for child in current.children.values():
            walk(child)
        if current.kind == "list" and current.item is not None:
            walk(current.item)

    walk(node)
    return max(lengths, default=1)


def render(node, index, warn):
    if node.kind == "leaf":
        leaf = node.leaf
        if leaf["fill"]:
            raw = leaf["fill"][index] if index < len(leaf["fill"]) else None
        else:
            raw = leaf["example"] if index == 0 else None
        return None if raw is None else coerce(raw, leaf["type"], warn, leaf["key"])
    if node.kind == "list":
        return [render(node.item, i, warn) for i in range(list_length(node))]
    return {name: render(child, index, warn) for name, child in node.children.items()}


def build_draft(entry, files, sheets, warn):
    root = Node("object")
    from_sheets = total = 0
    for headers, rows in entry["tables"] or [([], [])]:
        for column in ("Key", "Type", "Example"):
            if column not in headers:
                raise DesignError(f"config '{entry['title']}' has no {column} column")
        for cells in rows:
            if len(cells) != len(headers):
                raise DesignError(
                    f"config '{entry['title']}' has a row with {len(cells)} cells, expected {len(headers)}")
            key = cells[headers.index("Key")].strip("`")
            fill = None
            if sheets is not None and "Source" in headers:
                shape = "column" if "[]" in key else "cell"
                fill = sheet_values(cells[headers.index("Source")], files, sheets, shape, warn, key)
                from_sheets += bool(fill)
            add_key(root, key, {"key": key, "type": cells[headers.index("Type")],
                                "example": cells[headers.index("Example")].strip("`"), "fill": fill})
            total += 1
    return root, from_sheets, total


def emit_entry(entry, base, files, sheets, warn):
    draft = re.search(r"`([^`]+\.json)`", entry["fields"].get("Draft", ""))
    if not draft:
        raise DesignError(f"config '{entry['title']}' has no Draft line with a .json path in backticks")
    target = (base / draft.group(1)).resolve()
    if not target.is_relative_to(base.resolve()):
        raise DesignError(f"config '{entry['title']}' Draft path leaves the output folder")
    root, from_sheets, total = build_draft(entry, files, sheets, warn)
    data = render(root, 0, warn)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target, from_sheets, total


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    design, sheets_dir, out_dir, rest = None, None, None, list(argv)
    while rest:
        item = rest.pop(0)
        if item == "--sheets" and rest:
            sheets_dir = Path(rest.pop(0))
        elif item == "--out-dir" and rest:
            out_dir = Path(rest.pop(0))
        elif design is None and not item.startswith("--"):
            design = Path(item)
        else:
            design = None
            break
    if design is None:
        print("Usage: emit_json.py <design.md> [--sheets <work_dir>] [--out-dir <dir>]", file=sys.stderr)
        return 1
    if not design.is_file():
        print(f"Design file not found: {design}", file=sys.stderr)
        return 1

    warnings = []

    def warn(message):
        warnings.append(message)
        print(f"warning: {message}", file=sys.stderr)

    _, nodes, _ = parse_document(design.read_text(encoding="utf-8"))
    entries = config_entries(nodes)
    if not entries:
        print("No config tables in the design; nothing to emit.")
        return 0
    try:
        sheets = Sheets(sheets_dir) if sheets_dir else None
        base = out_dir or design.parent
        for entry in entries:
            target, from_sheets, total = emit_entry(entry, base, source_files(nodes), sheets, warn)
            print(f"{entry['title']} -> {target} ({total} keys, {from_sheets} filled from sheets)")
    except DesignError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"{len(entries)} draft file(s), {len(warnings)} warning(s). Check each draft against the design.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
