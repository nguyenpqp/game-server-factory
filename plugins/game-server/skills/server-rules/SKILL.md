---
name: server-rules
description: >
  This skill should be used when designing, writing, or reviewing Java game server
  feature code, such as a new command or packet handler, per-user persistence in
  Couchbase, Redis keys and Lua scripts, feature config files, metric logs and trace
  ids, cheat commands, admin commands, HTTP or payment callbacks, anti-cheat and server
  authority checks, multi-node safety, blue-green rollout, compatibility with old
  clients, feature boundaries, or client sync. It holds the fixed rule ids (AUTH, MN, BG,
  PERF, CFG, MET, CHEAT, ADMIN, HTTP, TEST, DES, MOD, SYNC) with a severity, a Java do and
  don't, and a review check for each rule.
  Specs, builds, reviews, and the feature linter cite these ids.
---

# Server rules

This skill is the rulebook for feature code on a Java game server. The server is authoritative, runs one world on many peer nodes, and rolls out by blue-green deploy while old clients stay online. Each rule has a fixed id, such as `MN-04`, that other skills and review findings cite.

## Boundary

This skill holds rules and nothing else. It does not scan a project, write a spec, write code, or run a review.

- The project profile from `server-profile` names the real classes behind each capability id, such as `CAP-CLOCK`. The examples here use generic names (`UserActor`, `KvStore`, `FeatureConfig`, `MetricLogger`, `TraceIds`, `ServerClock`, `RedisOps`, `Inbox`, `Env`, `GameRandom`). Map them to the profile's names before writing code.
- `feature-spec`, `feature-build`, and `feature-review` apply the rules and cite them by id.
- The rule set is fixed. Never invent an id. If a case needs a rule that the index lacks, report it as a gap.

## Look up a rule

1. Open [the rule index](references/index.md). It lists every id with its one-line rule, its severity, and the capability ids it needs.
2. Open the group file for that id and read its section. The section gives a one-line reason, a Java do and don't, how a reviewer checks it, and the same `needs` line.
3. Check the profile for each capability on the `needs` line. A capability marked `missing` blocks every rule whose `needs` line names it. A `partial` one blocks only the rule ids on its `blocker` line. Report the blocker and the profile's proposal instead of writing a workaround.

When designing a feature, read every group that the feature touches. When reviewing, report each finding with its severity, rule id, `file:line`, and a concrete failure scenario.

## Groups

- [AUTH, server authority and input](references/auth.md). The client sends intents, and the server checks every field, owner, precondition, and cost.
- [MN, multi-node safety](references/multi-node.md). No node-local state, one owner per user, CAS and atomic Redis for shared data, leased jobs, and cluster-unique ids.
- [BG, blue-green and client compatibility](references/blue-green.md). Additive data, unknown fields kept, new ids for new meanings, appended response fields, version gates, and lazy migration.
- [PERF, performance](references/performance.md). No blocking on the actor thread, bounded and batched DB and Redis calls, payload and state size bounds, and no hot keys.
- [CFG, feature config](references/config.md). One file per feature, validated at load, immutable snapshot, `isActive` and a time window, and no balance numbers in code.
- [MET, metrics](references/metric.md). One row per action with the result, one trace id per action, logged sources and sinks, funnel steps, and KPI queries.
- [CHEAT, cheat commands](references/cheat.md). Not registered on live, a live check at the mutation, separate marked classes, and logged like gameplay.
- [ADMIN, admin commands](references/admin.md). Authenticated per request, run on the target's owner, audited, guarded when destructive, and specified.
- [HTTP, HTTP callbacks](references/http.md). Outside callers only, signed and allowlisted, idempotent by transaction id, and delivered through the durable inbox.
- [TEST, tests](references/testing.md). A pure core tested without network, injected time and RNG, negative, cheat, config, compatibility, metric, and replay tests.
- [DES, design conformance](references/design-conformance.md). Every design id built and tested or recorded as descoped, the design's behavior and numbers in the code, and every settled decision kept.
- [MOD, modularity](references/modularity.md). Imports only of the feature's own, shared, and contract packages, and contract calls for every cross-feature effect a reply depends on.
- [SYNC, client sync](references/client-sync.md). A read command that rebuilds the client's view, absolute post-change values with server time, stored instants only, and pushes only for changes the client did not cause.

## Never

These critical rules apply to almost every feature. Breaking one can lose or duplicate player value, open an exploit, or break a rollout.

- Never trust a client value for a result, cost, or reward (AUTH-01).
- Never read time or random numbers outside the injected server clock and RNG (AUTH-02, AUTH-03).
- Never take a cost before checking all of it, or leave a failed step without a refund (AUTH-07).
- Never let a retried request or a duplicate callback grant value twice (AUTH-08, HTTP-04).
- Never keep game or user state in static fields or node-wide maps (MN-01).
- Never load and save another user's document from a non-owner thread or node (MN-02, MN-03).
- Never blind-set a document that several writers share (MN-04).
- Never remove, rename, or retype a stored field, or reuse an id for a new meaning (BG-01, BG-03).
- Never send an old client a packet it cannot parse (BG-06).
- Never register or run a cheat on live (CHEAT-01, CHEAT-02).
- Never let an HTTP callback change user state directly, or skip its signature check (HTTP-02, HTTP-05).
- Never block the user actor thread on I/O (PERF-01).
