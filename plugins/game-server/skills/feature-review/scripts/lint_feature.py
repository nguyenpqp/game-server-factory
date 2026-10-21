#!/usr/bin/env python3
"""Lint Java feature code for the rule breaks a regex can find.

Usage: lint_feature.py --profile <profile.md> <path>...

Reads the `lint` keys, `feature_root`, `test_root`, and `generated_paths` from the
profile's frontmatter, scans the .java files under each path, and prints one line
per finding as `path:line: <RULE-ID> message`.

Exit codes: 0 when clean, 1 when any finding exists, 2 when the profile, a regex, or
a path cannot be used.

Checks, with the rule each reports. A check whose profile value is empty is skipped.

- AUTH-02: a line matches a `forbidden_time` pattern.
- AUTH-03: a line matches a `forbidden_random` pattern.
- MN-01: a static field that is not final, or a `static final` mutable collection,
  array, or atomic holder. The config snapshot reference is exempt: a `volatile`
  static field whose type ends with `Config`, or an `AtomicReference<T>` whose `T`
  ends with `Config`.
  A `static final` collection built by `List.of`, `Set.of`, `Map.of`, `copyOf`, or
  `Collections.unmodifiable*` is immutable and exempt.
- CHEAT-02: a class whose signature (annotations, modifiers, extends, implements)
  matches `cheat_marker` has no `env_live_check` match in its body. This finds a
  class with no live check at all. Whether the check guards each mutation stays a
  review question.
- MET-01 and MET-02: a command class has no `metric_call` match (MET-01) or no
  `trace_id_call` match (MET-02) in its body. A command class is a class under
  `feature_root` that declares a method whose name matches `command_method`, or
  `handle\\w*` when the profile has no such key. A metric call in a shared helper or
  base class is a false finding, so treat the line as a prompt to check. When no
  checked class under `feature_root` is a command class, one note goes to stderr.
- PERF-01: a line matches a `blocking_calls` pattern.

`time_call` and `random_call` name the approved calls. The reviewer uses them, and the
linter does not.

Comments and string, text block, and character literals are blanked before any
pattern runs, so a commented-out call is not a finding. Import and package lines are
skipped. Files under `generated_paths` and `test_root` are skipped, even when named
on the command line. These paths and `feature_root` are relative to the repository
root, the directory that holds `docs/game-server/profile.md`.
"""
import argparse
import json
import re
import sys
from collections import namedtuple
from pathlib import Path

Finding = namedtuple("Finding", "path line rule message")

RULE_TIME = "AUTH-02"
RULE_RANDOM = "AUTH-03"
RULE_STATIC = "MN-01"
RULE_CHEAT_ENV = "CHEAT-02"
RULE_METRIC = "MET-01"
RULE_TRACE = "MET-02"
RULE_BLOCKING = "PERF-01"

LINT_KEYS = (
    "time_call", "forbidden_time", "random_call", "forbidden_random", "env_live_check",
    "metric_call", "trace_id_call", "command_method", "cheat_marker", "blocking_calls",
)
LIST_KEYS = {"forbidden_time", "forbidden_random", "blocking_calls"}
DEFAULT_COMMAND_METHOD = r"handle\w*"

TYPE_KEYWORD = re.compile(r"(?<![.\w@])(?:class|interface|enum|record)\s+([A-Za-z_]\w*)")
STATIC_KEYWORD = re.compile(r"\bstatic\b")
ANNOTATION = re.compile(r"@\w+(?:\.\w+)*\s*(?:\([^()]*\))?")
ANNOTATION_ARGS = re.compile(r"@\w+(?:\.\w+)*\s*\(")
SNAPSHOT_HOLDER = re.compile(r"\bAtomicReference\s*<\s*([\w.]+)\s*>")
GENERICS = re.compile(r"<[^<>]*>")
BRACES = re.compile(r"[{}]")
FIELD_END = re.compile(r"[=;({]")
METHOD_DECLARATION = re.compile(
    r"(?<![\w.])(?!(?:return|new|else|throw|case)\b)[\w<>\[\],.?]+\s+([A-Za-z_]\w*)\s*\("
)
SKIPPED_LINE = re.compile(r"^\s*(?:import|package)\b")
TYPE_WORDS = {"class", "interface", "enum", "record"}
MODIFIERS = {
    "public", "protected", "private", "static", "final", "volatile", "transient",
    "abstract", "synchronized", "native", "strictfp",
}
MUTABLE_TYPE = re.compile(
    r"(?:\w*(?:Map|List|Set|Queue|Deque|Collection|Stack|Vector)"
    r"|Atomic\w+|LongAdder|DoubleAdder|Concurrent\w+|CopyOnWrite\w+|StringBuilder|Properties)"
)
IMMUTABLE_INIT = re.compile(
    r"(?:(?:Map|List|Set)\.(?:of|ofEntries|copyOf)\(|Collections\.(?:unmodifiable|empty|singleton)\w*\(|Immutable\w+\.)"
)


