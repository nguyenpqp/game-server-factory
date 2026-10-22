# Spec template

`feature-spec` writes one `spec.md` per feature in this format. `feature-build` implements it, and `feature-review` checks code against it. The default path in the target repository is `docs/game-server/features/<feature>/spec.md`, next to the feature's `design.md`.

The spec is the server design of one feature. It turns the player-facing behavior of the [design](../../gdd-intake/references/design-template.md) into commands, state, config, metrics, cheats, admin commands, and tests on the project's core. The project's core is what the [profile](../../server-profile/references/profile-template.md) at `docs/game-server/profile.md` records. Rule ids refer to the [rule index](../../server-rules/references/index.md).

## Filling rules

- Keep every section in the order of [Sections](#sections). Under a section that does not apply, write `None.` and one sentence that says why.
- Every table row has a `Rules` cell with the rule ids it satisfies, and so does every command line that states behavior, such as `Effect`. A row with no rule to cite does not belong in the spec. The header and Design coverage are the only parts without rule ids.
- Every row that comes from the design has a `Design` cell with design ids, such as `R1` or `UI2`. A row that only the server needs, such as a migration, writes `none`.
- Name core calls as the profile's capability entries name them. Write a capability id, such as `CAP-INBOX`, where the spec depends on a capability.
- Write every budget and bound as a number with a unit.
- Fill Core blockers as soon as the cited rules are known. While it has a row that blocks, the spec stops there and goes to the developer.

## Status

The header's `Status` line holds one value.

| Status | Meaning |
| --- | --- |
| `draft` | Sections are still being filled. |
| `blocked` | Core blockers has a row that blocks. `feature-build` does not start. |
| `ready` | Every section is filled, no Core blockers row blocks, and the developer confirmed the spec. |

## Sections

The spec has a title, a header, and these `##` sections in this order.

1. Commands
2. Pushes
3. State model
4. Config schema
5. Metric events and KPI queries
6. Cheat commands
7. Admin commands and API spec
8. HTTP endpoints
9. Multi-node analysis
10. Blue-green and client compatibility
11. Performance budget
12. Core blockers
13. Test plan
14. Design coverage

The formats below use the daily login streak from the design template as their example. Replace every example row.

### Header

```markdown
# Login streak server spec

- Design: `docs/game-server/features/login-streak/design.md`
- Profile: `docs/game-server/profile.md`, profile_version 1
- Package: `com.example.game.feature.streak`
- Command ids: 4200 to 4299
- Minimum client for the feature: 1.4.0
- Status: draft
- Open design questions: Q1, skipped by <name> on <date>, with the interim default "the server day"
- Accepted risks: None.
```

`Package` is a Java package. Its directory is the profile's `feature_root` plus the package's last segment. `profile_version` is the version of the profile template that the profile follows. `Accepted risks` lists each `critical` rule id that a Core blockers row accepts, with its reason, and with its decision id when a project decision resolved the row. It says `None.` when there is none.

When the input is a prompt instead of a design, `Design` says `prompt`, and the prompt follows the header as a quote. The spec then gives the requirements it reads from the prompt their own ids, in the design template's id format.

### Commands

The section has one `###` entry per client command, in the order the player meets them. Checks run in table order, and each check has its own error code. Every entry fills each line below, with `None.` where a line does not apply. The section ends with the error codes that the feature adds.

The entries come from the design's UI touchpoints, Rules, Formulas, and Rewards. A client-facing feature has one read command that returns all of its client-visible state. A response carries stored values and the stored instant of each timer, never a derived boolean. A mutating response carries server time and the post-change value of what it changed, and the `Reject` line says which of those fields every error carries. The entries usually cite AUTH-01 to AUTH-10, BG-03, BG-05, BG-07, CFG-04, CFG-05, MET-01 to MET-04, MET-08, MOD-02, PERF-01, and SYNC-01 to SYNC-03.

````markdown
## Commands

### ClaimStreakReward

- Id: 4201
- Intent: The player asks to claim today's reward. The request names no reward and no amount. Design: UI1, R1. Rules: AUTH-01.

Request:

| Field | Type | Required | Allowed values | Rules |
| --- | --- | --- | --- | --- |
| `requestId` | string | yes | 8 to 64 characters | AUTH-04, AUTH-08 |

Checks:

| Order | Check | Error | Design | Rules |
| --- | --- | --- | --- | --- |
| 1 | The feature is active | `FEATURE_INACTIVE` | TM2 | AUTH-06, CFG-04 |
| 2 | The session's client version is 1.4.0 or later | `CLIENT_TOO_OLD` | none | BG-07 |
| 3 | The player's level is at least `unlockLevel` | `FEATURE_LOCKED` | ST1 | AUTH-06 |
| 4 | Today, by server day, is not claimed yet | `ALREADY_CLAIMED` | ST3, TM1 | AUTH-02, AUTH-06 |

- Cost: None. Rules: AUTH-07.
- Effect: The core computes the reward day with F1 from stored state, sets `lastClaimDay` to today, and adds the day's reward with reason `STREAK_CLAIM` and the action's trace id. Design: R1, F1, RW1, RW7. Rules: AUTH-01, CFG-05, MET-03, MET-04.

Response:

| Order | Field | Type | Optional | Meaning | Rules |
| --- | --- | --- | --- | --- | --- |
| 1 | `error` | int | no | Result code | AUTH-10 |
| 2 | `serverTime` | long | no | Server time in epoch milliseconds | SYNC-02 |
| 3 | `rewardDay` | int | no | Reward day just claimed | BG-04 |
| 4 | `items` | list | no | Items granted, at most 10 | BG-04, PERF-04 |
| 5 | `streakCount` | int | no | Stored `streakCount` after the claim | SYNC-02 |
| 6 | `lastClaimDay` | int | no | Stored `lastClaimDay` after the claim | SYNC-02, SYNC-03 |
| 7 | `balances` | list | no | The post-change amount of each item granted, at most 10 | SYNC-02, PERF-04 |

- Reject: Every error carries `serverTime`, `streakCount`, and `lastClaimDay` with their stored values. Rules: SYNC-02.
- Idempotency: The server keeps the last 20 request ids per user. A repeated id returns the first result and grants nothing. Rules: AUTH-08.
- Rate limit: None. The command reads only the player's own state. Rules: AUTH-09.
- Pushes: None. The response carries the change. Rules: SYNC-04.
- Metric: Action `streak_claim`, on success and on every error. Rules: MET-01, MET-02, MET-08.

### Error codes

| Code | Name | Meaning | Commands | Rules |
| --- | --- | --- | --- | --- |
| 4201 | `ALREADY_CLAIMED` | Today's reward is already claimed | ClaimStreakReward | AUTH-10 |
````

### Pushes

The section has one row per message that the server sends without a request. The rows come from the design's UI touchpoints, from the column for changes without player action, and from server-side changes such as another player's action or a support repair. A push reports only a change that the client did not cause, and the `Why the client cannot know` cell says why. A change that the player's own command made, a login, and a time the client can compute get no push. The rows usually cite BG-04, BG-06, BG-07, MN-10, PERF-04, PERF-07, SYNC-03, and SYNC-04.

```markdown
## Pushes

| Push | Id | Trigger | Why the client cannot know | Recipients | Fields in order | Minimum client | Design | Rules |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| StreakState | 4250 | AdminSetStreak changes the state of an online player | A support repair changed it, not the player's own command | The player | `serverTime`, `streakCount`, `lastClaimDay` | 1.4.0 | none | BG-04, BG-07, MN-10, SYNC-03, SYNC-04 |
```

### State model

The section has five parts, in this order: stored documents, timed fields, migrations, Redis keys, and states and transitions. Each stored document gets its key, writer, schema version, size bound, and a field table. A key added to an existing document has a default for documents that lack it. Fields that must change together, such as a cost and the purchase it records, go in one document, or in documents that CAP-USERSTORE saves in one atomic write, because the store has no transaction across documents.

The parts come from the design's States, Rules, Timing, and Config tables. They usually cite MN-02, MN-04, MN-05, MN-06, MN-11, MN-12, BG-01, BG-02, BG-09, PERF-06, and CFG-06.

````markdown
## State model

### Stored documents

#### StreakState

- Key: `streak_<userId>`, which does not change when a class is renamed. Rules: BG-01.
- Writer: The user's owner actor only. Rules: MN-02.
- Schema version: 1. Rules: BG-09.
- Size bound: Under 1 KB, with no lists. Rules: PERF-06.

| Field | Type | Default when absent | Bound | Added in version | Meaning | Design | Rules |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `schemaVersion` | int | 0 | 0 or more | 1 | Document schema version | none | BG-09 |
| `streakCount` | int | 0 | 0 to 10000 | 1 | Claims in a row before today | R1, F1 | BG-01, BG-02 |
| `lastClaimDay` | int | -1 | A server day number | 1 | Server day of the last claim | R1, TM1 | MN-11 |

### Timed fields

| Field | Effect derived from it | Derived when | Design | Rules |
| --- | --- | --- | --- | --- |
| `lastClaimDay` | A claim is ready when today is after it. The streak is broken when today is more than one day after it. | On each read of the state | ST2, R1 | MN-11, AUTH-02 |

### Migrations

| From version | To version | Step | Idempotent because | Rules |
| --- | --- | --- | --- | --- |
| 0 | 1 | Set the defaults above | It runs only when `schemaVersion` is below 1 | BG-09 |

### Redis keys

| Key pattern | Hash tag | Type | Written by | Atomic operation | TTL | Rules |
| --- | --- | --- | --- | --- | --- | --- |
| `<pattern>` | `<tag>` | <type> | <commands or jobs> | <command or script> | <ttl> | MN-05, MN-06, PERF-08 |

### States and transitions

| From | Event | Guard | To | Design | Rules |
| --- | --- | --- | --- | --- | --- |
| ST1 Locked | Level up | The level is at least `unlockLevel` | ST2 Ready | ST1, ST2 | AUTH-06 |
| ST2 Ready | ClaimStreakReward | Every check passes | ST3 Claimed | R1 | AUTH-06 |
| ST3 Claimed | The server day changes | None | ST2 Ready | TM1 | MN-11 |
````

### Config schema

The section names the feature's config file, how it loads, and every key. A key added to an existing file is optional and has a default, so both server versions read the file.

The rows come from the design's Config tables and Timing. Each cost and reward is an `{id, amount}` record, and each table of rows is a list with an `id` per row. They usually cite CFG-01 to CFG-10, BG-08, and PERF-05. A value that a request field multiplies, such as a price times the largest quantity, has a Validation cell that caps the product so it fits its type (AUTH-04).

```markdown
## Config schema

- File: `login-streak.json`, the feature's own file. Rules: CFG-01.
- Load: Validated at startup and at reload, then published as one immutable snapshot. Rules: CFG-02, CFG-03.
- Active flag and window: `isActive`, with no window. Rules: CFG-04.

| Key | Type | Required | Default | Validation | Index built at load | Design | Rules |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `isActive` | bool | yes | none | none | none | TM2 | CFG-04 |
| `unlockLevel` | int | yes | none | 1 or more | none | ST1 | CFG-02, CFG-05 |
| `rewards` | list | yes | none | Days 1 to 7, each once, each with one `reward`, an `{id, amount}` record with a known item id and an amount of 1 or more | Map from day to entry | RW1, RW7 | CFG-02, CFG-06, CFG-09, CFG-10, PERF-05 |

Environment values:

| Key | Environment config | Rules |
| --- | --- | --- |
| None | The feature has no secrets, allowlists, or endpoints | CFG-07 |

Generated files:

| File | Generator | Source change | Rules |
| --- | --- | --- | --- |
| Command id constants | The generator that the profile's CAP-GENERATED entry names | Add ids 4200 to 4299 | CFG-08 |
```

### Metric events and KPI queries

The section has three parts: actions, currency and item changes, and one KPI query per success measure. Extra fields state their meaning. KPI queries run against the tables that the profile's CAP-METRIC entry describes.

The rows come from the design's Overview, Gameplay loop, and Rewards. They usually cite MET-01 to MET-09.

````markdown
## Metric events and KPI queries

### Actions

| Action | Written by | Result codes | Extra fields | Funnel step | Rules |
| --- | --- | --- | --- | --- | --- |
| `streak_view` | GetStreakState | 0 and every command error | None | 1 view | MET-01, MET-02, MET-05 |
| `streak_claim` | ClaimStreakReward | 0 and every command error | `rewardDay` is the day claimed, `streakCount` is the streak after the claim | 2 claim | MET-01, MET-02, MET-05, MET-07 |

### Currency and item changes

| Reason | Source or sink | Currency or item | Amount | Command | Rules |
| --- | --- | --- | --- | --- | --- |
| `STREAK_CLAIM` | source | The item of the reward day | From `rewards[].reward` | ClaimStreakReward | MET-03, MET-04 |

### KPI queries

#### SM1: Share of daily active players who claim day 7 each week

- Table: The user action table from the profile's CAP-METRIC entry.
- Rules: MET-06.

```sql
SELECT COUNT(DISTINCT user_id) AS day7_claimers
FROM user_action
WHERE action = 'streak_claim'
  AND result = 0
  AND extra_reward_day = 7
  AND event_time >= :week_start
  AND event_time < :week_end
```
````

### Cheat commands

The section names the cheat handler and has one row per cheat. Every state in the design's States table appears in the `Design states` cell of at least one cheat. A state that an existing project cheat reaches, such as a level cheat, names that cheat.

The rows come from the design's States and Timing. They usually cite CHEAT-01 to CHEAT-07 and TEST-04.

```markdown
## Cheat commands

- Handler: `StreakCheatHandler`, registered only when the server is not live. Each cheat class carries the profile's cheat marker. Rules: CHEAT-01, CHEAT-03.

| Cheat | Id | Sets | Input checks | Domain method | Metric action | Design states | Rules |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CheatSetStreak | 4290 | `streakCount` and `lastClaimDay` | Count 0 to 10000, day not after today | `StreakState.restore` | `cheat_streak_set` | ST2, ST3 | CHEAT-02, CHEAT-04, CHEAT-05, CHEAT-06 |
| CheatShiftDay | 4291 | The player's time offset | 1 to 30 days | The server clock's per-user offset | `cheat_time_shift` | ST2 | CHEAT-02, CHEAT-04, CHEAT-07 |
| Existing level cheat | none | The player's level | As the project defines | As the project defines | As the project defines | ST1 | CHEAT-05 |
```

### Admin commands and API spec

The section has one summary row per admin command, then one API entry per command. Each feature ships commands that read and repair its per-user state. When the profile's CAP-ADMIN entry names an admin web repository, the spec also lists the screens that call these commands.

The rows come from support needs, so most write `none` under `Design`. They usually cite ADMIN-01 to ADMIN-08.

```markdown
## Admin commands and API spec

| Command | Permission | Mutating | Destructive on live | Target routing | Retry | Design | Rules |
| --- | --- | --- | --- | --- | --- | --- | --- |
| AdminGetStreak | support read | no | no | Snapshot from the owner, or a stored copy when offline | Harmless | none | ADMIN-01, ADMIN-06, ADMIN-08 |
| AdminSetStreak | support write | yes | yes, needs `confirm` set to true | The owner actor, or CAS when offline | The same `requestId` applies once | none | ADMIN-01, ADMIN-02, ADMIN-04, ADMIN-06, ADMIN-07, ADMIN-08 |

### AdminSetStreak

- Permission: support write.
- Audit: One row with the admin, the target user, the requested and the applied values, the result, and the trace id. Rules: ADMIN-03.
- Errors: `USER_NOT_FOUND`, `OUT_OF_RANGE`, `CONFIRM_REQUIRED`. Rules: ADMIN-05, ADMIN-06.

Request:

| Field | Type | Required | Allowed values | Rules |
| --- | --- | --- | --- | --- |
| `userId` | long | yes | An existing user | ADMIN-05, ADMIN-06 |
| `streakCount` | int | yes | 0 to 10000 | ADMIN-05, ADMIN-06 |
| `requestId` | string | yes | 8 to 64 characters | ADMIN-05, ADMIN-07 |
| `confirm` | bool | on live | true | ADMIN-04, ADMIN-05 |

Response:

| Field | Type | Meaning | Rules |
| --- | --- | --- | --- |
| `error` | int | Result code | ADMIN-05 |
| `before` | object | The state before the change | ADMIN-05 |
| `after` | object | The state after the change | ADMIN-05 |
```

### HTTP endpoints

The section has one entry per endpoint for callers that cannot log in. The login streak has none, so its spec says `None.` with its reason. The format below is for a feature that has an endpoint. The entries usually cite HTTP-01 to HTTP-08, MET-09, and BG-11.

```markdown
## HTTP endpoints

### POST /callback/<provider>

| Item | Value | Rules |
| --- | --- | --- |
| Caller | <provider> servers | HTTP-01 |
| Why it cannot log in | <reason> | HTTP-01 |
| Signature | <header> with <algorithm> over the raw body, secret <environment key>, timestamp at most <n> s old | HTTP-02 |
| Allowlist | <environment key>, non-empty on live | HTTP-03 |
| Idempotency key | <external transaction id> | HTTP-04 |
| Payload checks | User id, product id, price, currency, and expiry against server data | HTTP-06 |
| Inbox entry | Type <type> with fields <fields> | HTTP-05, BG-11 |
| Metric | Action <action> with the transaction id, the user id, the result, and the trace id | HTTP-07, MET-09 |
| Status codes | 200 for delivered or duplicate, 400 for a bad payload, 401 for a bad signature, 503 to ask for a retry | HTTP-08 |
```

### Multi-node analysis

The section is one table with fixed rows. Keep every row. A row that does not apply writes `none` under `Where it lives` and says why under `How it stays safe`.

```markdown
## Multi-node analysis

| Concern | Where it lives | Writers | How it stays safe | What fails without it | Rules |
| --- | --- | --- | --- | --- | --- |
| Static state | The config snapshot reference only | The config loader | One reference swap at reload | A node-local value differs between nodes | MN-01 |
| The player's own state | StreakState | The owner actor | Only the owner actor touches it | Two nodes overwrite each other's saves | MN-02 |
| Other users' state | none | none | The feature changes no other user | none | MN-03 |
| Shared documents | none | none | The feature has no shared document | none | MN-04 |
| Cluster-wide state | none | none | The feature keeps no Redis state | none | MN-05, MN-06, PERF-08 |
| Once-per-cluster jobs | none | none | The feature has no job | none | MN-07 |
| Unique ids | none | none | The feature mints no ids | none | MN-08 |
| Node-local caches | none | none | The feature reads only its config snapshot | none | MN-09 |
| Pushes and online checks for other users | none | none | The feature pushes only to the acting player | none | MN-10 |
| Timed effects | `lastClaimDay` | The owner actor | Derived from the stored day on each read | A timer lost at drain leaves a claim not ready | MN-11 |
| Contested shared things | none | none | No two users race for one thing | none | MN-03, MN-14 |
| Reads of another user's state | none | none | The feature reads no other user | none | MN-02 |
| Unknown results from Redis or the store | none | none | The feature makes no Redis call, and a failed save is the core's | none | MN-13 |
| Late writes after a handover | none | none | The feature buffers no write | none | MN-15 |
```

### Blue-green and client compatibility

The section starts with one Deploy line, then one table with fixed rows. Keep every row, and keep its `Rules` cell. The `Test` cell names a test from the Test plan, or says why no test applies.

The Deploy line says `rolling` or `maintenance` and why. A rolling deploy needs all four: stored data only gains fields with defaults, packets other users receive stay safe for old clients, the config of a running event and the formats of Redis keys and shared logs do not change, and no new inbox entry type must be understood by the old version, only kept. Anything else, and any change under BG-12, makes it a maintenance deploy with the rollback step written out.

```markdown
## Blue-green and client compatibility

- Deploy: rolling, because the feature only adds fields, adds no format the old version cannot read, and changes no running event's config. Rules: BG-12.

| Case | Expected behavior | How the spec ensures it | Rules | Test |
| --- | --- | --- | --- | --- |
| An old client calls existing commands on the new server | Same behavior and response layout as before | No existing command changes | BG-04, BG-05, BG-06 | none, no existing command changes |
| A client older than the feature's minimum reaches the new server | It never sees the feature and never gets its pushes | Check 2 of ClaimStreakReward and the push minimum | BG-06, BG-07 | `ClaimStreakRewardTest` old client |
| A new client reaches an old server, during rollout or after a rollback | The old server answers the new command ids as unknown, and the client hides the feature | New command ids only, no reused id | BG-03 | none, the old server has no feature code |
| The new version reads data that the old version wrote | Absent fields take their defaults, and migration runs once | Migration 0 to 1 | BG-09 | `StreakStateCompatTest` old document |
| The old version reads data that the new version wrote | The old version keeps the fields it does not know | The serializer keeps unknown fields | BG-01, BG-02 | `StreakStateCompatTest` unknown field |
| Both versions read the same config | Each version reads the keys it knows | New keys are optional with defaults | BG-08 | `StreakConfigTest` extra key |
| An old node meets a new inbox entry or cross-node message type | The entry stays in the inbox for a newer node, and an unknown message is ignored because it only carries a signal | The feature adds no entry type | BG-11 | none, no new entry type |
| A node drains during a claim | The claim finishes and its save is confirmed before ownership moves | The core's drain | BG-10 | none, core behavior |
| The servers roll back to the old version | Data and granted items from the new version survive | Additive fields only | BG-01, BG-02, BG-09 | `StreakStateCompatTest` unknown field |
| Both versions write the same shared document | Neither version drops the other's fields | The feature has no shared document | BG-02 | none, no shared document |
| A stored format changes in a way the old version cannot read | The release ships as a maintenance deploy with a rollback step | No format changes | BG-12 | none, no format change |
| A boot step of the feature fails | The node does not boot | The config load throws on an invalid file | BG-13 | `StreakConfigTest` invalid file |
| A cluster job runs while the old version holds the cluster lease | The job still runs, and runs once per unit | The feature has no job | MN-07 | none, no job |
```

### Performance budget

The section states the peak load and one row per command and push. Calls per second show the arithmetic. The default load is 100,000 concurrent players at peak and 1,000,000 daily active players, unless the developer gives other numbers. The per-user state bound comes from the State model, and the config lookups come from the Config schema index column.

```markdown
## Performance budget

- Peak load: 100,000 concurrent players, 1,000,000 daily active players.
- Per-user state: StreakState under 1 KB. Rules: PERF-06.

| Command | Calls per second at peak | DB reads | DB writes | Redis calls | Other users touched | Response bytes | Push bytes | Rules |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ClaimStreakReward | 35, from 1,000,000 claims a day and a peak of 3 times the average | 0 | 0, saved by the save cycle | 0 | 0 | 200 | 100 | PERF-01, PERF-02, PERF-03, PERF-04, PERF-07 |
```

### Core blockers

The section lists every capability that a cited rule needs and that the profile does not show as `present`. Build the list in four steps.

1. Collect every rule id that the spec cites. Leave out a rule that the spec cites only on a fixed Multi-node or Blue-green row that says the feature has nothing of that kind, such as "The feature has no job" under MN-07. When the profile blocks a rule you leave out, name it on a `Left out:` line at the end of the section, after the table or after `None.`, with the reason, such as `Left out: MN-07, cited only where the feature has no job.`
2. Read each rule's `needs:` line in the rule index.
3. Read each needed capability's status in the profile.
4. Write one row per capability that blocks a collected rule. A `missing` capability blocks every rule whose `needs:` line names it. A `partial` capability blocks only the rule ids on its profile `blocker` line. `Rules blocked` lists the collected rules that the capability blocks.

The smallest core change comes from the profile entry's `proposal`, cut down to what this feature needs.

```markdown
## Core blockers

| Capability | Profile status | Rules blocked | What fails for players | Smallest core change | Resolution |
| --- | --- | --- | --- | --- | --- |
| CAP-CLIENTVER | partial | BG-06, BG-07 | A client older than 1.4.0 receives StreakState and fails to parse it | Keep the login version per session and add a check against a minimum version | open |
```

The `Resolution` cell holds one value.

| Resolution | Meaning | Blocks |
| --- | --- | --- |
| `open` | The row waits for the developer. | yes |
| `core changed` | The developer changed the core, and the profile now shows the capability as `present`. | no |
| `descoped` | The developer removed the feature parts that need the capability. The row names the design ids dropped. | no |
| `accepted by <name>: <reason>` | The developer accepts the risk. The value is valid for any severity. When a rule blocked is `critical`, the reason names the deployment fact and says how that fact prevents or bounds the failure that the row names, such as "one node per realm, so no second node can load the player and save over the claim". The header's `Accepted risks` line lists the rule. A critical acceptance that cites a fact without that link counts as `open`. | no |
| `accepted by <name> (D<n>): <reason>` | A project decision in `docs/game-server/decisions.md` accepts the risk for every feature, as the [decisions template](decisions-template.md) says. The name and the reason come from the decision. | no |

While any row blocks, the spec status is `blocked`. The skill that writes the spec stops and gives this section to the developer, and `feature-build` does not start. Only the developer sets a resolution. Feature code never works around a missing capability.

A resolved row stays in the table with its resolution. The section says `None.` only when no row was ever needed, because every capability the spec needs is `present` in the profile.

A row that blocks PERF-01 is accepted call by call. When the developer accepts one, an `Accepted blocking calls` table follows the Core blockers table. It has one row per call site for each blocking call that the feature makes on the user actor thread, such as a call the profile's `lint.blocking_calls` names. `Class` is the Java class that makes the call. `Call` is the call's text as it appears on that line. Two call sites with the same text in one class take two rows, so a class with more such calls than rows makes one that is not accepted. `Bound` says how long the call can wait and whose work waits behind it, as any critical acceptance must. Write `None.` under the heading when the feature makes no such call. A blocking call that this table does not name stays a PERF-01 finding in `feature-build` and `feature-review`, whatever the row's reason says.

```markdown
### Accepted blocking calls

| Class | Call | Bound |
| --- | --- | --- |
| AdminGetStreak | kvStore.get | Support reads an offline player a few times a minute. The read waits at most the 2500 ms store timeout and holds only the target player's actor. |
```

### Test plan

The section names the check command and one row per test case. Each test class runs with the profile's `test_one_cmd`. The plan has at least these cases:

- For each command, the main flow, each time and random case with the clock and the RNG injected, one negative case per row of its Checks table, and its metric rows.
- For each command that takes a request id, and for each HTTP callback, a replay that asserts one effect.
- For each command whose grant can throw, a grant that throws after the take, which asserts that the cost comes back, the request id is not stored, and the exception reaches the runner.
- For each cheat, a run on live that asserts rejection and no change.
- For the config, a valid file and each invalid case that validation rejects.
- For each stored document, data from before the change and data with fields from a newer version.
- For each changed command, a request from an old client.
- For each command, a bot scenario when the profile shows CAP-BOT as `present`.

```markdown
## Test plan

- Check: The profile's `test_one_cmd` for each test class below, after each slice.

| Test class | Case | Level | Asserts | Design | Rules |
| --- | --- | --- | --- | --- | --- |
| `ClaimStreakRewardTest` | First claim on a new state | unit | Reward day 1, RW1 items, `lastClaimDay` is today | R1, RW1 | TEST-01, TEST-02 |
| `ClaimStreakRewardTest` | Claim after a missed day | unit | Reward day 1, `streakCount` restarts | R1, F1 | TEST-02 |
| `ClaimStreakRewardTest` | Second claim on the same day | unit | `ALREADY_CLAIMED`, state unchanged | ST3 | TEST-03 |
| `ClaimStreakRewardTest` | Old client, version 1.3.0 | unit | `CLIENT_TOO_OLD`, state unchanged | none | TEST-03, TEST-07 |
| `ClaimStreakRewardTest` | Replay of one request id | unit | One grant | none | TEST-09 |
| `ClaimStreakRewardTest` | Metric rows | unit | One `streak_claim` row with the trace id on success and on each error | none | TEST-08 |
| `StreakCheatTest` | CheatSetStreak on live | unit | Rejected, no change | ST2 | TEST-04, TEST-11 |
| `StreakConfigTest` | A reward for day 8 | unit | Load fails and names the file and the key | RW1 | TEST-05 |
| `StreakConfigTest` | Extra key | unit | Load succeeds and ignores a key it does not know | none | TEST-05, BG-08 |
| `StreakStateCompatTest` | Old document | compatibility | Defaults apply, and migration runs once | none | TEST-06, BG-09 |
| `StreakStateCompatTest` | Unknown field | compatibility | A save keeps the field | none | TEST-06, BG-02 |
```

### Design coverage

The section has one row per id in the design, including success measures and open questions. A design id that the spec does not build names the Core blockers row that descoped it, or the open question that holds it. An id with no server effect says `client only` and why.

```markdown
## Design coverage

| Design id | Spec rows | Tests |
| --- | --- | --- |
| R1 | ClaimStreakReward effect, State model timed field `lastClaimDay` | `ClaimStreakRewardTest` claim after a missed day |
| SM1 | KPI query SM1 | none |
| Q1 | Header, interim default | none |
```
