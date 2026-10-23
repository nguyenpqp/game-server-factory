---
name: feature-spec
description: Turn a game feature design into a Java game server spec and implementation plan. Use when a developer has a design.md from gdd-intake, a GDD, or a plain feature prompt and wants the server side designed before code, or wants to change a feature whose spec already exists, such as a new reward amount or an extra admin command. The spec covers command ids, request and response fields, checks and error codes, pushes, per-user state and migrations, Redis keys, the feature config schema, metric events and KPI queries, cheat commands, admin commands and their API spec, HTTP callbacks, multi-node safety, blue-green rollout and old client compatibility, a performance budget per command, core blockers, a test plan, and design coverage. It then slices the spec into an ordered task list that a developer or any workflow can build from. Requires the project profile from server-profile and cites rule ids from server-rules.
---

# Feature spec

This skill writes the server design of one feature as `docs/game-server/features/<feature>/spec.md` in the target repository, in the [spec template](references/spec-template.md) format. On request it also slices the spec into build units with [slicing](references/slicing.md). It writes no Java. `feature-build` implements the spec one slice at a time, and `feature-review` checks the code against it.

A complete spec for a daily login streak is in the [worked example](references/worked-example.md). Read it before your first spec.

## Inputs

- **The design.** `docs/game-server/features/<feature>/design.md`, written by `gdd-intake` in the [design template](../gdd-intake/references/design-template.md) format. Its requirement ids (`SM ST R F RW TM EC UI Q`) are what the spec's `Design` cells cite.
- **Or a prompt.** A plain description of the feature. The header then says `Design: prompt`, and the prompt follows the header as a quote. Under the quote, list the requirements you read from it, grouped by the design template's section names (States, Rules, Formulas, Rewards, Timing, Edge cases, Config tables, UI touchpoints, Open questions), each with a design-format id and `Source: prompt`. Use bold lead-ins for the groups, never `##` headings, so the spec keeps its 14 fixed sections. A prompt longer than a page, or one with balance tables, goes through `gdd-intake` first.
- **The profile.** `docs/game-server/profile.md`, in the [profile template](../server-profile/references/profile-template.md) format. It names every core call the spec may use, the command id scheme, the metric tables, and the test commands.
- **The rules.** The [rule index](../server-rules/references/index.md) lists every rule id with its severity and the capabilities it needs. Load `server-rules` for the do and don't of each rule.
- **The genre notes.** Read each [genre note](../server-rules/references/genres/index.md) that matches the feature. Design every row that a trap touches so the trap cannot happen, and cite the trap's rule ids on that row.
- **The project decisions.** `docs/game-server/decisions.md`, when it exists, in the [decisions template](references/decisions-template.md) format. It lists the Core blockers risks that the developer accepted for every feature.

## Stops before writing

Check these before you write the header. Each one ends the run until the developer acts.

1. **No profile.** When `docs/game-server/profile.md` does not exist, stop. Tell the developer to run `server-profile` first. It runs only on explicit request, so never start it yourself, and never guess the core from the code.
2. **An open Blocker question.** When the design has a question under `Open questions` > `Blocker` with status `open`, stop and ask the developer to answer it or skip it. An answered question settles the requirements it affects. A skipped question uses its interim default, and the header lists it. Important and Minor questions do not stop the spec, and the header lists each one with its interim default.
3. **A prescribed server mechanism.** When the design records that the GDD prescribes a server mechanism, such as "store the streak in Redis", weigh it against the rules. Follow it when no rule forbids it. Otherwise design what the rules allow, and say why in the header's open questions line.

When a workflow runs this skill inside a subagent, the subagent cannot ask the developer. It writes what it has, sets the status, and returns the stop and its questions to the caller, which asks the developer through its own interview.

## Procedure

Write the file top to bottom in the template's section order, with status `draft`. The template gives each section's table format and the rules that section usually cites. The notes below cover the decisions the template leaves to you.

### Header

Take the command id block from the profile's CAP-COMMAND entry, one block per feature. The package is a Java package, such as `com.example.game.feature.streak`. Its directory is the profile's `feature_root` plus the package's last segment. The minimum client is the first client version that ships the feature.

### 1. Commands

