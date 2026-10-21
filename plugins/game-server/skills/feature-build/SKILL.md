---
name: feature-build
description: Implement a Java game server feature, command, handler, or spec slice in the target project's own idiom, with unit tests first and metric logs on every action. Use when building a slice of a server feature spec, writing a command handler, request parsing and validation, a pure core with injected time and RNG, per-user state and lazy migration, a feature config class, cheat commands, admin commands, an HTTP callback through the durable inbox, metric rows with a trace id, or the registration code that wires them. Reads the project profile and the feature spec, and writes code only through the core APIs the profile records. Keywords are game server, Java, feature build, implement command, cmd handler, unit test, JUnit, metric log, trace id, cheat, admin command, config snapshot, Couchbase, Redis, multi-node, blue-green, client compatibility.
---

# Feature build

This skill implements one slice of a server feature spec in a Java game server. The slice ships with its unit tests, its metric calls, and its registration code. Every core call goes through an API that the project profile records.

The skill does not design the feature, and it does not review it. `feature-spec` writes the spec and slices it. `feature-review` checks the result. `server-rules` explains each rule id cited here. `server-profile` writes the profile.

## Required inputs

- The profile at `docs/game-server/profile.md` in the target repository. Its format is the [profile template](../server-profile/references/profile-template.md). When the file is missing, stop and tell the developer to run `server-profile`.
- The spec at `docs/game-server/features/<feature>/spec.md`. Its format is the [spec template](../feature-spec/references/spec-template.md). When the file is missing, stop and point to `feature-spec`.
- The slice to build. It is one ticket from the spec's slicing, with Builds, Writes, Acceptance, and Verify, or one item of the ordered task list. When the developer names no slice, build the first slice that is not built yet and say which one.

Rule ids refer to the [rule index](../server-rules/references/index.md).

## Gates before any code

Check these in order. Each failed gate stops the skill with a report to the developer.

1. The spec header's `Status` is `ready`. On `blocked`, refuse to start, and quote the Core blockers rows that block. On `draft`, ask the developer to finish and confirm the spec first.
2. The profile's `profile_version` matches the version that the spec header names. When they differ, list the capability entries that changed and ask whether the spec still holds.
3. Every capability that the slice uses is `present` in the profile, or its Core blockers row has the resolution `core changed`, `descoped`, or `accepted by <name>: <reason>`. Find the capabilities from the `needs` lines of the rules that the slice's spec rows cite. A capability that is `partial` or `missing` with no resolved row stops the build. Report the rule ids blocked, the profile entry's `blocker` and `proposal`, and the spec rows that need it. Never work around a missing capability in feature code.
4. Every command id, push id, error code, and wire key that the slice needs exists in the generated files. When one is missing, stop and name the change from the profile's CAP-GENERATED entry, which gives the generator source to edit, the ids to add, and the regenerate command. Never write into a path under `generated_paths` (CFG-08).

## Translate the patterns into the project

The references write Java with generic names. Before using a pattern, replace each name with the API from the profile entry in this table, and copy the call shape from that entry's `snippet`. When the profile entry has no API for what the pattern needs, gate 3 applies.

| Generic name | Profile entry |
| --- | --- |
| `UserActor`, `submitTo` | CAP-ACTOR, CAP-OWNERSHIP |
| `Request`, `Response`, `Push` | CAP-COMMAND, CAP-RESPONSE |
| `Errors` | CAP-ERRORS |
| `ClientVersion` | CAP-CLIENTVER |
| `KvStore`, the state document | CAP-USERSTORE, CAP-CAS |
| `RedisOps` | CAP-REDIS |
| `Inventory` | CAP-INVENTORY |
| `Inbox`, `CrossNode` | CAP-INBOX, CAP-CROSSNODE |
| `FeatureConfig`, `ConfigException` | CAP-CONFIG |
| `Env` | CAP-ENV |
| `ServerClock` | CAP-CLOCK |
| `GameRandom` | CAP-RNG |
| `MetricLogger` | CAP-METRIC |
| `TraceIds` | CAP-TRACEID |
| `@CheatCommand` | CAP-CHEAT |
| `AdminCommand`, `AdminAudit` | CAP-ADMIN |
| `HttpEndpoint` | CAP-HTTP |
| Test fixtures | CAP-UNITTEST |

