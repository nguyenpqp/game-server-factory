# Slicing a spec

Slicing cuts a `ready` spec into build units that each end in a check. It writes one task list, at `docs/game-server/features/<feature>/tasks.md` unless the developer names another path. The format does not depend on who runs the tasks: a developer, a subagent, or a workflow tool can each take one task at a time. Never slice a `draft` or `blocked` spec. Read the profile first, because Verify and Writes come from its `test_one_cmd`, `build_cmd`, `source_root`, `test_root`, `feature_root`, and `generated_paths` keys.

## Slice size

One slice fits one fresh context. Aim for 80 to 150 lines of production code, plus its tests. A slice larger than that splits. A slice much smaller merges into its neighbor in the same layer, unless a blocking edge keeps them apart.

A composite command splits into three slices, in this order:

1. **Parse and validate.** The request decoder, every field check, the Checks table with its error codes, and the negative and old-client tests.
2. **Business logic.** The pure core of the Effect, with `now` and the RNG as parameters. It covers the cost check before any take, the refund path, the grant call with its reason and trace id, and the main flow, time, and random tests.
3. **Persist, respond, and log.** The command entry that runs parse, process, respond, and log in that order. It adds the idempotency record, the response, the pushes, the metric rows, and the exception path, with the replay and metric tests.

A command is composite when it has a cost or a grant, plus idempotency or pushes, or when one slice would pass 150 lines. A read command or a small write command stays one slice.

## Slice order

Shared shapes come first, because every later slice reads them.

1. **Shared shapes.** These slices block on nothing and build in parallel.
   - Ids and wire keys. Command ids, push ids, error codes, and request and response keys, changed through the generator that the profile's CAP-GENERATED entry names. This is the ids slice. `feature-build` edits the generator source, runs the regenerate command, and reads the generated files back. Generated files never change by hand (CFG-08). When CAP-GENERATED's regenerate command runs outside the repository, such as an exporter in another repository, the ids slice is a developer hand step, not a `feature-build` slice. The developer runs the generator and brings its output into the repository. That step covers only files under `generated_paths`. Constants in ordinary source files, such as metric action names, log groups, and error codes outside `generated_paths`, go into the first build slice, not into the hand step.
   - State model. Each stored document with its defaults, bounds, schema version, and migration, plus the domain methods that cheats and admin commands call, such as a `restore` method. Its compatibility tests ship with it.
   - Config schema. The config class with its load, validation, indexes, and immutable snapshot, plus its validation tests.
2. **Commands.** One slice per command, or three for a composite command, in the order of the spec's Commands section. A command slice is blocked by the shared shapes it reads. Pushes ship with the command that triggers them.
3. **HTTP endpoints.** One slice per endpoint, blocked by the state model and the config schema.
4. **Cheats and admin.** One slice for the cheat handler and its cheats, and one for the admin commands with their API spec. Each is blocked by the state model and by any command slice whose domain method it calls.
5. **Wiring.** One slice registers the feature handler and its routes in the one place that CAP-COMMAND names, registers the cheat handler only off live, and adds login hooks. It is blocked by every command, endpoint, cheat, and admin slice. Only this slice writes the registration file and the feature handler, so no two slices write the same file.
6. **KPI queries and bot scenarios.** One slice copies each KPI query into the place that the profile's CAP-METRIC entry names, or `docs/game-server/features/<feature>/kpi.sql` when it names none. It adds a bot scenario per command when CAP-BOT is `present`. It is blocked by the command slices whose metric rows the queries read.

Two slices that write the same file need a blocking edge between them, or the task list pins the exact names each one adds. Prefer the edge.

## Line endings

When a slice changes an existing file, record that file's line endings in the slice as LF, CRLF, or mixed. `git ls-files --eol <file>` prints them as `w/lf`, `w/crlf`, or `w/mixed`. A mixed file keeps each line's own ending, so `feature-build` checks after each edit that the value did not change.

## Task fields

The task list starts with the spec path and the profile path. Then it has one `##` section per slice, numbered in dependency order as `T01`, `T02`, and so on, so every task comes after the tasks it depends on. Each task has these five lines.

