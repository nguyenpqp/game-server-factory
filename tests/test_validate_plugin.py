import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "validate_plugin.py"
spec = importlib.util.spec_from_file_location("validate_plugin", SCRIPT)
validate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validate)

PLUGIN = "plugins/game-server/.claude-plugin/plugin.json"
SKILLS = "plugins/game-server/skills"
RULES_SKILL = f"{SKILLS}/server-rules/SKILL.md"
RULES_INDEX = f"{SKILLS}/server-rules/references/index.md"
PROFILE_SKILL = f"{SKILLS}/server-profile/SKILL.md"
PROFILE_TEMPLATE = f"{SKILLS}/server-profile/references/profile-template.md"
MARKETPLACE = ".claude-plugin/marketplace.json"

GOOD_MARKETPLACE = {
    "name": "game-server-factory",
    "owner": {"name": "Someone"},
    "plugins": [
        {
            "name": "game-server",
            "source": "./plugins/game-server",
            "description": "Game server feature skills.",
        }
    ],
}
GOOD_PLUGIN = {
    "name": "game-server",
    "description": "Game server feature skills.",
    "author": {"name": "Someone"},
    "license": "MIT",
    "keywords": ["game", "server"],
}


def skill_md(name, description="Rules for server features.", extra=""):
    return f"---\nname: {name}\ndescription: {description}\n{extra}---\n# {name}\n"


def good_tree():
    return {
        MARKETPLACE: json.dumps(GOOD_MARKETPLACE, indent=2),
        PLUGIN: json.dumps(GOOD_PLUGIN, indent=2),
        RULES_SKILL: skill_md("server-rules")
        + "See [index](references/index.md) and `references/index.md`.\n"
        + "Cites AUTH-01.\n",
        RULES_INDEX: "# Index\n\n### AUTH-01 Client sends intents only\n",
        PROFILE_SKILL: skill_md(
            "server-profile", extra="disable-model-invocation: true\n"
        )
        + "Template at `references/profile-template.md`, needs CAP-TIME.\n",
        PROFILE_TEMPLATE: "# Profile\n\n### CAP-TIME Server time\n",
    }


def write_tree(root, files):
    for rel, content in files.items():
        if content is None:
            continue
        path = Path(root, rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def git(root, *args):
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


class ValidatorTestCase(unittest.TestCase):
    def setUp(self):
        if shutil.which("git") is None:
            self.skipTest("git binary is missing")
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("GSS_DENYLIST", None)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name, "repo")
        self.root.mkdir()
        self.outside = Path(tmp.name, "outside")
        self.outside.mkdir()

    def build(self, changes=None):
        files = {**good_tree(), **(changes or {})}
        write_tree(self.root, files)
        git(self.root, "init", "-q")
        git(self.root, "add", "-A")

    def run_validator(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = validate.main(["--root", str(self.root), *args])
        return code, out.getvalue().splitlines(), err.getvalue().splitlines()

    def denylist(self, *terms):
        path = self.outside / "denylist.txt"
        path.write_text("\n".join(terms) + "\n", encoding="utf-8")
        return str(path)

    def assert_fails_at(self, location, *args):
        code, out, _ = self.run_validator(*args)
        self.assertEqual(code, 1, out)
        self.assertEqual(len(out), 1, out)
        self.assertTrue(out[0].startswith(location + ": "), out)
        return out[0]


class CleanTreeTest(ValidatorTestCase):
    def test_clean_tree_passes_silently(self):
        self.build()
        code, out, err = self.run_validator("--denylist", self.denylist("acme"))
        self.assertEqual((code, out, err), (0, [], []))

    def test_cli_prints_path_line_message_and_exits_1(self):
        self.build({RULES_SKILL: skill_md("wrong-name")})
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(self.root)],
            capture_output=True,
            text=True,
            env={k: v for k, v in os.environ.items() if k != "GSS_DENYLIST"},
        )
        self.assertEqual(proc.returncode, 1)
        self.assertTrue(
            proc.stdout.startswith(f"{RULES_SKILL}:2: "), proc.stdout
        )


