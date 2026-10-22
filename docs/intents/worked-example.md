# The worked example follows the current rules

## Problem

`feature-spec` tells the agent to read the worked example before its first spec and to copy its shape. The example was last edited before the rule fixes for throws, missing admin fields, time zones, and overflow, so it no longer shows what those rules ask.

- ClaimStreakReward answers "an error code" when the reward add fails. A test cannot assert an unnamed code, and the shop example in `command-shape.md` names one.
- ClaimStreakReward does not say what happens when the add throws, and the test plan lacks the throw case that the spec template now requires.
- AdminSetStreak does not say what a missing `streakCount` returns, the gap that let a missing field read as 0 and reset a streak. It does not say what an absent `lastClaimDay` means either.
- The day boundary test does not pass the zone to the core, the gap that let a test pass only on a machine set to the server's zone.

## Outcome

- ClaimStreakReward returns `GRANT_FAILED` when the CAP-INVENTORY add refuses, such as a balance at the limit of its type. The error codes table, the generated constants, and the T01 slice in `slicing.md` include the new code, and the test plan asserts it.
- When the add throws, the ClaimStreakReward core catches it at the call, removes what the add put in, and rethrows, as AUTH-07 asks. The test plan has that case, with an add that adds and then throws, and it asserts the balance, the unstored request id, the exception row, and a retry that grants once.
- A claim keeps `streakCount` within its stored bound of 10000, with a test at the bound.
- AdminSetStreak returns `OUT_OF_RANGE` for a missing `streakCount` or `lastClaimDay`. Both are required, because a count kept with a stale day resets on the next claim. The test plan has both missing field cases.
- The test plan says every test passes `now` and the CAP-CLOCK zone to the core and never sets the JVM's zone, and the day boundary test also holds on a machine set to UTC.
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
- The zone rule goes on one `Time:` line of the test plan, because every claim test computes a server day from `now`.

## Open questions

- None.
