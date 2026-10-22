# Project-wide Core blockers decisions

## Problem

A Core blockers resolution lives only in the spec of one feature. The next feature on the same repository meets the same capability gaps and stops for the developer again. The acceptance eval stopped on 15 Core blockers rows for one small feature, on a profile with 21 partial and 2 missing capabilities. The owner wants an agent that can "vibe code tính năng cho server game" and stops only for product decisions.

## Outcome

- A developer can accept a Core blockers risk once for every feature. The acceptance is a row in `docs/game-server/decisions.md` in the target repository, with an id, the capability, the profile status at signing, the rules, the deployment fact, how the fact bounds the failure, the developer's name, and the date.
- `feature-spec` applies a decision to a blocking row when the decision names the row's capability, its recorded status equals the profile's status, it lists every rule that the row blocks, and its bound covers the row's failure. The row then gets the resolution `accepted by <name> (D<n>): <reason>`, and the spec does not stop on it.
- When the developer accepts a row, `feature-spec` asks in the same round whether the acceptance holds for this feature only or for every feature. For every feature, it appends a decision row.
- `check_profile.py --decisions <file>` fails on a decision that names PERF-01, names a rule that the capability does not block in the profile, records a status that differs from the profile, lacks a field, has a malformed date, or repeats an id. It fails at line 1 on a file it cannot read, a header with no separator row, or another table, and then no decision applies. It warns when the capability is now `present`.
- `feature-build` gate 3 treats a resolution that names a stale or absent decision as `open`.
- `python3 -m unittest discover -s tests` and `python3 scripts/validate_plugin.py --denylist <local denylist>` pass on the branch.

## Surfaces

- Developers and agents that run `feature-spec` and `feature-build` on a target game server repository.
- `feature-spec/SKILL.md`, `feature-spec/references/spec-template.md`, a new `feature-spec/references/decisions-template.md`, `feature-build/SKILL.md`, `server-profile/scripts/check_profile.py`, `docs/usage.md`, and `README.md` in this repository.

## Constraints

- The profile stays a scan result. `server-profile` never writes `decisions.md`.
- A decision comes only from the developer's explicit answer or the developer's own edit.
- The checker uses the Python standard library only, like the other scripts.
- No change lands on `main` without the owner's approval.

## Out of scope

- Standing descopes. A descope names the design ids of one feature, so it stays per feature.
- Standing acceptance of PERF-01. Its risk depends on each call site, which is item 3 of the review.
- An entry skill and task status (item 2), and the other review items.

## Decisions

### The owner's

- The developer records a decision through a question that `feature-spec` asks while resolving Core blockers. Hand edits are also valid.
- A decision holds an acceptance only, never for PERF-01.
- A matching decision resolves a row with no stop, and the spec names the decision id.
- Delivery is the branch `feat/project-decisions`. Nothing merges into `main` without asking.
- Later items get their own interview round when they carry a product decision.

### Mine

- The checker is a `--decisions` option of `check_profile.py`, because that script already reads the profile statuses and the rule index.
- The file format lives in `feature-spec/references/decisions-template.md`, because `feature-spec` writes the file.
- A decision is stale when the capability's status in the profile differs from the status recorded at signing, or when the profile no longer blocks one of its rules. A stale decision resolves nothing.
- Each review item gets its own branch, stacked on the branch of the item before it.
- The multi-model arena phase of `architect` is skipped, because the checker follows the existing shape of `check_profile.py`.

## Open questions

- None.