- One entry per thing the player can do, from the `The player can do` column of the UI touchpoints. A client-facing feature also has one read command whose response carries all of its client-visible state, so a client that reconnects rebuilds its view from it (SYNC-01).
- A mutating command's response carries server time and the post-change value of each field and balance it changed, and nothing else of the state. Its errors carry the same fields with the stored values (SYNC-02).
- Responses carry stored values and the stored instant of each timer. A boolean the client can derive, such as claimed today, and the second end of a timer stay out (SYNC-03).
- An effect on another feature that the response reports runs through that feature's contract before the response. An event only carries reactions that may run later (MOD-02).
- Requests carry intents only. A request never names an amount, a price, a reward, or a result (AUTH-01).
- Every request field has a type, a range or a length, and allowed values, checked before the Checks rows run (AUTH-04).
- Order the Checks rows as they run: feature active and window, client version, unlock, ownership of named objects, state preconditions, then costs. Each row has its own error code (AUTH-10).
- A cost is checked in full before any take, and the Effect says what is refunded if a later step fails (AUTH-07).
- The Effect runs on a pure core that receives `now` and the RNG as parameters (AUTH-02, AUTH-03). Name the inventory call from CAP-INVENTORY with the reason constant and the trace id (MET-03, MET-04).
- Decide idempotency per command. A command whose retry would grant value twice takes a `requestId` (AUTH-08). Store the smallest record that answers a replay with the first result, such as the last request id and its result for a once-a-day claim, and bound it (PERF-06).
- Add a rate limit when the command reads the database, touches other users, or fans out (AUTH-09). Otherwise say `None.` and why.
- New error codes come from the feature's block, added the way CAP-ERRORS describes. List shared codes in the Checks table, but only the feature's own codes in the Error codes table.

### 2. Pushes

Take the rows from the `Changes without player action` column of the UI touchpoints, and from server-side changes such as another player's action or a support repair. A push reports only a change that the client did not cause, and its row says why the client cannot know it (SYNC-04). The player's own command answers with the change, and a client that logs in or reconnects calls the read command, so the feature pushes nothing at login or after the player's own command. A change the client can compute from stored values and server time, such as a countdown that reaches zero, needs no push. Let the client refresh at a time the server sent, such as `nextDayStartsAt`. A server timer per user breaks MN-11. A push is best effort, so the value it reports is stored first, in the user's state or the durable inbox (SYNC-04). Every push has a minimum client and is never sent to an older one (BG-06).

A core call can push by itself. When the profile's CAP-INVENTORY `api` says a take or an add sends a push, every command that makes that call sends it after the player's own action. Use the form of the call that sends none when the profile names one. Otherwise name the push and the call on the command's `Pushes:` line, so the review can weigh it against SYNC-04, and keep the post-change balance in the reply (SYNC-02).

### 3. State model

- Put new per-user state in its own document, or as new fields on an existing one. Never rename, remove, or retype a stored field (BG-01).
- Fields that must change together go in one document, or in documents that CAP-USERSTORE saves in one atomic write, such as a grant and the feature's record of it. The store has no transaction across documents, so a crash between two saves keeps one change and loses the other (MN-12). When the profile gives no such write for them, such as a grant that the core inventory saves and the feature's record of it, cite MN-12 on the feature's document row and on the command's Effect, and let the Core blockers row name a process crash or a failed write between the two saves as the trigger, with what the player keeps and what they lose. An acceptance of that row bounds that trigger. State that lives only for a session stays out of stored documents (MN-02).
- Every field has a default for documents that lack it, and a bound. Every list has a cap (PERF-06).
- Store timestamps or day numbers, and derive ready, expired, and broken from them on each read (MN-11).
- Redis holds only cluster-wide state. Each key pattern names its hash tag, its atomic operation, and its TTL (MN-05, MN-06, PERF-08). A feature without such state writes `None.` under Redis keys.
- States and transitions cover every design state, with the guard the server checks.

### 4. Config schema

Build the keys from the design's Config tables, one file per feature (CFG-01). Each allowed value and cross-row check becomes a load-time validation (CFG-02). Each lookup on the command path gets an index built at load (PERF-05). A time-bound feature takes its window from the design's Timing table (CFG-04). Secrets, allowlists, and endpoints go to environment config (CFG-07). Each cost and reward is one `{id, amount}` record (CFG-09). Each table of rows is a list with an `id` per row, even for one row, an option that is not offered is an omitted key, never a zero, and no key repeats a value that another table owns (CFG-10). Command id constants and other generated files change through the generator that CAP-GENERATED names (CFG-08).

### 5. Metric events and KPI queries

