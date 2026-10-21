---
name: feature-review
description: Review Java game server feature code or a diff against the plugin's rule ids. Use when asked to review, audit, or check a game server feature, pull request, or diff for anti-cheat and server authority, multi-node safety, blue-green rollout, old client compatibility, performance, feature config, metrics, cheat commands, admin commands, HTTP callbacks, or tests. Runs a linter for the deterministic breaks, reviews the rest rule by rule against the feature spec, and reports findings with severity, rule id, file and line, and a concrete failure scenario.
---

# Feature review

Review feature code against the rule index, the project profile, and the feature spec. Report findings. Do not fix them. The `feature-build` skill fixes code.

## Inputs

- The code to review: a diff, a branch, or a list of paths. If none is given, review the diff of the current branch against its base branch.
- The profile, `docs/game-server/profile.md`, from the `server-profile` skill. It holds the lint patterns and the capability entries. If it is missing, stop and ask the developer to run `server-profile`. Do not guess the project's calls.
- The spec, `docs/game-server/features/<feature>/spec.md`, from the `feature-spec` skill. If it is missing, review against the rules alone and say so at the top of the report.
- The rule index from the `server-rules` skill. Open the rule text before you report a finding on it.

## Steps

1. **Scope.** List the changed files: Java sources, tests, config files, and docs. Read each changed source file in full, then the code it calls and the code that registers it. A diff hunk alone hides the checks around it.
2. **Run the linter first.**

   ```bash
   python3 <skill dir>/scripts/lint_feature.py --profile docs/game-server/profile.md <paths>
   ```

   `<skill dir>` is the directory of this file; the script is `scripts/lint_feature.py` in it. Pass the changed Java files or the feature package directory. Each output line is `path:line: RULE-ID message`. Exit code 1 means findings, 2 means the profile or a path could not be used. Treat each line as a finding after you check it against the code. The linter finds calls to forbidden time and random sources (AUTH-02, AUTH-03), mutable static fields (MN-01), cheat classes with no live check (CHEAT-02), command classes with no metric call or trace id (MET-01, MET-02), and blocking calls (PERF-01). A command class is a class under `feature_root` that declares a method whose name matches the profile's `lint.command_method`, or `handle\w*` when the key is absent. When no checked class is a command class, the linter prints a note to stderr, and MET-01 and MET-02 need a check by hand. The linter finds only what a pattern can find, so a clean run says nothing about the other rules. It reads the profile's `lint` patterns, and an empty pattern turns its check off. Name the checks that were off in the report.
3. **Review rule group by rule group.** Open `references/review-checklist.md`. Walk the groups in the order AUTH, MN, BG, PERF, CFG, MET, CHEAT, ADMIN, HTTP, TEST. For each group, compare the code with the matching spec sections:
   - Every spec row has code that does what the row says.
   - Every code path that changes state has a spec row.
   - Every capability the spec marks `missing` or `partial` in Core blockers is handled as the spec says, and the code does not work around the blocker.

   Skip a group only when the diff has nothing for it, and name the skipped groups in the report.
4. **Check lifecycle parity.** For each piece of state the feature touches, list every entry point that reads or changes it: gameplay command, login, offline load, periodic job, cheat command, admin command, HTTP callback, cross-node message, inbox drain, and drain. Check that each one follows the same rules as the main path. A break on a side path is a finding even when the main path is correct. The checklist has the details.
5. **Write the findings.** Each finding has:
   - a severity: `critical`, `important`, or `minor`, equal to the rule's severity in the index unless the audit in step 6 lowers it;
   - the rule id;
   - `file:line` of the code that breaks the rule;
   - a failure scenario: who does what, which line runs, and what the player or the operator sees. Use concrete commands, packets, nodes, and data.
   - a fix direction in one sentence.

   One cause that breaks several rules is one finding that lists the extra rule ids. Do not pad the report with style notes.
6. **Audit severity.** Keep a Critical finding only when you can name a reachable trigger: a command, a packet, a job, a callback, or a config state that a player, an operator, or the system can produce. If you cannot, demote it to important and say why. A rare trigger is still reachable, so rarity does not lower severity. Never raise a finding above the index severity. Record the result in the severity audit table from the checklist.
7. **Audit each dismissal once.** List every suspected break you decided not to report, with the reason. Then re-check each one against the code, the test it cites, and the catch block it relies on, as the checklist describes. Reverse a dismissal only on evidence, and keep the ones that hold.
8. **Report.**

   ```markdown
   ## Review of <feature or branch>

   Scope: <files reviewed>. Spec: <path or "none">. Profile: <path>.
   Lint: <n findings, exit code>. Checks off in the profile: <list or "none">.
   Groups skipped: <list with reasons or "none">.

   ### Findings
   1. [critical] MN-03 `src/.../GiftCommand.java:88`. Scenario: <who, what, result>. Fix: <one sentence>.

   ### Dismissals kept after audit
   - `file:line` <suspected break>. Kept because <evidence>.

   ### Severity audit
   <table from the checklist>

   ### Follow-ups
   <rule index or profile gaps found, if any>
   ```

   Order findings by severity, then by rule group. If there are no findings, say so, and still list the groups and checks you ran.

## Limits

- The review reads code and does not run the server. Say which findings are unconfirmed at runtime.
- Do not cite a rule id that is not in the rule index, and do not add ids. Report a missing rule as a follow-up.
- Do not edit the code, the spec, or the profile.
