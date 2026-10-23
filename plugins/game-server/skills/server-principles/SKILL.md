---
name: server-principles
description: >
  The principles for designing, writing, and reviewing Java game server feature code that
  runs on many nodes, survives blue-green deploys, and keeps old clients working. Use this
  skill whenever you plan, build, change, or check a game server feature, such as a command
  or packet handler, per-user state, Redis keys or scripts, a feature config, metric logs,
  cheat or admin commands, a payment or platform callback, a leaderboard, a gacha, a shop,
  an event, a guild, or PvP, even when the request only says "add a feature to the server".
  Covers server authority and anti-cheat, exactly-once value, multi-node safety, rollout and
  old clients, config, modularity, performance, client sync, metrics and logs, cheats and
  admin tools, tests, and staying true to the game design.
---

# Game server principles

These principles describe good feature code on a game server. They are not a procedure: read the project first, then judge how each one applies. When two principles pull against each other, or one does not fit the project, say so and explain your choice.

The target server runs one world on many peer nodes, with one owner node per player. Per-player data lives in a document store such as Couchbase, cluster-wide state in Redis. Two server versions run side by side during a deploy, old clients stay in use for weeks, and players probe every request for exploits. If the project differs, adapt the principles to it.

Thousands of players share each node, so one bad deploy hurts all of them at once. Put stability and safety ahead of delivery speed and clever code: the plain design that cannot lose value beats the fast one that usually does not, and the change that touches the least running code beats the neat refactor.

## 1. Work through the project's own core

Feature code adds features. It does not reinvent networking, login, sessions, storage clients, config loading, metrics, or the admin channel. Find how the project already does each, and write code that reads like the code around it.

When a principle needs something the core lacks, such as an atomic multi-document save, a durable per-player inbox, or compare-and-set, do not build a private workaround. Name the gap, say what breaks without it, and propose the smallest core change. The developer decides.

## 2. The server decides

The client sends intents, never results. The server computes every outcome, cost, and reward from its own state, and treats everything the client sends as hostile until checked.

- Check every request field for presence, type, range, and allowed values, and keep computed amounts inside their type. Overflow and negative amounts are classic exploits.
- Check that every object the request names (an item, a slot, a target player, a group) belongs to or is reachable by the acting player.
- Check every precondition against server state: the feature is active and unlocked, the transition is legal, the cooldown is over.
- Read time and randomness only from a clock and an RNG passed into the logic, and turn time into a date only with a zone the server owns. Node clocks drift, so a comparison that decides value across nodes (a tie, a window edge, an expiry) uses one shared time, such as Redis time inside the script or an instant already stored.
- Check the full cost before taking any of it, and order steps so a crash between them never creates value. When the effect lives outside the player's document, save the cost and the pending effect, keyed by the request id, together. Then apply the effect idempotently by that id, retry an unknown result until it is definite, and let the owner resume a pending effect after a crash. Refund only on a definite failure. Reserve a limited thing (stock, a slot) before taking the cost, and release it if the cost fails. When cost and effect share one document, save them together and nothing needs a refund.
- A rejected request changes nothing and returns an error code specific to the reason. Rate-limit commands that are expensive or touch other players.
- Check that actions are plausible over time, not only valid one by one. A fight cannot end, a timer cannot finish, and progress cannot pile up faster than the game allows. Speed hacks send requests that each look valid.
- Send the client only what the player may know. The next gacha result, a pity counter or drop rate the design hides, an opponent's hidden lineup, or another player's private data in a reply or config is read by anyone who inspects packets.
- Cap what each source of value can grant a player per period at a generous but sane level, and alert on hits, so a duplication bug the other principles missed stays small and gets noticed.

## 3. Value moves exactly once

Networks retry, players double-tap, nodes crash mid-command, and payment providers resend callbacks. Every path that grants or takes value gives the same result when it runs twice.

- A command whose retry would pay or count toward value twice (a reward, a purchase, event progress) carries a request id applied once per player. Applied ids are kept longer than any retry can arrive, then dropped, so the record stays bounded. Redis can lose acknowledged writes on failover, so it is never the only record of an applied id or of a counter that decides value.
- Value from an outside system is applied once per outside transaction id across all players, recorded durably. Before anything happens, verify the signature over the raw body with a per-environment secret, reject stale timestamps, and check the payload (player, product, price) against server data. On live, an empty caller allowlist rejects every call.
- Value for another player goes through that player's durable inbox, even when they are online on this node, and their owner applies each entry once: the entry's id is recorded in the player's document in the same save as its effect, and an entry already recorded is acknowledged without applying it again. A best-effort message or push is never the only carrier of value.

