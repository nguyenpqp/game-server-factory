# Genre notes

## Problem

The owner's goal is to finish the skill set so an agent can "vibe code" a game server. The rulebook is generic, and the only worked example is a daily login streak, which has no shared cluster state. Leaderboards, gacha, shops and gifts, and timed events each have traps that recur across games. The owner asked for notes per genre, with this condition: "skill không fix cứng, ưu tiên các tiêu chí tiên quyết như modular, configurable, anti-hack, server authorative".

## Outcome

- `server-rules/references/genres/` holds an index and four notes: rankings and seasons, randomness and gacha, economy and exchange, and events and passes.
- Each note says when to read it, lists the questions a design must answer, and lists the traps grouped under server authority and anti-cheat, config, modularity, and multi-node and rollout. Each trap cites rule ids that exist in the rule index. No note holds a sample design or sample code.
- `server-rules` names the notes in its Boundary and Groups. `gdd-intake` turns the unanswered questions of each matching note into open questions. `feature-spec` reads the traps of each matching note while it designs. `feature-review` checks those traps in the code.
- A trap that needs a rule the index lacks is listed as a gap in the pull request. No rule id is added.
- `python3 -m unittest discover -s tests` and `python3 scripts/validate_plugin.py --denylist <local denylist>` pass.

## Surfaces

- Agents and developers that run `gdd-intake`, `feature-spec`, and `feature-review`.
- `server-rules/SKILL.md`, the new `server-rules/references/genres/` files, `gdd-intake/prompts/extractor-prompt.md` or `SKILL.md`, `feature-spec/SKILL.md`, `feature-review/SKILL.md`, and `README.md` or `docs/usage.md` where they list what the rules hold.

## Constraints

- Prose only, with no scripts and no new rule ids.
- The notes guide and never prescribe a design, because game designs vary widely.
- The skills only help design and write server code. Git workflow, branching, and merging belong to the workflow plugin in use.
- No merge into `main` without the owner's word.

## Out of scope

- Other genres, such as guilds, PvP, and matchmaking. They can follow the same format later.
- Java do and don't snippets in the notes.
- A second worked example, the legacy feature path, and a lighter spec for tiny features.
- Any eval run.

## Decisions

### The owner's

- Four genres: rankings and seasons, randomness and gacha, economy and exchange, events and passes.
- Questions and traps that point at rule ids, with no fixed design.
- Intake, spec, and review all read the notes.
- Work on a feature branch and stop at the pull request.

### Mine

- The notes live under `server-rules`, because all three reading skills already load it and it is the shared knowledge base.
- Traps are grouped by the owner's four criteria first, then multi-node and rollout, so the priority shows in the layout.
- A feature that spans genres reads every matching note.

## Open questions

- None.