One action per command, written on success and on every error (MET-01). Each step of the design's Gameplay loop that the server sees is a funnel step (MET-05). Each reward and cost is a source or sink row (MET-04). Write one KPI query per success measure, against the tables that the profile's CAP-METRIC entry describes (MET-06). State the meaning of every extra field (MET-07).

### 6. Cheat commands

Give the client a cheat for every design state it must test (CHEAT-05). Reuse an existing project cheat when one reaches the state, such as a level cheat. A time cheat shifts the acting user's clock offset only (CHEAT-07). Each cheat changes state through the feature's domain methods (CHEAT-06).

### 7. Admin commands and API spec

Ship a read command and a repair command for the feature's per-user state (ADMIN-08). A command that overwrites or resets user data is destructive on live and needs `confirm` (ADMIN-04). Write one API entry per command (ADMIN-05). When CAP-ADMIN names an admin web repository, list the screens that call each command.

### 8. HTTP endpoints

Add an endpoint only for a caller that cannot log in, such as a payment provider (HTTP-01). Otherwise write `None.` with the reason.

### 9. Multi-node analysis

Fill every fixed row. A row that does not apply says `none` and why. Read the profile's CAP-OWNERSHIP, CAP-CROSSNODE, CAP-INBOX, CAP-LEASE, and CAP-REDIS entries before you claim a row is safe. CAP-REDIS says whether Redis is one instance or a cluster, which decides MN-06.

### 10. Blue-green and client compatibility

Write the Deploy line first, with the four conditions of a rolling deploy from the template. Then fill every fixed row. Each `Test` cell names a test class and case from the Test plan, or says why no test applies.

### 11. Performance budget

Use 100,000 peak concurrent players and 1,000,000 daily active players unless the developer gives other numbers. Show the arithmetic for calls per second: daily calls divided by 86,400 s, times a peak factor of 3 unless the profile states another. Count database and Redis calls on the command path, and say when the save cycle writes later. Add login cost when the feature loads a new document at login.

### 12. Core blockers

Run the four steps in the template. In step 1, leave out a rule that the spec cites only on a fixed Multi-node or Blue-green row stating the feature has nothing of that kind, such as "The feature has no job" under MN-07. The feature does not depend on that rule, so its capability is not needed. Name each such rule that the profile blocks on the template's `Left out:` line.

For each blocking row, cut the profile entry's `proposal` down to what this feature needs. Write the players' failure in one sentence.