class UsageError(Exception):
    pass


def strip_comment(text):
    text = text.strip()
    if text[:1] in ("'", '"'):
        quote, i = text[0], 1
        while i < len(text):
            if quote == "'" and text.startswith("''", i):
                i += 2
            elif text[i] == quote:
                break
            else:
                i += 2 if quote == '"' and text[i] == "\\" else 1
        rest = text[i + 1:].strip()
        return text[:i + 1] if rest.startswith("#") else text
    match = re.search(r"(?:^|\s)#", text)
    return text[:match.start()].rstrip() if match else text


def parse_scalar(text):
    text = strip_comment(text)
    if text == "[]":
        return []
    if len(text) >= 2 and text[0] == text[-1] == "'":
        return text[1:-1].replace("''", "'")
    if len(text) >= 2 and text[0] == text[-1] == '"':
        try:
            return json.loads(text)
        except ValueError:
            return text[1:-1]
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    return text


def parse_block(items, pos, indent, lines_of, prefix):
    if items[pos][1].startswith("- "):
        values = []
        while pos < len(items) and items[pos][0] == indent and items[pos][1].startswith("- "):
            values.append(parse_scalar(items[pos][1][2:]))
            pos += 1
        return values, pos
    result = {}
    while pos < len(items) and items[pos][0] == indent:
        _, text, number = items[pos]
        key, sep, value = text.partition(":")
        value = strip_comment(value)
        if not sep or not re.fullmatch(r"\w+", key):
            raise UsageError(f"line {number}: expected `key: value`")
        lines_of[prefix + key] = number
        pos += 1
        if value.strip():
            result[key] = parse_scalar(value)
        elif pos < len(items) and items[pos][0] > indent:
            result[key], pos = parse_block(items, pos, items[pos][0], lines_of, prefix + key + ".")
        else:
            result[key] = ""
    return result, pos


def parse_profile(text, lines_of=None):
    lines_of = {} if lines_of is None else lines_of
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise UsageError("no frontmatter: the file must start with ---")
    items = []
    for number, line in enumerate(lines[1:], start=2):
        if line.strip() == "---":
            break
        if line.strip() and not line.lstrip().startswith("#"):
            items.append((len(line) - len(line.lstrip(" ")), line.strip(), number))
    else:
        raise UsageError("frontmatter is not closed by ---")
    if not items:
        return {}
    data, pos = parse_block(items, 0, items[0][0], lines_of, "")
    if pos != len(items):
        raise UsageError(f"line {items[pos][2]}: unexpected indentation")
    return data


class Settings:
    def __init__(self, profile_path):
        try:
            text = Path(profile_path).read_text(encoding="utf-8")
        except OSError as error:
            raise UsageError(f"cannot read profile {profile_path}: {error.strerror}") from error
        lines_of = {}
        try:
            data = parse_profile(text, lines_of)
        except UsageError as error:
            raise UsageError(f"{profile_path}: {error}") from error
        raw = data.get("lint")
        if not isinstance(raw, dict):
            raise UsageError(f"{profile_path}: no lint block")
        self.patterns = {}
        for key in LINT_KEYS:
            value = raw.get(key, [] if key in LIST_KEYS else "")
            if key == "command_method" and key not in raw:
                value = DEFAULT_COMMAND_METHOD
            values = value if isinstance(value, list) else [value]
            compiled = []
            for pattern in filter(None, values):
                try:
                    compiled.append(re.compile(str(pattern)))
                except re.error as error:
                    number = lines_of.get(f"lint.{key}", 1)
                    raise UsageError(f"{profile_path}:{number}: lint.{key}: invalid regex: {error}") from error
            self.patterns[key] = compiled
        self.repo_root = Path(profile_path).resolve().parents[2]
        self.feature_root = str(data.get("feature_root") or "")
        generated = data.get("generated_paths") or []
        generated = generated if isinstance(generated, list) else [generated]
        self.skipped_roots = [str(root) for root in [data.get("test_root"), *generated] if root]

    def one(self, key):
        return self.patterns[key][0] if self.patterns[key] else None

    def under(self, path, root):
        parts = Path(root.strip("/")).parts
        try:
            relative = Path(path).resolve().relative_to(self.repo_root).parts
        except ValueError:
            return False
        return bool(parts) and relative[:len(parts)] == parts


