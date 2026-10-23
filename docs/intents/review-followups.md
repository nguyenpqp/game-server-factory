# Review follow-ups and small changes to a ready spec

## Problem

The owner asked how the plugin could better serve "vibe coding" a game server. A read of the skills against the last acceptance eval left four gaps open and showed two sources of friction.

- Review 4 raised a critical SYNC-04 finding because the project's own add-item call pushed `ADD_ITEM` to the acting player. The profile never records whether a core inventory call pushes on its own, so the spec could not plan for it.
- The same push carried a balance the server had already stored, and no player value was at risk, yet SYNC-04 stays critical.
- A KPI query joined with a default date and counted every account as a player of the feature.
- An accepted risk that saved the reward and the claim record in separate documents did not cite MN-12 or name a process crash as its trigger.
- `feature-build` starts only from a `ready` spec, and `feature-spec` says nothing about changing one. A small change or a bug fix on a built feature has no stated path.
- The first spec on a repository with 21 partial capabilities stopped on 15 Core blockers rows, while one deployment fact resolved 9 of them.
- `feature-review/scripts/` and `server-profile/scripts/` remain on disk holding only the bytecode of removed scripts.

## Outcome

- The profile template and scan guide record, under CAP-INVENTORY, whether a check, take, or add sends a push to the client by itself. `feature-spec` counts such a push as the feature's own in Commands and Pushes, and the SYNC-04 review check looks inside the core calls a command makes.
- MET-06, the spec template's KPI part, and the review checklist say that a KPI query counts only players who reached the feature, and name the default-date join as the trap.
- `feature-spec` asks an accepted risk on fields saved in separate documents to cite MN-12 and name a process crash between the saves as its trigger.
- The SYNC-04 index severity stays critical. The `feature-review` severity audit may lower a SYNC-04 finding to important when the pushed value was stored before the push and no value depends on its delivery.
- `feature-spec` has a section for changing a `ready` spec. A change to a rule, number, or end condition edits `design.md` first in the design template format. The change is an answered Important question with the date, and each changed requirement cites `answer Q<n>`. The skill then edits only the affected spec rows, reruns the self-check and Core blockers for them, shows the developer the change, and keeps `ready` when nothing new blocks. `feature-build` names a bug against a spec row as a valid slice. `docs/usage.md` follows.
- When Core blockers has open rows, `feature-spec` groups the rows that one deployment fact would bound and asks once per fact, offering acceptance for every feature. PERF-01 stays accepted call by call.
- The two stale script folders are gone from disk.
- `python3 -m unittest discover -s tests` and `python3 scripts/validate_plugin.py --denylist <local denylist>` pass.

## Surfaces

- Developers and agents that profile, spec, build, and review features with the plugin.
- `server-profile/references/profile-template.md` and `scan-guide.md`, `feature-spec/SKILL.md` and `references/spec-template.md`, `feature-build/SKILL.md`, `feature-review/SKILL.md` and `references/review-checklist.md`, `server-rules/references/metric.md` and `client-sync.md`, and `docs/usage.md`.

## Constraints

- Prose edits only, with no scripts and no new rule ids.
- The skills help an agent write correct server code. They never organize agents or the order of execution.
- `server-profile` never writes `decisions.md`.
- No change lands on `main` without the owner's approval.

## Out of scope

- Any eval run, including description tuning.
- Trimming the rule index, spec template, or worked example.
- Languages other than Java, and any driver or entry skill.
- A Core blockers row for TEST-10, since that rule applies only when the project has an E2E bot.

## Decisions

### The owner's

- SYNC-04 keeps its index severity, and the review audit may lower it in the stored-value case.
- A small change goes through a new `feature-spec` section, and a change to game rules edits `design.md` first.
- Open Core blockers rows are grouped by deployment fact, and the profile stays unchanged.
- No trimming without a way to measure it.
- Delete the stale script folders.
- One branch and one pull request.

### Mine

- Drop the TEST-10 follow-up, because a conditional minor rule should not add a stop.
- Put the core-push fact on CAP-INVENTORY rather than a new capability, since the grant call is where the push hides.
- Keep each item in its own commit so the owner can drop one in review.
- Record a design change as an answered question rather than a dated `prompt` source. The design template already gives that question a date and an `Affects` list, and `feature-review` reads an `answer Q<n>` source as having no GDD text to check, so the change does not show as a contradiction of the GDD.
- Set the spec to `draft` while a change is edited, so `feature-build` cannot build an unconfirmed change.

## Open questions

- None.
