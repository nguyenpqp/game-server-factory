# Rule index

This index lists every rule id that the plugin's skills, specs, reviews, and linter cite. The set is fixed. A citation of an id that is not a heading here fails the plugin validator.

## Entry format

Each rule is a heading `### <ID> <rule>`, where the rule is one testable statement. Two lines follow the heading, in this order:

- `severity:` is `critical`, `important`, or `minor`.
- `needs:` lists the capability ids from the profile template that the rule depends on, or `none`.

An id is a group name, a hyphen, and a two-digit number. Numbers run from `01` in each group.

## Severity

- `critical` means a break can lose, duplicate, or corrupt player value or stored data, open an exploit, run a cheat on live, leak a secret, break clients or servers during rollout, or stall other users.
- `important` means a break misses a budget, a compatibility test, an observability need, or a modularity need, with no direct harm to players.
- `minor` means a break costs review or maintenance time only.

## AUTH: server authority and input

### AUTH-01 The client sends intents only, and the server computes every result, cost, and reward.

- severity: critical
- needs: CAP-COMMAND

### AUTH-02 Game logic reads time only from the server clock, passed into the core as a parameter.

- severity: critical
- needs: CAP-CLOCK

### AUTH-03 Game logic draws random numbers only from the injected server RNG.

- severity: critical
- needs: CAP-RNG

### AUTH-04 Every request field is checked for presence, type, range, length, and allowed values before any state change.

- severity: critical
- needs: CAP-COMMAND, CAP-ERRORS

### AUTH-05 Every object a request names, such as an item, a slot, or a target user, is checked to belong to or be reachable by the acting user.

- severity: critical
- needs: CAP-USERSTORE

### AUTH-06 Every precondition, such as feature active, unlocked, legal state transition, or cooldown over, is checked against server state before any change.

- severity: critical
- needs: CAP-CONFIG, CAP-CLOCK

### AUTH-07 A command checks every cost in full before it takes any, and refunds what it took when a later step fails.

- severity: critical
- needs: CAP-INVENTORY

### AUTH-08 A command whose retry would grant value twice carries a request id, and the server applies each request id at most once per user.

- severity: critical
- needs: CAP-COMMAND, CAP-USERSTORE

### AUTH-09 A command that reads the database, touches other users, or fans out has a per-user rate limit, and excess calls get an error with no effect.

- severity: important
- needs: CAP-CLOCK, CAP-ERRORS

### AUTH-10 A rejected command changes no state and returns an error code specific to the failure.

- severity: important
- needs: CAP-ERRORS

## MN: multi-node safety

### MN-01 Feature code holds no game or user state in static fields, singletons, or node-wide maps, and its only mutable static field is the config snapshot reference that a reload swaps.

- severity: critical
- needs: none

### MN-02 Only the user actor on the user's owner node touches that user's live state, and any other reader works from a snapshot built on that actor or from a private load of the stored document.

- severity: critical
- needs: CAP-OWNERSHIP, CAP-ACTOR

### MN-03 A change to another user's state goes to that user's owner through cross-node delivery or the durable inbox, never through a direct load and save.

- severity: critical
- needs: CAP-CROSSNODE, CAP-INBOX

### MN-04 A stored document that several users or nodes write is updated with CAS and a bounded retry, never with a blind set.

- severity: critical
- needs: CAP-CAS

### MN-05 Cluster-wide state lives in Redis and changes through atomic commands or Lua scripts, never through a read-modify-write in Java.

- severity: critical
- needs: CAP-REDIS

### MN-06 Redis keys that one command or script touches together share a hash tag.

- severity: important
- needs: CAP-REDIS

### MN-07 A job that must run once per cluster runs only while it holds a lease, and it checks the lease token before each write.

- severity: critical
- needs: CAP-LEASE

### MN-08 Ids that must be unique across the cluster come from Redis `INCR` or a snowflake with unique node bits, never from an in-process counter.

- severity: critical
- needs: CAP-IDGEN

### MN-09 A node-local cache of shared data has an invalidation path and a stated staleness bound.

- severity: important
- needs: CAP-CROSSNODE, CAP-REDIS