class ManifestTest(ValidatorTestCase):
    def marketplace(self, **changes):
        return json.dumps({**GOOD_MARKETPLACE, **changes})

    def plugin(self, **changes):
        manifest = {**GOOD_PLUGIN, **changes}
        return json.dumps({k: v for k, v in manifest.items() if v is not None})

    def test_marketplace_with_wrong_name_fails(self):
        self.build({MARKETPLACE: self.marketplace(name="other")})
        self.assert_fails_at(f"{MARKETPLACE}:1")

    def test_marketplace_without_owner_fails(self):
        self.build({MARKETPLACE: self.marketplace(owner=None)})
        self.assert_fails_at(f"{MARKETPLACE}:1")

    def test_marketplace_plugin_with_wrong_source_fails(self):
        bad = [{**GOOD_MARKETPLACE["plugins"][0], "source": "./elsewhere"}]
        self.build({MARKETPLACE: self.marketplace(plugins=bad)})
        self.assert_fails_at(f"{MARKETPLACE}:1")

    def test_marketplace_plugin_without_description_fails(self):
        bad = [{**GOOD_MARKETPLACE["plugins"][0], "description": ""}]
        self.build({MARKETPLACE: self.marketplace(plugins=bad)})
        self.assert_fails_at(f"{MARKETPLACE}:1")

    def test_missing_marketplace_fails(self):
        self.build({MARKETPLACE: None})
        self.assert_fails_at(f"{MARKETPLACE}:1")

    def test_invalid_json_reports_the_line(self):
        self.build({PLUGIN: '{\n  "name": "game-server",\n  oops\n}\n'})
        self.assert_fails_at(f"{PLUGIN}:3")

    def test_plugin_missing_required_field_fails(self):
        for field in ("name", "description", "author", "license", "keywords"):
            with self.subTest(field=field):
                with tempfile.TemporaryDirectory() as tmp:
                    self.root = Path(tmp)
                    self.build({PLUGIN: self.plugin(**{field: None})})
                    line = self.assert_fails_at(f"{PLUGIN}:1")
                    self.assertIn(field, line)

    def test_plugin_with_version_fails(self):
        self.build({PLUGIN: self.plugin(version="1.0.0")})
        line = self.assert_fails_at(f"{PLUGIN}:1")
        self.assertIn("version", line)


class SkillFrontmatterTest(ValidatorTestCase):
    def test_name_must_equal_directory(self):
        self.build({RULES_SKILL: skill_md("other-name")})
        self.assert_fails_at(f"{RULES_SKILL}:2")

    def test_empty_description_fails(self):
        self.build({RULES_SKILL: skill_md("server-rules", "")})
        self.assert_fails_at(f"{RULES_SKILL}:3")

    def test_description_over_1024_characters_fails(self):
        too_long = skill_md("server-rules", "x" * 1025)
        self.build({RULES_SKILL: too_long})
        self.assert_fails_at(f"{RULES_SKILL}:3")

    def test_description_of_exactly_1024_characters_passes(self):
        exact = skill_md("server-rules", "x" * 1024)
        self.build({RULES_SKILL: exact})
        self.assertEqual(self.run_validator()[0], 0)

    def test_folded_description_counts_its_text_not_the_indicator(self):
        folded = "---\nname: server-rules\ndescription: >\n  First line\n  second line\n---\n"
        self.build({RULES_SKILL: folded})
        self.assertEqual(self.run_validator()[0], 0)

    def test_missing_frontmatter_fails(self):
        self.build({RULES_SKILL: "# No frontmatter\n"})
        self.assert_fails_at(f"{RULES_SKILL}:1")

    def test_missing_name_fails(self):
        self.build({RULES_SKILL: "---\ndescription: ok\n---\n"})
        self.assert_fails_at(f"{RULES_SKILL}:1")

    def test_disable_model_invocation_only_allowed_on_server_profile(self):
        flagged = skill_md("server-rules", extra="disable-model-invocation: true\n")
        self.build({RULES_SKILL: flagged})
        self.assert_fails_at(f"{RULES_SKILL}:4")

    def test_disable_model_invocation_false_is_allowed_anywhere(self):
        flagged = skill_md("server-rules", extra="disable-model-invocation: false\n")
        self.build({RULES_SKILL: flagged})
        self.assertEqual(self.run_validator()[0], 0)

    def test_skill_directory_without_skill_md_is_a_warning(self):
        self.build({f"{SKILLS}/gdd-intake/references/notes.md": "# Notes\n"})
        code, out, err = self.run_validator("--denylist", self.denylist("acme"))
        self.assertEqual((code, out), (0, []))
        self.assertEqual(len(err), 1, err)
        self.assertTrue(err[0].startswith(f"{SKILLS}/gdd-intake:1: warning"), err)


