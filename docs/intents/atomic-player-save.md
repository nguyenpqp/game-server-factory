# A player's documents save in one write

## Problem

MN-12 puts fields that change together in one document, because the store has no transaction across documents. A grant goes through CAP-INVENTORY into the core's document, while the feature records the claim or purchase in its own document. A crash between the two saves keeps the grant and loses the record, so a retry grants again, or keeps the record and loses the grant. The feature cannot move its fields into the core's document, so no feature can meet MN-12 on its own, and nothing in the profile shows whether the core prevents the split.

## Outcome

- CAP-USERSTORE must provide a save that writes every changed document of one player in one write that lands whole or not at all, such as one document per player or a batch the store applies all or nothing. A core whose documents save on their own is `partial`, and its blocker names MN-12.
- The scan guide says how to find that save and when it is partial.
- MN-12 says that a change spanning the core's documents and the feature's own, such as a grant and the record of it, relies on that save, so a partial CAP-USERSTORE puts MN-12 in Core blockers.
- `feature-spec`, the spec template, `command-shape.md`, and the review checklist say the same: fields that change together go in one document or in documents that CAP-USERSTORE saves in one write.
- The worked example's multi-node row for the player's own state says the claim's grant and StreakState save in one write.
- `python3 -m unittest discover -s tests` and `python3 scripts/validate_plugin.py --denylist <local denylist>` pass.

## Surfaces

- `server-profile` profile template and scan guide, `server-rules` MN-12, `feature-spec` skill, template, and worked example, `feature-build/references/command-shape.md`, and `feature-review/references/review-checklist.md`.

## Constraints

- The skills only help an agent write correct game server code. They never organize agents or the order of execution.
- No check scripts in the skills.
- No change lands on `main` without the owner's approval.

## Out of scope

- How a core implements the one write.
- Documents of other players, which MN-03 and MN-04 cover.

## Decisions

### The owner's

- The atomic save is a CAP-USERSTORE requirement. A core without it is `partial`, and MN-12 becomes a Core blockers row that the developer resolves like any other.

### Mine

- The requirement names the outcome, one write that lands whole or not at all, and gives two common forms, so the scan judges the core in front of it.

## Open questions

- None.
