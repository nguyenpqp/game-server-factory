# Review checklist

Use this checklist in `feature-review`. It lists every rule id by group with its severity, and what to look for in a diff. The wording of each rule is in the rule index of the `server-rules` skill. Open the rule text before you report a finding on it.

Severity here equals the severity in the rule index. A review may lower it with a reason, per [Severity audit](#severity-audit). It never raises it.

The `lint` column says what `../scripts/lint_feature.py` covers. A clean lint run proves nothing about the rest of the row.

## How to review a group

1. Open the spec section that the group maps to, and the changed code for it.
2. Walk the rule rows below in order. For each row, find the code that satisfies the rule or the code that breaks it.
3. Write a finding for each break. Skip a group only when the diff has nothing for it, such as no HTTP endpoint, and say so in the report.
4. For a rule that the spec cites for a command, check that the code does what the spec row says. A spec row with no code is a finding. Code with no spec row is a finding against the spec.

## AUTH: Server authority and input

Read each command handler and the core method it calls, in order. Trace every request field to its use.

| Rule | Severity | Lint | Look for |
| --- | --- | --- | --- |
| AUTH-01 | critical | no | A request field that carries a price, amount, reward, result, or success flag. A handler that trusts a client-computed value. |
| AUTH-02 | critical | yes | Any read of wall time in feature code, or a core method that fetches time itself instead of taking `now`. The linter finds direct calls. Look for time read through a helper or a stored static. |
| AUTH-03 | critical | yes | Any random source other than the injected one. Look for seeds taken from the request, and for a roll done twice so a client can retry for a better result. |
| AUTH-04 | critical | no | A request decoded and used before a range, length, enum, or null check. A list field with no size cap. A string used as a key with no length cap. |
| AUTH-05 | critical | no | An item, slot, or target id from the request used without a check that the acting user owns it or may reach it. A friend or guild member id used without a membership check. |
| AUTH-06 | critical | no | A state change that runs before the active, unlocked, state-transition, or cooldown check. A check that reads client-sent state. |
| AUTH-07 | critical | no | Several costs taken one by one with no up-front check. A cost taken before a later step that can fail, with no refund on that failure. |
| AUTH-08 | critical | no | A grant, purchase, or claim command with no request id, or a request id stored after the grant. A retry path that can run the grant twice. |
| AUTH-09 | important | no | A command that loads other users or the database, or fans out, with no per-user limit. A limit that still applies the effect once exceeded. |
| AUTH-10 | important | no | A failure branch that changes state before it returns, or returns one generic code for different failures. |

## MN: Multi-node safety

Ask which node and which thread run each line. Ask what happens when two nodes run the same line.

| Rule | Severity | Lint | Look for |
| --- | --- | --- | --- |
| MN-01 | critical | yes | Static fields, singletons, and `static final` maps or lists in feature code. The linter finds the field forms. Look for state hidden in a singleton or an enum field. |
| MN-02 | critical | no | Code that reads or writes another user's live state from the acting user's thread, or that holds a user object across commands outside the actor. |
| MN-03 | critical | no | A load-modify-save of a second user's document. A reward, gift, or penalty applied to a target user in the sender's command. |
| MN-04 | critical | no | A `set` or `replace` on a document that two users or two nodes write. A CAS loop with no attempt limit. |
| MN-05 | critical | no | A Redis `GET`, Java arithmetic, then `SET`. A check-then-act on a counter or a board across two calls. |
| MN-06 | important | no | A Lua script or a multi-key command over keys that have no shared hash tag. |
| MN-07 | critical | no | A scheduled job with no lease. A job that checks the lease once at the start and writes later without checking the token. |
| MN-08 | critical | no | A counter field or an `AtomicLong` used to make ids that are stored or sent to other users. A snowflake node id read from config that two nodes can share. |
| MN-09 | important | no | A node-local cache of shared data with no invalidation call or no stated staleness bound. |
| MN-10 | important | no | A lookup in a node-local session map to push to a user or test if the user is online. |
| MN-11 | critical | no | A scheduled timer, `schedule`, or `Timer` that finishes a user's effect. State that stores a remaining duration that is decremented. A ready time that is not read from a stored timestamp. |

## BG: Blue-green rollout and client compatibility

Compare the stored classes, packets, ids, and config before and after the change. Ask what the old version and the old client do with the new data.

| Rule | Severity | Lint | Look for |
| --- | --- | --- | --- |
| BG-01 | critical | no | A removed, renamed, or retyped field or key in a stored class. A class rename that changes a document key. A changed enum ordinal stored as a number. |
| BG-02 | critical | no | A serializer or loader that maps to a fixed class and drops fields it does not know. A save that rebuilds the document from the class only. |
| BG-03 | critical | no | An existing command id or field reused for a new meaning. A retired id handed to a new command. |
| BG-04 | critical | no | A response or push field inserted before existing fields, retyped, or made required. A changed meaning of an existing field. |
| BG-05 | critical | no | A new request field that is read without a default. A decoder that throws when the field is absent. |
| BG-06 | critical | no | Any new packet, field, or error code that an old client receives. A changed result of an existing command for an old client. |
| BG-07 | important | no | A new feature or changed behavior with no client version check. A check that reads a client-sent flag in the request body instead of the session version. |
| BG-08 | critical | no | A config key that is required, renamed, or changed in meaning. A parser that fails on an unknown key. |
| BG-09 | critical | no | A migration that runs for all users at startup, runs twice with a different result, or lowers the schema version. |
| BG-10 | critical | no | A drain or shutdown path that releases ownership before queued commands finish or before save results are confirmed. A feature job that keeps running during drain. |
| BG-11 | critical | no | An inbox or message receiver with a `default` branch that drops, fails on, or removes an unknown type. |

## PERF: Performance

Count the calls per command, and read every loop.

| Rule | Severity | Lint | Look for |
| --- | --- | --- | --- |
| PERF-01 | critical | yes | A blocking call, sleep, join, lock, or database or Redis call made on the user actor thread. The linter finds the listed blocking calls. Look for the project's own synchronous client calls. A blocking call in an HTTP endpoint class, built on the profile's CAP-HTTP endpoint API, runs on an HTTP worker thread and is not a finding. |
| PERF-02 | important | no | The count of database and Redis calls per command, against the spec's budget. |
| PERF-03 | important | no | A database or Redis call inside a `for`, `forEach`, or stream over users, items, or rows. A single `get` repeated where a multi-get exists. |
| PERF-04 | important | no | A list put into a response or push with no cap. A push sent for every change instead of once per command. |
| PERF-05 | important | no | A linear search through a config list on the command path. An index built per call. |
| PERF-06 | important | no | A list or map in user state with no cap or eviction. A history that only grows. |
| PERF-07 | important | no | A loop that pushes to or changes many users inside one command. |
| PERF-08 | important | no | A single Redis key that every active user writes on the command path. |

## CFG: Feature config

Read the config file, its loader, its validator, and every place that reads it.

| Rule | Severity | Lint | Look for |
| --- | --- | --- | --- |
| CFG-01 | important | no | Feature settings added to a shared config file. |
| CFG-02 | critical | no | A config field read and checked on first use. A validator that logs and continues on an invalid file. |
| CFG-03 | important | no | A config object that is mutated in place, or read twice in one command so a reload can change it in between. |
| CFG-04 | important | no | A feature config with no `isActive` flag, or a time-bound feature whose start and end are not checked against server time. |
| CFG-05 | important | no | A cost, reward, rate, limit, or duration written as a constant in code. |
| CFG-06 | critical | no | A stored or sent value that is an index into a config list. A config reorder that changes what a stored value means. |
| CFG-07 | important | no | A secret, allowlist, or endpoint in the feature's balance file. |
| CFG-08 | important | no | A hand edit in a generated path, or a generated file changed with no change to its source. |

## MET: Metrics

Follow one action from its first line to each return and each catch.

| Rule | Severity | Lint | Look for |
| --- | --- | --- | --- |
| MET-01 | important | partial | A command path with no user action row, or with a row only on success. Two rows for one action. The linter finds a command class with no metric call. Check each failure branch yourself. |
| MET-02 | important | partial | A command that mints no trace id, or that mints a second one. A metric row written with no trace id. The linter finds a command class with no trace id call. |
| MET-03 | important | no | A currency or inventory call with no trace id argument, or with a new one. |
| MET-04 | important | no | A source or sink with no reason constant, or a reason shared with another feature action. |
| MET-05 | important | no | A multi-step flow with one metric action for all steps. |
| MET-06 | important | no | A success measure in the spec with no KPI query. A query that names a column that does not exist. |
| MET-07 | important | no | A new fixed column for new metric data. An extra field with no stated meaning. |
| MET-08 | important | no | A command with no catch that writes an exception row, or a catch that swallows the error and sends no response. |
| MET-09 | critical | no | A metric extra or log line that includes a token, signature, key, or payment credential. |

## CHEAT: Cheat commands

Read the cheat registration, each cheat class, and its tests.

| Rule | Severity | Lint | Look for |
| --- | --- | --- | --- |
| CHEAT-01 | critical | no | A cheat handler registered with no live check at registration. |
| CHEAT-02 | critical | partial | A cheat class with no live check, or a check only at registration. The linter finds a class with no live check at all. Check that the check sits before each mutation. |
| CHEAT-03 | important | no | A cheat mixed into a gameplay handler, or a cheat class without the marker. |
| CHEAT-04 | important | no | A cheat with no metric row or no trace id. |
| CHEAT-05 | important | no | A feature state that a test account cannot reach by a cheat. |
| CHEAT-06 | important | no | A cheat that writes a field directly and skips the feature's domain method or validation. |
| CHEAT-07 | important | no | A time cheat that changes the node clock or a shared field instead of a per-user offset. |

## ADMIN: Admin commands

Read the admin handler, its routing to the owner, and the admin API spec.

| Rule | Severity | Lint | Look for |
| --- | --- | --- | --- |
| ADMIN-01 | critical | no | An admin handler path with no session check on every request. |
| ADMIN-02 | critical | no | An admin command that changes a user's state from the admin's thread, or a CAS-less write to an offline document. |
| ADMIN-03 | important | no | A mutating admin command with no audit row, or an audit row missing the target, applied change, result, or trace id. |
| ADMIN-04 | critical | no | A destructive admin command with no live block and no confirmation field. |
| ADMIN-05 | important | no | An admin command with no entry in the admin API spec. |
| ADMIN-06 | important | no | An admin command that applies an effect before it validates the target, range, and ids. |
| ADMIN-07 | important | no | A mutating admin command that applies twice when sent twice. |
| ADMIN-08 | important | no | A per-user state with no admin command to read it or repair it. |

## HTTP: HTTP callbacks

Read the endpoint from the first byte received to the answer.

| Rule | Severity | Lint | Look for |
| --- | --- | --- | --- |
| HTTP-01 | important | no | An endpoint that a logged-in player can use through the game channel instead. |
| HTTP-02 | critical | no | A callback handled before the signature check, a check over a parsed body instead of the raw body, a secret in code, or no timestamp check. |
| HTTP-03 | critical | no | An allowlist that is empty on live and allows every caller. |
| HTTP-04 | critical | no | A callback that acts before it takes the lock, releases the lock on success, or keeps it on failure. |
| HTTP-05 | critical | no | A callback that loads and saves user state, or that mutates a live user. |
| HTTP-06 | critical | no | A callback that trusts the user id, product, price, currency, or expiry in the body without a server-side check. |
| HTTP-07 | important | no | A callback path with no metric row, or a row without the transaction id. |
| HTTP-08 | important | no | A failure that answers success so the caller stops retrying, or a duplicate that answers an error. |

## TEST: Tests

Read the tests that the diff adds or should add. Judge the tests against the rule, not only their pass state.

| Rule | Severity | Lint | Look for |
| --- | --- | --- | --- |
| TEST-01 | important | no | A core test that needs a socket, a database, or a network. |
| TEST-02 | important | no | A test that reads real time or real random numbers. |
| TEST-03 | important | no | A command with a check and no negative test for it. |
| TEST-04 | important | no | A cheat with no test that it is rejected on live. |
| TEST-05 | important | no | A config validator with no test for a valid file or for an invalid case. |
| TEST-06 | important | no | A stored-data change with no test that loads old data and data with unknown fields. |
| TEST-07 | important | no | A request change with no test that decodes an old request. |
| TEST-08 | important | no | A command test that does not assert the metric row or the trace id. |
| TEST-09 | important | no | An idempotent request or callback with no replay test. |
| TEST-10 | minor | no | A command with no bot scenario, when the project has a bot. |
| TEST-11 | minor | no | A test that sets the config instance, clock, or environment and does not restore it. |

## Lifecycle parity

Rules about state hold only if every entry point that touches the state follows them. List the entry points, then check each one against the same rules. A rule that holds on the main command path and fails on a side path is a finding, even when nothing on the failing line looks wrong.

| Entry point | What to check |
| --- | --- |
| Gameplay command | The full spec row: checks, cost, effect, metric, trace id. |
| Login | Lazy migration, expiry of old periods, and pushes of current state run before the first command. |
| Offline load | A load of a document for a user who is not online runs the same migration and keeps unknown fields. |
| Periodic job or tick | The lease is held, the lease token is checked before each write, and the job reads stored timestamps. |
| Cheat command | The live check, the domain method, the metric row. |
| Admin command | The owner routing or CAS path, validation, audit row, and retry safety. |
| HTTP callback | Signature, allowlist, idempotency lock, delivery through the inbox. |
| Cross-node message and inbox drain | Unknown types are kept. Applying an entry twice has no second effect. |
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

## Dismissal audit

A suspected break that you decide not to report is a dismissal. Keep a list of them while you review. Before you write the report, audit each one once.

For each dismissal:

1. Reopen the code at the cited line, over a wide range.
2. If the reason is "a test covers it", open the test. A test that passes with and without the break covers nothing.
3. If the reason is "a guard prevents it", confirm that the guard is reached on this path. A guard behind an earlier return, or after the effect, guards nothing.
4. If the reason is "the exception is caught", read the catch. A catch that sends no response, or that hides a failed save, is a finding.
5. If the reason is "the config never triggers it", the finding stands, and you may note it as inert today.

Keep the dismissal only when the check holds. List the kept dismissals in the report with the evidence, so the developer can disagree.
