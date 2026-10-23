# Review checklist

Use this checklist in `feature-review`. It lists every rule id by group with its severity, and what to look for in a diff. The wording of each rule is in the rule index of the `server-rules` skill. Open the rule text before you report a finding on it.

Severity here equals the severity in the rule index. A review may lower it with a reason, per [Severity audit](#severity-audit). It never raises it.

The `Look for` column gives common shapes of a break, not a full list. A game that the rows did not foresee can break a rule another way. Judge by what the rule protects.

## How to review a group

1. Open the spec section that the group maps to, and the changed code for it.
2. Walk the rule rows below in order. For each row, find the code that satisfies the rule or the code that breaks it.
3. Write a finding for each break. Skip a group only when the diff has nothing for it, such as no HTTP endpoint, and say so in the report.
4. For a rule that the spec cites for a command, check that the code does what the spec row says. A spec row with no code is a finding. Code with no spec row is a finding against the spec.

## AUTH: Server authority and input

Read each command handler and the core method it calls, in order. Trace every request field to its use.

| Rule | Severity | Look for |
| --- | --- | --- |
| AUTH-01 | critical | A request field that carries a price, amount, reward, result, or success flag. A handler that trusts a client-computed value. |
| AUTH-02 | critical | Any read of wall time in feature code, or a core method that fetches time itself instead of taking `now`. The profile's `lint.forbidden_time` names the direct calls. Look also for time read through a helper or a stored static. A date, a day, or an hour built without the zone from CAP-CLOCK or the player's stored zone, such as with `ZoneId.systemDefault()`. A zone from the request, or a zone change that passes a reset twice. |
| AUTH-03 | critical | Any random source other than the injected one. Look for seeds taken from the request, and for a roll done twice so a client can retry for a better result. |
| AUTH-04 | critical | A request decoded and used before a range, length, enum, or null check. A list field with no size cap. A string used as a key with no length cap. A product or sum of a request field and a config value, such as a price times a quantity, with no bound that keeps it within its type. |
| AUTH-05 | critical | An item, slot, or target id from the request used without a check that the acting user owns it or may reach it. A friend or guild member id used without a membership check. |
| AUTH-06 | critical | A state change that runs before the active, unlocked, state-transition, or cooldown check. A check that reads client-sent state. A claim or grant command that does not check the feature's terminal state, such as finished, expired, or closed, before it grants, even when a claimed list seems to cover it. |
| AUTH-07 | critical | Several costs taken one by one with no up-front check. A cost taken before a later step that can fail, with no refund on that failure. A cost taken before the shared claim it pays for. A refund after a shared write that timed out and may have landed. A call after the first change that can throw, with no catch that undoes what ran, or a request id stored after such a call. |
| AUTH-08 | critical | A grant, purchase, or claim command with no request id. A forwarded receipt or outside transaction claimed per user only, so another account can replay it. A request id stored before a step that can still fail or throw, or in another document than the grant. A retry path that can run the grant twice. |
| AUTH-09 | important | A command that loads other users or the database, or fans out, with no per-user limit. A limit that still applies the effect once exceeded. |
| AUTH-10 | important | A failure branch that changes state before it returns, or returns one generic code for different failures. |

## MN: Multi-node safety

Ask which node and which thread run each line. Ask what happens when two nodes run the same line.

| Rule | Severity | Look for |
| --- | --- | --- |
| MN-01 | critical | Static fields, singletons, and `static final` maps or lists in feature code. Look also for state hidden in a singleton or an enum field. A shared pool loaded into memory at boot and written back at shutdown. |
| MN-02 | critical | Code that reads or writes another user's live state from the acting user's thread, or that holds a user object across commands outside the actor. State that lives only for a session, such as a session key or a per-session cache, stored in the user's document, so it survives into the next session or onto another node. A state reference read before an async hop and used after it, instead of a fresh read on the owner. A continuation that the owner drops when the session ends, used to signal a caller that outlives the session. A grant decided from a private copy of another user's document instead of the owner or a shared claim. An admin repair under ADMIN-02, with the held slot and CAS, is not such a grant. |
| MN-03 | critical | A load-modify-save of a second user's document. A reward, gift, or penalty applied to a target user in the sender's command, including a direct call because the target is on this node. For a contested thing: a cost taken before the claim, an append failure that keeps the claim, a claim deleted when it settles. |
| MN-04 | critical | A `set` or `replace` on a document that two users or two nodes write. A CAS loop with no attempt limit. A catch inside the loop that applies the change again without re-reading. A change made to an object the live state also holds. A log, push, or grant inside the loop. |
| MN-05 | critical | A Redis `GET`, Java arithmetic, then `SET`. A check-then-act on a counter or a board across two calls. A fact checked in Java, such as a role or a slot's item, that the script does not recheck. An index updated in a second call. A periodic job that rebuilds an index. |
| MN-06 | important | A key name built inside a Lua script instead of passed in KEYS. On Redis Cluster, a script or a multi-key command over keys that have no shared hash tag. |
| MN-07 | critical | A scheduled job with no lease or lock. A job that checks it once at the start and runs every unit after. A unit that pays a user with no per-user claim or idempotent write. A done marker set while a unit failed. A retry scheduled outside `finally`. A job for data only the new version has that waits on the cluster lease. A weekly job that fires once instead of ticking often. A payout by rank read from the live board instead of a stored copy. |
| MN-08 | critical | A counter field or an `AtomicLong` used to make ids that are stored or sent to other users. A snowflake node id read from config that two nodes can share. An increment that recreates a missing counter from zero. |
| MN-09 | important | A node-local cache of shared data with no stated staleness bound, or with no invalidation call where a stale value is not on the safe side. |
| MN-10 | important | A lookup in a node-local session map to push to a user or test if the user is online. An online check that reads the owner record without the owner's heartbeat. |
| MN-11 | critical | A scheduled timer, `schedule`, or `Timer` that finishes a user's effect. State that stores a remaining duration that is decremented. A ready time that is not read from a stored timestamp. A speed-up that stores a remaining time instead of moving the stored timestamp, such as the start back or the ready time to now. |
| MN-12 | critical | Fields that one invariant ties together, split across two documents that save at different times, such as a cost in one and the purchase it paid for in another. A take or grant through CAP-INVENTORY and the feature's record of it, when the profile's CAP-USERSTORE blocker line names MN-12 and the spec's Core blockers has no resolved MN-12 row. |
| MN-13 | critical | A Redis or store wrapper that returns null, false, or empty on error, and a caller that maps it to "full", "absent", "offline", "already claimed", or an empty list. A claim or login path that treats a fault as a definite answer. |
| MN-14 | important | A claim, counter, or event key with no occurrence id for a thing that can close or be recreated. A close that deletes the key. A branch where a missing key means open or zero. |
| MN-15 | important | A buffered, async, or shutdown-flushed write to a score, count, or board that is a plain set instead of a monotone or versioned write. An admin override that leaves pending buffered writes. |

## BG: Blue-green rollout and client compatibility

Compare the stored classes, packets, ids, and config before and after the change. Ask what the old version and the old client do with the new data.

| Rule | Severity | Look for |
| --- | --- | --- |
| BG-01 | critical | A removed, renamed, or retyped field or key in a stored class. A class rename that changes a document key. A changed enum ordinal stored as a number. A retired enum constant that was a key in a stored map, so an old document fails to load. A stored type removed outside a maintenance deploy. |
| BG-02 | critical | A document that both versions write, with a serializer or loader that maps to a fixed class and drops fields it does not know. A save that rebuilds such a document from the class only. A new field nested where the codec keeps only top-level unknown fields. A document only its owner writes that drops new fields, with no rollback note in the spec. |
| BG-03 | critical | An existing command id or field reused for a new meaning. A retired id handed to a new command. A retired feature whose handler or packet shape is removed while old clients still send it. |
| BG-04 | critical | A response or push field inserted before existing fields, retyped, or made required. A changed meaning of an existing field. |
| BG-05 | critical | A new request field that is read without a default. A decoder that throws when the field is absent. |
| BG-06 | critical | Any new packet, field, or error code that an old client receives, including a new code on the login or reconnect path. A changed result of an existing command for an old client. |
| BG-07 | important | A new feature or changed behavior with no client version check. A check that reads a client-sent flag in the request body instead of the session version. |
| BG-08 | critical | A config key that is required, renamed, or changed in meaning. A parser that fails on an unknown key. A change to the config of an event that is already running, shipped in a rolling deploy. |
| BG-09 | critical | A migration that runs for all users at startup, runs twice with a different result, or lowers the schema version. A boot step that overwrites shared data instead of adding where absent. |
| BG-10 | critical | A drain or shutdown path that releases ownership before queued commands finish or before save results are confirmed. A feature job that keeps running during drain. A release that deletes the owner record. A failed final save that releases anyway. |
| BG-11 | critical | An inbox receiver with a `default` branch that drops, fails on, or removes an unknown type, or removes it to add it back. A fire-and-forget cross-node message that carries value not already in the inbox. A message-driven refresh with no periodic sweep. A shared replayed log that blocks on an entry it cannot read. |
| BG-12 | critical | A stored key or document format that the old version cannot read, shipped in a rolling deploy, or with no rollback step in the spec. |
| BG-13 | critical | A boot hook of the feature that catches and logs a failed config load, seed, or migration, so the node boots without it. |

## PERF: Performance

Count the calls per command, and read every loop.

| Rule | Severity | Look for |
| --- | --- | --- |
| PERF-01 | critical | A blocking call, sleep, join, lock, or database or Redis call made on the user actor thread. The profile's `lint.blocking_calls` names the common ones. Look also for the project's own synchronous client calls. A blocking call in an HTTP endpoint class, built on the profile's CAP-HTTP endpoint API, runs on an HTTP worker thread and is not a finding. A call that the spec's `Accepted blocking calls` table names, by its class and its call, is accepted. It is a finding only when its bound does not hold, such as a call that runs more often or waits longer than the row says. |
| PERF-02 | important | The count of database and Redis calls per command, against the spec's budget. |
| PERF-03 | important | A database or Redis call inside a `for`, `forEach`, or stream over users, items, or rows. A single `get` repeated where a multi-get exists. |
| PERF-04 | important | A list put into a response or push with no cap. A push sent for every change instead of once per command. |
| PERF-05 | important | A linear search through a config list on the command path. An index built per call. |
| PERF-06 | important | A list or map in user state with no cap or eviction. A history that only grows. A counter or accumulated amount with no numeric cap, or a cap with no stated reject or clamp policy. A login or logout hook that creates a document for a user who never used the feature. |
| PERF-07 | important | A loop that pushes to or changes many users inside one command. |
| PERF-08 | important | A single Redis key that every active user writes on the command path. |

## CFG: Feature config

Read the config file, its loader, its validator, and every place that reads it.

| Rule | Severity | Look for |
| --- | --- | --- |
| CFG-01 | important | Feature settings added to a shared config file. |
| CFG-02 | critical | A config field read and checked on first use. A validator that logs and continues on an invalid file. A reward type allowlist that accepts a type whose grant can be partial, capped, silently empty, or written without a metric row and trace id (MET-03, MET-04). |
| CFG-03 | important | A config object that is mutated in place, or read twice in one command so a reload can change it in between. |
| CFG-04 | important | A feature config with no `isActive` flag, or a time-bound feature whose start and end are not checked against server time. |
| CFG-05 | important | A cost, reward, rate, limit, or duration written as a constant in code. |
| CFG-06 | critical | A stored or sent value that is an index into a config list. A config reorder that changes what a stored value means. |
| CFG-07 | important | A secret, allowlist, or endpoint in the feature's balance file. |
| CFG-08 | important | A hand edit in a generated path, or a generated file changed with no change to its source. |
| CFG-09 | important | A currency or an item in a key name, such as `gemCost`, or a `currency` key paired with a separate `price` key. A cost or reward that is not an `{id, amount}` record or a list of them. |
| CFG-10 | critical | A table of rows authored as one object or as a map without an `id` per row. A zero cost or price that stands for not offered, or a validator that accepts a zero amount. A string that packs a list, such as `gold:400;potion:3`. A value copied from a table that another feature or file owns. |

## MET: Metrics

Follow one action from its first line to each return and each catch.

| Rule | Severity | Look for |
| --- | --- | --- |
| MET-01 | important | A command path with no user action row, or with a row only on success. Two rows for one action. Check each failure branch, not only the class as a whole. |
| MET-02 | important | A command that mints no trace id, or that mints a second one. A metric row written with no trace id. |
| MET-03 | important | A currency or inventory call with no trace id argument, or with a new one. |
| MET-04 | important | A source or sink with no reason constant, or a reason shared with another feature action. A grant API that writes a change row only when the grant fails. |
| MET-05 | important | A multi-step flow with one metric action for all steps. |
| MET-06 | important | A success measure in the spec with no KPI query. A query that names a column that does not exist. A share whose denominator counts players the measure does not name, such as a join that gives every account a default date. |
| MET-07 | important | A new fixed column for new metric data. An extra field with no stated meaning. |
| MET-08 | important | A command with no catch that writes an exception row, or a catch that swallows the error and sends no response. |
| MET-09 | critical | A metric extra or log line that includes a token, signature, key, or payment credential. |

## CHEAT: Cheat commands

Read the cheat registration, each cheat class, and its tests.

| Rule | Severity | Look for |
| --- | --- | --- |
| CHEAT-01 | critical | A cheat handler registered with no live check at registration. |
| CHEAT-02 | critical | A cheat class with no live check, or a check only at registration. Check that the check sits before each mutation. |
| CHEAT-03 | important | A cheat mixed into a gameplay handler, or a cheat class without the marker. |
| CHEAT-04 | important | A cheat with no metric row or no trace id. |
| CHEAT-05 | important | A feature state that a test account cannot reach by a cheat. |
| CHEAT-06 | important | A cheat that writes a field directly and skips the feature's domain method or validation. |
| CHEAT-07 | important | A time cheat that changes the node clock or a shared field instead of a per-user offset. |

## ADMIN: Admin commands

Read the admin handler, its routing to the owner, and the admin API spec.

| Rule | Severity | Look for |
| --- | --- | --- |
| ADMIN-01 | critical | An admin handler path with no session check on every request. |
| ADMIN-02 | critical | An admin command that changes a user's state from the admin's thread, or a CAS-less write to an offline document. |
| ADMIN-03 | important | A mutating admin command with no audit row, or an audit row missing the target, applied change, result, or trace id. |
| ADMIN-04 | critical | A destructive admin command with no live block and no confirmation field. |
| ADMIN-05 | important | An admin command with no entry in the admin API spec. |
| ADMIN-06 | important | An admin command that applies an effect before it validates the target, range, and ids. A required field read into a primitive, so a missing field becomes 0 or false and passes the range check. |
| ADMIN-07 | important | A mutating admin command that applies twice when sent twice. |
| ADMIN-08 | important | A per-user state with no admin command to read it or repair it. |

## HTTP: HTTP callbacks

Read the endpoint from the first byte received to the answer.

| Rule | Severity | Look for |
| --- | --- | --- |
| HTTP-01 | important | An endpoint that a logged-in player can use through the game channel instead. |
| HTTP-02 | critical | A callback handled before the signature check, a check over a parsed body instead of the raw body, a secret in code, or no timestamp check. |
| HTTP-03 | critical | An allowlist that is empty on live and allows every caller. |
| HTTP-04 | critical | A callback that acts before it takes the lock, releases the lock on success, or keeps it on failure. |
| HTTP-05 | critical | A callback that loads and saves user state, or that mutates a live user. |
| HTTP-06 | critical | A callback that trusts the user id, product, price, currency, or expiry in the body without a server-side check. |
| HTTP-07 | important | A callback path with no metric row, or a row without the transaction id. |
| HTTP-08 | important | A failure that answers success so the caller stops retrying, or a duplicate that answers an error. |

## TEST: Tests

Read the tests that the diff adds or should add. Judge the tests against the rule, not only their pass state.

| Rule | Severity | Look for |
| --- | --- | --- |
| TEST-01 | important | A core test that needs a socket, a database, or a network. A Redis script test that shares a keyspace with other tests or leaves keys behind. |
| TEST-02 | important | A test that reads real time or real random numbers, or that passes only with the JVM in one zone. |
| TEST-03 | important | A command with a check and no negative test for it. |
| TEST-04 | important | A cheat with no test that it is rejected on live. |
| TEST-05 | important | A config validator with no test for a valid file or for an invalid case. |
| TEST-06 | important | A stored-data change with no test that loads old data and data with unknown fields. |
| TEST-07 | important | A request change with no test that decodes an old request. |
| TEST-08 | important | A command test that does not assert the metric row or the trace id. |
| TEST-09 | important | An idempotent request or callback with no replay test. A retried write with no test for a failure after it applied and one before. |
| TEST-10 | minor | A command with no bot scenario, when the project has a bot. A cross-node guarantee with no drill scenario, when the project has a drill. |
| TEST-11 | minor | A test that sets the config instance, clock, or environment and does not restore it. |
| TEST-12 | minor | A test of a getter, of the JSON library's parsing, of framework delivery or saves, or of a constant restated from config. A mock `verify` with no assertion on the effect. |
| TEST-13 | important | A shared document, counter, claim, queue, or cross-node push with no test that runs two instances over one store. A shared document with no stale-copy test. A node id, clock, or sender read from a global in the component under test. |

## MOD: Modularity

Read the imports of every changed file, and every call that reaches another feature.

| Rule | Severity | Look for |
| --- | --- | --- |
| MOD-01 | important | An import of another feature's package that the profile's `lint.allowed_import` does not allow. Look also for names used fully qualified in code, and for a static lookup of another feature's service. |
| MOD-02 | critical | A reply that reports a cross-feature effect, such as a debit or a grant, that only an event applies. An event used to deliver value to another user, or progress toward a reward to the same player. |

## SYNC: Client sync

Read each reply and push that the diff adds or changes, field by field, against the stored state.

| Rule | Severity | Look for |
| --- | --- | --- |
| SYNC-01 | important | A client-facing feature with no read command, or a read command that leaves out a part that a screen shows. State that reaches the client only in a push. |
| SYNC-02 | important | A mutating reply with no server time, with a delta instead of the post-change value, or with values the command did not change. A reject that carries only the error code while the client may hold the fields wrong. |
| SYNC-03 | important | A boolean in a reply or push that compares stored values, config, or server time, such as `ready` or `claimedToday`. Both the start and the end of one timer. |
| SYNC-04 | critical | A push after the player's own command or at login, including one that a core call such as an inventory add sends by itself. Read the profile's CAP-INVENTORY `api` for those. A push for a time the client can compute. Value that exists only in a push, with no stored state or inbox entry behind it. |

## LOG: Logging

Read every log call, comment, and exception message that the diff adds.

| Rule | Severity | Look for |
| --- | --- | --- |
| LOG-01 | important | `System.out`, `System.err`, `printStackTrace`, or a logger from any factory other than the profile's. |
| LOG-02 | important | An error for a failure the code handled, or a debug or info line for a lost write or a broken invariant. A message that does not say what the failure cost. |
| LOG-03 | important | A log call in a catch block that passes `e.getMessage()` or nothing instead of the exception as the last argument. |
| LOG-04 | important | A log line on a command, job, callback, or inbox path with no user id or no trace id. |
| LOG-05 | minor | An info line or higher on the success path of a command. |
| LOG-06 | minor | A rule id, a document file name, or a section number in a comment, a log message, or an exception message. |

## DES: Design conformance

Read `design.md` itself, beside the spec and the code. Build the trace table from the design's ids, not from the spec's Design coverage, so an id the spec dropped still gets a row. Read each row's cited source in the converted GDD text under `.gdd-intake/<feature>/raw/`. That folder is gitignored, so when it is missing, say so in the report and check against `design.md` alone.

| Rule | Severity | Look for |
| --- | --- | --- |
| DES-01 | important | A design id with no code, or with code and no test, and no Core blockers row, open question, or client-only reason that records the gap. A dropped push, such as a real-time progress update that a UI row asks for. |
| DES-02 | critical | An end condition, state transition, limit, reward, cost, duration, or count that differs from the design, such as a chain that ends only after every milestone is claimed, while the design ends it at the claim of milestone 3. A config value that differs from the design's Config tables or the sheet range they cite. A design row whose rule, number, or end condition contradicts the source it cites, which is a finding against the design. |
| DES-03 | critical | Code that follows an interim default after its question was answered, or ignores the default of a skipped question. Code that contradicts a Core blockers resolution. A handler, field, or config key for a descoped id. An interim default that contradicts its cited source or another design row, such as a default that ends the chain only after every milestone is claimed while the source ends it at the claim of milestone 3, which is a finding against the design. |

## Lifecycle parity

Rules about state hold only if every entry point that touches the state follows them. List the entry points, then check each one against the same rules. A rule that holds on the main command path and fails on a side path is a finding, even when nothing on the failing line looks wrong.

| Entry point | What to check |
| --- | --- |
| Gameplay command | The full spec row: checks, cost, effect, metric, trace id. |
| Login | Lazy migration and expiry of old periods run before the first command. The client reads current state through the read command, so login sends no state push (SYNC-01, SYNC-04). |
| Logout and session close | The hook reads only state already loaded and creates no document for a user who never used the feature. Session-only state is dropped, not saved. A continuation still waiting on I/O can be dropped, so nothing outside the session waits on it. |
| Offline load | A load of a document for a user who is not online runs the same migration and keeps unknown fields. |
| Non-owner read of another user | The copy is never saved, it may refuse but never grant, and claims overlay it. |
| Boot | Feature boot steps fail the boot on error, and a shared-data step adds where absent. |
| Periodic job or tick | A lease or lock is held and rechecked between units, each unit is claimed or idempotent, the job reads stored timestamps, and a second node running it at once grants nothing twice. |
| Cheat command | The live check, the domain method, the metric row. |
| Admin command | The owner routing or CAS path, validation, audit row, and retry safety. |
| HTTP callback | Signature, allowlist, idempotency lock, delivery through the inbox. |
| Cross-node message and inbox drain | Unknown inbox types are kept in place. Applying an entry twice has no second effect. Entries applied to a user this node then loses go back to the inbox. |
| Drain | The feature stops its jobs, flushes changed state, and confirms writes. |

Also check each gate that decides whether a handler runs. If the only code that refreshes stale state sits behind that gate, the gate drops every event once the state goes stale, and the refresh never runs.

For a timed feature, list its time bounds (start, end, settlement, expiry), and note which bound each entry point enforces. Two entry points for the same player-facing surface that stop at different bounds are a finding unless the spec says why.

## Severity audit

Every report ends with a severity audit table. It has one row for each reported finding whose severity differs from the index, and one row for each Critical finding.

| Finding | Rule | Index severity | Reported severity | Reachable trigger | Reason |
| --- | --- | --- | --- | --- | --- |
| F3 | MN-03 | critical | critical | A player sends gift command 4310 for a target on another node. | None. |
| F5 | CFG-02 | critical | important | None found. Config is checked at startup by `FeatureValidator`, line 40. | The invalid value cannot reach a command. |

Rules for the table:

- A Critical row names a reachable trigger: a command, a packet, a job, a callback, or a config state that a player, an operator, or the system can produce. If you cannot name one, report the finding as important and say why in the Reason cell.
- A trigger that is rare is still reachable. Rarity is not a reason to lower severity.
- Never raise a finding above its index severity. If the index looks wrong for the case, write it as a follow-up for the rule index.
- Lower a finding only with evidence, such as a guard on the path that you read and that cannot be bypassed.
- SYNC-04 is critical because value that only a push carries is lost. Lower a SYNC-04 finding to important when you read that the pushed value is stored, in the user's state or the durable inbox, before the push is sent, and that nothing the player gets depends on the push arriving, such as a balance push after a grant to the user's state. Name the save in the Reason cell.

## Dismissal audit

A suspected break that you decide not to report is a dismissal. Keep a list of them while you review. Before you write the report, audit each one once.

For each dismissal:

1. Reopen the code at the cited line, over a wide range.
2. If the reason is "a test covers it", open the test. A test that passes with and without the break covers nothing.
3. If the reason is "a guard prevents it", confirm that the guard is reached on this path. A guard behind an earlier return, or after the effect, guards nothing.
4. If the reason is "the exception is caught", read the catch. A catch that sends no response, or that hides a failed save, is a finding.
5. If the reason is "the config never triggers it", the finding stands, and you may note it as inert today.

Keep the dismissal only when the check holds. List the kept dismissals in the report with the evidence, so the developer can disagree.
