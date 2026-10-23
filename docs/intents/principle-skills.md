# Principle-only skills

## Request

The owner wants the skills to hold only the principles that matter, with no hard-coded templates and no rigid step-by-step procedures. The agent is capable enough to write and review code from the principles.

## Decisions

- Merge the six skills into three: `server-principles`, `gdd-intake`, and `feature-review`.
- Replace the 116 rule ids, their Java do and don't examples, and the capability ids with thirteen principles, each with its reason.
- Drop every template: the profile, the design, the spec, the decisions file, the task slicing, the worked example, and the review checklist.
- Keep the six genre notes as design questions and code traps, without rule ids.
- Keep the GDD office converter, the only script in the plugin.
- The validator stops checking rule ids, capability ids, and the rulebook.

## Outcome

An agent that loads `server-principles` knows what good feature code looks like and why, and decides the form of any plan, design, or report itself.

## Out of scope

Eval runs, workflow or git guidance, and changes to the converter.