## 4. No node is special

Any node can receive any command or job, two nodes can run the same job at once, and any node can die between two writes. Design for it.

- No game or player state in static fields, singletons, or node-wide maps. Only the immutable config snapshot lives there.
- Only a player's owner touches their live state, and changes to another player go through that owner, even on this node. A copy of another player's state read elsewhere may reject an action but never grant one.
- Every save of a player's document carries its compare-and-set value or the ownership epoch, so a stalled former owner (a GC pause, a network split) cannot overwrite the new owner. A document several nodes write uses compare-and-set with a bounded retry on a fresh copy. A late write from a former owner cannot move shared state backward: make it monotone or version-checked.
- Fields that must change together are saved together, since two saves can be split by a crash.
- Cluster-wide state changes in one atomic Redis step (a command or a script), never read, change in Java, write. The script rechecks every fact the caller decided on. On Redis Cluster, keys touched together share a hash tag.
- A store or Redis call has three outcomes: yes, no, and unknown. An unknown is re-read, never treated as an answer that grants, denies, or hides value.
- A cluster job stays correct when two nodes run it. A lease only saves duplicate work, so each unit is claimed or idempotent and the lease is rechecked between units. A job that pays from changing data pays from one stored copy taken after the data closed. A job for data only the new version understands does not rely on a lease the old version can take.
- A shared thing that closes and reopens (a season, a room, an event round) carries its occurrence id, and closing leaves a closed marker instead of deleting the key. The marker outlives any late writer.
- A node-local cache of shared data has a staleness bound and an invalidation path, unless staleness only errs on the safe side. Online checks and pushes to other players go through the ownership record, not a node-local session map.
- Every call to Redis, the store, or another node has a timeout, and retries have a budget with jitter, so a slow dependency does not become a retry storm. When a dependency is down, anything that moves value refuses with an error, while read-only views may serve stale data.
- Many players hit the same moment: a daily reset, an event opening, a season close. Reset per player lazily on read, jitter cluster jobs, and load shared data before the moment, not on the first request.
- Timed effects come from stored timestamps read at use time, not in-memory timers. Unique ids come from the cluster (a Redis counter, or a snowflake with unique node bits), not a node counter.

## 5. Two versions and old clients at the same time

During a deploy, old and new servers share the same data and call each other, and old clients talk to new servers. Every change stays safe in both directions until the old version is gone. Calls between nodes follow the same rules as client packets.

- Stored data changes by adding fields and keys only. Nothing is removed, renamed, or retyped, and a new structure gets a new key rather than a new type on an old one.
- Check whether the running version keeps unknown fields when it saves. If it drops them, every old-node save erases a new field, so ship in two deploys: first keep unknown fields, then add the field.
- A new field missing from older data reads as unset, never as a real value. An absent Java `int` reads as 0, which can look like level 0, so give the field an explicit unset state or fill it on load.
- New values inside known fields (an item id, an enum code, a config id only the new version grants) are kept untouched and skipped by old code, never crashed on or deleted. Rollback is safe only when the old version tolerates everything the new one wrote.
- A new meaning gets a new field or a new command id, and an old id never takes a new meaning. While both versions run, the new version keeps the old field correct too.
- New request fields are optional, and their absence means the old behavior. New response fields are appended and optional. New behavior is gated on the client version, and an old client never gets a packet or a value it cannot handle: no new reward type, item kind, error code, or enum value in an old field. Leave it out or map it.
- When old clients cannot be served safely, as with new economy or fight rules, raise the minimum client version instead of running both rules. Code kept for old clients states the version after which it goes.
- A command is retired only when metrics show nobody calls it, and an old client calling it gets a clear error, not a disconnect.
- Old and new Redis scripts on the same keys keep the same invariants. Config stays readable by both versions, so new keys have defaults.
- Deploy dark, then turn on: new code that writes new data or changes behavior ships off and is enabled by config once every node runs it. Add the new path beside the old one, and remove the old one in a later deploy when nothing reads it.
- Migration is idempotent and derived from stored data. Per-player data migrates lazily on load. Shared data migrated at boot is written only where the target is absent, since two nodes can boot at once. A format the old version cannot read is a one-way door: it ships only in a maintenance deploy with the rollback step written down.
- An inbox entry of an unknown type stays untouched for a newer node. Fire-and-forget messages carry only a signal, so ignoring an unknown one loses nothing.
- A draining node refuses new logins, finishes queued commands, and confirms every save before releasing ownership. If the final save fails, it keeps ownership and retries. A failed boot step stops the boot, so a node never reports healthy with a step undone.

