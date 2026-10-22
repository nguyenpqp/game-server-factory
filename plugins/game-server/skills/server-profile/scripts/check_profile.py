#!/usr/bin/env python3
"""Check a game server profile against the profile template.

Usage: check_profile.py [--blocked-rules] [--decisions <decisions.md>] <profile.md>

Prints `path:line: message` for each failure and exits 1 if any failure exists.
The required frontmatter keys and capability headings are read from
`references/profile-template.md` next to this script, so the template is the
single source. `lint.command_method` and `lint.allowed_import` are optional. With
`--blocked-rules`, a clean profile also prints, for each capability that is not
present, the rule ids it blocks: for a missing capability, every rule in the rule
index whose `needs` line names it, and for a partial one, the rule ids on its
`blocker` line.

A `blocker` line that names a rule whose `needs` line in the rule index does not
name that capability prints a warning to stderr. The exit code does not change.

With `--decisions`, the script also checks a project decisions file, in the format of
`feature-spec/references/decisions-template.md`, against the profile and the rule
index. A decision whose capability is present prints a warning to stderr.
"""
import argparse
import datetime
import re
import sys
from collections import namedtuple
from pathlib import Path

Finding = namedtuple("Finding", "path line message")
Decision = namedtuple("Decision", "line id capability status rules fact bound by date")

SKILLS = Path(__file__).resolve().parents[2]
TEMPLATE = SKILLS / "server-profile" / "references" / "profile-template.md"
RULE_INDEX = SKILLS / "server-rules" / "references" / "index.md"

STATUSES = ("present", "partial", "missing")
ACCEPTABLE_STATUSES = ("partial", "missing")
DECISION_COLUMNS = ("Id", "Capability", "Profile status", "Rules", "Deployment fact",
                    "How it bounds the failure", "Accepted by", "Date")
RULE_BLOCKING = "PERF-01"
FIELDS_WHEN_PRESENT = ("api", "file", "snippet")
FIELDS_WHEN_NOT_PRESENT = ("blocker", "proposal")
OPTIONAL_KEYS = {"lint.command_method", "lint.allowed_import"}

FENCE = re.compile(r"^\s*(```|~~~)")
CAP_HEADING = re.compile(r"^###\s+(CAP-[A-Z]+)\b")
ANY_HEADING = re.compile(r"^#{1,6}\s")
FIELD_LINE = re.compile(r"^-\s+(\w+):\s*(.*)$")
RULE_ID = re.compile(r"\b(?:AUTH|MN|BG|PERF|CFG|MET|CHEAT|ADMIN|HTTP|TEST|DES|MOD|SYNC|LOG)-\d{2}\b")
RULE_HEADING = re.compile(r"^###\s+(" + RULE_ID.pattern + ")")
KEY_LINE = re.compile(r"^(\s*)([A-Za-z_]\w*):(.*)$")
DECISION_ID = re.compile(r"^D[1-9]\d*$")
DECISION_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SEPARATOR_CELL = re.compile(r"^:?-+:?$")


def unfenced(lines):
    fenced = False
    for number, line in enumerate(lines, 1):
        if FENCE.match(line):
            fenced = not fenced
            continue
        if not fenced:
            yield number, line


def split_frontmatter(lines):
    if not lines or lines[0].strip() != "---":
        return None
    for end in range(1, len(lines)):
        if lines[end].strip() == "---":
            return [(n + 1, lines[n]) for n in range(1, end)]
    return None


def parse_keys(block):
    keys, parent = {}, None
    for number, line in block:
        match = KEY_LINE.match(line)
        if not match:
            continue
        if not match.group(1):
            parent = match.group(2)
            keys[parent] = number
        elif parent:
            keys[f"{parent}.{match.group(2)}"] = number
            keys.pop(parent, None)
    return keys


def load_template(path=TEMPLATE):
    text = Path(path).read_text(encoding="utf-8")
    lines = text.splitlines()
    sample = re.search(r"```yaml\n(.*?)```", text, re.S)
    block = split_frontmatter(sample.group(1).splitlines()) if sample else None
    if block is None:
        raise ValueError(f"{path}: no frontmatter example found")
    keys = [key for key in parse_keys(block) if key not in OPTIONAL_KEYS]
    caps = [m.group(1) for _, line in unfenced(lines) if (m := CAP_HEADING.match(line))]
    return keys, caps


def capability_sections(lines):
    sections, current, fenced = {}, None, False
    for number, line in enumerate(lines, 1):
        if FENCE.match(line):
            fenced = not fenced
            if current:
                sections[current][1].append((number, line))
        elif fenced:
            continue
        elif CAP_HEADING.match(line):
            current = CAP_HEADING.match(line).group(1)
            sections.setdefault(current, (number, []))
        elif ANY_HEADING.match(line):
            current = None
        elif current:
            sections[current][1].append((number, line))
    return sections


