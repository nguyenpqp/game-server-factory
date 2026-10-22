import re
import tempfile
import unittest
from pathlib import Path

from helpers import load_script, run_main

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "plugins/game-server/skills/server-profile/scripts/check_profile.py"
FIXTURES = ROOT / "tests/fixtures/profile"
TEMPLATE = ROOT / "plugins/game-server/skills/server-profile/references/profile-template.md"
DECISIONS_TEMPLATE = ROOT / "plugins/game-server/skills/feature-spec/references/decisions-template.md"

check = load_script(SCRIPT)


def run(*args):
    code, out, err = run_main(check, args)
    return code, out.splitlines(), err.splitlines()


def run_text(text, *flags):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp, "profile.md")
        path.write_text(text, encoding="utf-8")
        return (path, *run(*flags, path))


def line_of(path, text):
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if text in line:
            return number
    raise AssertionError(f"{text!r} not in {path}")


def run_decisions(text, *flags, profile=FIXTURES / "valid.md"):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp, "decisions.md")
        path.write_text(text, encoding="utf-8")
        return (path, *run(*flags, "--decisions", path, profile))


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
        _, code, out, _ = run_text(cut)
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
        path, code, out, _ = run_text(text)
        self.assertEqual(code, 1)
        self.assertEqual(out, [f"{path}:{heading}: CAP-CLIENTVER is partial and its blocker names no rule id"])

    def test_unreadable_profile(self):
        path = FIXTURES / "does-not-exist.md"
        code, out, _ = run(path)
        self.assertEqual((code, out), (1, [f"{path}:1: file not found"]))

    def test_no_frontmatter(self):
        path, code, out, _ = run_text("# Profile\n")
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
        self.assertIn("CAP-DRAIN (missing): BG-10, BG-13", out)

    def test_valid_profile_prints_no_warning(self):
        code, _, err = run(FIXTURES / "valid.md")
        self.assertEqual((code, err), (0, []))

    def test_a_blocker_id_off_the_capability_needs_lines_warns(self):
        text = (FIXTURES / "valid.md").read_text(encoding="utf-8").replace(
            "- blocker: BG-07 cannot be met for part of the cases.",
            "- blocker: BG-07 and MN-10 cannot be met for part of the cases.",
        )
        heading = line_of(FIXTURES / "valid.md", "### CAP-CLIENTVER")
        path, code, out, err = run_text(text, "--blocked-rules")
        self.assertEqual(code, 0, out)
        self.assertIn("CAP-CLIENTVER (partial): BG-07, MN-10", out)
        self.assertEqual(len(err), 1, err)
        self.assertTrue(err[0].startswith(f"warning: {path}:{heading}: "), err)
        self.assertIn("CAP-CLIENTVER", err[0])
        self.assertIn("MN-10", err[0])
        self.assertNotIn("BG-07", err[0])

    def test_blocked_rules_is_silent_when_the_profile_fails(self):
        code, out, _ = run("--blocked-rules", FIXTURES / "missing-key.md")
        self.assertEqual(code, 1)
        self.assertEqual(len(out), 1, out)