## 6. Numbers live in config

Designers tune balance after launch, often mid-event, and a hard-coded number needs a deploy to change.

- Every cost, reward, rate, limit, and duration comes from the feature's own config. Code holds rules, config holds numbers.
- Config is validated at load, and a bad file fails the load with the file and key named, never the first player who hits it. A loaded config is an immutable snapshot swapped whole, and one command reads one snapshot throughout.
- A feature has an on switch and, when time-bound, start and end times checked against server time.
- Stored data and packets refer to config entries by stable id, never list position, and rows have explicit ids. Costs and rewards share one record shape with the item id as a value, so every grant and log takes one path.
- An option not offered is left out, never set to zero, since a zero price sells for free. No config string hides a mini-language. Secrets, endpoints, and allowlists are environment config, apart from balance.

## 7. Features are independent modules

Code already on live is proven, and every edit to it risks players who never touch the new feature. A new feature plugs in beside the others, not into them.

- A new feature avoids editing other features. It extends them through their contracts, extension points, or events. When running code truly must change, find every caller, keep the change small, behind its contract, and switched by config, and say who is affected if it is wrong.
- A feature imports only its own package, shared code, and other features' contracts.
- A feature is plug-and-play: it registers its own commands, config, jobs, and handlers, and turning it off or removing it leaves the server working.
- Parts that may change are swappable. A reward source, a matchmaking rule, or a storage detail sits behind an interface with one job, so a new implementation replaces the old without touching callers. Behavior designers or operators may want to change is configurable within validated limits.
- An effect on another feature that the reply depends on, or that pays value, is a contract call or a durable inbox entry. Events carry only reactions whose loss costs nothing.

Every module has the same five parts, each with one job, named and placed the way the project already does:

- **Config.** The feature's numbers and switches, as the validated snapshot above.
- **Data model.** The user model is per-player state in the player's document. The server model is shared state, such as a board, a group, or a stock, in Redis or a shared document.
- **Logic.** The game rules as plain code over the models and config, with time and randomness passed in. No I/O and no packets, so unit tests cover every rule.
- **API.** The client, cheat, admin, and callback handlers. A handler validates, loads, calls the logic, saves, replies, and writes the metric row. It holds no game rule.
- **Metric log.** The feature's actions, reasons, and extra fields, defined in one place.

Dependencies point one way: the API calls the logic, and the logic reads the models and config, never a handler or the store.

## 8. Every command has a bounded cost

The game holds its peak player count without one popular command taking a node or a database down.

- The player's actor thread never blocks on I/O, sleeps, or holds a lock across I/O.
- Each command makes a known, small number of store and Redis calls, never one per item in a loop. Batch with multi-get, pipelines, or one script.
- The document store is read and written by known key on the command path. A query or index scan on a hot path is a red flag: its cost grows with the data and competes with every save.
- Redis runs one command at a time. An O(N) command on a large key (`KEYS`, a full `HGETALL` or `SMEMBERS`, a `ZRANGE` over a whole board) or a long Lua script stalls every node sharing that Redis.
- Estimate peak writes per second to each shared key. Merge or batch per player first, and shard only when the feature still works sharded: an exact leaderboard needs one sorted set, a global counter can split.
- A save writes the whole player document, so its cost is size times save rate. Growing history and logs live outside it. Every stored list or map has a cap or an eviction rule, and lists sent to the client are capped or paged.
- Memory per online player, times the peak player count, fits the heap.
- A command touches a bounded number of other players. Larger fan-out runs as a batched job.
- What a feature adds to login, every player pays at once after maintenance, the worst peak there is. Load feature data when first needed unless the login reply needs it.

## 9. The client can always catch up

Clients disconnect, miss pushes, and run on bad networks, so their view must be easy to rebuild.

- Each feature has one read command that returns all its client-visible state.
- A reply carries server time and the absolute new value of what changed, not a delta or a derived flag. Timers travel as stored instants.
- A push reports a change the client did not cause, and is best effort, so no value depends on it.

## 10. Every action can be traced

