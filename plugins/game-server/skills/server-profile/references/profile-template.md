# Profile template

The profile is the file `docs/game-server/profile.md` in the target game server repository. It records how that project's core provides each capability that feature code needs. Every other skill in this plugin reads the project through the profile, never through guesses about the code.

The profile has two parts, in this order:

1. YAML frontmatter with the keys in [Frontmatter](#frontmatter).
2. One section per capability in [Capabilities](#capabilities), with the same heading, in the same order.

Rule ids such as `MN-02` refer to the rule index of the `server-rules` skill. Each rule there lists the capability ids it needs.

## Frontmatter

The block below is the complete key set. Every key is required except `lint.command_method` and `lint.allowed_import`. The values are generic examples.

```yaml
---
profile_version: 1
language: 'java'
build_cmd: 'gradle build -x test'
test_cmd: 'gradle test'
test_one_cmd: 'gradle test --tests {class}'
source_root: 'src/main/java'
test_root: 'src/test/java'
feature_root: 'src/main/java/com/example/game/feature'
generated_paths:
  - 'src/main/java/com/example/game/generated'
lint:
  time_call: 'ServerClock\.now\('
  forbidden_time:
    - 'System\.currentTimeMillis\('
    - 'Instant\.now\('
    - 'LocalDate(Time)?\.now\('
    - 'new Date\(\)'
  random_call: 'GameRandom\.next\w*\('
  forbidden_random:
    - 'new Random\('
    - 'Math\.random\('
    - 'ThreadLocalRandom'
  env_live_check: 'Env\.isLive\(\)'
  metric_call: 'MetricLogger\.userAction\('
  trace_id_call: 'TraceIds\.next\('
  command_method: 'handle\w*'
  cheat_marker: '@CheatCommand'
  allowed_import: 'com\.example\.game\.contract\.'
  blocking_calls:
    - 'Thread\.sleep\('
    - '\.join\(\)'
    - '\.await\('
    - '\.block\(\)'
---
```

### Keys

| Key | Type | Meaning | Capability |
| --- | --- | --- | --- |
| `profile_version` | integer | Version of this template that the profile follows. This template is version 1. | none |
| `language` | string | Source language of the project. Always `java`. | none |
| `build_cmd` | string | Command, run from the repository root, that compiles the project. | CAP-BUILD |
| `test_cmd` | string | Command, run from the repository root, that runs every unit test. | CAP-BUILD |
| `test_one_cmd` | string | Command that runs one test class. `{class}` stands for the fully qualified test class name, such as `com.example.game.feature.streak.StreakClaimTest`. | CAP-BUILD |
| `source_root` | string | Directory of production Java sources, relative to the repository root. | CAP-BUILD |
| `test_root` | string | Directory of test Java sources, relative to the repository root. | CAP-UNITTEST |
| `feature_root` | string | Directory that holds one package per feature, relative to the repository root. The linter scans feature code here. | CAP-COMMAND |
| `generated_paths` | list of strings | Files or directories that a generator writes. Skills never edit them by hand, and the linter skips them. | CAP-GENERATED |
| `lint.time_call` | regex | The call that reads server time. | CAP-CLOCK |
| `lint.forbidden_time` | list of regexes | Time calls that feature code must not make. | CAP-CLOCK |
| `lint.random_call` | regex | The call that draws a random number from the injected RNG. | CAP-RNG |
| `lint.forbidden_random` | list of regexes | Random sources that feature code must not use. | CAP-RNG |
| `lint.env_live_check` | regex | The expression that is true when the server runs on live. | CAP-ENV |
| `lint.metric_call` | regex | The call that writes a user action metric row. | CAP-METRIC |
| `lint.trace_id_call` | regex | The call that mints a trace id. | CAP-TRACEID |
| `lint.command_method` | regex | Name of the method that marks a command class: a class that declares a method whose whole name matches is a command class. Optional. When the key is absent, the linter uses `handle\w*`. | CAP-COMMAND |
| `lint.cheat_marker` | regex | Text that every cheat command class contains, such as an annotation or a base class. | CAP-CHEAT |
| `lint.allowed_import` | regex | Prefixes of imported names that feature code may use across features, such as the contract packages. The linter matches it from the start of each imported name, and an import of another feature's package that does not match is a MOD-01 finding. Optional. When the key is absent or empty, the linter skips MOD-01. | CAP-MODULE |
| `lint.blocking_calls` | list of regexes | Calls that block the calling thread on I/O, a sleep, or a wait. Name the project's own future and sync client calls, and leave out patterns such as `\.get\(\)` that also match plain getters. | CAP-ACTOR |

### Value format

The frontmatter uses a small YAML subset, so plugin scripts parse it with the Python standard library.

- Write each key at the start of a line as `key: value`. The `lint` sub-keys are indented two spaces.
- Write a list as the key alone on its line, then one `- 'item'` line per item, indented two spaces deeper than the key.
- Write an empty list as `key: []` and an empty string as `key: ''`.
- Wrap every string in single quotes. Inside single quotes, a backslash is literal and `''` stands for one quote.
- Write `profile_version` as a bare integer.
- Each `lint` value is a Python regular expression that the linter searches for in Java source lines. `lint.allowed_import` is the exception. The linter matches it from the start of each imported name.

An empty `lint` value means the project has no such call. The capability that the key maps to is then `partial` or `missing`, and the linter skips the checks that need the value.

## Capability entries

Each capability section in the profile starts with the heading from this template, then a list of `- <field>: <value>` lines in this order.

| Field | Holds | Required when |
| --- | --- | --- |
| `status` | `present`, `partial`, or `missing`. | always |
| `api` | The classes and methods that feature code calls, with one line on how to call them. | `present`, `partial` |
| `file` | The repository path of the main source file. Add more paths separated by commas. | `present`, `partial` |
| `snippet` | A short Java fragment copied from the project that shows the call in use. A fenced code block follows the `snippet` line. | `present`, `partial` |
| `blocker` | The rule ids that cannot be met and what fails for players or operators without the missing part. | `partial`, `missing` |
| `proposal` | The smallest core change that would make the capability `present`. | `partial`, `missing` |

The status follows from the "Must provide" list under each capability:

- `present` means the project provides every item in the list.
- `partial` means the project provides some items. `blocker` and `proposal` cover the missing items.
- `missing` means the project provides none of the items.

To find the rules that a missing capability blocks, take every rule in the rule index whose `needs` line lists that capability id. A partial capability blocks only the rule ids on its `blocker` line.

An entry for a present capability, under its heading `### CAP-CLOCK Server time`:

````markdown
- status: present
- api: `ServerClock.now()` returns epoch milliseconds. Commands receive `now` as a parameter.
- file: `src/main/java/com/example/core/ServerClock.java`
- snippet:

```java
long now = ServerClock.now();
Result result = StreakClaim.process(state, config, now);
```
````

An entry for a missing capability, under its heading `### CAP-LEASE Cluster-wide job lease`:

````markdown
- status: missing
- blocker: MN-07 cannot be met. Every node runs the weekly ranking job, so each player gets the reward once per node.
- proposal: Add a `JobLease` helper that takes a Redis `SET key token NX PX ttl`, renews it while the job runs, and answers whether it is still held, so a job checks it between units of work.
````

## Capabilities

### CAP-COMMAND Command channel and ids

Must provide:

- A login-gated socket channel that hands each client request to a handler, with the authenticated user id.
- A numeric command id per request type, and a way to reserve a block of ids for one feature.
- A request decoder that reads typed fields and reports a missing field instead of failing or reading garbage.
- One place where handlers are registered at startup.

Typical partial: ids are hand-picked with no reserved block, or the decoder throws when an old client omits a field.

### CAP-RESPONSE Response and push

Must provide:

- A response to the requesting session with the command id, an error code, and fields.
- A push to an online user by user id, whichever node the user is on.
- An encoding in which an old client ignores fields appended after the ones it knows, such as keyed fields or a length-prefixed layout.

Typical partial: the layout is positional with no length, so an appended field breaks old parsers. Its blocker names BG-04 and BG-06. A push that reaches only users on the same node is a CAP-CROSSNODE partial, because MN-10 needs CAP-CROSSNODE, not CAP-RESPONSE.

### CAP-ERRORS Error codes

Must provide:

- A shared set of numeric error codes that the client understands.
- A way to add feature error codes without renumbering existing ones.
- A generic code for an unexpected server failure.

Typical partial: features reuse one generic failure code, so the client and the metric rows cannot tell failures apart.

### CAP-CLIENTVER Client version

Must provide:

- The client version, as a build number or protocol version, that the client sends at login and the server keeps per session.
- A helper that compares the session's version with a minimum version.

Typical partial: the handshake carries a version, but the server ignores it or accepts every value.

### CAP-ACTOR User actor execution

Must provide:

- One single-threaded executor per user or per stripe of users, so commands for one user run in order on one thread.
- A way to submit a task to another user's executor.
- A way to run blocking I/O off the executor and continue on the executor with the result.

Typical partial: executors exist, but loading a user from the database blocks the executor that serves other users.

### CAP-OWNERSHIP User ownership across nodes

Must provide:

- A cluster-wide record of the node that owns each online user, taken at login and released at logout or drain. A release writes a released marker instead of deleting the record, so a paused old node cannot claim the user again.
- Fencing, so a node that lost ownership of a user cannot save that user. A token checked at write time, such as a CAS write on an owner field, is the strong form. A check of the owner record right before each save is accepted when two more items hold: a node writes on an unknown answer only while its own heartbeat is fresh, measured on a monotonic clock, and after one lapse it refuses saves until it restarts.
- Takeover at login that asks the live owner to release and waits for it, and takes the user without consent only when the owner's heartbeat has expired, never after a fixed wait.
- Ownership checks and claims that answer yes, no, or unknown, where login refuses with retry-later on unknown.
- A short hold of the ownership slot for an offline edit, such as an admin change, so a login waits for it.
- A lookup of a user's owner node and online status, where online also needs the owner's heartbeat.

Typical partial: the load balancer routes a user to one node, but nothing stops a second node from loading and saving the same user. Or ownership exists, but a Redis error during the check counts as "owned" or "free", or takeover happens after a timeout while the old owner still saves.

### CAP-DRAIN Drain and handover

Must provide:

- A drain mode that refuses new logins before it claims them and stops new commands on a node while queued commands finish.
- A flush of every changed user, with each write confirmed, before the node releases ownership.
- A final save that keeps ownership when it fails and retries, with a limit per kind of failure (store error, a payload that cannot be built, owner unknown), a give-up that still releases, and a pending mark that makes login answer retry-later and shutdown wait.
- A shutdown order: refuse logins, disconnect users, wait for confirmed saves and pending final saves, then remove the node's heartbeat and leases last, in a `finally` block.
- Feature hooks that run at drain, to stop jobs and release leases.
- A boot that exits the process on any boot failure, so a half-started node never holds a heartbeat or a lease.
- A readiness signal that is true only after listeners are bound and startup completes, and false again during drain. Record how an operator reads it.

Typical partial: shutdown saves users but ignores the write results, or listeners stay open while the node drains. Or readiness is only a log line that also prints when a listener fails to bind.

### CAP-USERSTORE Per-user storage

Must provide:

- Load and save of per-user documents in Couchbase through the project's client, keyed by user id.
- Document keys that do not change when a Java class is renamed.
- A serializer that keeps unknown fields on load and writes them back on save, for every document that two server versions can write. Record which documents keep them and how deep, top level only or nested.
- A hook on the owner's executor that runs after load and before the first command, where lazy migration runs.
- A changed flag and a save cycle that reports a failed write and keeps the change for the next attempt.

Typical partial: the serializer drops unknown fields, keeps them only at the top level, or keeps them only on the shared-document write path, the key contains the class name, or a failed async write is lost because the changed flag was already cleared.

### CAP-CAS CAS writes

Must provide:

- A read that returns a CAS token, and a write that fails when the document changed since that read.
- A retry helper with a bounded attempt count, which applies the change to a fresh copy on each try.
- A write result that tells a version mismatch apart from a timeout or error whose outcome is unknown.
- An add that writes only when the key is absent.

Typical partial: the client supports CAS, but most writes are blind sets, so the last writer wins. Or a timeout surfaces as a mismatch, so the helper applies the change again.

### CAP-REDIS Redis access

Must provide:

- A client for the project's Redis, single instance or cluster, with atomic commands such as `INCR`, `SET NX PX`, `HSETNX`, and sorted sets.
- Lua scripts for multi-key atomic updates.
- Calls with a timeout that do not block the user actor thread. When the project makes synchronous calls on the actor thread by design, record the timeout and the circuit breaker that guard them.
- A call that reports an error apart from an empty result, so a caller can tell "absent" from "Redis is down".
- On Redis Cluster, a key naming convention with a hash tag for keys that one command or script touches together.

Record the deployment form: one instance or a cluster, the eviction policy, and persistence. Claim keys are often the only record of who won, so they need `noeviction` and persistence.

Typical partial: there is no Lua support, keys have no hash tags while the deployment uses Redis Cluster, or the wrapper returns null on error.

### CAP-IDGEN Unique ids

Must provide:

- Ids that stay unique across nodes, restarts, and crashes, from Redis `INCR` or a shared store counter per id space, or from a snowflake whose node bits are unique per running process.
- An increment that fails on a missing counter instead of creating it from zero.
- A bounded retry, which is safe because an increment that landed and then failed only skips an id.

Typical partial: an in-process counter saved on a timer, so a crash or a second node repeats ids, or an increment that recreates a lost counter from zero.

### CAP-INVENTORY Currency and inventory

Must provide:

- Check, take, and add for each currency and item type, called on the owner's executor.
- A reason (source or sink) and a trace id on every change, and a metric row per change.
- A guard that rejects unknown item ids and non-positive amounts before any change.
- A take of several items that takes nothing when any item is short.

Typical partial: take and add exist, but they accept no trace id, or a multi-item take can stop halfway.

### CAP-CROSSNODE Cross-node delivery

Must provide:

- A message to a user's owner node that runs on that user's executor, with ordering per sender and a bounded queue, and a sender that never blocks on Redis.
- A fallback to the durable inbox when the user is offline or the owner cannot be reached.
- A receiver that ignores a message type it does not know, without failing the executor. This is safe only because messages carry signals, and anything that must arrive is in the durable inbox first.
- A periodic sweep that covers a lost message, such as an inbox sweep of online users and a periodic config reload.
- A broadcast to every node, for cache invalidation.

Typical partial: delivery works only for users on the same node, or a message carries a payload that exists nowhere else, so a pub/sub drop loses it.

### CAP-INBOX Durable inbox

Must provide:

- A per-user queue in Couchbase that any node or HTTP handler can append to, with a CAS retry and a dedup by entry id when an append times out.
- A drain by the owner at login and on notice while the user is online, only while this node is the confirmed owner.
- An id per entry, so applying an entry twice has no second effect.
- An entry that leaves the inbox only once its effect is saved. Apply, record the entry id in the user's document, save, then remove. A drain that removes first must save right after applying and put the entries back when the save fails or reports that this node is no longer the owner.
- A drain that leaves an entry of a type the running version does not know in place, never removing it to add it back, and payloads stored as raw text that every version writes back unchanged.

Typical partial: entries carry no id, the owner removes an entry before it applies the entry and saves later on the timer, or the drain drops entries of unknown types.

### CAP-LEASE Cluster-wide job lease

Must provide:

- A scheduler for periodic jobs.
- A lease per job and period that one node holds, such as Redis `SET NX PX` with a token, renewed while the job runs and released at drain.
- A held check that a job calls between units of work, with validity counted from the send time of the last successful renew on a monotonic clock.
- A per-job lock beside the cluster lease, for a job whose data only one server version knows.

Typical partial: jobs are scheduled on every node with no lease.

### CAP-CONFIG Config loading

Must provide:

- A load of one JSON file per feature from the project's config directory at startup.
- A validation hook that fails startup and names the file and key.
- An immutable snapshot published by one reference swap, so a reload replaces it whole.
- A test hook that sets a config instance in a unit test.

When the project keeps runtime config in the store, such as a maintenance schedule, record its write path: a CAS update on a fresh copy, a broadcast reload, a periodic reload as the fallback, and reloads serialized with writes.

Typical partial: config needs a restart to change, or features keep config in mutable static fields.

### CAP-ENV Environment

Must provide:

- The environment name, such as live, staging, qc, or dev, read at runtime from deployment config that players cannot change.
- One call that answers whether the server runs on live.
- Per-environment values for secrets, allowlists, and endpoints.

Typical partial: several flags decide live behavior, and one of them can be on in live config, such as a flag that enables cheats.

### CAP-CLOCK Server time

Must provide:

- One call that returns server time in epoch milliseconds, and the timezone that day resets use.
- Time passed into core logic as a parameter, so tests inject it.
- A per-user time offset for cheats, ignored on live.
- A monotonic clock, separate from the game clock, for heartbeat and lease freshness, so a wall clock step cannot make a stale heartbeat look fresh.

Typical partial: there is no per-user offset, so a time cheat moves the clock of the whole node.

### CAP-RNG Random numbers

Must provide:

- One injectable source of random numbers for game logic, and a seedable implementation for tests.

Typical partial: game logic calls a static random source directly, so tests cannot fix outcomes.

### CAP-CHEAT Cheat channel

Must provide:

- A client command channel for cheats whose handler is not registered on live.
- A marker that every cheat class carries, such as an annotation or a base class.

Typical partial: the cheat handler is registered on every environment and gated only by a config flag.

### CAP-ADMIN Admin channel

Must provide:

- An authenticated admin session, with a second factor on live, checked on every request.
- Routing of a per-user admin command to the target user's owner, and a CAS path when the user is offline.
- An audit record of each mutating command.
- Request and response bodies in one documented format, such as JSON, for the admin API spec.

Typical partial: admin commands run on the admin's executor and change another user's state from there.

When the project has an admin web repository, the `api` field names it. Skills write admin web screens only when that repository is named.

### CAP-HTTP HTTP channel

Must provide:

- An HTTP server for callers that cannot log in, with access to the raw body, the headers, and the caller IP.
- Per-environment secrets and caller allowlists.
- A way to append to the durable inbox and then answer the caller.

Typical partial: an empty allowlist allows every caller.

### CAP-METRIC Metric logger

Must provide:

- One call that writes a user action row with the user id, the action, the result code, the trace id, and free extra fields.
- System rows and exception rows.
- A description of where rows land, such as one table per log type, and how to query them for KPIs.
- Asynchronous writes that never block the user actor thread, with the drop policy stated.
- The application logger for feature code, with the call that gives each feature its logger and the config that sets that logger's level.

Typical partial: rows have no trace id column, or extra fields cannot be queried downstream.

### CAP-TRACEID Trace id

Must provide:

- One call that mints a trace id that is unique across nodes.
- Currency, inventory, and metric calls that accept the trace id.

Typical partial: ids are unique on one node only, because the node bits come from config that two nodes can share.

### CAP-UNITTEST Unit test support

Must provide:

- A unit test framework that the build runs, such as JUnit 5.
- Per-user state that a test can build in memory, with no database or network.
- Hooks that inject time, random numbers, config, and environment in a test, and reset them after it, plus a reset for every process-wide gate or circuit breaker.
- An in-memory store fake with the production write contract: a CAS token that changes on every write, add-if-absent, and switches for a refused write and for a write that fails after it applied or before it.
- For tests of Redis scripts and coordination code, a key prefix unique to the run and a wipe helper. Record whether the test command needs a local Redis.

Typical partial: state classes need a live database connection to construct, or the store fake accepts every write, so CAS conflicts and ambiguous writes are never tested.

### CAP-BOT E2E bot

Must provide:

- A scripted client that logs in to a running server, sends commands, and checks the responses.
- Scenarios stored as files that a developer can add per feature.

When the project has a two-process drill, record it here: two servers on one machine with distinct node ids over one store and Redis, process faults such as a hard kill, a suspend and resume, and a Redis pause, a pass or fail per scenario, and whether it can run an old build next to a new one.

Typical partial: a load test client sends commands but does not check responses.

### CAP-MODULE Feature modules and contracts

Must provide:

- One package per feature under `feature_root`, and shared packages that hold no feature logic.
- Contract packages that hold the interfaces and value types one feature calls on another, apart from the package of either feature.
- One registration point where each feature registers at startup, provides its contracts, and resolves the contracts it calls.
- A synchronous contract call for an effect that the caller's reply depends on. When the project has events, a statement of their delivery: whether they run after the reply, in which order, and whether they can be dropped.

Typical partial: features import each other's packages because no contract package exists, or a handler looks up another feature's service at call time instead of at registration.

### CAP-GENERATED Generated files

Must provide:

- The list of generated files, the generator that writes each one, and the source it reads, such as a spreadsheet of command ids.
- The command that regenerates them.

Typical partial: the generator lives outside the repository and its command is not written down.

### CAP-BUILD Build

Must provide:

- Build and test commands that run from the repository root, recorded as `build_cmd`, `test_cmd`, and `test_one_cmd`.
- The JDK and build tool versions the project needs.

Typical partial: unit tests need a running external service, so `test_cmd` fails on a clean machine.
