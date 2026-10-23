---
name: feature-review
description: Review Java game server feature code, a pull request, or a diff against the feature's game design and the server-principles skill. Use when asked to review, audit, or check game server code for exploits and server authority, double grants or lost value, multi-node races, blue-green rollout and old-client breaks, config, performance, metrics and logs, cheat and admin commands, payment callbacks, tests, whether the code does what the GDD says, or how far a change to existing running code reaches. Reports concrete findings with severity, location, and a failure scenario, and does not change the code.
---

# Feature review

A review answers three questions: does the code do what the design says, can it break in production, and how far does a change reach into code that already runs on live. Judge it by the principles in the `server-principles` skill and by the feature's design, not by personal taste. Report findings. Do not fix them unless asked.

## How to look

- **Read enough context.** A diff hunk hides the checks around it. Read each changed file in full, the code it calls, and the code that registers it. For a feature built before any design existed, read the whole feature.
- **Start from the design when there is one.** Walk every requirement and check that code and a test cover it, that the numbers and rules in code and config equal the design, and that decisions already made hold. A requirement with no code and no agreed descope is a finding. When there is no design, say so and review against the principles alone.
- **Think like an attacker and like a crash.** For each command ask what a hostile client can send, what happens when it is retried, when two nodes run it at once, when the node dies between two writes, when Redis times out, and when an old server or old client meets the new data. The worst bugs on a game server hide in those moments, not in the happy path.
- **Know the project's idiom.** Find how this project does clocks, randomness, storage, config, metrics, and module boundaries, and check the new code uses those. A call that bypasses them is often a finding by itself.
- **Check compatibility in four directions.** For every change to stored data, packets, or calls between nodes, ask what happens when an old server reads the new data, a new server reads old data, an old client gets the new reply, and an old client calls the new server. Then ask whether rolling back is still safe.
- **Check the module's shape.** Each part of the feature does its own job, as principle 7 of `server-principles` describes. A game rule inside a handler, I/O inside the logic, or a balance number outside the config is a finding, because it breaks testing, swapping, or tuning.
- **Use the genre notes.** If the feature matches a note in `server-principles`, check the code for each trap the note lists.

## Blast radius of changes to running code

The server is shared by thousands of players, and code already on live is proven. One changed line in the save path or the inventory can hurt every player, while a hundred new lines inside a new feature can hurt only that feature. Weigh the diff by that, not by size.

- **Split the diff.** Separate the new feature's own code from every change to code that already runs: the core, shared code, other features, and shared config. Review the second part hardest.
- **Trace every change to running code.** Find all its callers across the server, not only the new feature. Ask whether their behavior changes, whether the code sits on a path every player takes (login, load and save, inventory, currency), whether stored data or the wire format changes, whether the change can be switched off by config or rolled back without a deploy, and whether tests pin the old behavior.
- **Unneeded edits are findings.** A refactor, rename, or reformat of running code that the feature does not need adds risk with no gain.
- **Severity follows reach.** A change to shared code that alters behavior for features that did not ask for it, on a path every player takes, with no switch, is critical even when it looks correct. The same change behind a switch with tests pinning the old behavior is much smaller.

## What a finding needs

Each finding has a severity (from `server-principles`), the file and line, the principle it breaks, and a concrete failure scenario: what input or timing, what goes wrong, and who loses what. If you cannot describe a scenario, it is not a finding yet. Say how confident you are when the scenario depends on something you could not see.

Open the report with one line on blast radius: how many files of running code changed, which of them sit on paths every player takes, and whether each can be switched off. Then order findings by severity. Keep style preferences out unless they hide a real risk. End with what you did not check, such as files you could not read or a missing design, so nobody mistakes a partial review for a clean one.
