#!/usr/bin/env python3
"""Check the game-server plugin's structure, links, ids, and private terms.

Prints `path:line: message` for each failure and exits 1 if any failure exists.
Warnings go to stderr and do not change the exit code.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from collections import namedtuple
from pathlib import Path

Finding = namedtuple("Finding", "path line message warning", defaults=(False,))

MARKETPLACE = ".claude-plugin/marketplace.json"
PLUGIN_DIR = "plugins/game-server"
PLUGIN_MANIFEST = f"{PLUGIN_DIR}/.claude-plugin/plugin.json"
SKILLS_DIR = f"{PLUGIN_DIR}/skills"
RULE_INDEX = f"{SKILLS_DIR}/server-rules/references/index.md"
PROFILE_TEMPLATE = f"{SKILLS_DIR}/server-profile/references/profile-template.md"
MODEL_INVOCATION_OFF_ONLY_ON = "server-profile"
MAX_DESCRIPTION = 1024

RULE_ID = re.compile(r"\b(?:AUTH|MN|BG|PERF|CFG|MET|CHEAT|ADMIN|HTTP|TEST)-\d{2}\b")
CAP_ID = re.compile(r"\bCAP-[A-Z]+\b")
MD_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
INLINE_CODE = re.compile(r"`([^`\n]+)`")
CHECKED_PREFIXES = ("references/", "scripts/", "prompts/", "../")
# Placeholders and globs name no single file, so they cannot resolve.
PLACEHOLDER_CHARS = "<>{}*"
SCHEME = re.compile(r"[a-z][a-z0-9+.-]*:", re.IGNORECASE)
HOME_PATH = re.compile(r"/(?:Users|home)/[\w.-]+/")
PRIVATE_KEY = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")


def relative(root, path):
    return path.relative_to(root).as_posix()


def load_json(root, rel):
    """Return (object or None, findings)."""
    path = root / rel
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, [Finding(rel, 1, "file not found")]
    except json.JSONDecodeError as error:
        return None, [Finding(rel, error.lineno, f"invalid JSON: {error.msg}")]
    if not isinstance(data, dict):
        return None, [Finding(rel, 1, "top level must be a JSON object")]
    return data, []


def check_marketplace(root):
    data, findings = load_json(root, MARKETPLACE)
    if data is None:
        return findings

    def fail(message):
        findings.append(Finding(MARKETPLACE, 1, message))

    if data.get("name") != "game-server-factory":
        fail("name must be game-server-factory")
    if not data.get("owner"):
        fail("missing owner")
    entries = [
        entry
        for entry in data.get("plugins") or []
        if isinstance(entry, dict) and entry.get("name") == "game-server"
    ]
    if not entries:
        fail("plugins must list game-server")
    else:
        if entries[0].get("source") != "./plugins/game-server":
            fail("game-server source must be ./plugins/game-server")
        if not entries[0].get("description"):
            fail("game-server entry has no description")
    return findings


def check_plugin_manifest(root):
    data, findings = load_json(root, PLUGIN_MANIFEST)
    if data is None:
        return findings
    for field in ("name", "description", "author", "license", "keywords"):
        if not data.get(field):
            findings.append(Finding(PLUGIN_MANIFEST, 1, f"missing field {field}"))
    if data.get("name") and data["name"] != "game-server":
        findings.append(Finding(PLUGIN_MANIFEST, 1, "name must be game-server"))
    if "version" in data:
        findings.append(
            Finding(PLUGIN_MANIFEST, 1, "version must be absent so installs track the commit")
        )
    return findings


def parse_frontmatter(text):
    """Return {key: (value, line)} for a leading `---` block, or None.

    Handles `key: value` lines and indented continuation lines; nothing else.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    fields, last = {}, None
    for number, line in enumerate(lines[1:], start=2):
        if line.strip() == "---":
            return fields
        if line[:1] in (" ", "\t") and last:
            value, at = fields[last]
            fields[last] = (f"{value} {line.strip()}".strip(), at)
        elif ":" in line:
            key, _, value = line.partition(":")
            value = value.strip()
            if value in (">", "|", ">-", "|-"):
                value = ""
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            last = key.strip()
            fields[last] = (value, number)
    return None


def check_skill(root, skill_dir):
    rel = relative(root, skill_dir / "SKILL.md")
    fields = parse_frontmatter((skill_dir / "SKILL.md").read_text(encoding="utf-8"))
    if fields is None:
        return [Finding(rel, 1, "missing or unterminated frontmatter")]
    findings = []
    if "name" not in fields:
        findings.append(Finding(rel, 1, "frontmatter has no name"))
    elif fields["name"][0] != skill_dir.name:
        value, line = fields["name"]
        findings.append(Finding(rel, line, f"name '{value}' must equal directory '{skill_dir.name}'"))
    if "description" not in fields:
        findings.append(Finding(rel, 1, "frontmatter has no description"))
    else:
        value, line = fields["description"]
        if not value:
            findings.append(Finding(rel, line, "description is empty"))
        elif len(value) > MAX_DESCRIPTION:
            findings.append(
                Finding(rel, line, f"description has {len(value)} characters, limit is {MAX_DESCRIPTION}")
            )
    flag = fields.get("disable-model-invocation")
    if flag and flag[0].lower() == "true" and skill_dir.name != MODEL_INVOCATION_OFF_ONLY_ON:
        findings.append(
            Finding(
                rel,
                flag[1],
                f"disable-model-invocation: true is allowed only on {MODEL_INVOCATION_OFF_ONLY_ON}",
            )
        )
    return findings


