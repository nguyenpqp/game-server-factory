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

These principles describe what good feature code on a game server looks like. They are not a procedure. Read the project first, then use your judgment about how each one applies to the feature in front of you. When two principles pull against each other, or one does not fit the project, say so and explain the choice you made.

The server this plugin has in mind runs one world on many peer nodes behind a load balancer. One node owns a user at a time. Per-user data lives in a document store such as Couchbase, and cluster-wide state lives in Redis. Two server versions run side by side during a deploy, and players keep using older clients for weeks. Expect real players to probe every request for an exploit. If the project you are working on differs, adapt the principles to it rather than the other way round.

Thousands of players share each node, and one bad deploy hurts all of them at once. Put stability and safety ahead of speed of delivery and clever code. Prefer the plain design that cannot lose value over the fast one that usually does not, and the change that touches the least running code over the neat refactor.

## 1. Work through the project's own core

Feature code adds features. It does not reinvent the network layer, login, sessions, storage clients, config loading, metrics, or the admin channel. Before writing anything, find out how this project already does each of those, and write code that reads like the code around it.

When a principle below needs something the core does not offer, such as an atomic save across documents, a durable per-user inbox, or a compare-and-set write, do not build a private workaround inside the feature. Name the gap, explain what breaks without it, and propose the smallest core change. The developer decides.

## 2. The server decides

The client sends intents, never results. The server computes every outcome, cost, and reward from its own state. Anything the client sends is hostile until checked.

- Check every request field for presence, type, range, and allowed values, and keep computed amounts inside their type. Overflow and negative amounts are classic exploits.
- Check that every object the request names (an item, a slot, a target player, a group) belongs to or is reachable by the acting player.
- Check every precondition against server state: the feature is active, the player unlocked it, the state transition is legal, the cooldown is over.
- Read time and random numbers only from a clock and an RNG passed into the logic, never from the client, and turn time into a date only with a zone the server owns. This keeps the client out and makes the logic testable. Node clocks drift apart, so a comparison that decides value across nodes (a tie order, a window edge, a protection expiry) uses one shared time, such as the Redis time inside the script or an instant already stored.
- Check the full cost before taking any of it. Order the steps so that a crash between them can never create value. When the effect lives outside the player's document, take the cost and record the pending effect, keyed by the request id, in the same save. Then apply the effect idempotently by that id, and keep retrying an unknown result until it is definite. The owner resumes a pending effect after a crash. Refund only when the effect definitely failed, such as stock that ran out or a group that is gone. When the action reserves a limited thing, reserve it first and release it if the cost cannot be taken. When cost and effect live in the same document, save them together and there is nothing to refund.
- A rejected request changes nothing and returns an error code specific to the reason.
- Rate-limit commands that are expensive or touch other players.
- Check that actions are plausible over time, not only valid one by one. A fight cannot end, a timer cannot finish, and progress cannot pile up faster than the game allows. Speed hacks send requests that each look valid.
- Send the client only what the player is allowed to know. A reply or config that carries the next gacha result, a pity counter or drop rate the design hides, an opponent's hidden lineup, or another player's private data is read by anyone who inspects packets.
- Cap what each source of value can grant a player per period at a generous but sane level, and alert when a player hits it. A duplication bug the other principles missed then stays small and gets noticed.

## 3. Value moves exactly once

Networks retry, players double-tap, nodes crash mid-command, and payment providers resend callbacks. Every path that grants or takes value must give the same result when it runs twice.

- A command whose retry would pay or count toward value twice, such as a reward, a purchase, or event progress, carries a request id, and the server applies each id once per player. Applied ids are kept for a stated time, longer than any client or callback retry can arrive, and then dropped, so the record stays bounded.
- Value from an outside system (a purchase, a platform reward) is applied once per outside transaction id across all players, recorded durably. Before anything happens, verify the caller's signature over the raw body with a per-environment secret, reject stale timestamps, and check the business payload (player, product, price) against server data. On live, an empty caller allowlist rejects every call rather than allowing all.
- Value for another player goes through that player's durable inbox, even when they are on this node or online, and their owner applies each entry once.
- A best-effort message or push must never be the only carrier of value.

## 4. No node is special

Any node can run any command, two nodes can run the same job at once, and any node can die between two writes. Design for that, and do not rely on it not happening.

