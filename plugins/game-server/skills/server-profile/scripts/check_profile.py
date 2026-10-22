#!/usr/bin/env python3
"""Check a game server profile against the profile template.

Usage: check_profile.py [--blocked-rules] <profile.md>

Prints `path:line: message` for each failure and exits 1 if any failure exists.
The required frontmatter keys and capability headings are read from
`references/profile-template.md` next to this script, so the template is the
single source. `lint.command_method` is optional. With `--blocked-rules`, a clean
profile also prints, for each capability that is not present, the rule ids it
blocks: for a missing capability, every rule in the rule index whose `needs` line
names it, and for a partial one, the rule ids on its `blocker` line.

A `blocker` line that names a rule whose `needs` line in the rule index does not
name that capability prints a warning to stderr. The exit code does not change.
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
OPTIONAL_KEYS = {"lint.command_method"}

FENCE = re.compile(r"^\s*(```|~~~)")
CAP_HEADING = re.compile(r"^###\s+(CAP-[A-Z]+)\b")
ANY_HEADING = re.compile(r"^#{1,6}\s")
FIELD_LINE = re.compile(r"^-\s+(\w+):\s*(.*)$")
RULE_ID = re.compile(r"\b(?:AUTH|MN|BG|PERF|CFG|MET|CHEAT|ADMIN|HTTP|TEST)-\d{2}\b")
RULE_HEADING = re.compile(r"^###\s+(" + RULE_ID.pattern + ")")
KEY_LINE = re.compile(r"^(\s*)([A-Za-z_]\w*):(.*)$")


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
        heading_line, body, fence = sections[cap]
        section_findings, status, fields = check_section(path, cap, heading_line, body, fence[0])
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


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check a game server profile.")
    parser.add_argument("profile")
    parser.add_argument("--blocked-rules", action="store_true")
    args = parser.parse_args(argv)
    findings, statuses, blockers, headings = check_profile(args.profile)
    for finding in findings:
        print(f"{finding.path}:{finding.line}: {finding.message}")
    for warning in blocker_warnings(args.profile, blockers, headings):
        print(f"warning: {warning.path}:{warning.line}: {warning.message}", file=sys.stderr)
    if findings:
        return 1
    if args.blocked_rules:
        for cap, rules in blocked_rules(statuses, blockers).items():
            print(f"{cap} ({statuses[cap]}): {', '.join(rules) if rules else 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
