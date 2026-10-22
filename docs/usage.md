# Use the skills

This guide takes one game server feature from a GDD or a prompt to reviewed code. It describes what each step needs, what it writes, and where it stops for you. It does not tie you to a workflow. You can drive the steps by hand in one chat, split them across sessions, or hand them to a workflow plugin or to subagents. The files the skills write are the same either way.

## Before you start

Install the plugin (see the [README](../README.md#install)) and work from the root of your game server repository. Pick a short kebab-case name for the feature, such as `daily-streak`. Every file for the feature goes under `docs/game-server/features/daily-streak/`.

You can ask for a skill in plain words, such as "use feature-spec on the daily-streak design". Most skills also load on their own when the request matches their description. Naming the skill makes sure the right one runs. The prompts below are examples, not required wording.

In this guide, `<plugin>` is the plugin directory. For an installed plugin, `claude plugin list --json` shows it as `installPath`. With `claude --plugin-dir`, it is the folder you passed.

## The flow

| Step | Skill | Needs | Writes | Stops for you when |
| --- | --- | --- | --- | --- |
| 1. Profile | `server-profile` | The server repository | `docs/game-server/profile.md` | Never. It reports which rules the core's gaps block. |
| 2. Design | `gdd-intake` | GDD files or a prompt | `design.md`, draft config JSON in `config/` | The design has open questions |
| 3. Spec | `feature-spec` | The profile and `design.md` | `spec.md` | A core blocker needs a decision, or a Blocker question is still open |
| 4. Plan | `feature-spec` | A `ready` spec | `tasks.md` | Never |
| 5. Build | `feature-build` | The profile, the spec, and one slice | Java code and unit tests | A gate fails |
| 6. Review | `feature-review` | The code, the profile, the spec, and the design | A findings report | Never. It reports and does not fix. |

Steps 1 and 2 do not depend on each other. Step 4 is optional. A small feature can go straight from the spec to one build.

Commit each file when you accept it. A later step, or a session that starts from a fresh checkout, reads the committed version.

## 1. Profile the server

`server-profile` runs only when you ask for it by name, because it writes into your repository from a scan. Ask for it once per server repository, and again after the core changes.

```
/game-server:server-profile
```

The skill scans the repository read-only and writes `docs/game-server/profile.md`. The profile records how the core provides each capability that feature code needs, such as commands, per-user state, Redis, config, metrics, cheats, and admin. Each capability is `present`, `partial`, or `missing`. The skill checks the file and lists the rules that each gap blocks.

Read that list. If a capability the feature needs is missing, the spec will stop on it, so decide early whether to change the core. The spec, build, and review skills do not run without a profile.

## 2. Turn the GDD into a design

Add `.gdd-intake/` to `.gitignore` first. The skill keeps converted text and images there, and they may hold GDD content you do not want committed.

Give `gdd-intake` the design material: a folder of pptx, docx, xlsx, PDF, Markdown, or images, or a plain prompt.

```
Use gdd-intake on ./gdd/daily-streak. The feature name is daily-streak and the scope is server-only.
```

```
Use gdd-intake for a daily login streak. Players who log in on consecutive days
earn a reward that grows each day, and a missed day resets the streak.
```

A prompt skips conversion and gives a design with more open questions. docx files need python-docx and xlsx files need openpyxl (`python3 -m pip install python-docx openpyxl`). PDF files need PyMuPDF (`python3 -m pip install pymupdf`). Without a package, the skill lists the files it could not read and asks you to install it. A PDF can also be exported to docx or Markdown. Slides and text files need only Python 3.

The skill writes `design.md` with an id on every requirement and a source citation for each one. It then lists the open questions. Each question has a tier (Blocker, Important, or Minor) and an interim default. Answer them, or skip one to keep its default. A Blocker question left open stops the spec. If a workflow you use runs its own interview, the skill stops after the open questions and hands them over instead of asking you itself.

After your answers, the skill refines the design, runs a self-review, and writes draft config JSON from any balance sheets into `config/` beside the design. The drafts hold example or sheet values, so check them before they ship.

Read the design before moving on. It is the cheapest place to fix a wrong rule.

## 3. Write the spec

```
Use feature-spec to write the server spec for daily-streak from its design.md.
```

The skill writes `spec.md` section by section. Each row cites rule ids from the rulebook, and each row taken from the design cites its design id. The spec covers commands, pushes, state, config, metrics, cheats, admin commands, HTTP endpoints, the multi-node analysis, the blue-green and old-client matrix, the performance budget, and the test plan.

If a capability the feature needs is missing or partial, the Core blockers section gets a row that names the capability, the rules it breaks, what players would see, and the smallest core change. The spec status becomes `blocked`, and the skill stops. Choose one resolution per row.

- **Change the core.** Make the change, rerun `server-profile`, then continue the spec.
- **Descope.** Drop what depends on the capability.
- **Accept the risk** as `accepted by <name>: <reason>`. You may accept a critical rule too, but the reason must name the deployment fact and say how it prevents or bounds the failure, such as "one node per realm, so two nodes never hold the same user". The spec header lists every accepted critical rule, and the build report repeats them.
- **Accept the risk for every feature.** The skill adds a decision to `docs/game-server/decisions.md` with your name, the deployment fact, and how it bounds the failure. Every later spec applies it to a matching row and does not stop there. PERF-01 is never accepted this way, because its risk depends on each blocking call.

A decision stops applying when a new profile changes its capability's status or no longer blocks one of its rules. `<plugin>/skills/feature-spec/references/decisions-template.md` gives the format and the rules. Commit `decisions.md` with the spec, like the profile.

Read the finished spec and ask for fixes in plain words. When you confirm it, the status becomes `ready`.

## 4. Plan the build (optional)

A large feature builds better in slices, each small enough for one session. Ask `feature-spec` to slice the `ready` spec.

```
Slice the daily-streak spec into an ordered task list.
```

The task list goes to `docs/game-server/features/daily-streak/tasks.md`, or to a path you name. Each task has Builds (the spec rows it makes work), Depends on, Writes (the files it may change), Acceptance (one checkable line per spec row), and Verify, which is the profile's `test_one_cmd` with the test class filled in. The format does not assume who runs the tasks. If your workflow tool wants a different file, point it at this one or have it convert the list.

Shared shapes come first: command ids, the state model, and the config schema. Then come the commands, the HTTP endpoints, the cheat and admin commands, the wiring that registers everything, and the KPI queries. A composite command splits into three slices. Slices with no dependency between them can build at the same time.

## 5. Build

Ask `feature-build` for one slice at a time, in the order of the plan. Without a plan, name the spec rows to build.

```
Use feature-build to build task 3 from docs/game-server/features/daily-streak/tasks.md.
```

A build sees less noise in a fresh context, so starting each slice in a new session or a new subagent helps on a large feature. It is not required.

The skill checks its gates before it writes any code.

- The spec is `ready`.
- Every capability the slice uses is `present` in the profile or has a resolved Core blockers row.
- The command ids the slice needs exist in the generated files.

A failed gate stops the skill with the exact change you need. The skill never edits generated files or core code by hand. When the ids are missing, the slice that adds them edits the generator source and runs the profile's regenerate command.

When the gates pass, the skill writes the failing tests first, then the code, then the registration and the metric calls. It runs the slice's check command and fixes the code until the check passes. Its report lists the files, the tests, the check result, and a sweep of the added lines for the breaks a reviewer finds first.

If the build tool is not installed, the skill still writes the tests and the code, and reports the check as unrun with the code not compiled. Treat an unrun check as unrun, not as passed, and run it on a machine that has the tool.

## 6. Review

Ask for a review after the last slice, or after each command on a large feature.

```
Use feature-review on the daily-streak branch against main.
```

The skill runs in three passes.

1. **Sweep.** It reads the lines the branch adds for breaks that one call shows: forbidden time and random calls, static mutable state, cheat classes without the live environment check, commands without a metric row or trace id, blocking calls on the user actor thread, and imports of another feature's package. The profile's `lint` keys tell it how your project spells those calls.
2. **Design conformance.** It traces every design id to a spec row, code, and a test, and marks each one matched, partial, divergent, missing, descoped, or client only. It checks every number and settled decision in the design against the code, and checks each design row against the GDD text it cites, in `.gdd-intake/<feature>/raw/` when that folder exists.
3. **Rule groups.** It walks the rulebook group by group.

Each finding has a severity, a rule id, `file:line`, and a failure scenario that says who does what and what the player or operator sees. A critical finding needs a trigger that can really happen, or the skill lowers it. The skill does not fix anything. Hand the findings to `feature-build`, one at a time or as a batch, and rerun the review after the fix.

```
Use feature-build to fix finding 2 of the review above, then rerun feature-review on the fixed files.
```

A clean review covers the server rules and the design. It does not replace a general code review.

The skills check their own work by reading, with no check scripts. The one script in the plugin is the `gdd-intake` converter, which turns docx, pptx, xlsx, and PDF files into Markdown that the agent reads.

## With subagents or a workflow

The skills work the same under any workflow, with a few limits.

- **Explicit skills.** `server-profile` never starts from a description match, so a subagent will not load it on its own. Run it in your main session, or name its `SKILL.md` path in the brief.
- **Skill paths.** A subagent may not load a skill by name. Give it the absolute paths `<plugin>/skills/<skill>/SKILL.md` to read, and add `<plugin>/skills/server-rules/SKILL.md` for spec, build, and review work. `${CLAUDE_PLUGIN_ROOT}` and `${CLAUDE_SKILL_DIR}` appear in the skill text, but Claude Code fills them in only when a skill loads. They are not shell variables, so a brief uses the real path.
- **Questions.** Only your main session can ask you something. A subagent that hits a stop, such as a core blocker or an open Blocker question, should write what it has, set the status, and return the stop.
- **Commits.** A subagent in its own worktree sees only what is committed, so commit the profile, the design, and the spec before you start one.

## Keep the files current

- The profile, design, and spec are plain files in your repository. Edit them like any other file.
- After a core change, rerun `server-profile`, then rerun the Core blockers step of every spec not yet built. That step checks each decision in `decisions.md` against the new profile. `profile_version` is the version of the profile template, so it does not catch a core change.
- When a design rule changes, edit `design.md`, check it against the design template, and ask `feature-spec` to update the spec rows that cite the changed ids.
- `server-rules` loads on its own when a skill needs a rule. To read the rules yourself, start from `<plugin>/skills/server-rules/references/index.md`.