Then apply the project decisions, the risks the developer accepted for every feature. When `docs/game-server/decisions.md` exists, read it against the current profile and each row. The [decisions template](references/decisions-template.md#when-a-decision-applies) says when a decision resolves a row and how to write the resolution. A row that a decision resolves does not stop the spec.

A `critical` rule may be accepted only with a reason that names the deployment fact and says how that fact prevents or bounds the failure in the row's `What fails for players` cell, such as "one node per realm, so no second node can load the player and save over the claim". A reason that only cites a fact, without that link, counts as `open`. Ask the developer for the link. List each accepted critical rule id with its reason, and its decision id when a decision resolved it, on the header's `Accepted risks` line. Write `None.` there when there is none.

A row that blocks PERF-01 is accepted call by call. When the developer accepts one, fill the template's `Accepted blocking calls` table. Find the calls in the Commands, Admin commands, and HTTP endpoints sections, such as an admin read of an offline player.

When any row counts as `open`:

1. Set the header to `Status: blocked`.
2. Leave sections 13 and 14 under their headings with the line `Not written while Core blockers has an open row.`
3. Save the file and give the Core blockers section to the developer. Ask about the open rows in groups, because one fact about how the project runs often bounds many of them. Read the profile and the project's deploy files, such as deploy scripts and server config, for candidate facts, such as one game process per realm. Group the rows that one fact would bound, and for each row in a group write how the fact bounds its `What fails for players` cell. Ask one question per group, showing the fact, its evidence, and each row's bound. The developer confirms or rejects the fact, keeps or drops each row's bound, and chooses this feature or every feature. A row whose bound the developer drops, and every row of a rejected fact, goes back to its own question. Offer the other resolutions too: change the core, descope, or accept with another reason. Ask about a row that no fact bounds on its own, with the same resolutions. Keep a row that blocks PERF-01 out of the groups, and never offer accept for every feature on it.
4. Stop. Only the developer sets a resolution. Never design around a missing capability.

When the developer accepts a row for every feature, add a decision to `docs/game-server/decisions.md` in the decisions template format, with the developer's name and today's date. A group accepted for every feature adds one decision per capability, each with the group's fact. Create the file with its title, header row, and separator row when it does not exist. Read the new decision against the template, then resolve the row from it. When the developer resolves every row, finish the remaining sections.

### 13. Test plan

Cover every case the template lists. Put each test class in the header's package, so the profile's `test_one_cmd` runs it as `<package>.<class>`. When the profile shows CAP-BOT as anything but `present`, write no bot scenario and say so in the Check line.

### 14. Design coverage

One row per design id, including success measures and open questions. An id the spec does not build names the Core blockers row that descoped it, or the open question that holds it. An id with no server effect, such as a layout-only UI row, says `client only` and why. `feature-review` traces each id from this table to code and tests, so name each spec row by its section and entry, and each test by class and case.

## Self-check

Before you ask the developer to confirm, read the spec once against this list and fix what fails.

- The 14 `##` sections appear in the template's order, with the template's headings.
- Every table row and every behavior line has a `Rules` cell, and every cited id is a heading in the rule index.
- Every row that comes from the design has a `Design` cell, and every design id has a Design coverage row.
- Every capability is named by its `CAP-*` id, and every core call matches the profile's `api` field.
- Every budget and bound is a number with a unit.
- No request field carries a result, an amount, or a price.
- Every Blue-green `Test` cell names a row in the Test plan.

## Status and confirmation

Show the developer the spec and ask for confirmation. On confirmation, set `Status: ready`. Under a workflow, the workflow's own interview confirms it. Never set `ready` while Core blockers has a row that blocks.

## Change a ready spec

A developer may ask to change a feature whose spec is `ready`, such as a new reward amount, an extra admin command, or a fix after a bug report. Change only what the request reaches, and keep every other row as it is.

1. **Sort the request.** A change to what the player sees, does, or gets, such as a rule, a number, a state, a timer, or an end condition, is a design change. A change only to the server side, such as an admin command, a metric field, or a budget, is a spec change. So is a spec row that departs from a design that stays as it is, which the spec fixes to match the design. A bug where the code breaks a spec row that is right needs no spec change. Tell the developer to hand it to `feature-build` as a slice that names the row, and stop.
2. **Set `Status: draft`** while you edit, so `feature-build` does not build an unconfirmed change.
3. **Change the design first.** For a design change, add a question under the design's Important open questions. Its title is the request, its source is `prompt`, its status is `answered on <date>: <the change>`, its interim default is the change, and `Affects` lists the ids it changes. Edit each requirement the change reaches, or add one with the next free id, and cite `answer Q<n>` as its source. Never reuse an id. A changed number in a Config tables row changes its Example cell and its Source cell, which cites `answer Q<n>`, and the same value in the draft config JSON. Change the same number wherever else the design states it. Check the design against the [design template](../gdd-intake/references/design-template.md). `feature-review` checks the code against this file, so a change that skips it reads as a divergence. When the spec header says `Design: prompt`, make the same edits to the requirements and questions listed under the prompt.
4. **Change the spec rows.** Edit the rows whose `Design` cell cites a changed id and the rows the request names, and add rows where needed. A stored field, response field, or config key changes only in the ways BG-01, BG-04, and BG-08 allow. Update the Test plan and Design coverage rows for each changed id.
5. **Recheck the changed rows.** Run the [self-check](#self-check) over them. Run the Core blockers steps for each rule id that the changed rows cite and the spec did not cite before. A new blocking row sets `Status: blocked` and goes to the developer as steps 3 and 4 of section 12 say. Keep sections 13 and 14, because the feature is already built from them.
6. **Confirm.** Show the developer what changed in each file. On confirmation, set `Status: ready`. When the spec has a task list, add a task for the changed rows at its end, in the [slicing](references/slicing.md) format, and name in it each value the shipped config file must change. When the developer rejects the change, restore every file you edited and set `Status: ready` again.

## Slicing

When the spec is `ready` and the developer asks for a build plan, follow [slicing](references/slicing.md). It writes an ordered task list to `docs/game-server/features/<feature>/tasks.md`, or to the path the developer names. Never slice a `draft` or `blocked` spec.

## Output

- `docs/game-server/features/<feature>/spec.md`, the spec.
- On request, the task list from slicing.
- A decision in `docs/game-server/decisions.md` for each risk the developer accepts for every feature.
- For a design change to a ready spec, the edited `design.md` and draft config JSON.

The skill writes nothing else in the target repository.