- Keep no game or player state in static fields, singletons, or node-wide maps. Only the immutable config snapshot may live there.
- Only the owner of a player touches that player's live state. Changes to another player go through their owner, even when the owner is this node. A copy of another player's state read elsewhere may reject an action but never grant one.
- A document several nodes write is updated with compare-and-set and a bounded retry, on a fresh copy.
- Every save of a player's document carries its compare-and-set value or the owner's ownership epoch, so a stalled former owner (a long GC pause, a network split) cannot overwrite the new owner's save after its ownership lapsed.
- Cluster-wide state changes in one atomic Redis step (a command or a script), never as read, change in Java, then write. The script rechecks every fact the caller decided on. On Redis Cluster, keys touched together share a hash tag.
- A job that runs on the cluster stays correct when two nodes run it together. A lease only saves duplicate work, so each unit of work is claimed or idempotent, and the job rechecks its lease between units. A job that pays from data that still changes pays from one stored copy taken after the data closed. A job for data only the new version understands must not rely on a lease the old version can also take.
- Fields that must change together are saved together. Two separate saves can be split by a crash.
- A Redis or store call has three outcomes, yes, no, and unknown. An unknown result is re-read, never treated as success or failure that grants, denies, or hides value.
- A shared thing that can close and open again (a season, a room, an event round) carries the id of that occurrence, and closing it leaves an explicit closed marker instead of deleting the key. The marker expires only after any late writer could still arrive.
- A late or buffered write from a former owner, flushed after a handover, cannot move shared state backward: make it monotone or version-checked.
- A node-local cache of shared data has a stated staleness bound and an invalidation path, unless staleness only errs on the safe side. Online checks and pushes to other players go through the ownership record, not a node-local session map.
- Every call to Redis, the store, or another node has a timeout, and retries have a budget with jitter, so a slow dependency does not turn into a retry storm. When a dependency is down, anything that grants or takes value refuses with an error, while read-only views may serve stale data.
- Many players hit the same moment together: a daily reset, an event opening, a season close. Reset per player lazily when their state is read, spread cluster jobs out with jitter, and load shared data before the moment rather than on the first request.
- Timed effects come from stored timestamps read at use time, not from in-memory timers. Unique ids come from the cluster (a Redis counter, or a snowflake with unique node bits), not from a node counter.

## 5. Two versions and old clients at the same time

During a deploy, old and new servers read and write the same data, and old clients talk to new servers. Every change must be safe in both directions until the old version is gone.

- Stored data changes by adding fields and keys only. Nothing is removed, renamed, or retyped.
- Check whether the version already running keeps fields it does not know when it saves. If it drops them, a new field is erased by every save from an old node, so the change ships in two deploys: first teach the code to keep unknown fields, then add the field.
- A new field that is missing from older data reads as "not set", never as a real value. In Java, an absent `int` reads as 0, which can look like level 0 or zero uses left, so give the field an explicit unset state or fill it when the data loads.
- Old code meets new values inside fields it already knows: an item id, an enum code, or a config id that only the new version grants. It keeps the value it does not know untouched and skips it, and never crashes or deletes it. A rollback is safe only when the old version tolerates everything the new version wrote.
- A new meaning gets a new field or a new command id. An old id never takes a new meaning. While both versions run, the new version also keeps the old field correct, because a player can move back to an old node mid-deploy.
- New request fields are optional and their absence means the old behavior. New response fields are appended and optional. An old client never receives a packet it cannot parse, and new behavior is gated on the client version. The same holds for values: an old client never gets a new reward type, item kind, error code, or enum value in an old field. The server leaves it out or maps it to something the old client understands.
- When a change cannot be served safely to old clients, such as new economy or fight rules, raise the minimum client version rather than run old and new rules side by side. Code kept only for old clients has a stated end, the version after which it is removed.
- A command is retired only after metrics show no client still calls it. An old client that calls a retired command gets a clear error code, not a disconnect.
- Requests and replies between nodes follow the same rules as client packets, since an old node and a new node call each other during a deploy.
- Old and new Redis scripts that touch the same keys keep the same invariants. A new structure gets a new key rather than a new type on an old key, which would fail on the old nodes.
- Config stays readable by both versions, so new keys have defaults.
- Deploy dark, then turn on. New code that writes new data or changes behavior ships switched off and is enabled through config only once every node runs the new version. Change in two steps: first add the new path next to the old one, then remove the old one in a later deploy when nothing reads it.
- Migration is idempotent and derived from stored data only. Per-player data migrates lazily when its owner loads it. Shared data migrated at boot is written only where the target is absent, because two nodes can boot at once. A format the old version cannot read is a one-way door that ships only in a maintenance deploy, with the rollback step written down.
- An inbox entry of a type this node does not know stays in the inbox untouched for a newer node. Fire-and-forget cross-node messages carry only a signal, so ignoring an unknown one loses nothing.
- A draining node refuses new logins, finishes queued commands, and confirms every save before releasing ownership. If the final save fails, it keeps ownership and retries.
- A step that runs at boot and fails stops the boot. A node never reports healthy with a step undone.

