---
name: server-profile
description: Builds or refreshes docs/game-server/profile.md for a Java game server repository, which records how the core provides each capability that feature code needs (commands, actors, storage, Redis, config, metrics, cheats, admin) and which missing capabilities block multi-node or blue-green safety. Use only when the developer explicitly asks to create, update, or check the server profile.
disable-model-invocation: true
---

# Server profile

Scan a Java game server repository and write `docs/game-server/profile.md`. Every other skill in this plugin reads the project through that file, so a wrong entry here misleads all of them.

## Boundaries

- The scan is read-only. The only file you write is `docs/game-server/profile.md`.
- Never edit core code, tests, config, or generated files. A missing capability gets a `proposal` in the profile and nothing more.
- Copy snippets from the project as they are. Do not invent an `api` or a `snippet` you did not read in the source.
- Rule ids come from `../server-rules/references/index.md`. Capability ids and the profile format come from `references/profile-template.md`. Do not add ids.

## Order of work

1. Read `references/profile-template.md` in full. It defines the frontmatter keys, the entry fields, the status meanings, and the capability sections in order.
2. Read `references/scan-guide.md` for the search recipes. Run them against the repository. Start from the build file and the entry point that registers handlers.
3. If `docs/game-server/profile.md` already exists, read it first. Re-check every entry against the code and keep the entries that still hold.
4. Fill the frontmatter keys first, in template order. Verify each command and regex against the code, and run `build_cmd` only when the developer allows it. An empty regex or an empty list is valid when the project has no such call, and the matching capability is then `partial` or `missing`.
5. Fill each capability section in template order, with the same heading. Do not skip a section and do not reorder them.
6. Check the profile against the template, as [Check](#check) says.
7. Report to the developer as described under Report.

## Fill each capability

Judge the status against the "Must provide" list under the capability in the template.

- `present` means the project provides every item. Fill `api`, `file`, and `snippet`.
- `partial` means it provides some items. Fill `api`, `file`, and `snippet` for what exists. Then fill `blocker` and `proposal` for what is missing.
- `missing` means it provides none. Fill `blocker` and `proposal` only.

Field rules.

- `api` names the classes and methods that feature code calls, with one line on how to call them.
- `file` is the repository path of the main source file. Use a path relative to the repository root.
- `snippet` is a short Java fragment from the project that shows the call in use. Put it in a fenced `java` block under the `snippet` line.
- `blocker` names the rule ids that cannot be met and says what fails for players or operators. Take the ids from the `needs:` lines of the rule index.
- `proposal` is the smallest core change that would make the capability `present`. Name the class to add or extend and the behavior it must have. Do not design a rewrite.

Judge by what the code does, not by what its name suggests. A class called a lease that never renews is not a lease. When you cannot tell, read the call sites. When you still cannot tell, mark the capability `partial`. In the `blocker`, name the rule ids that the unconfirmed part would break and say what you could not confirm.

## Check

Read the finished profile against the template. The other skills find each value by its frontmatter key and each capability by its heading, so a renamed or missing one stops them later. Every frontmatter key and every capability heading from the template is there. Each status is `present`, `partial`, or `missing`, and each entry has the fields its status needs. Fix the profile until all of that holds.

## Report

For each capability that is not `present`, list the rule ids it blocks. A `missing` capability blocks every rule whose `needs:` line in the [rule index](../server-rules/references/index.md) lists it. A `partial` one blocks only the rule ids on its `blocker` line. A `blocker` rule id whose `needs:` line does not list that capability is misplaced. Move the id to a capability on that rule's `needs:` line, or drop it. Put that list in your report, one line per capability, so the developer sees which rules cannot be met until the core changes. Also report the capabilities you marked `partial` because you could not confirm them. The profile file itself stays in the format of the template, with no extra sections.