class CheckDecisionsTest(unittest.TestCase):
    HEADER = re.search(r"^\| Id \|.*$", DECISIONS_TEMPLATE.read_text(encoding="utf-8"), re.M).group(0)
    COLUMNS = check.DECISION_COLUMNS
    GOOD = dict(zip(COLUMNS, ("D1", "CAP-LEASE", "missing", "MN-07", "One node per realm",
                              "No second node runs the job", "An", "2026-10-22")))

    def file(self, *rows):
        lines = ["# Project decisions", "", self.HEADER, "| " + " | ".join(["---"] * 8) + " |"]
        for row in rows:
            cells = {**self.GOOD, **row}
            lines.append("| " + " | ".join(cells[column] for column in self.COLUMNS) + " |")
        return "\n".join(lines) + "\n"

    def messages(self, *rows, **kw):
        path, code, out, err = run_decisions(self.file(*rows), **kw)
        self.assertEqual(code, 1, out)
        for line in out:
            self.assertRegex(line, rf"^{re.escape(str(path))}:\d+: ")
        return path, out

    def one_error(self, row, *words, line=5, before=()):
        path, out = self.messages(*before, row)
        self.assertEqual(len(out), 1, out)
        self.assertTrue(out[0].startswith(f"{path}:{line}: "), out)
        for word in words:
            self.assertIn(word, out[0])

    def test_valid_decisions_pass_silently(self):
        rows = [{}, {"Id": "D2", "Capability": "CAP-DRAIN", "Rules": "BG-10, BG-13"},
                {"Id": "D3", "Capability": "CAP-BOT", "Profile status": "partial", "Rules": "TEST-10"}]
        _, code, out, err = run_decisions(self.file(*rows))
        self.assertEqual((code, out, err), (0, [], []))

    def test_missing_decisions_file(self):
        path = FIXTURES / "no-decisions.md"
        code, out, _ = run("--decisions", path, FIXTURES / "valid.md")
        self.assertEqual((code, out), (1, [f"{path}:1: file not found"]))

    def test_file_without_the_template_table(self):
        path, code, out, _ = run_decisions("# Project decisions\n\nNothing yet.\n")
        self.assertEqual(code, 1)
        self.assertEqual(len(out), 1, out)
        self.assertTrue(out[0].startswith(f"{path}:1: no table"), out)

    def test_file_that_is_not_utf8(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "decisions.md")
            path.write_bytes(self.file().encode("utf-8") + b"\xff\xfe\n")
            code, out, _ = run("--decisions", path, FIXTURES / "valid.md")
        self.assertEqual(code, 1)
        self.assertEqual(len(out), 1, out)
        self.assertTrue(out[0].startswith(f"{path}:1: cannot read"), out)

    def test_header_without_a_separator_row(self):
        text = self.file().replace("| " + " | ".join(["---"] * 8) + " |\n", "")
        path, code, out, _ = run_decisions(text)
        self.assertEqual(code, 1)
        self.assertEqual(len(out), 1, out)
        self.assertTrue(out[0].startswith(f"{path}:1: "), out)
        self.assertIn("separator", out[0])

    def test_rows_split_off_by_a_blank_line(self):
        moved = "| " + " | ".join({**self.GOOD, "Id": "D2", "Date": "soon"}[c] for c in self.COLUMNS) + " |\n"
        path, code, out, _ = run_decisions(self.file({}) + "\n" + moved)
        self.assertEqual(code, 1)
        self.assertEqual(len(out), 1, out)
        self.assertTrue(out[0].startswith(f"{path}:1: line 7 starts another table"), out)

    def test_columns_in_another_order_are_not_the_table(self):
        swapped = self.HEADER.replace("Capability | Profile status", "Profile status | Capability")
        path, code, out, _ = run_decisions(self.file().replace(self.HEADER, swapped))
        self.assertEqual(code, 1)
        self.assertTrue(out[0].startswith(f"{path}:1: no table"), out)

    def test_template_header_matches_the_checker(self):
        self.assertEqual(tuple(check.row_cells(self.HEADER)), check.DECISION_COLUMNS)

    def test_escaped_pipe_stays_inside_its_cell(self):
        _, code, out, _ = run_decisions(self.file({"Deployment fact": "One node per realm \\| stop then start"}))
        self.assertEqual((code, out), (0, []))

    def test_id_must_be_d_and_digits(self):
        for id in ("X1", "D01", "D0", "D"):
            with self.subTest(id=id):
                self.one_error({"Id": id}, id, "D")

    def test_repeated_id(self):
        self.one_error({"Capability": "CAP-DRAIN", "Rules": "BG-10"}, "D1", "repeats", "line 5",
                       line=6, before=({},))

    def test_unknown_capability(self):
        self.one_error({"Capability": "CAP-NOPE"}, "CAP-NOPE", "capability")

    def test_recorded_status_must_be_partial_or_missing(self):
        self.one_error({"Profile status": "present"}, "present", "partial or missing")

    def test_rules_cell_without_a_rule_id(self):
        self.one_error({"Rules": ""}, "D1", "no rule id")

    def test_rule_not_in_the_index(self):
        self.one_error({"Rules": "MN-07, MN-99"}, "MN-99", "rule index")

    def test_rule_the_capability_does_not_block(self):
        self.one_error({"Rules": "MN-07, MN-02"}, "MN-02", "CAP-LEASE", "does not block", "re-decide")

    def test_partial_capability_blocks_only_its_blocker_line(self):
        row = {"Capability": "CAP-CLIENTVER", "Profile status": "partial"}
        self.one_error({**row, "Rules": "BG-07, BG-04"}, "BG-04", "CAP-CLIENTVER", "does not block")
        _, code, out, _ = run_decisions(self.file({**row, "Rules": "BG-07"}))
        self.assertEqual((code, out), (0, []))

    def test_rule_on_the_blocker_line_outside_its_needs_line(self):
        text = (FIXTURES / "valid.md").read_text(encoding="utf-8").replace(
            "- blocker: BG-07 cannot be met for part of the cases.",
            "- blocker: BG-07 and MN-10 cannot be met for part of the cases.",
        )
        row = {"Capability": "CAP-CLIENTVER", "Profile status": "partial", "Rules": "MN-10"}
        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp, "profile.md")
            profile.write_text(text, encoding="utf-8")
            _, code, out, _ = run_decisions(self.file(row), profile=profile)
        self.assertEqual((code, out), (0, []))

    def test_perf_01_is_never_accepted_in_decisions(self):
        self.one_error({"Capability": "CAP-BOT", "Profile status": "partial", "Rules": "PERF-01"},
                       "PERF-01", "per call site", "never in decisions")

    def test_empty_cells(self):
        for column in ("Deployment fact", "How it bounds the failure", "Accepted by"):
            with self.subTest(column=column):
                self.one_error({column: ""}, "empty", column)

    def test_malformed_dates(self):
        for date in ("", "22-10-2026", "2026-1-2", "2026-02-30", "soon"):
            with self.subTest(date=date):
                self.one_error({"Date": date}, "YYYY-MM-DD")

    def test_stale_decision_must_be_re_decided(self):
        self.one_error({"Profile status": "partial"}, "stale", "partial", "missing", "re-decide")

    def test_present_capability_warns_and_exits_zero(self):
        path, code, out, err = run_decisions(self.file({"Capability": "CAP-OWNERSHIP", "Rules": "MN-02"}))
        self.assertEqual((code, out), (0, []))
        self.assertEqual(len(err), 1, err)
        self.assertTrue(err[0].startswith(f"warning: {path}:5: "), err)
        self.assertIn("CAP-OWNERSHIP", err[0])
        self.assertIn("no longer needed", err[0])

    def test_present_capability_with_a_bad_cell_still_fails(self):
        _, code, out, err = run_decisions(self.file({"Capability": "CAP-OWNERSHIP", "Rules": "MN-02", "Date": ""}))
        self.assertEqual(code, 1)
        self.assertEqual(len(out), 1, out)
        self.assertEqual(len(err), 1, err)

    def test_each_failing_row_reports_its_own_line(self):
        path, out = self.messages({"Date": "soon"}, {"Id": "D2", "Capability": "CAP-DRAIN", "Rules": "MN-07"})
        self.assertEqual(len(out), 2, out)
        self.assertTrue(out[0].startswith(f"{path}:5: "), out)
        self.assertTrue(out[1].startswith(f"{path}:6: "), out)

    def test_row_with_the_wrong_cell_count(self):
        text = self.file() + "| D2 | CAP-DRAIN |\n"
        path, code, out, _ = run_decisions(text)
        self.assertEqual(code, 1)
        self.assertEqual(len(out), 1, out)
        self.assertTrue(out[0].startswith(f"{path}:5: "), out)

    def test_decisions_do_not_change_profile_checking(self):
        code, out, _ = run("--decisions", FIXTURES / "does-not-exist.md", FIXTURES / "missing-key.md")
        self.assertEqual(code, 1)
        self.assertIn(f"{FIXTURES / 'missing-key.md'}:1: missing frontmatter key lint.env_live_check", out)

    def test_blocked_rules_still_prints_with_valid_decisions(self):
        _, code, out, _ = run_decisions(self.file(), "--blocked-rules")
        self.assertEqual(code, 0, out)
        self.assertIn("CAP-LEASE (missing): MN-07", out)

    def test_blocked_rules_is_silent_when_the_decisions_fail(self):
        _, code, out, _ = run_decisions(self.file({"Date": "soon"}), "--blocked-rules")
        self.assertEqual(code, 1)
        self.assertEqual(len(out), 1, out)

    def test_blocker_warning_still_prints_with_decisions(self):
        text = (FIXTURES / "valid.md").read_text(encoding="utf-8").replace(
            "- blocker: BG-07 cannot be met for part of the cases.",
            "- blocker: BG-07 and MN-10 cannot be met for part of the cases.",
        )
        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp, "profile.md")
            profile.write_text(text, encoding="utf-8")
            _, code, out, err = run_decisions(self.file(), profile=profile)
        self.assertEqual((code, out), (0, []))
        self.assertEqual(len(err), 1, err)
        self.assertIn("MN-10", err[0])


if __name__ == "__main__":
    unittest.main()