def check_section(path, cap, heading_line, body):
    findings = []
    has_fence = any(FENCE.match(line) for _, line in body)
    fields, status_line = {}, heading_line
    for number, line in body:
        match = FIELD_LINE.match(line)
        if match and match.group(1) not in fields:
            fields[match.group(1)] = match.group(2).strip()
            if match.group(1) == "status":
                status_line = number

    def fail(message, line=heading_line):
        findings.append(Finding(path, line, message))

    if "status" not in fields:
        fail(f"{cap} has no status line (use present, partial, or missing)")
        return findings, None, fields
    status = fields["status"].strip("`")
    if status not in STATUSES:
        fail(f"{cap} has invalid status '{status}' (use present, partial, or missing)", status_line)
        return findings, None, fields
    required = {
        "present": FIELDS_WHEN_PRESENT,
        "partial": FIELDS_WHEN_PRESENT + FIELDS_WHEN_NOT_PRESENT,
        "missing": FIELDS_WHEN_NOT_PRESENT,
    }[status]
    for field in required:
        filled = has_fence if field == "snippet" and "snippet" in fields else bool(fields.get(field))
        if not filled:
            fail(f"{cap} is {status} and needs {'an' if field == 'api' else 'a'} {field}")
    if status == "partial" and fields.get("blocker") and not RULE_ID.search(fields["blocker"]):
        fail(f"{cap} is partial and its blocker names no rule id")
    return findings, status, fields


def check_profile(path, template=TEMPLATE):
    required_keys, required_caps = load_template(template)
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return [Finding(path, 1, "file not found")], {}, {}, {}
    findings = []
    block = split_frontmatter(lines)
    if block is None:
        findings.append(Finding(path, 1, "missing frontmatter block"))
    else:
        present = parse_keys(block)
        findings += [
            Finding(path, 1, f"missing frontmatter key {key}")
            for key in required_keys
            if key not in present
        ]
    sections = capability_sections(lines)
    statuses, blockers, headings = {}, {}, {}
    for cap in required_caps:
        if cap not in sections:
            findings.append(Finding(path, 1, f"missing capability heading {cap}"))
            continue
        heading_line, body = sections[cap]
        section_findings, status, fields = check_section(path, cap, heading_line, body)
        findings += section_findings
        if status:
            statuses[cap] = status
            blockers[cap] = fields.get("blocker", "")
            headings[cap] = heading_line
    return findings, statuses, blockers, headings


def rule_needs(index=RULE_INDEX):
    needs, rule = {}, None
    for line in Path(index).read_text(encoding="utf-8").splitlines():
        heading = RULE_HEADING.match(line)
        if heading:
            rule = heading.group(1)
        elif rule and line.startswith("- needs:"):
            needs[rule] = re.findall(r"CAP-[A-Z]+", line)
    return needs


def blocker_warnings(path, blockers, headings, index=RULE_INDEX):
    needs = rule_needs(index)
    warnings = []
    for cap, blocker in blockers.items():
        for rule in dict.fromkeys(RULE_ID.findall(blocker)):
            if cap not in needs.get(rule, []):
                warnings.append(Finding(path, headings[cap], f"{cap} blocker names {rule}, "
                                        f"whose needs line in the rule index does not name {cap}"))
    return warnings


def blocked_rules(statuses, blockers, index=RULE_INDEX):
    needs = {}
    for rule, caps in rule_needs(index).items():
        for cap in caps:
            needs.setdefault(cap, []).append(rule)
    blocked = {}
    for cap, status in statuses.items():
        if status == "missing":
            blocked[cap] = needs.get(cap, [])
        elif status == "partial":
            blocked[cap] = list(dict.fromkeys(RULE_ID.findall(blockers.get(cap, ""))))
    return blocked


def row_cells(line):
    if not line.lstrip().startswith("|"):
        return None
    cells = re.split(r"(?<!\\)\|", line.strip())[1:]
    if cells and not cells[-1].strip():
        cells = cells[:-1]
    return [cell.strip().replace("\\|", "|") for cell in cells]


def tables(numbered_lines):
    table = []
    for number, line in numbered_lines:
        cells = row_cells(line)
        if cells is not None:
            table.append((number, cells))
        elif table:
            yield table
            table = []
    if table:
        yield table


