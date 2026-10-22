# Skills as guidelines, with no check scripts

## Problem

Three skills run check scripts, and the review fixes added two more. A script freezes one project's shape into the skill. Game designs and server codebases vary a lot, so a fixed check either rejects a valid design or misses what it was not written for. The owner wants each skill to describe what correct work looks like, and the agent to check its own work against that description.

- `server-profile` runs `check_profile.py` to check the profile and to list the rules each capability blocks.
- `gdd-intake` runs `lint_design.py` on every design draft.
- `feature-spec` runs `check_profile.py --decisions` before it applies a project decision.
- `feature-review` runs `lint_feature.py`, and its checklist has a column for what the linter covers.

## Outcome

- The plugin ships two scripts, both `gdd-intake` converters. `convert_office.py` turns office files into text. `emit_json.py` turns the design's config tables into draft JSON, and it holds the design parsing that it used to import from `lint_design.py`.
- `check_profile.py`, `lint_design.py`, and `lint_feature.py` are gone, with their tests and fixtures.
- Each step that ran one of them now says what the agent checks, why, and where to read it. The check names its purpose, so the agent can apply it to a design or codebase that the template did not foresee.
- A PERF-01 acceptance names its call sites. The spec lists each accepted blocking call in an `Accepted blocking calls` table, and `feature-build` and `feature-review` treat any other blocking call as a PERF-01 break. A rule that step 1 of Core blockers leaves out goes on a `Left out:` line with its reason.
- `feature-build` and `slicing.md` check line endings with `git ls-files --eol`, one plain command, in place of the `tr` and `wc` pipeline.
- `python3 -m unittest discover -s tests` and `python3 scripts/validate_plugin.py --denylist <local denylist>` pass.

## Surfaces

- Agents and developers who run the six skills on a target game server repository.
- `server-profile`, `gdd-intake`, `feature-spec`, `feature-build`, and `feature-review` skill files and references, `docs/usage.md`, the `gdd-intake` scripts, and the tests in this repository.

## Constraints

- The skills only help an agent write correct game server code. They never organize agents or the order of execution.
- A guideline names a check and its purpose, and leaves the method to the agent. It may suggest a command, but no step depends on a script.
- No change lands on `main` without the owner's approval.

## Out of scope

- Rule fixes B1, B3, B5, B6 (item 4). They come next, stacked on this branch.
- The worked example and slice size (item 5).
- The eval (item 6).
- Loosening the fixed parts of the templates, such as the sixteen design sections and the fourteen spec sections. The guidelines in this branch keep the templates as they are.
- `scripts/validate_plugin.py`. It checks this repository, and the plugin does not ship it.

## Decisions

### The owner's

- No check scripts in the skills. Only the `gdd-intake` converters stay.
- A skill gives guidelines, and the agent checks its own work. Scripts hard-code the skill.
- Skills must stay flexible, because game designs vary a lot.
- PERF-01 is accepted per call site in each spec, never in `decisions.md`.

### Mine

- This branch stacks on `feat/project-decisions` and keeps its prose. Removing `check_profile.py` also removes its `--decisions` check.
- `feat/check-scripts` stays as it is. Its prose parts, the `Accepted blocking calls` table and the `Left out:` line, are rewritten here without the scripts.
- The profile's `lint` keys stay. They tell the agent which calls the project forbids, and the agent searches for them itself.
- The checklist's `lint` column goes, because no linter fills it.

## Open questions

- None.
