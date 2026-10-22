# Use the skills in a plain Claude Code chat

This guide builds one game server feature from a GDD or a prompt in an ordinary Claude Code session, with no workflow plugin. You drive each step and keep each build in a fresh context. For the nstack version, see [Use the skills with nstack](usage-nstack.md).

Install the plugin first (see the [README](../README.md#install)). Open Claude Code in the root of your game server repository. Pick a short kebab-case feature name, such as `daily-streak`. Every file for the feature goes under `docs/game-server/features/daily-streak/`.

The example prompts below are starting points. The skills load from their descriptions, so plain wording works. Naming the skill makes sure the right one runs.

## 1. Write the profile

`server-profile` is explicit only, so type the command.

```
/game-server:server-profile
```

The skill scans the repository read-only and writes `docs/game-server/profile.md`. It then checks the file and lists the rules that a missing or partial capability blocks. You can rerun the checker yourself at any time. `<plugin>` is the plugin directory, which `claude plugin list --json` shows as `installPath`, or the folder you gave to `--plugin-dir`.

```bash
python3 <plugin>/skills/server-profile/scripts/check_profile.py docs/game-server/profile.md
```

Read the blocked-rules list. If a capability that the feature needs is missing, the later skills stop and ask you, so decide now whether to change the core. Commit the profile.

## 2. Take in the GDD

Add `.gdd-intake/` to `.gitignore`, because the skill keeps converted text and images there. Then point `gdd-intake` at the design material.

```
Use gdd-intake on ./gdd/daily-streak. The feature name is daily-streak and the scope is server-only.
```

For a feature with no GDD files, give a prompt.

```
Use gdd-intake for a daily login streak. Players who log in on consecutive days
earn a reward that grows each day, and a missed day resets the streak.
```

A prompt skips the conversion step and gives a design with more open questions.

The skill writes `docs/game-server/features/daily-streak/design.md` and lints it. Outside a workflow, it then asks you the open questions itself, Blocker questions first, and offers its interim default with one or two alternatives. Answer them, or skip a question to keep its default. A Blocker question left open stops `feature-spec` in the next step.

After your answers, the skill refines the design, runs a self-review with a separate agent, and writes draft config JSON from any balance sheets into `docs/game-server/features/daily-streak/config/`. The drafts hold example or sheet values, so treat them as drafts. You can rerun the lint yourself.

```bash
python3 -I <plugin>/skills/gdd-intake/scripts/lint_design.py docs/game-server/features/daily-streak/design.md
```

Read the design before moving on. It is the last place where a wrong rule is cheap to fix. Commit it.

## 3. Write the spec

```
Use feature-spec to write the server spec for daily-streak from its design.md.
```

The skill needs the profile, so it stops and points you to `server-profile` if the file is missing. It writes `docs/game-server/features/daily-streak/spec.md` section by section. Each row cites rule ids from the rulebook, and each row from the design cites a design id. The spec covers commands, pushes, state, config, metrics, cheats, admin commands, HTTP endpoints, the multi-node analysis, the blue-green and old-client matrix, the performance budget, and the test plan.

If Core blockers has a row that blocks, the skill sets the status to `blocked` and stops. The row names the capability, the rules it breaks, the players' failure, and the smallest core change. Choose a resolution for each row. You can change the core, descope what depends on it, or accept the risk by name. You may accept a critical rule too, but the reason must state the deployment fact that makes the risk acceptable, such as "one node per realm". The spec header lists every accepted critical rule, and the feature-build report repeats them. Tell the skill your choice, and it finishes the remaining sections.

Read the finished spec, ask for fixes in plain words, and confirm it. The status then becomes `ready`. Commit the spec.

## 4. Slice the spec into tasks

```
Slice the daily-streak spec into an ordered task list for plain Claude Code.
```

The skill writes `docs/game-server/features/daily-streak/tasks.md`. Each task has a Goal, the tasks it Depends on, its Files, the Spec rows it builds, and a Done when command. The command is the profile's `test_one_cmd` with the test class filled in. Shared shapes come first (command ids, the state model, the config schema), then the commands, the HTTP endpoints, the cheat and admin commands, the wiring, and the KPI queries. A composite command splits into three tasks.

## 5. Build one task at a time

Run each task in a fresh context so the build sees only the files it needs. Clear the chat, then ask for one task.

```
/clear
Use feature-build to build task 3 from docs/game-server/features/daily-streak/tasks.md.
```

The skill reads the profile, the spec, and the task. It checks its gates first. The spec must be `ready`, every capability the task uses must be `present` or have a resolved blocker row, and the command ids it needs must exist in the generated files. A failed gate stops the skill with the exact change you need to make. It never edits generated files by hand, and it never edits core code.

When the gates pass, it writes the failing tests first, then the code, then the registration and the metric calls. It runs the task's Done when command and fixes the code until it passes. It finishes with a report that lists the files, the tests, the check result, and a self-check against the profile's lint patterns.

If the build tool is not installed on the machine, the skill still writes the tests and the code. It reports the check as unrun and says the code was not compiled. Run the command on a machine with the tool before you trust the task.

Run the task's Done when command yourself if you want to see it, then commit. Repeat with the next task number, in the order of the list.

## 6. Review

After the last task, or after a command's last task on a large feature, ask for a review.

```
Use feature-review on the daily-streak branch against main.
```

The skill runs the feature linter first.

```bash
python3 <plugin>/skills/feature-review/scripts/lint_feature.py --profile docs/game-server/profile.md --diff $(git merge-base HEAD main) <paths>
```

Pass the changed Java files or the feature package directory. With `--diff`, the linter reports only the lines that the branch adds since its base, so old code in a shared file does not count. The linter prints `path:line: RULE-ID message` for forbidden time and random calls, static mutable state, cheat classes without the live environment check, commands without a metric call or trace id, and blocking calls. It exits 1 when it finds anything. An empty pattern in the profile turns a check off, and the report names the checks that were off.

The skill then walks the checklist group by group. Each finding has a severity, a rule id, `file:line`, and a failure scenario that names who does what and what the player or operator sees. A critical finding needs a reachable trigger, or the skill demotes it. The skill reports and does not fix. To fix the findings, ask `feature-build` for each one, or hand the report back to your own task list.

```
Use feature-build to fix finding 2 of the review above, then rerun feature-review's linter.
```

## Keep the files current

- The profile, design, and spec are plain files in your repository. After a core change, rerun `server-profile`, then rerun feature-spec's Core blockers step on every spec not yet built. `profile_version` is the profile template's version, so it does not catch a core change.
- When a design rule changes, edit `design.md`, rerun the lint, and ask `feature-spec` to update the spec rows that cite the changed ids.
- `server-rules` loads on its own when a skill needs a rule. To read one yourself, ask for it by id, such as the rule index at `plugins/game-server/skills/server-rules/references/index.md`.