def mask(text):
    out = list(text)
    n, i = len(text), 0

    def blank(start, end):
        for k in range(start, min(end, n)):
            if out[k] != "\n":
                out[k] = " "

    while i < n:
        if text.startswith("//", i):
            end = text.find("\n", i)
            end = n if end < 0 else end
            blank(i, end)
            i = end
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            end = n if end < 0 else end + 2
            blank(i, end)
            i = end
        elif text.startswith('"""', i):
            end = i + 3
            while end < n and not text.startswith('"""', end):
                end += 2 if text[end] == "\\" else 1
            blank(i + 3, end)
            i = min(end + 3, n)
        elif text[i] in "\"'":
            quote, end = text[i], i + 1
            while end < n and text[end] != quote and text[end] != "\n":
                end += 2 if text[end] == "\\" else 1
            blank(i + 1, end)
            i = end + 1
        else:
            i += 1
    return "".join(out)


class TypeSpan:
    def __init__(self, name, keyword_at, signature_at):
        self.name = name
        self.keyword_at = keyword_at
        self.signature_at = signature_at
        self.body_start = -1
        self.body_end = -1


def without_annotation_braces(masked):
    out = list(masked)
    for match in ANNOTATION_ARGS.finditer(masked):
        depth, i = 1, match.end()
        while i < len(masked) and depth:
            char = masked[i]
            depth += {"(": 1, ")": -1}.get(char, 0)
            if char in "{}":
                out[i] = " "
            i += 1
    return "".join(out)


def is_declaration(masked, match):
    tail = masked[match.end():match.end() + 400]
    brace, semicolon = tail.find("{"), tail.find(";")
    return brace >= 0 and (semicolon < 0 or brace < semicolon)


def type_spans(masked):
    events = [
        (m.start(), "type", m) for m in TYPE_KEYWORD.finditer(masked) if is_declaration(masked, m)
    ] + [(m.start(), m.group(), None) for m in BRACES.finditer(masked)]
    events.sort(key=lambda event: event[0])
    spans, stack, pending = [], [], None
    for at, kind, match in events:
        if kind == "type":
            start = max(masked.rfind(c, 0, at) for c in ";{}") + 1
            pending = TypeSpan(match.group(1), at, start)
        elif kind == "{":
            if pending is not None:
                pending.body_start = at
                spans.append(pending)
            stack.append(pending)
            pending = None
        else:
            span = stack.pop() if stack else None
            if span is not None:
                span.body_end = at
    return [s for s in spans if s.body_end >= 0]


def enclosing(spans, at):
    inside = [s for s in spans if s.body_start < at < s.body_end]
    return min(inside, key=lambda s: s.body_end - s.body_start) if inside else None


def line_of(masked, at):
    return masked.count("\n", 0, at) + 1


def scan_lines(path, masked, patterns, rule, label):
    findings = []
    for number, line in enumerate(masked.splitlines(), start=1):
        if SKIPPED_LINE.match(line):
            continue
        for pattern in patterns:
            match = pattern.search(line)
            if match:
                findings.append(Finding(path, number, rule, f"{label} `{match.group()}`"))
    return findings


def check_static(path, masked, spans):
    findings = []
    for match in STATIC_KEYWORD.finditer(masked):
        at = match.start()
        start = max(masked.rfind(c, 0, at) for c in "\n;{}") + 1
        stop = FIELD_END.search(masked, at)
        if not stop or SKIPPED_LINE.match(masked[start:at] + "static"):
            continue
        if stop.group() in "({":
            continue
        end = stop.start()
        header = ANNOTATION.sub("", masked[start:end])
        holder = SNAPSHOT_HOLDER.search(header)
        while True:
            header, count = GENERICS.subn("", header)
            if not count:
                break
        tokens = header.split()
        if TYPE_WORDS & set(tokens):
            continue
        mods = {t for t in tokens if t in MODIFIERS}
        names = [t for t in tokens if t not in MODIFIERS]
        if len(names) < 2:
            continue
        name = names[-1].split("[")[0]
        type_name = names[-2].split(".")[-1]
        owner = enclosing(spans, at)
        owner_name = owner.name if owner else ""
        if (type_name.endswith("Config") and "volatile" in mods) or (
                type_name == "AtomicReference" and holder and holder.group(1).endswith("Config")):
            continue
        line = line_of(masked, at)
        if "final" not in mods:
            findings.append(Finding(path, line, RULE_STATIC,
                                    f"non-final static field `{name}` in `{owner_name}` holds mutable state"))
            continue
        initializer = ""
        if stop.group() == "=":
            initializer = re.sub(r"\s+", "", masked[end + 1:end + 200].split(";")[0])
        if type_name.startswith(("Immutable", "Unmodifiable")) or IMMUTABLE_INIT.match(initializer):
            continue
        if "[" in header or MUTABLE_TYPE.fullmatch(type_name):
            findings.append(Finding(path, line, RULE_STATIC,
                                    f"static final mutable `{type_name}` field `{name}` in `{owner_name}`"))
    return findings


