---
name: feature-review
description: Review Java game server feature code, a pull request, or a diff against the feature's game design and the server-principles skill. Use when asked to review, audit, or check game server code for exploits and server authority, double grants or lost value, multi-node races, blue-green rollout and old-client breaks, config, performance, metrics and logs, cheat and admin commands, payment callbacks, tests, or whether the code does what the GDD says. Reports concrete findings with severity, location, and a failure scenario, and does not change the code.
---

# Feature review

A review answers two questions: does the code do what the design says, and can it break in production. Judge it by the principles in the `server-principles` skill and by the feature's design, not by personal taste. Report findings. Do not fix them unless asked.

## How to look

- **Read enough context.** A diff hunk hides the checks around it. Read each changed file in full, the code it calls, and the code that registers it. For a feature built before any design existed, read the whole feature.
- **Start from the design when there is one.** Walk every requirement and check that code and a test cover it, that the numbers and rules in code and config equal the design, and that decisions already made hold. A requirement with no code and no agreed descope is a finding. When there is no design, say so and review against the principles alone.
- **Think like an attacker and like a crash.** For each command ask what a hostile client can send, what happens when it is retried, when two nodes run it at once, when the node dies between two writes, when Redis times out, and when an old server or old client meets the new data. The worst bugs on a game server hide in those moments, not in the happy path.
- **Know the project's idiom.** Find how this project does clocks, randomness, storage, config, metrics, and module boundaries, and check the new code uses those. A call that bypasses them is often a finding by itself.
- **Use the genre notes.** If the feature matches a note in `server-principles`, check the code for each trap the note lists.

## What a finding needs

Each finding has a severity (from `server-principles`), the file and line, the principle it breaks, and a concrete failure scenario: what input or timing, what goes wrong, and who loses what. If you cannot describe a scenario, it is not a finding yet. Say how confident you are when the scenario depends on something you could not see.

Order findings by severity. Keep style preferences out unless they hide a real risk. End with what you did not check, such as files you could not read or a missing design, so nobody mistakes a partial review for a clean one.