## 6. Numbers live in config

Designers tune balance after launch, often during live events. Code that hard-codes a number forces a deploy to change it.

- Every cost, reward, rate, limit, and duration comes from the feature's own config file. Code holds rules, config holds numbers.
- Config is validated at load, and a bad file fails the load with the file and key named, never the first player who hits it.
- A loaded config is an immutable snapshot that a reload swaps whole, and one command reads one snapshot from start to end.
- A feature has an on switch and, when it is time-bound, start and end times checked against server time.
- Stored data and packets refer to config entries by stable id, never by list position. Rows have explicit ids. Costs and rewards share one record shape with the item id as a value, so every grant and every log goes through one path.
- An option that is not offered is left out, never written as zero, since a zero price sells for free. No string in config hides a mini-language that code has to parse.
- Secrets, endpoints, and allowlists are environment config, apart from balance.

## 7. Features are independent modules

Code that already runs on live is proven, and every edit to it risks players who never touch the new feature. A new feature should plug in beside the existing ones, not into them.

- A new feature avoids editing other features' code. It extends them through their published contracts, extension points, or events. When an existing feature truly must change, keep the change small, behind its contract, and switched by config, and say why it was unavoidable. Before changing running code, find every caller and say who is affected if the change is wrong.
- A feature imports only its own package, shared code, and other features' published contracts.
- A feature is plug-and-play: it registers its own commands, config, jobs, and handlers, and turning it off in config, or removing it, leaves the rest of the server working.
- Parts that may change are swappable: a reward source, a matchmaking rule, or a storage detail sits behind an interface with one clear job, so a new implementation replaces the old one without touching callers.
- Behavior that designers or operators may want to change is configurable, within the limits the code validates.
- An effect on another feature that the reply depends on, or that pays value, is a direct contract call or a durable inbox entry. Events are fine for reactions whose loss costs nothing.

Every feature module has the same five parts, each with one job, so any engineer finds things in the same place and one part changes without touching the others. Name and place them the way the project already does.

- **Config.** The feature's numbers and switches, loaded as the validated, immutable snapshot of principle 6.
- **Data model.** The user model is the per-player state saved in the player's document. The server model is shared state, such as a board, a group, or a stock, kept in Redis or a shared document. Both change only by adding fields, as principle 5 requires.
- **Logic.** The game rules as plain code over the models and the config, with time and randomness passed in. It does no I/O and builds no packets, so unit tests cover every rule.
- **API.** The command handlers for the client, and the cheat, admin, and callback handlers. A handler validates the request, loads state, calls the logic, saves, replies, and writes the metric row. It holds no game rule.
- **Metric log.** The feature's metric actions, reasons, and extra fields, defined in one place so every row has the same shape.

Dependencies point one way: the API calls the logic, and the logic reads the models and the config. The logic never calls a handler or the store.

## 8. Every command has a bounded cost

The game should hold its peak player count without one popular command taking a node down.

- The player's actor thread never blocks on I/O, sleeps, or holds a lock across I/O.
- Each command makes a known, small number of store and Redis calls, never one per item in a loop. Batch with multi-get, pipelines, or one script.
- Every stored list or map has a cap or an eviction rule, for per-player data and for shared documents like a guild's. Lists sent to the client are capped or paged.
- A command touches a bounded number of other players. Larger fan-out runs as a batched job.
- Estimate the peak writes per second to each shared Redis key. When one key takes too many, merge writes per player or batch them first, and shard only when the feature still works sharded. An exact leaderboard needs one sorted set, while a global counter can be split.

## 9. The client can always catch up

Clients disconnect, miss pushes, and run on bad networks. The server state must be easy to rebuild on the client at any time.

- Each feature has one read command that returns all of its client-visible state.
- A reply carries server time and the absolute new value of what changed, not a delta and not a flag derived from stored state. Timers travel as stored instants.
- A push tells the client about a change it did not cause. Pushes are best effort, so nothing of value depends on one arriving.

## 10. Every action can be traced

Support, analytics, and incident response all start from metric rows and logs. If an action left no trace, nobody can answer "where did my gems go".