def check_cheat(path, masked, spans, settings):
    marker, live = settings.one("cheat_marker"), settings.one("env_live_check")
    if not marker or not live:
        return []
    findings = []
    for span in spans:
        signature = masked[span.signature_at:span.body_start]
        if marker.search(signature) and not live.search(masked[span.body_start:span.body_end]):
            findings.append(Finding(path, line_of(masked, span.keyword_at), RULE_CHEAT_ENV,
                                    f"cheat class `{span.name}` has no live environment check"))
    return findings


def declares_command_method(masked, span, spans, method):
    for match in METHOD_DECLARATION.finditer(masked, span.body_start + 1, span.body_end):
        if not method.fullmatch(match.group(1)):
            continue
        at = match.end()
        if enclosing(spans, at) is not span:
            continue
        depth, i = 1, at
        while i < len(masked) and depth:
            depth += {"(": 1, ")": -1}.get(masked[i], 0)
            i += 1
        rest = re.sub(r"^\s*throws\s+[\w.,\s]+", "", masked[i:i + 200])
        if rest.lstrip().startswith("{"):
            return True
    return False


def check_commands(path, masked, spans, settings):
    method = settings.one("command_method")
    if not method or not settings.under(path, settings.feature_root):
        return [], False
    metric, trace = settings.one("metric_call"), settings.one("trace_id_call")
    findings, found = [], False
    for span in spans:
        if not declares_command_method(masked, span, spans, method):
            continue
        found = True
        body = masked[span.body_start:span.body_end]
        line = line_of(masked, span.keyword_at)
        if metric and not metric.search(body):
            findings.append(Finding(path, line, RULE_METRIC, f"command class `{span.name}` has no metric call"))
        if trace and not trace.search(body):
            findings.append(Finding(path, line, RULE_TRACE, f"command class `{span.name}` mints no trace id"))
    return findings, found


def lint_file(path, settings):
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError as error:
        raise UsageError(f"{path}: cannot read: {error.strerror}") from error
    masked = mask(text)
    spans = type_spans(without_annotation_braces(masked))
    commands, found = check_commands(path, masked, spans, settings)
    return found, (
        scan_lines(path, masked, settings.patterns["forbidden_time"], RULE_TIME,
                   "server time must be injected, found")
        + scan_lines(path, masked, settings.patterns["forbidden_random"], RULE_RANDOM,
                     "random numbers must come from the injected source, found")
        + check_static(path, masked, spans)
        + check_cheat(path, masked, spans, settings)
        + commands
        + scan_lines(path, masked, settings.patterns["blocking_calls"], RULE_BLOCKING, "blocking call")
    )


def collect(paths, settings):
    files = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            files += sorted(path.rglob("*.java"))
        elif path.is_file():
            files.append(path)
        else:
            raise UsageError(f"{raw}: no such file or directory")
    return [f for f in files if not any(settings.under(f, root) for root in settings.skipped_roots)]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--profile", required=True, type=Path, help="docs/game-server/profile.md of the project")
    parser.add_argument("paths", nargs="+", help="Java files or directories")
    args = parser.parse_args(argv)
    try:
        settings = Settings(args.profile)
        findings, any_command = [], False
        for file in collect(args.paths, settings):
            found, file_findings = lint_file(str(file), settings)
            findings += file_findings
            any_command = any_command or found
    except UsageError as error:
        print(error, file=sys.stderr)
        return 2
    method = settings.one("command_method")
    if method and not any_command and (settings.one("metric_call") or settings.one("trace_id_call")):
        print(f"note: no class under feature_root declares a method matching lint.command_method "
              f"`{method.pattern}`, so MET-01 and MET-02 checked no class", file=sys.stderr)
    for finding in sorted(findings, key=lambda f: (f.path, f.line, f.rule)):
        print(f"{finding.path}:{finding.line}: {finding.rule} {finding.message}")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