### MN-10 Pushes to another user and checks of another user's online status go through the ownership record and cross-node delivery, never through a node-local session map.

- severity: important
- needs: CAP-OWNERSHIP, CAP-CROSSNODE

### MN-11 A timed per-user effect, such as an expiry, a ready time, or a deadline, is derived from a stored timestamp when the state is read, never from an in-memory timer.

- severity: critical
- needs: CAP-CLOCK, CAP-USERSTORE

## BG: blue-green rollout and client compatibility

### BG-01 Stored data in Couchbase and Redis changes only by added fields and keys, never by a removed, renamed, or retyped one.

- severity: critical
- needs: CAP-USERSTORE, CAP-REDIS

### BG-02 Loading and saving a document keeps every field that the running server version does not know.

- severity: critical
- needs: CAP-USERSTORE

### BG-03 A changed meaning gets a new field or a new command id, and an existing or retired id never takes a new meaning.

- severity: critical
- needs: CAP-COMMAND, CAP-USERSTORE

### BG-04 New response and push fields are appended and optional, and existing fields keep their position, type, and meaning.

- severity: critical
- needs: CAP-RESPONSE

### BG-05 A new request field is optional, and a request without it behaves as it did before the change.

- severity: critical
- needs: CAP-COMMAND

### BG-06 A client older than the change keeps the old behavior of every existing command and never receives a packet it cannot parse.

- severity: critical
- needs: CAP-CLIENTVER, CAP-RESPONSE

### BG-07 The server gates each new feature and each changed behavior on the client version that the session reported at login.

- severity: important
- needs: CAP-CLIENTVER

### BG-08 Feature config is readable by both the old and the new server version, so new keys are optional with defaults and no key changes meaning.

- severity: critical
- needs: CAP-CONFIG

### BG-09 Data migration runs lazily on the owner at load, is idempotent, and records a per-document schema version that only increases.

- severity: critical
- needs: CAP-USERSTORE

### BG-10 A draining node finishes every queued command and confirms every save before it releases user ownership.

- severity: critical
- needs: CAP-DRAIN, CAP-OWNERSHIP, CAP-USERSTORE

### BG-11 A node that meets an inbox entry or cross-node message of a type it does not know leaves it unchanged in the user's inbox, so a newer version applies it later.

- severity: critical
- needs: CAP-INBOX, CAP-CROSSNODE

## PERF: performance

### PERF-01 The user actor thread never blocks on I/O, a sleep, or a lock held across I/O.

- severity: critical
- needs: CAP-ACTOR

### PERF-02 Each command makes a bounded number of database and Redis calls, stated in the spec's performance budget.

- severity: important
- needs: CAP-USERSTORE, CAP-REDIS

### PERF-03 No database or Redis call runs inside a loop over items, users, or rows, and batch reads use multi-get, pipelining, or one script.

- severity: important
- needs: CAP-USERSTORE, CAP-REDIS

### PERF-04 Each response and push stays within its byte budget, and lists sent to the client are capped or paginated.

- severity: important
- needs: CAP-RESPONSE

### PERF-05 Config lookups on the command path are constant-time reads from indexes built at load.

- severity: important
- needs: CAP-CONFIG

### PERF-06 Per-user state has a stated size bound, and every list or map in it has a cap or an eviction rule.

- severity: important
- needs: CAP-USERSTORE

### PERF-07 A command pushes to or changes at most a stated number of other users, and larger fan-out runs as a batched job.

- severity: important
- needs: CAP-CROSSNODE

### PERF-08 No single Redis key takes a write from every active user on the command path, so hot counters and boards are sharded or batched.

- severity: important
- needs: CAP-REDIS

## CFG: feature config

### CFG-01 Each feature keeps its config in its own file.

- severity: important
- needs: CAP-CONFIG

### CFG-02 Config is validated at load, and an invalid file fails startup or the reload with the file and key named, never the first command.

- severity: critical
- needs: CAP-CONFIG

### CFG-03 Loaded config is an immutable snapshot that one reference swap replaces whole, and each command reads one snapshot from start to end.