def read_decisions(path):
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return [Finding(path, 1, "file not found")], []
    except (OSError, UnicodeDecodeError) as error:
        return [Finding(path, 1, f"cannot read the file as UTF-8 text ({error})")], []
    found = list(tables(unfenced(lines)))
    table = next((t for t in found if tuple(t[0][1]) == DECISION_COLUMNS), None)
    if table is None:
        return [Finding(path, 1, f"no table with the columns {' | '.join(DECISION_COLUMNS)}")], []
    findings, decisions = [], []
    findings += [Finding(path, 1, f"line {other[0][0]} starts another table, whose rows are not checked; "
                         "keep every decision in the one table, with no blank line between rows")
                 for other in found if other is not table]
    (header_line, _), *rows = table
    if rows and all(SEPARATOR_CELL.match(cell) for cell in rows[0][1]):
        rows = rows[1:]
    else:
        findings.append(Finding(path, 1, f"the header on line {header_line} has no separator row under it"))
    for number, cells in rows:
        if len(cells) == len(DECISION_COLUMNS):
            decisions.append(Decision(number, *cells))
        else:
            findings.append(Finding(path, number, f"row has {len(cells)} cells, expected {len(DECISION_COLUMNS)}"))
    return findings, decisions


def valid_date(text):
    if not DECISION_DATE.match(text):
        return False
    try:
        datetime.date.fromisoformat(text)
    except ValueError:
        return False
    return True


def decision_errors(decision, caps, rule_ids, status, blocked, first_line):
    label, cap = decision.id or "row", decision.capability
    errors = []
    if not DECISION_ID.match(decision.id):
        errors.append(f"id '{decision.id}' is not D followed by a number with no leading zero")
    elif decision.id in first_line:
        errors.append(f"{label} repeats the id on line {first_line[decision.id]}")
    if cap not in caps:
        errors.append(f"{label} names {cap or 'no capability'}, which is not a capability of the profile template")
    if decision.status not in ACCEPTABLE_STATUSES:
        errors.append(f"{label} has profile status '{decision.status}' (use partial or missing)")
    rules = [token.strip() for token in decision.rules.split(",") if token.strip()]
    if not rules:
        errors.append(f"{label} names no rule id")
    for rule in dict.fromkeys(rules):
        if rule == RULE_BLOCKING:
            errors.append(f"{label} names {rule}, which is accepted per call site in each spec, never in decisions")
        elif rule not in rule_ids:
            errors.append(f"{label} names {rule}, which is not in the rule index")
        elif status in ACCEPTABLE_STATUSES and rule not in blocked:
            errors.append(f"{label} names {rule}, which {cap} does not block in the profile, "
                          "so the developer must re-decide it")
    for column, value in (("Deployment fact", decision.fact), ("How it bounds the failure", decision.bound),
                          ("Accepted by", decision.by)):
        if not value:
            errors.append(f"{label} has an empty {column}")
    if not valid_date(decision.date):
        errors.append(f"{label} has date '{decision.date}' (use YYYY-MM-DD)")
    if status in ACCEPTABLE_STATUSES and decision.status in ACCEPTABLE_STATUSES and decision.status != status:
        errors.append(f"{label} is stale: it records {cap} as {decision.status} but the profile says {status}, "
                      "so the developer must re-decide it")
    return errors


def check_decisions(path, statuses, blockers, index=RULE_INDEX):
    _, caps = load_template()
    rule_ids = set(rule_needs(index))
    blocked = blocked_rules(statuses, blockers, index)
    findings, decisions = read_decisions(path)
    warnings, first_line = [], {}
    for decision in decisions:
        status = statuses.get(decision.capability)
        errors = decision_errors(decision, caps, rule_ids, status, blocked.get(decision.capability, []), first_line)
        findings += [Finding(path, decision.line, error) for error in errors]
        first_line.setdefault(decision.id, decision.line)
        if status == "present":
            warnings.append(Finding(path, decision.line, f"{decision.id or 'row'} names {decision.capability}, "
                                    "which is present in the profile, so the decision is no longer needed"))
    return sorted(findings, key=lambda finding: finding.line), warnings


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check a game server profile.")
    parser.add_argument("profile")
    parser.add_argument("--blocked-rules", action="store_true")
    parser.add_argument("--decisions")
    args = parser.parse_args(argv)
    findings, statuses, blockers, headings = check_profile(args.profile)
    decision_findings, decision_warnings = (check_decisions(args.decisions, statuses, blockers)
                                            if args.decisions else ([], []))
    for finding in findings + decision_findings:
        print(f"{finding.path}:{finding.line}: {finding.message}")
    for warning in blocker_warnings(args.profile, blockers, headings) + decision_warnings:
        print(f"warning: {warning.path}:{warning.line}: {warning.message}", file=sys.stderr)
    if findings or decision_findings:
        return 1
    if args.blocked_rules:
        for cap, rules in blocked_rules(statuses, blockers).items():
            print(f"{cap} ({statuses[cap]}): {', '.join(rules) if rules else 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
