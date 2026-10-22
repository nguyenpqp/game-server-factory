# Use the skills with nstack

This guide builds one game server feature from a GDD with the nstack `/nstack:n-mode` workflow and the `game-server` plugin. The coordinator chat runs the Interview and Spec build playbooks. The plugin's skills supply the server knowledge, and delegates do the writing.

Before you start, install both plugins (see the [README](../README.md#install)) and open Claude Code in the root of your game server repository. Pick a short kebab-case feature name, such as `daily-streak`. Use it for the nstack branch (`feat/daily-streak`) too, so the intent file `docs/intents/daily-streak.md` and the tickets file `docs/intents/daily-streak-tickets.md` line up with the feature folder `docs/game-server/features/daily-streak/`.

## 1. Find the skill paths

Delegates do not see your chat. Each brief names the absolute path of the `SKILL.md` files it must read. Find the plugin directory once, then build the paths from it.

An installed plugin sits in the plugin cache. This command prints its directory.

```bash
claude plugin list --json | python3 -c 'import json,sys; print(next(p["installPath"] for p in json.load(sys.stdin) if p["id"]=="game-server@game-server-factory"))'
```

With `claude --plugin-dir`, the directory is the absolute form of the path you passed, such as the `plugins/game-server` folder of your clone. When a skill loads, Claude Code substitutes `${CLAUDE_PLUGIN_ROOT}` and `${CLAUDE_SKILL_DIR}` in the text of its SKILL.md. They are not shell variables. A person or a delegate brief that runs a script by hand uses the plugin's `installPath`.

The six files you will name are `<plugin>/skills/<skill>/SKILL.md`, where `<skill>` is `server-rules`, `server-profile`, `gdd-intake`, `feature-spec`, `feature-build`, or `feature-review`. Write them out in full in every brief. A relative path or a skill name alone is not enough, because a delegate may not load the skill by name.

## 2. Write the profile in the main session

`server-profile` is explicit only. Claude does not start it from a description match, and a delegate will not load it that way. Run it yourself in the main session, before the nstack run.

```
/game-server:server-profile
```

The skill scans the repository read-only and writes `docs/game-server/profile.md`. It runs the profile checker, then lists which rules are blocked by capabilities the core lacks. Read that list. A blocked capability stops the spec later, so decide now whether to change the core.

Commit the profile. Ticket worktrees start from the spec branch, so anything a delegate must read has to be committed on it.

## 3. Turn the GDD into a design

Run `gdd-intake` on the GDD folder, in the main session or in a delegate whose brief names its `SKILL.md`. Add `.gdd-intake/` to the repository's `.gitignore` first, because the skill keeps converted text and images there.

```
Use gdd-intake on ./gdd/daily-streak. The feature name is daily-streak and the scope is server-only.
```

Inside nstack, the skill follows its hand-off rule. It converts and extracts, writes `docs/game-server/features/daily-streak/design.md`, runs `lint_design.py`, and then stops. It gives the coordinator the Open questions section instead of asking you itself. Each question has an id, a tier (Blocker, Important, or Minor), a source citation, and an interim default.

For a plain prompt with no GDD files, give the prompt instead of a folder. The skill skips conversion and writes the same format, with more open questions.

## 4. Interview with the design as the answer sheet

Start the workflow with the feature request.

```
/nstack:n-mode Build the daily-streak feature from docs/game-server/features/daily-streak/design.md
```

The coordinator matches the Spec build playbook and opens the Interview round first. It reads `design.md` as its answer sheet, so it does not ask what the design already says. It asks only about the design's open questions, Blocker first, and about what the design leaves to engineering. Each question cites the design id it comes from. You answer through the coordinator, because a subagent cannot reach you with a question.

The coordinator hands your answers back to `gdd-intake`, which applies them in its refine step, lints again, and runs its self-review. Then it records each answer in the question's status line in `design.md`. A skipped question keeps its interim default. A Blocker question still open stops `feature-spec`, so answer those.

Commit the finished `design.md` and any draft config JSON under `docs/game-server/features/daily-streak/config/`.

## 5. Write the spec

The coordinator spawns one delegate to write the spec. Use the strongest tier, because this is design work. The brief points at files and does not paste them.

```
Read these skill files in full before you start.
- <plugin>/skills/feature-spec/SKILL.md
- <plugin>/skills/server-rules/SKILL.md

Inputs
- Profile: <repo>/docs/game-server/profile.md
- Design: <repo>/docs/game-server/features/daily-streak/design.md

Write <repo>/docs/game-server/features/daily-streak/spec.md. You cannot ask the
developer. If the spec hits a stop (a core blocker or an open Blocker question),
write what you have, set the status, and return the stop and its questions to me.
```

The skill fills all fourteen sections of the spec and cites a rule id on every row. If Core blockers has a row that blocks, the spec is `blocked`, and the delegate returns the row with the smallest core change. The coordinator brings it to you. You pick a resolution for each row (the core changes, the requirement is descoped, or you accept the risk by name). You may accept a critical rule too, but the reason must state the deployment fact that makes the risk acceptable, such as "one node per realm". The spec header lists every accepted critical rule, and the feature-build report repeats them.

The coordinator then shows you the spec as part of the Interview confirmation. When you confirm, the spec status becomes `ready`. Commit the spec.

## 6. Slice the spec into tickets

Ask the same skill for the slicing, which writes the tickets file nstack Spec build reads.

```
Slice the daily-streak spec for nstack Spec build, following the slicing reference of feature-spec.
```

The result is `docs/intents/daily-streak-tickets.md`. Shared shapes come first as tickets with no blockers (command ids, the state model, the config schema), so they build in parallel. Command tickets follow, then HTTP endpoints, cheats and admin, the wiring ticket that registers everything, and the KPI queries. A composite command splits into three tickets. Every ticket has the five fields the playbook reads.

- **Builds.** What the ticket makes work, naming the spec rows.
- **Blocked by.** The tickets that gate it.
- **Writes.** The paths it may write. Feature code goes under the profile's `feature_root` and tests under `test_root`.
- **Acceptance.** One checkable line per spec row, with its rule ids.
- **Verify.** The profile's `test_one_cmd`, with `{class}` replaced by each test class of the ticket, joined with `&&`.

A Verify that needs a database or credentials a worktree lacks is marked `root-only`. The playbook runs those in the root checkout and reports them as unrun when the machine cannot.

The Interview confirmation names this tickets file, and the intent in `docs/intents/daily-streak.md` points to it. The coordinator commits the tickets file as Spec build step 1.

## 7. Build the tickets

Spec build opens the spec branch worktree, then spawns every ready ticket at once, each in its own worktree on `feat/daily-streak--tNN`. Every brief names the absolute paths a build delegate needs.

```
Read these skill files in full before you start.
- <plugin>/skills/feature-build/SKILL.md
- <plugin>/skills/server-rules/SKILL.md

Inputs
- Intent: <spec worktree>/docs/intents/daily-streak.md
- Tickets: <spec worktree>/docs/intents/daily-streak-tickets.md, ticket T05
- Spec: <spec worktree>/docs/game-server/features/daily-streak/spec.md
- Profile: <spec worktree>/docs/game-server/profile.md

Build only T05. Write only inside its Writes. Write the failing test first.
End every commit message with the line "Ticket: 05".
```

`feature-build` checks its gates before any code. The spec must be `ready`, every capability the slice uses must be `present` in the profile or have a resolved blocker row, and the command ids must exist in the generated files. If a gate fails, the delegate stops and reports it. If the generated ids are missing, the ids ticket (T01 in the worked example) is the one that adds them. It edits the generator source, runs the regenerate command from the profile's CAP-GENERATED entry, and reads the generated files back. No ticket edits a generated file by hand.

The check after each slice is the ticket's Verify, which is the profile's `test_one_cmd`. If the build tool (such as `gradle` or `mvn`) is not on the machine, the delegate still writes the tests and the code, and reports every check as unrun with the line "code not compiled". The coordinator treats an unrun check as unrun and never as green. On a machine with no JDK, the whole build lands that way, and the compile and test run happens later on a machine that has the tool.

## 8. Review the branch

When nothing is in flight and no ticket is blocked, Spec build reviews the branch once. Add `feature-review` to the reviewer's brief.

```
Read these skill files in full before you start.
- <plugin>/skills/feature-review/SKILL.md
- <plugin>/skills/server-rules/SKILL.md

Review the diff of the spec branch against <integration branch>. Spec: <spec worktree>/docs/game-server/features/daily-streak/spec.md
Profile: <spec worktree>/docs/game-server/profile.md
```

The reviewer runs the linter first.

```bash
python3 <plugin>/skills/feature-review/scripts/lint_feature.py --profile docs/game-server/profile.md --diff $(git merge-base HEAD <integration branch>) <paths>
```

With `--diff`, it reports only the lines that the spec branch adds since its base, so old code in a shared file does not count. It prints `path:line: RULE-ID message` for forbidden time and random calls, static mutable state, cheat classes without the live environment check, commands without a metric call or trace id, and blocking calls. Exit code 1 means findings. A check whose profile pattern is empty is off, and the report names it. A clean run does not clear the other rules, so the reviewer then walks the checklist group by group and reports each finding with a severity, a rule id, `file:line`, and a failure scenario. Spec build gives the findings to one fix delegate and lands the result like a ticket. Tell the fix delegate to rerun the linter besides the test command.

Nstack's built-in `/code-review` still runs over the branch. It checks general correctness, and `feature-review` checks the server rules.

## Notes

- The profile, design, and spec are plain files in the target repository. After a core change, rerun `server-profile`, then rerun feature-spec's Core blockers step on every spec not yet built. `profile_version` is the profile template's version, so it does not catch a core change.
- Only the main session can ask you questions. A delegate that hits a stop returns it, and the coordinator asks.
- If you skip nstack for a feature, the same files drive [a plain Claude Code chat](usage-plain.md).