- severity: important
- needs: CAP-CONFIG

### CFG-04 Each feature config has an `isActive` flag and, when the feature is time-bound, a start and an end time checked against server time.

- severity: important
- needs: CAP-CONFIG, CAP-CLOCK

### CFG-05 Balance numbers, such as costs, rewards, rates, limits, and durations, come from config, never from constants in code.

- severity: important
- needs: CAP-CONFIG

### CFG-06 Stored data and client packets refer to config entries by stable id, never by list position.

- severity: critical
- needs: CAP-CONFIG

### CFG-07 Environment-specific values, such as secrets, allowlists, and endpoints, live in environment config, apart from the feature's balance file.

- severity: important
- needs: CAP-ENV, CAP-CONFIG

### CFG-08 Generated files change only through their generator and its source, never by hand.

- severity: important
- needs: CAP-GENERATED

## MET: metrics

### MET-01 Every user action command writes exactly one user action row, on success and on each failure, with the result code.

- severity: important
- needs: CAP-METRIC, CAP-ERRORS

### MET-02 Each user action mints one trace id, and every metric row that the action writes carries it.

- severity: important
- needs: CAP-TRACEID, CAP-METRIC

### MET-03 Every currency and inventory change carries the trace id of the action that caused it.

- severity: important
- needs: CAP-INVENTORY, CAP-TRACEID

### MET-04 Every currency and item source and sink is logged with its amount and a reason constant unique to the feature action.

- severity: important
- needs: CAP-INVENTORY, CAP-METRIC

### MET-05 Each funnel step of the feature has its own metric action, so a query can count drop-off between steps.

- severity: important
- needs: CAP-METRIC

### MET-06 The spec ships a KPI query for each success measure of the feature, written against the profile's metric tables.

- severity: important
- needs: CAP-METRIC

### MET-07 New metric data goes into free extra fields, never into new fixed columns, and the spec states the meaning of each extra.

- severity: important
- needs: CAP-METRIC

### MET-08 An unexpected exception writes an exception row with the trace id, and the command still answers with an error code.

- severity: important
- needs: CAP-METRIC, CAP-TRACEID, CAP-ERRORS

### MET-09 Metric rows and logs never contain secrets, tokens, signatures, or payment credentials.

- severity: critical
- needs: CAP-METRIC

## CHEAT: cheat commands

### CHEAT-01 Cheat command handlers are not registered when the server runs on live.

- severity: critical
- needs: CAP-CHEAT, CAP-ENV

### CHEAT-02 Every cheat command checks the environment at the point of mutation and rejects the request on live.

- severity: critical
- needs: CAP-ENV

### CHEAT-03 Cheat commands live in their own handler and classes, apart from gameplay commands, and each cheat class carries the profile's cheat marker.

- severity: important
- needs: CAP-CHEAT

### CHEAT-04 Cheat commands write metric rows like gameplay commands, under their own action names and with a trace id.

- severity: important
- needs: CAP-METRIC, CAP-TRACEID

### CHEAT-05 Each feature ships cheat commands that put a test account into every state the client needs to test.

- severity: important
- needs: CAP-CHEAT

### CHEAT-06 A cheat validates its input and changes state through the feature's own domain methods, so the result passes the feature's invariants.

- severity: important
- needs: CAP-CHEAT

### CHEAT-07 A time cheat shifts server time for the acting user only, through the server clock, so other users and other nodes keep real time.

- severity: important
- needs: CAP-CLOCK

## ADMIN: admin commands

### ADMIN-01 Every admin command requires an authenticated admin session, checked on each request.

- severity: critical
- needs: CAP-ADMIN

### ADMIN-02 An admin command that changes a user's state runs on that user's owner, or with CAS on the stored document when the user is offline.

- severity: critical
- needs: CAP-ADMIN, CAP-OWNERSHIP, CAP-CROSSNODE, CAP-CAS

### ADMIN-03 Every mutating admin command writes an audit row with the admin, the target, the requested and applied change, the result, and the trace id.

- severity: important
- needs: CAP-ADMIN, CAP-METRIC, CAP-TRACEID

