import contextlib
import importlib.util
import io
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "plugins" / "game-server" / "skills" / "feature-review"
SCRIPT = SKILL / "scripts" / "lint_feature.py"
CHECKLIST = SKILL / "references" / "review-checklist.md"
RULE_INDEX = ROOT / "plugins" / "game-server" / "skills" / "server-rules" / "references" / "index.md"
PROFILE_TEMPLATE = (
    ROOT / "plugins" / "game-server" / "skills" / "server-profile" / "references" / "profile-template.md"
)
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "lint"
PROFILE = FIXTURES / "docs" / "game-server" / "profile.md"
MAIN = FIXTURES / "src" / "main" / "java"
TEST_TREE = FIXTURES / "src" / "test" / "java"
DEMO = MAIN / "com" / "example" / "game" / "feature" / "demo"
FEATURE_DIR = "src/main/java/com/example/game/feature/demo"
SKILLS = ROOT / "plugins" / "game-server" / "skills"
NO_COMMAND_NOTE = "note: no class under feature_root declares a method matching lint.command_method"

spec = importlib.util.spec_from_file_location("lint_feature", SCRIPT)
lint = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lint)

RULE_TOKEN = re.compile(r"\b(?:AUTH|MN|BG|PERF|CFG|MET|CHEAT|ADMIN|HTTP|TEST)-\d{2}\b")
OUTPUT_LINE = re.compile(r"^(?P<path>.+?):(?P<line>\d+): (?P<rule>[A-Z]+-\d{2}) (?P<message>.+)$")
EXPECT = re.compile(r"//\s*EXPECT:\s*([A-Z0-9 -]+)$")


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = lint.main([str(a) for a in argv])
    return code, out.getvalue(), err.getvalue()


def parse_output(text):
    found = set()
    for line in text.splitlines():
        match = OUTPUT_LINE.match(line)
        assert match, f"output line does not match path:line: RULE message: {line!r}"
        found.add((Path(match["path"]).name, int(match["line"]), match["rule"]))
    return found


def expected_markers(path):
    expected = set()
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        match = EXPECT.search(line)
        if match:
            expected.update((path.name, number, rule) for rule in match.group(1).split())
    return expected


def index_ids():
    ids = set()
    for line in RULE_INDEX.read_text(encoding="utf-8").splitlines():
        match = re.match(r"###\s+(" + RULE_TOKEN.pattern + ")", line)
        if match:
            ids.add(match.group(1))
    return ids


def profile_with(replacements):
    text = PROFILE.read_text(encoding="utf-8")
    for old, new in replacements:
        assert old in text, old
        text = text.replace(old, new)
    profile = Path(tempfile.mkdtemp()) / "docs" / "game-server" / "profile.md"
    profile.parent.mkdir(parents=True)
    profile.write_text(text, encoding="utf-8")
    return profile


def write_repo(root, files, profile_text=None, replacements=()):
    text = PROFILE.read_text(encoding="utf-8") if profile_text is None else profile_text
    for old, new in replacements:
        assert old in text, old
        text = text.replace(old, new)
    profile = Path(root) / "docs" / "game-server" / "profile.md"
    profile.parent.mkdir(parents=True, exist_ok=True)
    profile.write_text(text, encoding="utf-8")
    for rel, content in files.items():
        path = Path(root) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return profile


def template_profile():
    text = PROFILE_TEMPLATE.read_text(encoding="utf-8")
    return re.search(r"```yaml\n(---\n.*?\n---)\n```", text, re.S).group(1) + "\n"