def check_skills(root):
    skills = root / SKILLS_DIR
    if not skills.is_dir():
        return []
    findings = []
    for skill_dir in sorted(p for p in skills.iterdir() if p.is_dir()):
        if (skill_dir / "SKILL.md").is_file():
            findings += check_skill(root, skill_dir)
        else:
            findings.append(Finding(relative(root, skill_dir), 1, "no SKILL.md", True))
    return findings


def plugin_files(root):
    """Yield (path, text) for each text file under the plugin directory."""
    for path in sorted((root / PLUGIN_DIR).rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        try:
            yield path, path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue


def markdown_lines(text):
    """Yield (number, line) outside fenced code blocks."""
    fenced = False
    for number, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
        elif not fenced:
            yield number, line


def check_links(root):
    findings = []
    for path, text in plugin_files(root):
        if path.suffix != ".md":
            continue
        rel = relative(root, path)
        for number, line in markdown_lines(text):
            targets = [
                t for t in MD_LINK.findall(line) if not SCHEME.match(t) and not t.startswith("#")
            ]
            for span in INLINE_CODE.findall(line):
                token = span.split()[0] if span.split() else ""
                if token.startswith(CHECKED_PREFIXES):
                    targets.append(token)
            for target in targets:
                file_part = target.split("#")[0]
                if any(c in file_part for c in PLACEHOLDER_CHARS):
                    continue
                if file_part and not (path.parent / file_part).exists():
                    findings.append(Finding(rel, number, f"broken link {target}"))
    return findings


def heading_ids(path, id_pattern):
    found = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            match = id_pattern.match(line.lstrip("#").strip())
            if match:
                found.add(match.group(0))
    return found


def check_ids(root, id_pattern, definitions, kind):
    defined_in = root / definitions
    if not defined_in.is_file():
        return []
    defined = heading_ids(defined_in, id_pattern)
    findings = []
    for path, text in plugin_files(root):
        for number, line in enumerate(text.splitlines(), start=1):
            for token in id_pattern.findall(line):
                if token not in defined:
                    findings.append(
                        Finding(
                            relative(root, path),
                            number,
                            f"{kind} {token} is not a heading in {definitions}",
                        )
                    )
    return findings


def tracked_texts(root):
    """Map each git-tracked file to its text, or None when git cannot list files."""
    proc = subprocess.run(["git", "-C", str(root), "ls-files", "-z"], capture_output=True)
    if proc.returncode != 0:
        return None
    texts = {}
    for name in filter(None, proc.stdout.decode("utf-8", "replace").split("\0")):
        try:
            texts[name] = (root / name).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
    return texts


def scan(texts, pattern, message):
    findings = []
    for name, text in texts.items():
        for number, line in enumerate(text.splitlines(), start=1):
            if pattern.search(line):
                findings.append(Finding(name, number, message))
    return findings


def read_denylist(path):
    terms = []
    for line in path.read_text(encoding="utf-8").splitlines():
        term = line.strip()
        if term and not term.startswith("#"):
            terms.append(term)
    return terms


def check_denylist(texts, denylist):
    if not denylist:
        return [
            Finding(
                ".",
                1,
                "private-term scan skipped; pass --denylist or set GSS_DENYLIST",
                True,
            )
        ]
    path = Path(denylist)
    if not path.is_file():
        return [Finding(denylist, 1, "denylist file not found")]
    terms = read_denylist(path)
    if not terms:
        return []
    pattern = re.compile(
        "|".join(rf"(?<!\w){re.escape(term)}(?!\w)" for term in terms), re.IGNORECASE
    )
    # The message omits the matched term so output stays safe to paste.
    return scan(texts, pattern, "contains a denylist term")


def check_tracked_files(root, denylist):
    texts = tracked_texts(root)
    if texts is None:
        return [Finding(".", 1, "git ls-files failed; cannot scan tracked files")]
    return (
        scan(texts, HOME_PATH, "contains an absolute home path")
        + scan(texts, PRIVATE_KEY, "contains a private key block")
        + check_denylist(texts, denylist)
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--denylist", help="file of private terms, one per line; default $GSS_DENYLIST")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    denylist = args.denylist or os.environ.get("GSS_DENYLIST")

    findings = (
        check_marketplace(root)
        + check_plugin_manifest(root)
        + check_skills(root)
        + check_links(root)
        + check_ids(root, RULE_ID, RULE_INDEX, "rule id")
        + check_ids(root, CAP_ID, PROFILE_TEMPLATE, "capability id")
        + check_tracked_files(root, denylist)
    )
    for finding in findings:
        if finding.warning:
            print(f"{finding.path}:{finding.line}: warning: {finding.message}", file=sys.stderr)
        else:
            print(f"{finding.path}:{finding.line}: {finding.message}")
    return 1 if any(not f.warning for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
