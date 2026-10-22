# Rule gaps for exceptions, admin fields, time zones, and overflow

## Problem

The plugin review found four ways that feature code can follow every rule and still lose or forge player value.

- A step that throws after the first change leaves a half-applied command. When the grant throws, the player loses the cost. When the request id is stored after the grant and that store throws, a retry grants again. AUTH-07 covers only a step that definitely fails.
- An admin command reads a required number into a primitive, so a missing field becomes 0. The ADMIN-06 example checks a value that the decoder already filled with that default. An eval run reopened a finished chain this way and paid its rewards again.
- No rule names the time zone. A core that turns server time into a date with the JVM's default zone resets the day at different times on nodes with different zones, and its tests pass only on a machine in the right zone. An eval test needed a JVM zone flag to pass.
- No rule bounds the arithmetic on amounts. `price times quantity` is safe in the command shape example only because an earlier check caps the quantity, and no rule asks for that cap to keep the product in range.

## Outcome

- AUTH-07 also covers a step that throws. Work that can throw runs before the first change. A change call that can throw is caught at the call, which undoes what ran and rethrows. The command shape notes say which steps after the grant must not throw.
- ADMIN-06 keeps a missing field apart from zero. Its example reads a required field so that absence stays visible and returns an error. The admin command reference and the review checklist say the same.
- AUTH-02 also covers the zone. Feature code turns server time into a date or a day only with the zone that CAP-CLOCK names, never the JVM default. The profile template's `lint.forbidden_time` example lists the default-zone calls. TEST-02 asks for tests that pass in any JVM zone.
- AUTH-04 also covers overflow. The checks on a field bound every amount computed from it, with the largest config values, so the result fits its type. The config check at load bounds products of config values. `Math.multiplyExact` and `Math.addExact` cover a product that no bound proves. The command shape notes point at the bound behind `times`.
- Each changed rule keeps its id, and its heading in the rule file matches the index.
- `python3 -m unittest discover -s tests` and `python3 scripts/validate_plugin.py --denylist <local denylist>` pass.

## Surfaces

- Agents and developers who build and review features with the plugin.
- `server-rules` references `auth.md`, `admin.md`, `testing.md`, and `index.md`, the `feature-build` references `command-shape.md` and `admin-commands.md`, `feature-review/references/review-checklist.md`, `server-profile/references/profile-template.md`, and `feature-spec/references/spec-template.md`.

## Constraints

- Prose and rule edits only, with no scripts.
- The skills only help an agent write correct game server code. They never organize agents or the order of execution.
- No change lands on `main` without the owner's approval.

## Out of scope

- The worked example (item 5) and the eval (item 6).
- B2 and B4, which the Accepted blocking calls table and the prose checks already cover, and the minor defects in B7.
- New rule ids.

## Decisions

### The owner's

- Fix B1, B3, B5, and B6 as prose, stacked on `refactor/prose-only-skills`.

### Mine

- Extend AUTH-07, ADMIN-06, AUTH-02, and AUTH-04 rather than add rule ids. Each gap is a case the rule already means to cover, the severity stays the same, and existing specs keep citing the same ids.
- The eval names in the review stay out of the tracked files. The rule text gives generic examples.

## Open questions

- None.