- Every player action writes one metric row, on success and on each failure, with the result code.
- One trace id per action ties together every metric row, currency change, and log line it caused.
- Every currency and item source and sink is logged with its amount and a reason unique to the action.
- Funnel steps are separate actions, so drop-off can be counted, and each success measure of the feature has a query that answers it.
- New metric data goes into free extra fields with a stated meaning, not new fixed columns.
- Logs go through the project's logger, at a level that matches the consequence, with the player id and trace id, and the exception itself when there is one. Success paths stay quiet. Secrets, tokens, and payment data never reach a log or a metric row.

## 11. Testers and support have tools, and live is protected

- Each feature ships cheat commands that put a test account into every state the client needs to test, including time shifts for that account only. Cheats change state through the feature's own logic, are not registered on live, and refuse to act on live anyway.
- Each feature ships admin commands that read and repair its per-player state. Admin commands authenticate every call, act through the player's owner (or, for an offline player, hold the ownership slot and write with compare-and-set), audit every change, need explicit confirmation for destructive changes on live, have no second effect on retry, and are documented with their fields and errors.

## 12. Tests prove behavior

- The feature's logic runs in unit tests without a network or database, with injected time and randomness, so every window, cooldown, and random outcome is tested deterministically. Redis scripts are tested against a real Redis.
- Each rejection has a test that checks the error code and that nothing changed.
- Tests replay retried requests and duplicate callbacks and check for exactly one effect, including a write that fails after it applied.
- Compatibility tests load old data, data with unknown newer fields, and data holding item ids or enum codes the code does not know, and decode old-client requests. They check that a save loses nothing and old behavior holds.
- Cross-node logic is tested with two instances over one shared store, including a stale copy and a store fault.
- Metric rows, config validation, and cheats being refused on live have tests.
- Tests check what users of the code can observe. Skip tests of getters, constants, framework behavior, or mock wiring.

## 13. Code is typed and quiet

- Use enums for states, types, reasons, and error codes instead of integer or string constants, in new code even when older code nearby uses integers. The compiler then catches a wrong value and a missing case. When an enum value is stored or sent to the client, give each constant an explicit, stable code and map by that code, never by ordinal or name, because a reordered or renamed constant would silently change stored data and break old clients.
- Write comments only when the code cannot say why: a non-obvious constraint, a race, or a deliberate trade-off. Names and structure explain what the code does.

## 14. Build what the design says

The game design is the contract with designers and players. Every requirement in it is built and tested, or explicitly descoped with the developer's agreement. Numbers, rules, state transitions, and end conditions in code and config equal the design. Decisions already made, including answers to questions and agreed defaults, hold in the code.

When the design is silent or ambiguous on something that changes player value or fairness, ask. Do not invent a rule to fill the gap, and do not quietly pick the easiest one to build. When the code you are changing already behaves differently from the design, say which one you followed.

## Before writing code

For anything bigger than a small fix, settle the server design before writing code, and show it to the developer: the commands and their checks, the stored state and its migration, the shared keys and how they stay consistent across nodes, the config, the metrics, the rollout and old-client story, and what the core is missing. Write it in whatever form fits the project. The point is that these decisions are made on purpose and visible, not discovered in review.

## Genre notes

Some kinds of feature come back in game after game with the same design gaps and the same server bugs. When the feature matches one of these, read its note. Each lists questions the design must answer and the traps the code tends to fall into. A note never prescribes a design. A feature can match several notes.

| Note | Read when the feature has |
| --- | --- |
| [Rankings and seasons](references/rankings-and-seasons.md) | Players ranked by a score, such as a leaderboard, a ladder, a tournament, or a season paid by rank |
| [Randomness and gacha](references/randomness-and-gacha.md) | A random outcome that carries value, such as a gacha, a loot box, a drop, a wheel, or a craft that can fail |
| [Economy and exchange](references/economy-and-exchange.md) | Currency or items bought, sold, sent, or traded, such as a shop, mail with attachments, gifts, trades, or a real-money purchase |
| [Events and passes](references/events-and-passes.md) | Progress inside a time window, such as a limited event, missions, milestones, a battle pass, or a login calendar |
| [Guilds and groups](references/guilds-and-groups.md) | Players in a shared group, such as a guild, a clan, a party, or a friend list |
| [PvP and matchmaking](references/pvp-and-matchmaking.md) | Players who fight or compete against each other, live or against a stored defense |

## Severity

When you judge a break, in review or when deciding what to fix first:

- **Critical.** It can lose, duplicate, or corrupt player value or stored data, open an exploit, run a cheat on live, leak a secret, break servers or clients during a rollout, or stall other players.
- **Important.** The game keeps working but worse: a missed performance budget, a gap in observability or modularity, or a compatibility weakness that harms no player.
- **Minor.** It costs maintenance time only.
