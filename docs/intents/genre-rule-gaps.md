# Rule gaps from the genre notes

## Problem

The review of the genre notes found four breaks that lose or forge player value while no rule covers them.

- Progress that pays a reward, such as points toward a milestone, can reach another feature of the same player on a best-effort event. MOD-02 lets that event drop, and MN-03's inbox covers only another user.
- A design may reset limits or missions at each player's local time. AUTH-02 allows only the zone that CAP-CLOCK names, so the rule forbids the design, and nothing stops a zone change from passing the same reset twice.
- A season close pays by rank from a board that still changes, so a late write or a removed entry shifts ranks during the payout. MN-07 claims each unit once but says nothing about the input.
- A store receipt that the client forwards can be replayed on another account. AUTH-08 dedupes per user, and HTTP-04 covers callbacks only.

## Outcome

- MOD-02 says that a same-player effect that pays value never rides only an event. It is a contract call before the reply, or an entry in the player's durable inbox whose id comes from the action's request id.
- AUTH-02 allows a player zone that the server stores, set by a rule the design gives, and requires a stored period label that only rises, so a zone change never gives a reset for a period already had. The core still takes the zone as a parameter, and when a change takes effect stays the design's call.
- MN-07 says that a job paying by rank, or by any value that still changes, pays every unit and every retry from one whole stored copy of its input, taken after the closed marker and written create-if-absent.
- AUTH-08 says that value from an outside system, such as a store receipt, is applied at most once per outside transaction id across all users. The verified id is claimed in one durable record with no expiry, shared by the callback and receipt paths, released only on a definite grant failure.
- Each changed heading matches its index line. The review checklist rows for the four rules carry the new look-fors.
- `python3 -m unittest discover -s tests` and `python3 scripts/validate_plugin.py --denylist <local denylist>` pass.

## Surfaces

- `server-rules/references/index.md`, `auth.md`, `multi-node.md`, `modularity.md`, and `feature-review/references/review-checklist.md`.
- The genre notes on the branch below this one, which already cite these four ids.

## Constraints

- Extend existing rules. No new rule ids, and each rule keeps its severity.
- Prose and rule edits only, with no scripts.
- Stacked on `feat/genre-notes`. No merge into `main` without the owner's word.

## Out of scope

- Other gaps not found by the genre review.
- Changes to the genre notes themselves.

## Decisions

### The owner's

- An earlier round set the pattern: extend a rule that already means to cover a case rather than add an id.
- Work on a branch, and stop at the pull request.

### Mine

- Close the four gaps that the genre review listed, on a branch stacked on the genre notes, so the owner can take the notes without these rule changes.
- The same-player path names the durable inbox, since it already exists for every user and is applied once by the owner.
- A season snapshot is required by MN-07 rather than by a genre note, because any job that pays from changing data has the same break.
- AUTH-08 keeps its `needs` line. The receipt claim is a create-if-absent insert in the store that CAP-USERSTORE already names.

## Open questions

- None.
