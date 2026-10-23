# Genre notes for guilds and PvP

## Problem

The first genre notes covered rankings, gacha, economy, and events, and left guilds and PvP for later. Both are common in the games this plugin serves, and both put several players on one piece of state, which is where multi-node breaks hide. The owner set the goal "hoàn thiện bộ skill để vibe code game server" and chose genre notes that prescribe no design and put modularity, config, anti-cheat, and server authority first.

## Outcome

- `server-rules/references/genres/` gains a note for guilds and groups and a note for PvP and matchmaking, in the same format as the first four.
- The genres index, the `server-rules` skill, and the README list them.
- Every cited rule id exists in the index. No note holds a sample design or sample code.
- `python3 -m unittest discover -s tests` and `python3 scripts/validate_plugin.py --denylist <local denylist>` pass.

## Surfaces

- The same readers as the first notes: `gdd-intake`, `feature-spec`, and `feature-review`.

## Constraints

- The constraints of `docs/intents/genre-notes.md` hold: prose only, no new rule ids, no prescribed design.
- Stacked on `fix/genre-rule-gaps`. No merge into `main` without the owner's word.

## Out of scope

- Other genres, and any change to the first four notes.

## Decisions

### The owner's

- Genre notes as questions and traps, read by intake, spec, and review.

### Mine

- Take the two genres the first round left for later, under the owner's standing goal, rather than start a direction the owner did not pick.
- A gap found while writing is reported in the pull request, as before.
- One gap, the size of a shared group document, is closed here by extending PERF-06 to shared documents, the same way the earlier rounds extended rules instead of adding ids.

## Open questions

- None.
