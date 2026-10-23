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

## 1. Work through the project's own core

Feature code adds features. It does not reinvent the network layer, login, sessions, storage clients, config loading, metrics, or the admin channel. Before writing anything, find out how this project already does each of those, and write code that reads like the code around it.

When a principle below needs something the core does not offer, such as an atomic save across documents, a durable per-user inbox, or a compare-and-set write, do not build a private workaround inside the feature. Name the gap, explain what breaks without it, and propose the smallest core change. The developer decides.

## 2. The server decides

The client sends intents, never results. The server computes every outcome, cost, and reward from its own state. Anything the client sends is hostile until checked.

- Check every request field for presence, type, range, and allowed values, and keep computed amounts inside their type. Overflow and negative amounts are classic exploits.
- Check that every object the request names (an item, a slot, a target player, a group) belongs to or is reachable by the acting player.
- Check every precondition against server state: the feature is active, the player unlocked it, the state transition is legal, the cooldown is over.
- Read time only from the server clock, passed into the logic, and turn it into a date only with a zone the server owns. Draw random numbers only from a server RNG passed into the logic. Both make the logic testable and keep the client out of it.
- Check the full cost before taking any of it. Take it after any shared claim the action needs, and give it back when a later step definitely fails.
- A rejected request changes nothing and returns an error code specific to the reason.
- Rate-limit commands that are expensive or touch other players.

## 3. Value moves exactly once

Networks retry, players double-tap, nodes crash mid-command, and payment providers resend callbacks. Every path that grants or takes value must give the same result when it runs twice.

- A command whose retry would pay twice carries a request id, and the server applies each id once per player.
- Value from an outside system (a purchase, a platform reward) is applied once per outside transaction id across all players, recorded durably. Verify the caller's signature over the raw body and the business payload against server data before anything happens.
- Value for a player who is not on this node, or who may be offline, goes through that player's durable inbox, and the owner applies each entry once.
- A best-effort message or push must never be the only carrier of value.

## 4. No node is special

Any node can run any command, two nodes can run the same job at once, and any node can die between two writes. Design for that, and do not rely on it not happening.

- Keep no game or player state in static fields, singletons, or node-wide maps. Only the immutable config snapshot may live there.
- Only the owner of a player touches that player's live state. Changes to another player go through their owner, even when the owner is this node.
- A document several nodes write is updated with compare-and-set and a bounded retry, on a fresh copy.
- Cluster-wide state changes in one atomic Redis step (a command or a script), never as read, change in Java, then write. The script rechecks every fact the caller decided on.
- A job that runs on the cluster stays correct when two nodes run it together. A lease only saves duplicate work, so each unit of work is claimed or idempotent. A job that pays from data that still changes pays from one stored copy taken after the data closed.
- Fields that must change together are saved together. Two separate saves can be split by a crash.
- A Redis or store call has three outcomes, yes, no, and unknown. An unknown result is re-read, never treated as success or failure that grants, denies, or hides value.
- A shared thing that can close and open again (a season, a room, an event round) carries the id of that occurrence, and closing it leaves an explicit closed marker instead of deleting the key.
- Timed effects come from stored timestamps read at use time, not from in-memory timers. Unique ids come from the cluster, not from a node counter.

## 5. Two versions and old clients at the same time

During a deploy, old and new servers read and write the same data, and old clients talk to new servers. Every change must be safe in both directions until the old version is gone.

- Stored data changes by adding fields and keys only. Nothing is removed, renamed, or retyped. A writer keeps fields it does not know about.
- A new meaning gets a new field or a new command id. An old id never takes a new meaning.
- New request fields are optional and their absence means the old behavior. New response fields are appended and optional. An old client never receives a packet it cannot parse, and new behavior is gated on the client version.
- Config stays readable by both versions, so new keys have defaults.
- Migration is lazy on load, idempotent, and derived from stored data only. A format the old version cannot read is a one-way door that ships only in a maintenance deploy, with the rollback step written down.
- A step that runs at boot and fails stops the boot. A node never reports healthy with a step undone.

## 6. Numbers live in config

Designers tune balance after launch, often during live events. Code that hard-codes a number forces a deploy to change it.

- Every cost, reward, rate, limit, and duration comes from the feature's own config file. Code holds rules, config holds numbers.
- Config is validated at load, and a bad file fails the load with the file and key named, never the first player who hits it.
- A loaded config is an immutable snapshot that a reload swaps whole, and one command reads one snapshot from start to end.
- A feature has an on switch and, when it is time-bound, start and end times checked against server time.
- Stored data and packets refer to config entries by stable id, never by list position. Rows have explicit ids, and costs and rewards share one record shape with the item id as a value.
- Secrets, endpoints, and allowlists are environment config, apart from balance.

## 7. Features are modules

A feature imports only its own package, shared code, and other features' published contracts. An effect on another feature that the reply depends on, or that pays value, is a direct contract call or a durable inbox entry. Events are fine for reactions whose loss costs nothing. This keeps a feature removable and testable on its own.

## 8. Every command has a bounded cost

The game should hold its peak player count without one popular command taking a node down.

- The player's actor thread never blocks on I/O, sleeps, or holds a lock across I/O.
- Each command makes a known, small number of store and Redis calls, never one per item in a loop. Batch with multi-get, pipelines, or one script.
- Every stored list or map has a cap or an eviction rule, for per-player data and for shared documents like a guild's. Lists sent to the client are capped or paged.
- A command touches a bounded number of other players. Larger fan-out runs as a batched job.
- No single Redis key takes a write from every active player. Shard or batch hot counters and boards.

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
- Each feature ships admin commands that read and repair its per-player state. Admin commands authenticate every call, act through the player's owner, audit every change, need explicit confirmation for destructive changes on live, have no second effect on retry, and are documented with their fields and errors.

## 12. Tests prove behavior

- The feature's logic runs in unit tests without a network or database, with injected time and randomness, so every window, cooldown, and random outcome is tested deterministically. Redis scripts are tested against a real Redis.
- Each rejection has a test that checks the error code and that nothing changed.
- Tests replay retried requests and duplicate callbacks and check for exactly one effect, including a write that fails after it applied.
- Compatibility tests load old data and data with unknown newer fields, and decode old-client requests, and check that nothing is lost and old behavior holds.
- Cross-node logic is tested with two instances over one shared store, including a stale copy and a store fault.
- Metric rows, config validation, and cheats being refused on live have tests.
- Tests check what users of the code can observe. Skip tests of getters, constants, framework behavior, or mock wiring.

## 13. Build what the design says

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
- **Important.** It misses a performance budget, a compatibility guarantee, observability, or modularity, with no direct harm to players.
- **Minor.** It costs maintenance time only.