- **Builds.** What the slice makes work, from the player's or the developer's side, naming the spec rows it builds.
- **Depends on.** The task numbers that must be built first, or `None`.
- **Writes.** The paths or globs the slice may write. Feature code goes under `feature_root`, tests under `test_root`. The ids slice lists the generator source and the files in `generated_paths` that the generator rewrites. A hand-step ids slice lists only the files in `generated_paths`.
- **Acceptance.** One checkable line per spec row the slice builds, with the spec row's rule ids. Add one line per Test plan case the slice must pass, naming the class and the case.
- **Verify.** One exact command. Take the profile's `test_one_cmd`, put each test class's fully qualified name in `{class}`, and join the commands with `&&`. A slice with no test class uses `build_cmd`. The ids slice runs the regenerate command from CAP-GENERATED, then `build_cmd`. A hand-step ids slice runs `build_cmd` after the developer's step. Say so on the line when the command needs a database, a metric store, or credentials that a fresh checkout lacks.

## Running the tasks

Each task goes to `feature-build` with the spec and the profile. `feature-build` writes the tests first, runs Verify, and reports Verify as unrun when the build tool is missing on the machine. A task builds best in its own context, and tasks with no dependency between them can build at the same time. Run `feature-review` after the last task, or after each command's last task when the feature is large.

## Example for the login streak

These are the slices of the [worked example](worked-example.md), with the example profile's `test_one_cmd` of `gradle test --tests {class}`. ClaimStreakReward has a grant and idempotency, so it splits into three slices.

| Task | Builds | Depends on | Verify classes |
| --- | --- | --- | --- |
| T01 | Command, push, and cheat ids and the error codes 4201 to 4203 | None | none, the generator and `build_cmd` |
| T02 | StreakState with migration and `restore` | None | `StreakStateCompatTest` |
| T03 | The login streak config | None | `StreakConfigTest` |
| T04 | GetStreakState and the view it reads from StreakState | T01, T02, T03 | `GetStreakStateTest` |
| T05 | ClaimStreakReward parse and validate | T01, T02, T03 | `ClaimStreakRewardTest` |
| T06 | ClaimStreakReward business logic | T05 | `ClaimStreakRewardTest` |
| T07 | ClaimStreakReward persist, respond with the post-change state, and log | T04, T06 | `ClaimStreakRewardTest` |
| T08 | CheatSetStreak and CheatShiftDay | T01, T02 | `StreakCheatTest` |
| T09 | AdminGetStreak and AdminSetStreak with their API spec, and the StreakState push to an online target | T01, T02 | `StreakAdminTest` |
| T10 | Handler routes and registration | T04, T07, T08, T09 | none, `build_cmd` |
| T11 | KPI query SM1 | T07 | `ClaimStreakRewardTest` |

T05, T06, and T07 all add cases to `ClaimStreakRewardTest`, so they run as a chain. T05 creates the test class, and T06 and T07 each add their own cases to it. The chain costs little, because T04, T08, and T09 build beside it.

Two of the tasks in full:

```markdown
## T02. StreakState document

- **Builds.** The server keeps each player's streak in StreakState, with the defaults, bounds, and migration of the spec's State model, and a `restore` method that cheats and admin commands call.
- **Depends on.** None.
- **Writes.** `src/main/java/com/example/game/feature/streak/StreakState.java`, `src/test/java/com/example/game/feature/streak/StreakStateCompatTest.java`.
- **Acceptance.**
  - Key `streak_<userId>`, which does not change when a class is renamed. BG-01.
  - Every field has the default and the bound of the field table. BG-02, PERF-06.
  - Migration 0 to 1 runs once and records `schemaVersion` 1. BG-09.
  - `StreakStateCompatTest` passes its cases for no document and an unknown field. TEST-06.
- **Verify.** `gradle test --tests com.example.game.feature.streak.StreakStateCompatTest`

## T05. ClaimStreakReward parse and validate

- **Builds.** A claim request with a bad request id, an inactive feature, an old client, a locked player, or a claimed day gets its error code and changes nothing.
- **Depends on.** T01, T02, T03.
- **Writes.** `src/main/java/com/example/game/feature/streak/ClaimStreakRequest.java`, `src/test/java/com/example/game/feature/streak/ClaimStreakRewardTest.java`.
- **Acceptance.**
  - `requestId` is 8 to 64 characters of letters, digits, and hyphens, else `INVALID_REQUEST`. AUTH-04, AUTH-08.
  - Checks 1 to 4 run in the spec's order, each with its own error code. AUTH-06, AUTH-10, BG-07.
  - `ClaimStreakRewardTest` passes its cases for an inactive feature, an old client, a player below level 5, a second claim on the same day, and a request id of 7 characters. TEST-03, TEST-07.
- **Verify.** `gradle test --tests com.example.game.feature.streak.ClaimStreakRewardTest`
```