### ADMIN-04 On live, a destructive admin command, such as a delete, a reset, or an overwrite of user data, is blocked or requires an explicit confirmation field.

- severity: critical
- needs: CAP-ADMIN, CAP-ENV

### ADMIN-05 Each admin command has an entry in the feature's admin API spec with its request fields, response fields, errors, and required permission.

- severity: important
- needs: CAP-ADMIN

### ADMIN-06 An admin command validates its target, ranges, and referenced ids before any effect, as a gameplay command does.

- severity: important
- needs: CAP-ADMIN, CAP-ERRORS

### ADMIN-07 A retried mutating admin command has no second effect.

- severity: important
- needs: CAP-ADMIN

### ADMIN-08 Each feature ships admin commands that read and repair its per-user state for support.

- severity: important
- needs: CAP-ADMIN

## HTTP: HTTP callbacks

### HTTP-01 An HTTP endpoint serves only callers that cannot log in to the game channel, such as payment providers and platform webhooks.

- severity: important
- needs: CAP-HTTP

### HTTP-02 Each request's signature is verified over the raw body with a per-environment secret, and a stale timestamp is rejected, before any effect.

- severity: critical
- needs: CAP-HTTP, CAP-ENV

### HTTP-03 On live, the caller allowlist is non-empty, and an empty allowlist rejects every call.

- severity: critical
- needs: CAP-HTTP, CAP-ENV

### HTTP-04 Each callback takes an idempotency lock on the external transaction id before any effect, keeps it on success, and releases it on failure.

- severity: critical
- needs: CAP-REDIS

### HTTP-05 A callback never changes user state directly, and it delivers through the user's durable inbox, which the owner applies once.

- severity: critical
- needs: CAP-INBOX

### HTTP-06 A callback checks the business payload, such as the user id, product id, price, currency, and expiry, against server data before delivery.

- severity: critical
- needs: CAP-CONFIG

### HTTP-07 Every callback writes a metric row with the transaction id, the user id, the result, and the trace id.

- severity: important
- needs: CAP-METRIC, CAP-TRACEID

### HTTP-08 The response status tells the caller whether to retry, and a duplicate of a delivered call gets a success answer.

- severity: important
- needs: CAP-HTTP

## TEST: tests

### TEST-01 The feature's core logic has unit tests that run without network, sockets, or a database.

- severity: important
- needs: CAP-UNITTEST

### TEST-02 Tests inject time and random numbers, so every time window, cooldown, and random outcome has a deterministic test.

- severity: important
- needs: CAP-CLOCK, CAP-RNG, CAP-UNITTEST

### TEST-03 Each command has a negative test per validation and precondition failure that asserts the error code and unchanged state.

- severity: important
- needs: CAP-UNITTEST, CAP-ERRORS

### TEST-04 Each cheat command has a test that proves it is rejected on live and changes nothing.

- severity: important
- needs: CAP-UNITTEST, CAP-ENV

### TEST-05 Config validation has a test for a valid file and a test for each invalid case that the validator rejects.

- severity: important
- needs: CAP-CONFIG, CAP-UNITTEST

### TEST-06 Compatibility tests load stored data from before the change and from a newer version with unknown fields, then assert that a save loses nothing.

- severity: important
- needs: CAP-USERSTORE, CAP-UNITTEST

### TEST-07 Compatibility tests decode old-client requests that lack the new fields and assert the old behavior and the old response layout.

- severity: important
- needs: CAP-COMMAND, CAP-UNITTEST

### TEST-08 Tests assert the metric rows of each command, on success and on failure, including the trace id.

- severity: important
- needs: CAP-METRIC, CAP-UNITTEST

### TEST-09 Tests replay each idempotent request and each duplicate callback, and assert exactly one effect.

- severity: important
- needs: CAP-UNITTEST

### TEST-10 When the project has an E2E bot, each command has a bot scenario for its main flow.

- severity: minor
- needs: CAP-BOT

### TEST-11 A test that changes global state, such as the config instance, the clock, or the environment, restores it afterward.

- severity: minor
- needs: CAP-UNITTEST