class LinkTest(ValidatorTestCase):
    def with_body(self, body, path=RULES_SKILL):
        return {path: skill_md("server-rules") + body}

    def test_broken_markdown_link_fails_at_its_line(self):
        self.build(self.with_body("\nSee [gone](references/gone.md).\n"))
        self.assert_fails_at(f"{RULES_SKILL}:7")

    def test_broken_inline_code_path_fails_at_its_line(self):
        self.build(self.with_body("\nRun `scripts/gone.py <file>`.\n"))
        self.assert_fails_at(f"{RULES_SKILL}:7")

    def test_inline_code_path_with_each_prefix_is_checked(self):
        for prefix in ("references/", "scripts/", "prompts/", "../"):
            with self.subTest(prefix=prefix):
                with tempfile.TemporaryDirectory() as tmp:
                    self.root = Path(tmp)
                    self.build(self.with_body(f"\nUse `{prefix}gone.md`.\n"))
                    self.assert_fails_at(f"{RULES_SKILL}:7")

    def test_existing_targets_pass(self):
        body = "\n[a](references/index.md#top) `references/index.md` `../server-profile/SKILL.md`\n"
        self.build(self.with_body(body))
        self.assertEqual(self.run_validator()[0], 0)

    def test_links_resolve_from_the_containing_file(self):
        nested = RULES_INDEX
        body = "[up](../SKILL.md) and [self](index.md) and [bad](SKILL.md)\n"
        self.build({nested: "### AUTH-01 Rule\n" + body})
        self.assert_fails_at(f"{nested}:2")

    def test_external_anchor_and_mailto_links_are_ignored(self):
        body = "\n[a](https://example.com/x) [b](#section) [c](mailto:a@example.com)\n"
        self.build(self.with_body(body))
        self.assertEqual(self.run_validator()[0], 0)

    def test_placeholder_and_glob_paths_are_ignored(self):
        body = "\n`references/<group>.md` `references/*.md` `scripts/{name}.py`\n"
        self.build(self.with_body(body))
        self.assertEqual(self.run_validator()[0], 0)

    def test_fenced_code_blocks_are_ignored(self):
        body = "\n```\n[x](references/gone.md) `references/gone.md`\n```\n"
        self.build(self.with_body(body))
        self.assertEqual(self.run_validator()[0], 0)

    def test_paths_that_do_not_start_with_a_known_prefix_are_ignored(self):
        body = "\n`python3 scripts/gone.py` and `docs/gone.md`\n"
        self.build(self.with_body(body))
        self.assertEqual(self.run_validator()[0], 0)


class RuleIdTest(ValidatorTestCase):
    def cite(self, token, path=RULES_SKILL):
        return {path: skill_md("server-rules") + f"\nCites {token}.\n"}

    def test_undefined_rule_id_fails_at_its_line(self):
        self.build(self.cite("AUTH-99"))
        line = self.assert_fails_at(f"{RULES_SKILL}:7")
        self.assertIn("AUTH-99", line)

    def test_every_rule_group_is_checked(self):
        for group in "AUTH MN BG PERF CFG MET CHEAT ADMIN HTTP TEST".split():
            with self.subTest(group=group):
                with tempfile.TemporaryDirectory() as tmp:
                    self.root = Path(tmp)
                    self.build(self.cite(f"{group}-77"))
                    self.assert_fails_at(f"{RULES_SKILL}:7")

    def test_defined_rule_id_passes(self):
        self.build(self.cite("AUTH-01"))
        self.assertEqual(self.run_validator()[0], 0)

    def test_rule_ids_in_non_markdown_plugin_files_are_checked(self):
        script = f"{SKILLS}/server-rules/scripts/check.py"
        self.build({script: "# AUTH-42\n"})
        self.assert_fails_at(f"{script}:1")

    def test_ids_with_other_digit_counts_are_not_rule_ids(self):
        self.build(self.cite("AUTH-1 and AUTH-123"))
        self.assertEqual(self.run_validator()[0], 0)

    def test_check_is_skipped_while_index_is_missing(self):
        changes = self.cite("AUTH-99")
        changes[RULES_INDEX] = None
        self.build(changes)
        self.assertEqual(self.run_validator()[0], 0)

    def test_mention_outside_a_heading_does_not_define_an_id(self):
        self.build({RULES_INDEX: "### AUTH-01 Rule\n\nAUTH-02 is only prose.\n"})
        self.assert_fails_at(f"{RULES_INDEX}:3")


