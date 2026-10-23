# Spec a feature that already exists

## Problem

Most vibe coding on a live game server changes features that were built before this plugin. Those features have no `design.md` and no `spec.md`. `feature-build` stops without a ready spec, `feature-spec` only writes a spec from a design or a prompt, and `feature-review` falls back to the rules alone. So a developer who says "fix the claim bug in the old daily quest" gets no path through the skills. The owner's goal is "hoàn thiện bộ skill để vibe code game server".

## Outcome

- `feature-spec` has a section for a feature that exists in code and has no spec. It reads the feature through the profile and writes `design.md` in the design template format, then `spec.md` in the spec template format. It changes no code.
- The design describes what the player sees, does, and gets today, in game terms. Each requirement cites the code with a new source format, `code <path>:<line>`. Behavior that looks unintended, or whose fix would change what players see, becomes an open question whose interim default is the current behavior.
- The spec describes the feature as it should run under the rules. A rule break that players cannot see is written as the rule-correct row. A break whose fix players would see follows the answer to its question.
- `feature-review` treats a `code` source as having no GDD text, so it writes `no source` for it.
- The design template, `docs/usage.md`, the README, and the `feature-spec` description name the path.
- `python3 -m unittest discover -s tests` and `python3 scripts/validate_plugin.py --denylist <local denylist>` pass.

## Surfaces

- Developers and agents that change, fix, or review features built before the plugin.
- `feature-spec/SKILL.md`, `gdd-intake/references/design-template.md`, `feature-review/SKILL.md`, `docs/usage.md`, and `README.md`.

## Constraints

- Prose only, no scripts, no new rule ids.
- The skills only help design and write server code. They organize no agents and no git workflow.
- No merge into `main` without the owner's word.

## Out of scope

- A second worked example and a lighter spec for small features.
- Fixing the old code. That stays with `feature-review` findings and `feature-build` slices.

## Decisions

### The owner's

- The standing goal above. Earlier rounds set the rules: prose only, no orchestration, no eval runs, no merge without permission.

### Mine

- Take this direction under the goal without a new interview round, because the goal hook asks to keep working without pausing, and this is the direction recommended first in the last round.
- `feature-spec` writes the design from code, not `gdd-intake`, because `gdd-intake` reads design material, and reading code needs the profile that `feature-spec` already loads.
- The spec states the rule-correct target, so the review of the old code lists its breaks as findings, and `feature-build` fixes them one slice at a time.

## Open questions

- None.
