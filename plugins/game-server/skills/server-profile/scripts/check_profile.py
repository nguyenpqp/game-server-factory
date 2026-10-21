#!/usr/bin/env python3
"""Check a game server profile against the profile template.

Usage: check_profile.py [--blocked-rules] <profile.md>

Prints `path:line: message` for each failure and exits 1 if any failure exists.
The required frontmatter keys and capability headings are read from
`references/profile-template.md` next to this script, so the template is the
single source. With `--blocked-rules`, a clean profile also prints, for each
capability that is not present, the rule ids from the rule index that need it.
"""
import argparse
import re
import sys
from collections import namedtuple
from pathlib import Path

Finding = namedtuple("Finding", "path line message")

SKILLS = Path(__file__).resolve().parents[2]
TEMPLATE = SKILLS / "server-profile" / "references" / "profile-template.md"
RULE_INDEX = SKILLS / "server-rules" / "references" / "index.md"

STATUSES = ("present", "partial", "missing")
FIELDS_WHEN_PRESENT = ("api", "file", "snippet")
FIELDS_WHEN_NOT_PRESENT = ("blocker", "proposal")

FENCE = re.compile(r"^\s*(```|~~~)")
CAP_HEADING = re.compile(r"^###\s+(CAP-[A-Z]+)\b")
ANY_HEADING = re.compile(r"^#{1,6}\s")
FIELD_LINE = re.compile(r"^-\s+(\w+):\s*(.*)$")
RULE_HEADING = re.compile(r"^###\s+((?:AUTH|MN|BG|PERF|CFG|MET|CHEAT|ADMIN|HTTP|TEST)-\d{2})\b")
KEY_LINE = re.compile(r"^(\s*)([A-Za-z_]\w*):(.*)$")


def unfenced(lines):
    """Yield (line number, text) for lines outside fenced code blocks."""
    fenced = False
    for number, line in enumerate(lines, 1):
        if FENCE.match(line):
            fenced = not fenced
            continue
        if not fenced:
            yield number, line


def split_frontmatter(lines):
    """Return (block lines with their numbers, or None when there is no block)."""
    if not lines or lines[0].strip() != "---":
        return None
    for end in range(1, len(lines)):
        if lines[end].strip() == "---":
            return [(n + 1, lines[n]) for n in range(1, end)]
    return None


def parse_keys(block):
    """Return {dotted key: line number} for the leaf keys of a frontmatter block.

    A top-level key with indented `sub: value` children is replaced by its
    dotted children. A key with an inline value or `- item` children is a leaf.
    """
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
    """Return (required frontmatter keys, capability ids in template order)."""
    text = Path(path).read_text(encoding="utf-8")
    lines = text.splitlines()
    sample = re.search(r"```yaml\n(.*?)```", text, re.S)
    block = split_frontmatter(sample.group(1).splitlines()) if sample else None
    if block is None:
        raise ValueError(f"{path}: no frontmatter example found")
    keys = [key for key in parse_keys(block)]
    caps = [m.group(1) for _, line in unfenced(lines) if (m := CAP_HEADING.match(line))]
    return keys, caps


def capability_sections(lines):
    """Return {cap id: (heading line, field lines, has fenced block)} for the profile body."""
    sections, current, fenced = {}, None, False
    for number, line in enumerate(lines, 1):
        if FENCE.match(line):
            fenced = not fenced
            if current:
                sections[current][1].append((number, line))
                sections[current][2][0] = True
        elif fenced:
            continue
        elif CAP_HEADING.match(line):
            current = CAP_HEADING.match(line).group(1)
            sections.setdefault(current, (number, [], [False]))
        elif ANY_HEADING.match(line):
            current = None
        elif current:
            sections[current][1].append((number, line))
    return sections


def check_section(path, cap, heading_line, body, has_fence):
    findings = []
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
        return findings, None
    status = fields["status"].strip("`")
    if status not in STATUSES:
        fail(f"{cap} has invalid status '{status}' (use present, partial, or missing)", status_line)
        return findings, None
    required = {
        "present": FIELDS_WHEN_PRESENT,
        "partial": FIELDS_WHEN_PRESENT + FIELDS_WHEN_NOT_PRESENT,
        "missing": FIELDS_WHEN_NOT_PRESENT,
    }[status]
    for field in required:
        filled = has_fence if field == "snippet" and "snippet" in fields else bool(fields.get(field))
        if not filled:
            fail(f"{cap} is {status} and needs {'an' if field == 'api' else 'a'} {field}")
    return findings, status


def check_profile(path, template=TEMPLATE):
    required_keys, required_caps = load_template(template)
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return [Finding(path, 1, "file not found")], {}
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
    statuses = {}
    for cap in required_caps:
        if cap not in sections:
            findings.append(Finding(path, 1, f"missing capability heading {cap}"))
            continue
        heading_line, body, fence = sections[cap]
        section_findings, status = check_section(path, cap, heading_line, body, fence[0])
        findings += section_findings
        if status:
            statuses[cap] = status
    return findings, statuses


def blocked_rules(statuses, index=RULE_INDEX):
    """Return {cap id: [rule ids that list it in `needs:`]} for non-present caps."""
    needs, rule = {}, None
    for line in Path(index).read_text(encoding="utf-8").splitlines():
        heading = RULE_HEADING.match(line)
        if heading:
            rule = heading.group(1)
        elif rule and line.startswith("- needs:"):
            for cap in re.findall(r"CAP-[A-Z]+", line):
                needs.setdefault(cap, []).append(rule)
    return {cap: needs.get(cap, []) for cap, status in statuses.items() if status != "present"}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check a game server profile.")
    parser.add_argument("profile")
    parser.add_argument("--blocked-rules", action="store_true")
    args = parser.parse_args(argv)
    findings, statuses = check_profile(args.profile)
    for finding in findings:
        print(f"{finding.path}:{finding.line}: {finding.message}")
    if findings:
        return 1
    if args.blocked_rules:
        for cap, rules in blocked_rules(statuses).items():
            print(f"{cap} ({statuses[cap]}): {', '.join(rules) if rules else 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
