import contextlib
import importlib.util
import io
import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "plugins/game-server/skills/server-profile/scripts/check_profile.py"
FIXTURES = ROOT / "tests/fixtures/profile"
TEMPLATE = ROOT / "plugins/game-server/skills/server-profile/references/profile-template.md"

spec = importlib.util.spec_from_file_location("check_profile", SCRIPT)
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


def run(*args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = check.main([str(a) for a in args])
    return code, out.getvalue().splitlines(), err.getvalue().splitlines()


def line_of(path, text):
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if text in line:
            return number
    raise AssertionError(f"{text!r} not in {path}")


class CheckProfileTest(unittest.TestCase):
    def failures(self, name):
        path = FIXTURES / name
        code, out, _ = run(path)
        self.assertEqual(code, 1, out)
        for line in out:
            self.assertRegex(line, rf"^{re.escape(str(path))}:\d+: ")
        return path, out

    def test_valid_profile_passes(self):
        code, out, _ = run(FIXTURES / "valid.md")
        self.assertEqual((code, out), (0, []))

    def test_missing_frontmatter_key(self):
        path, out = self.failures("missing-key.md")
        self.assertEqual(out, [f"{path}:1: missing frontmatter key lint.env_live_check"])

    def test_missing_capability_heading(self):
        path, out = self.failures("missing-cap-heading.md")
        self.assertEqual(out, [f"{path}:1: missing capability heading CAP-CLOCK"])

    def test_invalid_status(self):
        path, out = self.failures("invalid-status.md")
        line = line_of(path, "status: working")
        self.assertEqual(len(out), 1, out)
        self.assertTrue(out[0].startswith(f"{path}:{line}: "), out)
        self.assertIn("CAP-RNG", out[0])
        self.assertIn("working", out[0])

    def test_non_present_without_blocker_or_proposal(self):
        path, out = self.failures("no-blocker-proposal.md")
        lease = line_of(path, "### CAP-LEASE")
        bot = line_of(path, "### CAP-BOT")
        self.assertEqual(
            out,
            [
                f"{path}:{lease}: CAP-LEASE is missing and needs a proposal",
                f"{path}:{bot}: CAP-BOT is partial and needs a blocker",
            ],
        )

    def test_present_without_api_file_snippet(self):
        text = (FIXTURES / "valid.md").read_text(encoding="utf-8")
        head = text.index("### CAP-COMMAND")
        end = text.index("### CAP-RESPONSE")
        cut = text[:head] + "### CAP-COMMAND Command channel and ids\n\n- status: present\n\n" + text[end:]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "profile.md")
            path.write_text(cut, encoding="utf-8")
            code, out, _ = run(path)
        self.assertEqual(code, 1)
        self.assertEqual(
            [line.split(": ", 1)[1] for line in out],
            [
                "CAP-COMMAND is present and needs an api",
                "CAP-COMMAND is present and needs a file",
                "CAP-COMMAND is present and needs a snippet",
            ],
        )

    def test_partial_blocker_without_rule_id(self):
        text = (FIXTURES / "valid.md").read_text(encoding="utf-8").replace(
            "- blocker: BG-07 cannot be met for part of the cases.",
            "- blocker: Old clients cannot be told apart.",
        )
        heading = line_of(FIXTURES / "valid.md", "### CAP-CLIENTVER")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "profile.md")
            path.write_text(text, encoding="utf-8")
            code, out, _ = run(path)
        self.assertEqual(code, 1)
        self.assertEqual(out, [f"{path}:{heading}: CAP-CLIENTVER is partial and its blocker names no rule id"])

    def test_unreadable_profile(self):
        path = FIXTURES / "does-not-exist.md"
        code, out, _ = run(path)
        self.assertEqual((code, out), (1, [f"{path}:1: file not found"]))

    def test_no_frontmatter(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "profile.md")
            path.write_text("# Profile\n", encoding="utf-8")
            code, out, _ = run(path)
        self.assertEqual(code, 1)
        self.assertEqual(out[0], f"{path}:1: missing frontmatter block")

    def test_required_sets_come_from_the_template(self):
        keys, caps = check.load_template(TEMPLATE)
        template = TEMPLATE.read_text(encoding="utf-8")
        headings = re.findall(r"^### (CAP-[A-Z]+)\b", template, re.M)
        self.assertEqual(caps, headings)
        self.assertIn("lint.time_call", keys)
        self.assertIn("profile_version", keys)
        self.assertNotIn("lint", keys)
        self.assertNotIn("lint.command_method", keys)

    def test_blocked_rules_lists_rules_per_non_present_capability(self):
        code, out, _ = run("--blocked-rules", FIXTURES / "valid.md")
        self.assertEqual(code, 0, out)
        by_cap = {line.split(" ")[0]: line for line in out}
        self.assertEqual(set(by_cap), {"CAP-CLIENTVER", "CAP-DRAIN", "CAP-LEASE", "CAP-BOT"})
        self.assertRegex(by_cap["CAP-LEASE"], r"^CAP-LEASE \(missing\): .*\bMN-07\b")
        self.assertRegex(by_cap["CAP-BOT"], r"^CAP-BOT \(partial\): .*\bTEST-\d\d\b")

    def test_partial_blocks_only_the_rules_on_its_blocker_line(self):
        code, out, _ = run("--blocked-rules", FIXTURES / "valid.md")
        self.assertEqual(code, 0, out)
        self.assertIn("CAP-CLIENTVER (partial): BG-07", out)
        self.assertIn("CAP-DRAIN (missing): BG-10", out)

    def test_blocked_rules_is_silent_when_the_profile_fails(self):
        code, out, _ = run("--blocked-rules", FIXTURES / "missing-key.md")
        self.assertEqual(code, 1)
        self.assertEqual(len(out), 1, out)


if __name__ == "__main__":
    unittest.main()