def reference_snippets():
    snippets = []
    for path in sorted((SKILLS / "server-rules" / "references").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        snippets += [(path.name, b) for b in re.findall(r"^Do:\n\n```java\n(.*?)^```", text, re.M | re.S)]
    for path in sorted((SKILLS / "feature-build" / "references").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        snippets += [(path.name, b) for b in re.findall(r"^```java\n(.*?)^```", text, re.M | re.S)]
    return snippets


class FixtureChecks(unittest.TestCase):
    def check_file(self, name):
        path = DEMO / name
        code, out, err = run("--profile", PROFILE, path)
        self.assertEqual(parse_output(out), expected_markers(path))
        self.assertEqual(code, 1)
        self.assertTrue(err == "" or err.startswith(NO_COMMAND_NOTE), err)

    def test_forbidden_time_calls(self):
        self.check_file("ForbiddenTime.java")

    def test_forbidden_random_calls(self):
        self.check_file("ForbiddenRandom.java")

    def test_static_mutable_state(self):
        self.check_file("StaticState.java")

    def test_cheat_class_without_live_check(self):
        self.check_file("CheatNoEnv.java")

    def test_command_class_without_metric_or_trace(self):
        self.check_file("CommandNoMetric.java")

    def test_command_class_without_trace_id_only(self):
        self.check_file("CommandNoTrace.java")

    def test_blocking_calls(self):
        self.check_file("Blocking.java")

    def test_clean_file_has_no_findings(self):
        code, out, err = run("--profile", PROFILE, DEMO / "Clean.java")
        self.assertEqual((code, out, err), (0, "", ""))

    def test_output_line_format(self):
        _, out, _ = run("--profile", PROFILE, DEMO / "ForbiddenTime.java")
        first = out.splitlines()[0]
        self.assertTrue(first.startswith(f"{DEMO / 'ForbiddenTime.java'}:8: AUTH-02 "), first)


class Scope(unittest.TestCase):
    def test_directory_scan_skips_generated_and_test_roots(self):
        code, out, _ = run("--profile", PROFILE, MAIN, TEST_TREE)
        expected = set()
        for path in sorted(DEMO.glob("*.java")):
            expected |= expected_markers(path)
        self.assertEqual(parse_output(out), expected)
        self.assertEqual(code, 1)
        self.assertNotIn("Generated.java", out)
        self.assertNotIn("ClockTest.java", out)

    def test_command_check_applies_only_under_feature_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            outside = Path(tmp) / "util" / "ClaimHandler.java"
            outside.parent.mkdir()
            outside.write_text(
                "final class ClaimHandler {\n    Result handle(Object r) { return null; }\n}\n",
                encoding="utf-8",
            )
            code, out, _ = run("--profile", PROFILE, outside)
        self.assertEqual((code, out), (0, ""))

    def test_roots_compare_path_components_from_the_repo_root(self):
        forbidden = "final class A {\n    long t() { return System.currentTimeMillis(); }\n}\n"
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "test" / "repo"
            profile = write_repo(
                repo,
                {
                    f"{FEATURE_DIR}/test/Foo.java": forbidden,
                    f"{FEATURE_DIR}/Bar.java": forbidden,
                    "test/Skipped.java": forbidden,
                },
                replacements=[("test_root: 'src/test/java'", "test_root: 'test'")],
            )
            code, out, _ = run("--profile", profile, repo)
        self.assertEqual({name for name, _, _ in parse_output(out)}, {"Foo.java", "Bar.java"})
        self.assertEqual(code, 1)

    def test_a_scalar_generated_paths_is_one_path(self):
        forbidden = "final class A {\n    long t() { return System.currentTimeMillis(); }\n}\n"
        with tempfile.TemporaryDirectory() as tmp:
            profile = write_repo(
                tmp,
                {"src/gen/Gen.java": forbidden, "src/gens/Kept.java": forbidden},
                replacements=[("generated_paths:\n  - 'src/main/java/com/example/game/generated'\n",
                               "generated_paths: 'src/gen'\n")],
            )
            code, out, _ = run("--profile", profile, tmp)
        self.assertEqual({name for name, _, _ in parse_output(out)}, {"Kept.java"})


class CommandClasses(unittest.TestCase):
    def lint_one(self, source, replacements=()):
        with tempfile.TemporaryDirectory() as tmp:
            profile = write_repo(tmp, {f"{FEATURE_DIR}/Cmd.java": source}, replacements=replacements)
            return run("--profile", profile, Path(tmp) / FEATURE_DIR / "Cmd.java")

    def test_a_handle_client_request_class_without_a_metric_call_fails(self):
        source = (
            "final class ClaimHandler {\n"
            "    public void handleClientRequest(User user, DataCmd cmd) {\n"
            "        String trace = TraceIds.next();\n"
            "    }\n"
            "}\n"
        )
        code, out, err = self.lint_one(source)
        self.assertEqual(parse_output(out), {("Cmd.java", 1, "MET-01")})
        self.assertEqual((code, err), (1, ""))

    def test_the_profile_names_the_command_method(self):
        source = "final class ClaimHandler {\n    Result execute(Request r) { return null; }\n}\n"
        code, out, _ = self.lint_one(
            source, [("  cheat_marker:", "  command_method: 'execute'\n  cheat_marker:")]
        )
        self.assertEqual(parse_output(out), {("Cmd.java", 1, "MET-01"), ("Cmd.java", 1, "MET-02")})
        code, out, _ = self.lint_one(source)
        self.assertEqual((code, out), (0, ""))

    def test_no_command_class_prints_one_note_and_keeps_the_exit_code(self):
        code, out, err = self.lint_one("final class Util {\n    int one() { return 1; }\n}\n")
        self.assertEqual((code, out), (0, ""))
        self.assertEqual(len(err.splitlines()), 1, err)
        self.assertTrue(err.startswith(NO_COMMAND_NOTE), err)


class ClassSignatures(unittest.TestCase):
    def test_braces_inside_annotation_arguments_keep_the_cheat_check(self):
        source = (
            '@CheatCommand(names = {"a", "b"})\n'
            "final class GrantCheat {\n"
            "    void apply(UserActor user) { user.add(1); }\n"
            "}\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            profile = write_repo(tmp, {f"{FEATURE_DIR}/GrantCheat.java": source})
            code, out, _ = run("--profile", profile, Path(tmp) / FEATURE_DIR / "GrantCheat.java")
        self.assertEqual(parse_output(out), {("GrantCheat.java", 2, "CHEAT-02")})

    def test_config_snapshot_fields_are_exempt_by_their_type(self):
        source = (
            "import java.util.concurrent.atomic.AtomicReference;\n"
            "final class StreakService {\n"
            "    private static volatile StreakConfig config;\n"
            "    static final AtomicReference<StreakConfig> REF = new AtomicReference<>();\n"
            "}\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            profile = write_repo(tmp, {"src/main/java/StreakService.java": source})
            code, out, _ = run("--profile", profile, Path(tmp) / "src/main/java/StreakService.java")
        self.assertEqual((code, out), (0, ""))


class ReferenceSnippets(unittest.TestCase):
    def test_every_do_snippet_and_build_reference_snippet_lints_clean(self):
        snippets = reference_snippets()
        self.assertGreater(len(snippets), 40)
        with tempfile.TemporaryDirectory() as tmp:
            files = {f"{FEATURE_DIR}/Snippet{n:03d}.java": body for n, (_, body) in enumerate(snippets)}
            profile = write_repo(tmp, files, profile_text=template_profile())
            failures = []
            for n, (source, _) in enumerate(snippets):
                code, out, err = run("--profile", profile, Path(tmp) / FEATURE_DIR / f"Snippet{n:03d}.java")
                if code == 2 or out:
                    failures.append(f"{source} snippet {n}: {out or err}")
        self.assertEqual(failures, [], "\n".join(failures))


class ProfileKeys(unittest.TestCase):
    def test_empty_list_skips_the_check(self):
        profile = profile_with(
            [("  forbidden_time:\n    - 'System\\.currentTimeMillis\\('\n    - 'Instant\\.now\\('\n"
              "    - 'LocalDate(Time)?\\.now\\('\n    - 'new Date\\(\\)'\n", "  forbidden_time: []\n")]
        )
        code, out, _ = run("--profile", profile, DEMO / "ForbiddenTime.java")
        self.assertEqual((code, out), (0, ""))

    def test_empty_string_skips_the_check(self):
        profile = profile_with([("  cheat_marker: '@CheatCommand'", "  cheat_marker: ''")])
        code, out, _ = run("--profile", profile, DEMO / "CheatNoEnv.java")
        self.assertEqual((code, out), (0, ""))

    def test_profile_patterns_drive_the_check(self):
        profile = profile_with([("'Math\\.random\\('", "'Dice\\.roll\\('")])
        code, out, _ = run("--profile", profile, DEMO / "ForbiddenRandom.java")
        self.assertEqual({line for _, line, _ in parse_output(out)}, {7, 9})

    def test_invalid_regex_is_a_usage_error(self):
        profile = profile_with([("'Math\\.random\\('", "'Math(random'")])
        code, out, err = run("--profile", profile, DEMO / "ForbiddenRandom.java")
        self.assertEqual((code, out), (2, ""))
        self.assertIn("forbidden_random", err)

    def test_missing_profile_and_missing_path_are_usage_errors(self):
        self.assertEqual(run("--profile", FIXTURES / "nope.md", DEMO)[0], 2)
        code, _, err = run("--profile", PROFILE, FIXTURES / "nope")
        self.assertEqual(code, 2)
        self.assertIn("nope", err)

    def test_a_profile_outside_docs_game_server_is_a_usage_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp) / "profile.md"
            profile.write_text(PROFILE.read_text(encoding="utf-8"), encoding="utf-8")
            code, out, err = run("--profile", profile, DEMO / "ForbiddenTime.java")
        self.assertEqual((code, out), (2, ""))
        self.assertEqual(len(err.splitlines()), 1)
        self.assertIn("docs/game-server/profile.md", err)

    def test_real_profile_template_parses(self):
        text = PROFILE_TEMPLATE.read_text(encoding="utf-8")
        block = re.search(r"```yaml\n(---\n.*?\n---)\n```", text, re.S).group(1)
        data = lint.parse_profile(block)
        self.assertEqual(data["profile_version"], 1)
        self.assertEqual(data["lint"]["cheat_marker"], "@CheatCommand")
        self.assertEqual(len(data["lint"]["forbidden_time"]), 4)
        self.assertEqual(data["generated_paths"], ["src/main/java/com/example/game/generated"])
        self.assertEqual(data["lint"]["command_method"], "handle\\w*")

    def test_a_trailing_comment_after_a_scalar_is_dropped(self):
        data = lint.parse_profile(
            "---\n"
            "lint:  # patterns\n"
            "  time_call: 'ServerClock\\.now\\(' # the clock\n"
            "  plain: abc # note\n"
            "  hashed: 'a # b'\n"
            "  forbidden_time:\n"
            "    - 'Instant\\.now\\(' # legacy\n"
            "---\n"
        )
        self.assertEqual(
            data["lint"],
            {"time_call": "ServerClock\\.now\\(", "plain": "abc", "hashed": "a # b",
             "forbidden_time": ["Instant\\.now\\("]},
        )

    def test_a_commented_cheat_marker_still_drives_the_check(self):
        profile = profile_with([("  cheat_marker: '@CheatCommand'", "  cheat_marker: '@CheatCommand' # marker")])
        code, out, _ = run("--profile", profile, DEMO / "CheatNoEnv.java")
        self.assertEqual({rule for _, _, rule in parse_output(out)}, {"CHEAT-02"})


class RuleIds(unittest.TestCase):
    def test_every_rule_id_in_the_script_is_in_the_index(self):
        used = set(RULE_TOKEN.findall(SCRIPT.read_text(encoding="utf-8")))
        self.assertTrue(used)
        self.assertEqual(used - index_ids(), set())

    def test_every_reported_rule_id_is_in_the_index(self):
        _, out, _ = run("--profile", PROFILE, MAIN)
        reported = {rule for _, _, rule in parse_output(out)}
        self.assertEqual(
            reported,
            {"AUTH-02", "AUTH-03", "MN-01", "CHEAT-02", "MET-01", "MET-02", "PERF-01"},
        )
        self.assertEqual(reported - index_ids(), set())


class Checklist(unittest.TestCase):
    def test_checklist_severities_match_the_index(self):
        severities, current = {}, None
        for line in RULE_INDEX.read_text(encoding="utf-8").splitlines():
            head = re.match(r"###\s+(" + RULE_TOKEN.pattern + ")", line)
            if head:
                current = head.group(1)
            elif current and line.startswith("- severity:"):
                severities[current] = line.split(":", 1)[1].strip()
                current = None
        rows = {}
        for line in CHECKLIST.read_text(encoding="utf-8").splitlines():
            match = re.match(r"\|\s*(" + RULE_TOKEN.pattern + r")\s*\|\s*(\w+)\s*\|", line)
            if match:
                rows[match.group(1)] = match.group(2)
        self.assertEqual(rows, severities)


class CommandLine(unittest.TestCase):
    def test_exit_code_and_output_through_the_shell(self):
        bad = subprocess.run(
            [sys.executable, str(SCRIPT), "--profile", str(PROFILE), str(DEMO / "Blocking.java")],
            capture_output=True, text=True,
        )
        self.assertEqual(bad.returncode, 1)
        self.assertEqual(len(bad.stdout.splitlines()), 4)
        good = subprocess.run(
            [sys.executable, str(SCRIPT), "--profile", str(PROFILE), str(DEMO / "Clean.java")],
            capture_output=True, text=True,
        )
        self.assertEqual((good.returncode, good.stdout), (0, ""))


if __name__ == "__main__":
    unittest.main()