Put production code under the profile's `feature_root`, in the package that the spec header names. Put tests under `test_root`, in the same package.

## The slice loop

Run these steps for each slice, in order.

1. Read the spec rows that the slice covers. They are its commands, pushes, state documents, config keys, metric actions, cheats, admin commands, HTTP endpoints, and test plan rows. Note each row's rule ids.
2. Write the failing unit tests first, against the pure core. Take the cases from the slice's rows in the Test plan, and add the cases that [unit tests](references/unit-tests.md) requires for each shape the slice adds. Run them once with `test_one_cmd` and confirm that they fail because the code is absent, not because a fixture is broken.
3. Implement the slice with the matching reference. Write only the code that the slice's spec rows ask for.
   - A client command uses [command shape](references/command-shape.md).
   - Feature config uses [config class](references/config-class.md).
   - Stored per-user state uses [state model](references/state-model.md).
   - Cheat commands use [cheat commands](references/cheat-commands.md).
   - Admin commands use [admin commands](references/admin-commands.md).
   - An HTTP endpoint uses [HTTP callbacks](references/http-callbacks.md).
4. Wire registration in the places that the profile names. Register the command handler where CAP-COMMAND says. Register the cheat handler only when the server is not live (CHEAT-01). Load the config at startup and in the reload hook from CAP-CONFIG. Register each inbox entry type with CAP-INBOX. Add each per-user admin command to the routing that sends it to the target user's owner (ADMIN-02). A command that is coded but not registered fails no unit test, so read the registration code back after the edit.
5. Add the metric calls that the spec's Metric events section lists. Every action row, currency or item reason, and extra field matches the spec by name. Every row carries the action's trace id (MET-01, MET-02, MET-03, MET-04, MET-07).
6. Run `test_one_cmd` from the profile once per test class of the slice, with `{class}` replaced by the fully qualified class name. Fix the code until every class passes. Do not weaken a test to make it pass.
7. Check the new files against the profile's `lint` keys. None contains a match for `lint.forbidden_time`, `lint.forbidden_random`, or `lint.blocking_calls`. Each command class contains `lint.metric_call` and `lint.trace_id_call`. A command class is a class under `feature_root` that declares a method whose name matches `lint.command_method`, or `handle\w*` when the profile has no such key. Each cheat class contains `lint.cheat_marker` and `lint.env_live_check`. A key with an empty value skips its check.
8. Report the slice. Hand the diff to `feature-review` when the developer or the workflow asks for a review.

### When the build tool is missing

Before step 2, check that the first word of `test_one_cmd`, such as `gradle` or `mvn`, is on the `PATH`, or that the wrapper script it names exists in the repository. When neither holds, write the tests and the code anyway, skip the runs in steps 2 and 6, and report every check as unrun. Never report an unrun test as passing.

## Report

End each slice with this report. Write `none` for an empty part.

```markdown
## Slice <name>

- Spec rows: <the commands, documents, config keys, and other rows the slice covers>
- Files: <every file added or changed>
- Tests: <each test class and its cases>
- Check: <each test_one_cmd as run> passed | failed with <failing cases> | NOT RUN, <tool> not found
- Lint self-check: clean | <file:line and the matched key>
- Rules: <the rule ids the slice implements>
- Stopped on: <the failed gate, with the blocker or the generator change the developer must make>
- Follow-ups: <work outside the slice, such as a spec row that contradicts the profile>
```

When the check did not run, the report also says that the code was not compiled.

## Never

- Never start while the spec status is `blocked`.
- Never edit core code, such as networking, login, sessions, database clients, or ownership. Report the need as a blocker.
- Never hand-edit a file under `generated_paths`.
- Never read time or random numbers outside the injected clock and RNG (AUTH-02, AUTH-03).
- Never hold game or user state in a static field. The config snapshot reference is the only mutable static (MN-01).
- Never block the user actor thread on I/O, a sleep, or a wait (PERF-01).
- Never touch another user's live state from the acting user's thread (MN-02, MN-03).
- Never take a cost before every cost is checked (AUTH-07).
- Never add a fixed metric column, and never log a secret, token, or signature (MET-07, MET-09).
- Never remove, rename, or retype a stored field, a response field, or a config key (BG-01, BG-04, BG-08).
- Never put a balance number in code (CFG-05).