Support, analytics, and incident response start from metric rows and logs. An action with no trace leaves "where did my gems go" unanswerable.

- Every player action writes one metric row, on success and each failure, with the result code. One trace id ties together every row, currency change, and log line the action caused.
- Every currency and item source and sink is logged with its amount and a reason unique to the action.
- Funnel steps are separate actions, so drop-off can be counted, and each success measure has a query that answers it. New metric data goes into extra fields with a stated meaning, not new fixed columns.
- Logs go through the project's logger at a level that matches the consequence, with the player id, the trace id, and the exception itself. Success paths stay quiet. Secrets, tokens, and payment data never reach a log or a metric row.

## 11. Testers and support have tools, and live is protected

- Each feature ships cheats that put a test account into every state the client must test, including time shifts for that account only. Cheats change state through the feature's logic, are not registered on live, and refuse to act there anyway.
- Each feature ships admin commands that read and repair its per-player state. They authenticate every call, act through the player's owner (or, for an offline player, hold the ownership slot and write with compare-and-set), audit every change, need explicit confirmation for destructive changes on live, have no second effect on retry, and are documented with their fields and errors.

## 12. Tests prove behavior

- The logic runs in unit tests without network or database, with injected time and randomness, so every window, cooldown, and random outcome is deterministic. Redis scripts are tested against a real Redis.
- Each rejection has a test that checks the error code and that nothing changed.
- Tests replay retried requests and duplicate callbacks and expect exactly one effect, including a write that fails after it applied.
- Compatibility tests load old data and data with unknown fields, item ids, or enum codes, and decode old-client requests. A save loses nothing, and old behavior holds.
- Cross-node logic is tested with two instances over one shared store, including a stale copy and a store fault.
- Metric rows, config validation, and cheats refused on live have tests. Tests check observable behavior, not getters, constants, framework behavior, or mock wiring.

## 13. Code is typed and quiet

- Use enums for states, types, reasons, and error codes instead of integer or string constants, even when older code nearby uses integers, so the compiler catches wrong values and missing cases. An enum that is stored or sent gets an explicit, stable code per constant, mapped by that code, never by ordinal or name, so reordering or renaming changes no data.
- Comment only what the code cannot say: a non-obvious constraint, a race, or a deliberate trade-off.

## 14. Build what the design says

The game design is the contract with designers and players. Every requirement is built and tested, or descoped with the developer's agreement. Numbers, rules, transitions, and end conditions in code and config equal the design, and decisions already made, including answers and agreed defaults, hold.

When the design is silent or ambiguous on something that affects value or fairness, ask. Do not invent a rule or quietly pick the easiest to build. When existing code differs from the design, say which one you followed.

## Before writing code

For anything bigger than a small fix, settle the server design first and show it to the developer: commands and their checks, stored state and migration, shared keys and their consistency across nodes, config, metrics, the rollout and old-client story, and what the core lacks. Use whatever form fits the project. The point is that these decisions are made on purpose, not discovered in review.

## Genre notes

Some kinds of feature recur across games with the same design gaps and server bugs. When the feature matches one, read its note: design questions and code traps, never a prescribed design. A feature can match several.

| Note | Read when the feature has |
| --- | --- |
| [Rankings and seasons](references/rankings-and-seasons.md) | Players ranked by a score, such as a leaderboard, a ladder, a tournament, or a season paid by rank |
| [Randomness and gacha](references/randomness-and-gacha.md) | A random outcome that carries value, such as a gacha, a loot box, a drop, a wheel, or a craft that can fail |
| [Economy and exchange](references/economy-and-exchange.md) | Currency or items bought, sold, sent, or traded, such as a shop, mail with attachments, gifts, trades, or a real-money purchase |
| [Events and passes](references/events-and-passes.md) | Progress inside a time window, such as a limited event, missions, milestones, a battle pass, or a login calendar |
| [Guilds and groups](references/guilds-and-groups.md) | Players in a shared group, such as a guild, a clan, a party, or a friend list |
| [PvP and matchmaking](references/pvp-and-matchmaking.md) | Players who fight or compete against each other, live or against a stored defense |

## Severity

- **Critical.** It can lose, duplicate, or corrupt player value or stored data, open an exploit, run a cheat on live, leak a secret, break servers or clients during a rollout, or stall other players.
- **Important.** The game keeps working but worse: a missed performance budget, a gap in observability or modularity, or a compatibility weakness that harms no player.
- **Minor.** It costs maintenance time only.
