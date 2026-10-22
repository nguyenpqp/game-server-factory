# The worked example follows the current rules

## Problem

`feature-spec` tells the agent to read the worked example before its first spec and to copy its shape. The example was last edited before the rule fixes for throws, missing admin fields, time zones, and overflow, so it no longer shows what those rules ask.

- ClaimStreakReward answers "an error code" when the reward add fails. A test cannot assert an unnamed code, and the shop example in `command-shape.md` names one.
- ClaimStreakReward does not say what happens when the add throws, and the test plan lacks the throw case that the spec template now requires.
- AdminSetStreak does not say what a missing `streakCount` returns, the gap that let a missing field read as 0 and reset a streak. It does not say what an absent `lastClaimDay` means either.
- The day boundary test does not pass the zone to the core, the gap that let a test pass only on a machine set to the server's zone.

## Outcome

- ClaimStreakReward returns `GRANT_FAILED` when the CAP-INVENTORY add refuses, such as a balance at the limit of its type. The error codes table, the generated constants, and the T01 slice in `slicing.md` include the new code, and the test plan asserts it.
- The ClaimStreakReward effect says that a throwing add changes nothing and reaches the runner. The test plan has that case, and it asserts that the request id is not stored and that a retry grants once.
- AdminSetStreak returns `OUT_OF_RANGE` for a missing `streakCount`, and an absent `lastClaimDay` keeps the stored day. The test plan has the missing field case.
- The day boundary tests pass the CAP-CLOCK zone to the core with `now`, so they give the same result under any JVM zone.
- `python3 -m unittest discover -s tests` and `python3 scripts/validate_plugin.py --denylist <local denylist>` pass.

## Surfaces

- `feature-spec/references/worked-example.md` and `feature-spec/references/slicing.md`.

## Constraints

- The skills only help an agent write correct game server code. They never organize agents or the order of execution.
- No check scripts in the skills.
- No change lands on `main` without the owner's approval.

## Out of scope

- Slice size and the slicing rules, which decide how the work runs.
- A grant through CAP-INVENTORY and the feature's own state live in two documents, which MN-12 forbids for fields that change together. Fixing it needs a decision on how the core saves a player's documents, so it goes to the owner.
- The eval, which the owner dropped.

## Decisions

### The owner's

- Fix the worked example only. Do not merge slices.
- No eval.

### Mine

- The failed add gets a feature code, `GRANT_FAILED`, as in the shop example, rather than a shared code that CAP-ERRORS does not list.
- The zone goes into the test rows that cross a day boundary, not into the Check line, so each row shows what it passes.

## Open questions

- None.