class CapabilityIdTest(ValidatorTestCase):
    def cite(self, token):
        return {PROFILE_SKILL: skill_md("server-profile") + f"\nNeeds {token}.\n"}

    def test_undefined_capability_id_fails_at_its_line(self):
        self.build(self.cite("CAP-NOPE"))
        line = self.assert_fails_at(f"{PROFILE_SKILL}:7")
        self.assertIn("CAP-NOPE", line)

    def test_defined_capability_id_passes(self):
        self.build(self.cite("CAP-TIME"))
        self.assertEqual(self.run_validator()[0], 0)

    def test_placeholder_heading_syntax_is_not_a_capability_id(self):
        self.build(self.cite("CAP-<NAME>"))
        self.assertEqual(self.run_validator()[0], 0)

    def test_check_is_skipped_while_template_is_missing(self):
        changes = self.cite("CAP-NOPE")
        changes[PROFILE_TEMPLATE] = None
        self.build(changes)
        self.assertEqual(self.run_validator()[0], 0)


class TrackedFileScanTest(ValidatorTestCase):
    def test_home_path_in_tracked_file_fails(self):
        for prefix in ("/Us" + "ers/alice/", "/ho" + "me/alice/"):
            with self.subTest(prefix=prefix):
                with tempfile.TemporaryDirectory() as tmp:
                    self.root = Path(tmp)
                    self.build({"docs/notes.txt": f"ok\nsee {prefix}work/x\n"})
                    self.assert_fails_at("docs/notes.txt:2")

    def test_private_key_block_fails(self):
        key = "-----BEGIN RSA PRIV" + "ATE KEY-----\nabc\n"
        self.build({"docs/key.txt": "x\n" + key})
        self.assert_fails_at("docs/key.txt:2")

    def test_untracked_files_are_not_scanned(self):
        self.build()
        Path(self.root, "stray.txt").write_text("/Us" + "ers/alice/x\n", encoding="utf-8")
        self.assertEqual(self.run_validator()[0], 0)

    def test_placeholder_home_paths_pass(self):
        self.build({"docs/notes.txt": "use /Users/<name>/ or /home/<name>/\n"})
        self.assertEqual(self.run_validator()[0], 0)


class DenylistTest(ValidatorTestCase):
    def test_term_match_is_case_insensitive(self):
        self.build({"docs/notes.txt": "fine\nthe ACME server\n"})
        line = self.assert_fails_at("docs/notes.txt:2", "--denylist", self.denylist("acme"))
        self.assertNotIn("ACME", line)
        self.assertNotIn("acme", line)

    def test_term_inside_a_longer_word_does_not_match(self):
        self.build({"docs/notes.txt": "acmeish and preacme and acme_corp\n"})
        code, out, _ = self.run_validator("--denylist", self.denylist("acme"))
        self.assertEqual((code, out), (0, []))

    def test_term_next_to_punctuation_matches(self):
        self.build({"docs/notes.txt": "(acme), acme.Foo\n"})
        self.assert_fails_at("docs/notes.txt:1", "--denylist", self.denylist("acme"))

    def test_multiword_and_dotted_terms_match(self):
        self.build({"docs/notes.txt": "uses org.acme.Foo here\n"})
        self.assert_fails_at("docs/notes.txt:1", "--denylist", self.denylist("org.acme.Foo"))

    def test_blank_lines_and_comments_in_denylist_are_ignored(self):
        self.build({"docs/notes.txt": "# comment text\n\n"})
        code, out, _ = self.run_validator("--denylist", self.denylist("# comment", "", "  "))
        self.assertEqual((code, out), (0, []))

    def test_untracked_files_are_not_scanned(self):
        self.build()
        Path(self.root, "stray.txt").write_text("acme\n", encoding="utf-8")
        self.assertEqual(self.run_validator("--denylist", self.denylist("acme"))[0], 0)

    def test_env_var_supplies_the_denylist(self):
        self.build({"docs/notes.txt": "acme\n"})
        os.environ["GSS_DENYLIST"] = self.denylist("acme")
        self.assert_fails_at("docs/notes.txt:1")

    def test_flag_wins_over_env_var(self):
        self.build({"docs/notes.txt": "acme\n"})
        os.environ["GSS_DENYLIST"] = self.denylist("acme")
        other = self.outside / "other.txt"
        other.write_text("unrelated\n", encoding="utf-8")
        self.assertEqual(self.run_validator("--denylist", str(other))[0], 0)

    def test_without_a_denylist_the_scan_is_skipped_with_a_warning(self):
        self.build({"docs/notes.txt": "acme\n"})
        code, out, err = self.run_validator()
        self.assertEqual((code, out), (0, []))
        self.assertEqual(len(err), 1, err)
        self.assertIn("warning", err[0])
        self.assertIn("skipped", err[0])

    def test_missing_denylist_file_fails(self):
        self.build()
        code, out, _ = self.run_validator("--denylist", str(self.outside / "nope.txt"))
        self.assertEqual(code, 1)
        self.assertEqual(len(out), 1, out)


if __name__ == "__main__":
    unittest.main()
