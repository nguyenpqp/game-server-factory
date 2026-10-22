# Worked example

This file shows a complete spec for a daily login streak with rewards, in the [spec template](spec-template.md) format. The spec sits in one fenced block so its headings stay exact. Copy its shape, never its numbers.

## The design it reads

The spec reads a `design.md` built from the [design template](../../gdd-intake/references/design-template.md) skeleton, with these ids.

| Id | Requirement |
| --- | --- |
| SM1 | The share of daily active players who claim the day 7 reward at least once a week |
| ST1 | Locked, while the player is below level 5 |
| ST2 | Ready, after a new day starts and while today is unclaimed |
| ST3 | Claimed, after the player claims today |
| R1 | A day with no claim resets the streak, so the next claim is day 1 |
| R2 | The reward track repeats after day 7 |
| F1 | `rewardDay = (streakCount mod 7) + 1`, where `streakCount` counts claims in a row before this claim |
| RW1 to RW7 | Day rewards of 500 gold, 800 gold, 1 common chest, 1,200 gold, 5 gems, 1,500 gold, 1 rare chest |
| TM1 | The day starts at 00:00 in the server timezone |
| TM2 | The feature is always on |
| EC1 | A claim at 00:01 after the panel opened at 23:59 counts for the new day |
| UI1 | The streak panel shows the current day, the seven rewards, and the time until the next day |
| UI2 | The lobby icon shows a red dot while a claim is ready |
| Q1 | Which day a claim at 00:01 counts for. Answered on 2026-10-01: the server day |

## The profile it reads

The profile shows every capability the spec needs as `present`, with two exceptions.

- CAP-CLIENTVER was `partial`. The handshake carried a client version, but the server dropped it after login.
- CAP-BOT is `missing`. The spec cites no rule that needs it, so it is not a blocker, and the Test plan has no bot scenario.

Its CAP-USERSTORE entry records that the save cycle writes every changed document of a player, the inventory balances included, in one Couchbase transaction, so a claim's reward and StreakState land together.

## How the blocker resolved

The first draft cited BG-06 and BG-07, and the `blocker` line of the partial CAP-CLIENTVER entry names both. The skill wrote the Core blockers row with resolution `open`, set `Status: blocked`, and stopped. The developer kept the login version on the session and added a minimum version check to the core, then updated the profile entry to `present`. The skill set the resolution to `core changed`, wrote the Test plan and Design coverage, and asked for confirmation. The developer confirmed, and the status became `ready`.

## The spec

````markdown
# Login streak server spec

- Design: `docs/game-server/features/login-streak/design.md`
- Profile: `docs/game-server/profile.md`, profile_version 1
- Package: `com.example.game.feature.streak`
- Command ids: 4200 to 4299
- Minimum client for the feature: 1.4.0
- Status: ready
- Open design questions: None. Q1 is answered, and TM1 and EC1 use the answer.
- Accepted risks: None.

## Commands

A server day number is the count of whole days since the epoch in the timezone that the profile's CAP-CLOCK entry names. Rules: AUTH-02, MN-11.

### GetStreakState

- Id: 4200
- Intent: The client asks for the panel data when the panel opens and when its countdown reaches zero. Design: UI1, UI2. Rules: AUTH-01.

Request: None. The command takes no fields.

Checks:

| Order | Check | Error | Design | Rules |
| --- | --- | --- | --- | --- |
| 1 | The feature is active | `FEATURE_INACTIVE` | TM2 | AUTH-06, CFG-04 |
| 2 | The session's client version is 1.4.0 or later | `CLIENT_TOO_OLD` | none | BG-07 |

- Cost: None. Rules: AUTH-07.
- Effect: Read only. On the owner actor, the core reads the stored StreakState fields, computes the next reward day with F1 and the next day boundary from `now`, and takes `unlockLevel` and the rewards from the config snapshot. The client derives locked, ready, and claimed from these values and `serverTime`. Design: ST1, ST2, ST3, R1, F1. Rules: AUTH-02, MN-02, MN-11, CFG-03, SYNC-01, SYNC-03.

Response:

| Order | Field | Type | Optional | Meaning | Rules |
| --- | --- | --- | --- | --- | --- |
| 1 | `error` | int | no | Result code | AUTH-10 |
| 2 | `serverTime` | long | no | Server time in epoch milliseconds | SYNC-01 |
| 3 | `unlockLevel` | int | no | The level at which the feature unlocks, from the config | SYNC-01 |
| 4 | `streakCount` | int | no | Stored claims in a row, up to and including `lastClaimDay` | SYNC-03 |
| 5 | `lastClaimDay` | int | no | Stored server day of the last claim, -1 before the first claim | SYNC-03 |
| 6 | `rewardDay` | int | no | The day the next claim grants, 1 to 7 | BG-04 |
| 7 | `nextDayStartsAt` | long | no | Epoch milliseconds of the next day boundary | BG-04, MN-11 |
| 8 | `rewards` | list | no | The 7 reward days, each with its one `{id, amount}` reward | BG-04, PERF-04 |

- Reject: Every error carries `serverTime`. The command changes nothing, so it has no other field to resync. Rules: SYNC-02.
- Idempotency: None. The command changes nothing, so a retry is harmless. Rules: AUTH-08.
- Rate limit: None. The command reads only the player's own state in memory. Rules: AUTH-09.
- Pushes: None.
- Metric: Action `streak_view`, on success and on every error. An unexpected exception writes an exception row with the trace id and answers the shared server error code. Rules: MET-01, MET-02, MET-05, MET-08.

### ClaimStreakReward

- Id: 4201
- Intent: The player asks to claim today's reward. The request names no reward and no amount. Design: UI1, R1. Rules: AUTH-01.

Request:

| Field | Type | Required | Allowed values | Rules |
| --- | --- | --- | --- | --- |
| `requestId` | string | yes | 8 to 64 characters of letters, digits, and hyphens | AUTH-04, AUTH-08 |

A field that fails its check returns the shared `INVALID_REQUEST` and changes nothing. Rules: AUTH-04, AUTH-10.

Checks:

| Order | Check | Error | Design | Rules |
| --- | --- | --- | --- | --- |
| 1 | The feature is active | `FEATURE_INACTIVE` | TM2 | AUTH-06, CFG-04 |
| 2 | The session's client version is 1.4.0 or later | `CLIENT_TOO_OLD` | none | BG-07 |
| 3 | The player's level is at least `unlockLevel` | `FEATURE_LOCKED` | ST1 | AUTH-06 |
| 4 | Today, by server day, is not claimed yet | `ALREADY_CLAIMED` | ST3, TM1, EC1 | AUTH-02, AUTH-06 |

- Cost: None. The claim is free. Rules: AUTH-07.
- Effect: The core takes today's server day from `now`. It keeps `streakCount` when `lastClaimDay` is yesterday and sets it to 0 otherwise, then computes the reward day with F1. It adds the day's reward through the CAP-INVENTORY add with reason `STREAK_CLAIM` and the action's trace id. Only after the add succeeds does it set `streakCount` to the old value plus 1, at most 10000, `lastClaimDay` to today, and the last claim fields to this request, so a failed add changes nothing. When the add refuses, such as for a balance at the limit of its type, the command returns `GRANT_FAILED`. When the add throws, the core catches it at the call, removes what the add put in, and rethrows, so no StreakState field changes, the runner writes the exception row, and a retry with the same request id claims again. Design: R1, R2, F1, RW1, RW2, RW3, RW4, RW5, RW6, RW7, EC1. Rules: AUTH-01, AUTH-02, AUTH-04, AUTH-07, CFG-05, MET-03, MET-04.

Response:

| Order | Field | Type | Optional | Meaning | Rules |
| --- | --- | --- | --- | --- | --- |
| 1 | `error` | int | no | Result code | AUTH-10 |
| 2 | `serverTime` | long | no | Server time in epoch milliseconds | SYNC-02 |
| 3 | `rewardDay` | int | no | The reward day just claimed | BG-04 |
| 4 | `items` | list | no | Items granted, at most 10 | BG-04, PERF-04 |
| 5 | `streakCount` | int | no | Stored claims in a row after this claim | SYNC-02 |
| 6 | `lastClaimDay` | int | no | Stored server day of the last claim, after this claim | SYNC-02, SYNC-03 |
| 7 | `balances` | list | no | The post-change amount of each item granted, from CAP-INVENTORY, at most 10 | SYNC-02, PERF-04 |

- Reject: Every error carries `serverTime`, `streakCount`, and `lastClaimDay` with their stored values, so the client resyncs from the reject. Rules: SYNC-02.

- Idempotency: StreakState keeps the last claim's `requestId` and reward day. A request with that id returns the first result, with the day's reward read from the config, and grants nothing. Any other request on a claimed day gets `ALREADY_CLAIMED`. The record is one id, so the state stays bounded. Rules: AUTH-08, PERF-06.
- Rate limit: None. The command reads and writes only the player's own state. Rules: AUTH-09.
- Pushes: None. The response carries the change. Rules: SYNC-04.
- Metric: Action `streak_claim`, on success, on a replay, and on every error. An unexpected exception writes an exception row with the trace id and answers the shared server error code. Rules: MET-01, MET-02, MET-08.

### Error codes

The shared codes `FEATURE_INACTIVE`, `CLIENT_TOO_OLD`, `FEATURE_LOCKED`, `INVALID_REQUEST`, and `USER_NOT_FOUND` come from the profile's CAP-ERRORS entry. Rules: AUTH-10.

| Code | Name | Meaning | Commands | Rules |
| --- | --- | --- | --- | --- |
| 4201 | `ALREADY_CLAIMED` | Today's reward is already claimed | ClaimStreakReward | AUTH-10 |
| 4202 | `OUT_OF_RANGE` | A cheat or admin value is missing or outside its range | CheatSetStreak, CheatShiftDay, AdminSetStreak | AUTH-10, ADMIN-06 |
| 4203 | `CONFIRM_REQUIRED` | A destructive admin command on live lacks `confirm` | AdminSetStreak | ADMIN-04 |
| 4204 | `GRANT_FAILED` | The reward add refused, and nothing changed | ClaimStreakReward | AUTH-10 |

## Pushes

| Push | Id | Trigger | Why the client cannot know | Recipients | Fields in order | Minimum client | Design | Rules |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| StreakState | 4250 | AdminSetStreak changes the state of a player who is online | A support repair changed it, not the player's own command | The target player, through the ownership record and cross-node delivery | `serverTime`, `streakCount`, `lastClaimDay` | 1.4.0 | none | BG-04, BG-06, BG-07, MN-10, PERF-04, SYNC-03, SYNC-04 |

The client refreshes at `nextDayStartsAt` with GetStreakState, so the server keeps no timer per user. Rules: MN-11.

The client calls GetStreakState at login and after a reconnect, and a claim answers with its change, so the server pushes nothing at login or after a claim. Rules: SYNC-01, SYNC-04.

## State model

### Stored documents

#### StreakState

- Key: `streak_<userId>`, which does not change when a class is renamed. Rules: BG-01.
- Writer: The user's owner actor, and AdminSetStreak through the owner, or holding the user's ownership slot and writing with CAS when the user is offline. Rules: MN-02, ADMIN-02.
- Schema version: 1. Rules: BG-09.
- Size bound: Under 1 KB, with no lists. Rules: PERF-06.

| Field | Type | Default when absent | Bound | Added in version | Meaning | Design | Rules |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `schemaVersion` | int | 0 | 0 or more | 1 | Document schema version | none | BG-09 |
| `streakCount` | int | 0 | 0 to 10000 | 1 | Claims in a row, up to and including `lastClaimDay` | R1, F1 | BG-01, BG-02 |
| `lastClaimDay` | int | -1 | -1, or a server day number | 1 | Server day of the last claim | R1, TM1 | MN-11 |
| `lastClaimRequestId` | string | empty | 0 to 64 characters | 1 | Request id of the last claim | none | AUTH-08, PERF-06 |
| `lastClaimRewardDay` | int | 0 | 0 to 7 | 1 | Reward day of the last claim | F1 | AUTH-08 |

### Timed fields

| Field | Effect derived from it | Derived when | Design | Rules |
| --- | --- | --- | --- | --- |
| `lastClaimDay` | Claimed when it equals today. Ready when it is before today and the player is unlocked. The streak is broken when it is before yesterday. | On each read of the state | ST2, ST3, R1 | MN-11, AUTH-02 |

### Migrations

| From version | To version | Step | Idempotent because | Rules |
| --- | --- | --- | --- | --- |
| 0 | 1 | Set the defaults above and `schemaVersion` to 1 | It runs only when `schemaVersion` is below 1 | BG-09 |

### Redis keys

None. The feature keeps no cluster-wide state. Rules: MN-05.

### States and transitions

| From | Event | Guard | To | Design | Rules |
| --- | --- | --- | --- | --- | --- |
| ST1 Locked | Level up, seen on the next read | The level is at least `unlockLevel` | ST2 Ready | ST1, ST2 | AUTH-06 |
| ST2 Ready | ClaimStreakReward | Every check passes | ST3 Claimed | R1 | AUTH-06 |
| ST3 Claimed | The server day changes | None | ST2 Ready | TM1 | MN-11 |

## Config schema

- File: `login-streak.json`, the feature's own file. Rules: CFG-01.
- Load: Validated at startup and at reload, then published as one immutable snapshot. Rules: CFG-02, CFG-03.
- Active flag and window: `isActive`, with no window, because TM2 says always on. Rules: CFG-04.

| Key | Type | Required | Default | Validation | Index built at load | Design | Rules |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `isActive` | bool | yes | none | none | none | TM2 | CFG-04 |
| `unlockLevel` | int | yes | none | 1 or more | none | ST1 | CFG-02, CFG-05 |
| `rewards` | list | yes | none | Exactly one entry for each day from 1 to 7 | Array of 7 entries indexed by day | RW1, RW2, RW3, RW4, RW5, RW6, RW7 | CFG-02, CFG-06, PERF-05 |
| `rewards[].day` | int | yes | none | 1 to 7, each once | none | F1 | CFG-02, CFG-06 |
| `rewards[].reward` | object | yes | none | One `{id, amount}` record, a known item id from CAP-INVENTORY with an amount of 1 or more | none | RW1, RW2, RW3, RW4, RW5, RW6, RW7 | CFG-02, CFG-05, CFG-09, CFG-10 |

Environment values:

| Key | Environment config | Rules |
| --- | --- | --- |
| None | The feature has no secrets, allowlists, or endpoints | CFG-07 |

Generated files:

| File | Generator | Source change | Rules |
| --- | --- | --- | --- |
| Command id constants | The generator that the profile's CAP-GENERATED entry names | Add ids 4200, 4201, 4250, 4290, and 4291 | CFG-08 |
| Error code constants | The generator that the profile's CAP-GENERATED entry names | Add codes 4201 to 4204 | CFG-08 |

## Metric events and KPI queries

### Actions

| Action | Written by | Result codes | Extra fields | Funnel step | Rules |
| --- | --- | --- | --- | --- | --- |
| `streak_view` | GetStreakState | 0 and every command error | `rewardDay` is the day the next claim grants, `claimedToday` is 1 or 0 | 1 view | MET-01, MET-02, MET-05, MET-07 |
| `streak_claim` | ClaimStreakReward | 0 and every command error | `rewardDay` is the day claimed, `streakCount` is the streak after the claim, `replay` is 1 for a repeated request id | 2 claim | MET-01, MET-02, MET-05, MET-07 |
| `cheat_streak_set` | CheatSetStreak | 0 and every cheat error | `streakCount` and `lastClaimDay` as set | none | CHEAT-04, MET-07 |
| `cheat_time_shift` | CheatShiftDay | 0 and every cheat error | `days` is the shift | none | CHEAT-04, MET-07 |
| `admin_streak_set` | AdminSetStreak | 0 and every admin error | `adminId`, `before`, and `after` | none | ADMIN-03, MET-07 |

### Currency and item changes

| Reason | Source or sink | Currency or item | Amount | Command | Rules |
| --- | --- | --- | --- | --- | --- |
| `STREAK_CLAIM` | source | The item of the reward day | From `rewards[].reward` | ClaimStreakReward | MET-03, MET-04 |

### KPI queries

#### SM1: Share of daily active players who claim day 7 each week

- Table: The user action table from the profile's CAP-METRIC entry. The entry maps the extra `rewardDay` to the column `extra_reward_day`.
- Rules: MET-06.

```sql
SELECT
  COUNT(DISTINCT CASE
    WHEN action = 'streak_claim' AND result = 0 AND extra_reward_day = 7
    THEN user_id END) * 1.0
  / COUNT(DISTINCT user_id) AS day7_share
FROM user_action
WHERE event_time >= :week_start
  AND event_time < :week_end
```

## Cheat commands

- Handler: `StreakCheatHandler`, registered only when the server is not live. Each cheat class carries the profile's cheat marker. Rules: CHEAT-01, CHEAT-03.

| Cheat | Id | Sets | Input checks | Domain method | Metric action | Design states | Rules |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CheatSetStreak | 4290 | `streakCount` and `lastClaimDay` | Count 0 to 10000, day from 30 days before today to today, else `OUT_OF_RANGE` | `StreakState.restore` | `cheat_streak_set` | ST2, ST3 | CHEAT-02, CHEAT-04, CHEAT-05, CHEAT-06 |
| CheatShiftDay | 4291 | The player's time offset | 1 to 30 days, else `OUT_OF_RANGE` | The server clock's per-user offset | `cheat_time_shift` | ST2 | CHEAT-02, CHEAT-04, CHEAT-07 |
| Existing level cheat | none | The player's level | As the project defines | As the project defines | As the project defines | ST1 | CHEAT-05 |

## Admin commands and API spec

The profile's CAP-ADMIN entry names no admin web repository, so the spec lists no screens. Rules: ADMIN-05.

| Command | Permission | Mutating | Destructive on live | Target routing | Retry | Design | Rules |
| --- | --- | --- | --- | --- | --- | --- | --- |
| AdminGetStreak | support read | no | no | A snapshot built on the owner, or a stored copy when offline | Harmless | none | ADMIN-01, ADMIN-06, ADMIN-08 |
| AdminSetStreak | support write | yes | yes, needs `confirm` set to true | The owner actor, or CAS on the stored document when offline | The same `requestId` applies once | none | ADMIN-01, ADMIN-02, ADMIN-04, ADMIN-06, ADMIN-07, ADMIN-08 |

### AdminGetStreak

- Permission: support read.
- Audit: None. The command changes nothing. Rules: ADMIN-03.
- Errors: `USER_NOT_FOUND`. Rules: ADMIN-05, ADMIN-06.

Request:

| Field | Type | Required | Allowed values | Rules |
| --- | --- | --- | --- | --- |
| `userId` | long | yes | An existing user | ADMIN-05, ADMIN-06 |

Response:

| Field | Type | Meaning | Rules |
| --- | --- | --- | --- |
| `error` | int | Result code | ADMIN-05 |
| `state` | object | Every StreakState field | ADMIN-05 |
| `claimedToday` | bool | Today's reward is claimed, by server day | ADMIN-05 |

### AdminSetStreak

- Permission: support write.
- Audit: One row with the admin, the target user, the requested and the applied values, the result, and the trace id. Rules: ADMIN-03.
- Errors: `USER_NOT_FOUND`, `OUT_OF_RANGE`, `CONFIRM_REQUIRED`. Rules: ADMIN-05, ADMIN-06.

Request:

| Field | Type | Required | Allowed values | Rules |
| --- | --- | --- | --- | --- |
| `userId` | long | yes | An existing user | ADMIN-05, ADMIN-06 |
| `streakCount` | int | yes | 0 to 10000. A missing value returns `OUT_OF_RANGE`. | ADMIN-05, ADMIN-06 |
| `lastClaimDay` | int | yes | -1, or a server day number not after today. A missing value returns `OUT_OF_RANGE`, because a count kept with a stale day resets on the next claim. | ADMIN-05, ADMIN-06 |
| `requestId` | string | yes | 8 to 64 characters | ADMIN-05, ADMIN-07 |
| `confirm` | bool | on live | true | ADMIN-04, ADMIN-05 |

Response:

| Field | Type | Meaning | Rules |
| --- | --- | --- | --- |
| `error` | int | Result code | ADMIN-05 |
| `before` | object | The state before the change | ADMIN-05 |
| `after` | object | The state after the change | ADMIN-05 |

## HTTP endpoints

None. Every caller is a logged-in player or an admin session. Rules: HTTP-01.

## Multi-node analysis

| Concern | Where it lives | Writers | How it stays safe | What fails without it | Rules |
| --- | --- | --- | --- | --- | --- |
| Static state | The config snapshot reference only | The config loader | One reference swap at reload | A node-local value differs between nodes | MN-01 |
| The player's own state | StreakState | The owner actor | Only the owner actor touches it, and CAP-USERSTORE saves it with the inventory in one transaction | Two nodes overwrite each other's saves, or a crash keeps the reward without the claim, and a claim is lost or granted twice | MN-02, MN-12 |
| Other users' state | The StreakState of an admin's target | AdminSetStreak | The command runs on the target's owner through cross-node delivery | An admin write and a claim on another node overwrite each other | MN-03, ADMIN-02 |
| Shared documents | StreakState while its user is offline | AdminSetStreak, through the CAP-ADMIN offline path | Holds the user's ownership slot, then CAS with at most 3 attempts | Two support writes at once lose one repair, or a login loads before the repair and saves over it | MN-04, ADMIN-02 |
| Cluster-wide state | none | none | The feature keeps no Redis state | none | MN-05, MN-06, PERF-08 |
| Once-per-cluster jobs | none | none | The feature has no job | none | MN-07 |
| Unique ids | none | none | The feature mints no ids | none | MN-08 |
| Node-local caches | none | none | The feature reads only its config snapshot | none | MN-09 |
| Pushes and online checks for other users | The StreakState push to an admin's target | AdminSetStreak | Through the ownership record and cross-node delivery | A push through a node-local session map misses a target on another node | MN-10 |
| Timed effects | `lastClaimDay` | The owner actor | Derived from the stored day on each read | A timer lost at drain leaves a claim not ready | MN-11 |
| Contested shared things | none | none | No two users race for one thing | none | MN-03, MN-14 |
| Reads of another user's state | The StreakState of an admin's target | AdminGetStreak, read only | A snapshot built on the owner, or a private copy when offline that it only shows and never saves | A stale copy used to grant or saved back overwrites the player's progress | MN-02 |
| Unknown results from Redis or the store | The offline CAS write of AdminSetStreak | AdminSetStreak | A timeout re-reads and answers retry-later, never applies the change twice | A repair applied twice, or reported as failed after it landed | MN-04, MN-13 |
| Late writes after a handover | none | none | The feature buffers no write | none | MN-15 |

## Blue-green and client compatibility

- Deploy: rolling, because StreakState only gains fields with defaults, the new pushes go only to clients 1.4.0 or later, and nothing changes a format the old version reads. Rules: BG-12.

| Case | Expected behavior | How the spec ensures it | Rules | Test |
| --- | --- | --- | --- | --- |
| An old client calls existing commands on the new server | Same behavior and response layout as before | No existing command changes | BG-04, BG-05, BG-06 | none, no existing command changes |
| A client older than the feature's minimum reaches the new server | It never sees the feature and never gets its pushes | Check 2 of both commands and the push minimum | BG-06, BG-07 | `ClaimStreakRewardTest` old client 1.3.0, `StreakAdminTest` push to a 1.3.0 player |
| A new client reaches an old server, during rollout or after a rollback | The old server answers the new command ids as unknown, and the client hides the feature | New command ids only, no reused id | BG-03 | none, the old server has no feature code |
| The new version reads data that the old version wrote | Absent fields take their defaults, and migration runs once | Migration 0 to 1 | BG-09 | `StreakStateCompatTest` no document |
| The old version reads data that the new version wrote | The old version keeps the fields it does not know | The serializer keeps unknown fields | BG-01, BG-02 | `StreakStateCompatTest` unknown field |
| Both versions read the same config | Each version reads the keys it knows | New keys are optional with defaults | BG-08 | `StreakConfigTest` extra key |
| An old node meets a new inbox entry or cross-node message type | The entry stays in the inbox for a newer node, and an unknown message is ignored because it only carries a signal | The feature adds no entry type, and AdminSetStreak uses the core's existing admin routing | BG-11 | none, no new entry type |
| A node drains during a claim | The claim finishes and its save is confirmed before ownership moves | The core's drain | BG-10 | none, core behavior |
| The servers roll back to the old version | Data and granted items from the new version survive | Additive fields only | BG-01, BG-02, BG-09 | `StreakStateCompatTest` unknown field |
| Both versions write the same shared document | Neither version drops the other's fields | Only the new version has code that writes StreakState | BG-02 | none, the old version never writes StreakState |
| A stored format changes in a way the old version cannot read | The release ships as a maintenance deploy with a rollback step | No format changes | BG-12 | none, no format change |
| A boot step of the feature fails | The node does not boot | The config load throws on an invalid file | BG-13 | `StreakConfigTest` day 3 missing |
| A cluster job runs while the old version holds the cluster lease | The job still runs, and runs once per unit | The feature has no job | MN-07 | none, no job |

## Performance budget

- Peak load: 100,000 concurrent players, 1,000,000 daily active players.
- Per-user state: StreakState under 1 KB. Rules: PERF-06.
- Login: One more key in the login multi-get, under 1 KB. Rules: PERF-02, PERF-03.
- Cheats: Not budgeted, because they are not registered on live. Rules: CHEAT-01.

| Command | Calls per second at peak | DB reads | DB writes | Redis calls | Other users touched | Response bytes | Push bytes | Rules |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GetStreakState | 104, from 3 views per daily player, 3,000,000 / 86,400 s times a peak factor of 3 | 0 | 0 | 0 | 0 | 1,000 | 0 | PERF-01, PERF-02, PERF-04 |
| ClaimStreakReward | 35, from 1 claim per daily player, 1,000,000 / 86,400 s times 3 | 0 | 0 on the command path, 1 later by the save cycle | 0 | 0 | 200 | 100 | PERF-01, PERF-02, PERF-03, PERF-04, PERF-07 |
| StreakState push after AdminSetStreak | under 1, support use | 0 | 0 | 0 | 1 | none | 100 | PERF-04, PERF-07 |
| AdminGetStreak | under 1, support use | 1 when the user is offline | 0 | 0 | 1 | 300 | 0 | PERF-02, PERF-07 |
| AdminSetStreak | under 1, support use | 1 when the user is offline | 1, or at most 3 CAS attempts when offline | 0 | 1 | 400 | 100 | PERF-02, PERF-07 |

## Core blockers

| Capability | Profile status | Rules blocked | What fails for players | Smallest core change | Resolution |
| --- | --- | --- | --- | --- | --- |
| CAP-CLIENTVER | partial at the first draft, present now | BG-06, BG-07 | A client older than 1.4.0 receives StreakState and fails to parse it | Keep the login version per session and add a check against a minimum version | core changed |

## Test plan

- Check: The profile's `test_one_cmd` for each test class below, after each slice. The profile shows CAP-BOT as missing, so the plan has no bot scenario. Rules: TEST-01.
- Time: Every test passes `now` and the CAP-CLOCK zone to the core and never sets the JVM's default zone, so the plan gives the same result on a machine in any zone. Rules: TEST-02.

| Test class | Case | Level | Asserts | Design | Rules |
| --- | --- | --- | --- | --- | --- |
| `GetStreakStateTest` | Unlocked player on an unclaimed day | unit | `serverTime` is `now`, the stored `streakCount` and `lastClaimDay`, `rewardDay` from F1, `nextDayStartsAt` at the next boundary | ST2, F1, UI1 | TEST-01, TEST-02 |
| `GetStreakStateTest` | Player below level 5 | unit | `unlockLevel` 5 and the stored fields, state unchanged | ST1, UI2 | TEST-01 |
| `GetStreakStateTest` | Feature inactive | unit | `FEATURE_INACTIVE` | TM2 | TEST-03 |
| `GetStreakStateTest` | Old client 1.3.0 | unit | `CLIENT_TOO_OLD` | none | TEST-03, TEST-07 |
| `GetStreakStateTest` | Metric rows | unit | One `streak_view` row with the trace id on success and on each error | none | TEST-08 |
| `ClaimStreakRewardTest` | First claim on a new state | unit | Reward day 1, RW1 items, `lastClaimDay` is today, and the response carries `serverTime`, `lastClaimDay`, and the post-change balance of each item | R1, RW1 | TEST-01, TEST-02 |
| `ClaimStreakRewardTest` | Claim on the day after a claim | unit | Reward day 2, RW2 items, `streakCount` 2 | F1, RW2 | TEST-02 |
| `ClaimStreakRewardTest` | Claim after a missed day | unit | Reward day 1, `streakCount` restarts at 1 | R1, F1 | TEST-02 |
| `ClaimStreakRewardTest` | Claim after a day 7 claim | unit | Reward day 1, `streakCount` 8 | R2, F1, RW7 | TEST-02 |
| `ClaimStreakRewardTest` | Claim at 00:00:01 after a claim at 23:59:59 | unit | The claim counts for the new day, and so does the same pair of times run on a machine set to UTC | EC1, TM1 | TEST-02 |
| `ClaimStreakRewardTest` | Feature inactive | unit | `FEATURE_INACTIVE`, state unchanged | TM2 | TEST-03 |
| `ClaimStreakRewardTest` | Old client 1.3.0 | unit | `CLIENT_TOO_OLD`, state unchanged | none | TEST-03, TEST-07 |
| `ClaimStreakRewardTest` | Player below level 5 | unit | `FEATURE_LOCKED`, state unchanged | ST1 | TEST-03 |
| `ClaimStreakRewardTest` | Second claim on the same day with a new request id | unit | `ALREADY_CLAIMED` with the stored `streakCount` and `lastClaimDay`, state unchanged | ST3 | TEST-03 |
| `ClaimStreakRewardTest` | Request id of 7 characters | unit | `INVALID_REQUEST`, state unchanged | none | TEST-03 |
| `ClaimStreakRewardTest` | The item add refuses | unit | `GRANT_FAILED` with the stored `streakCount` and `lastClaimDay`, state unchanged | none | TEST-03 |
| `ClaimStreakRewardTest` | The item add adds the reward and then throws | unit | The balance is back to its value before the claim, no StreakState field changes, the request id is not stored, one exception row with the trace id is written, and a retry with the same id grants once | none | TEST-08, TEST-09, AUTH-07 |
| `ClaimStreakRewardTest` | Claim with `streakCount` 10000 stored and yesterday claimed | unit | Reward day 5 from F1, and `streakCount` stays 10000 | F1 | TEST-02 |
| `ClaimStreakRewardTest` | Replay of one request id | unit | One grant, and the replay returns the first reward day | none | TEST-09 |
| `ClaimStreakRewardTest` | Metric rows | unit | One `streak_claim` row and one `STREAK_CLAIM` item row with the same trace id on success, and one `streak_claim` row on each error | none | TEST-08 |
| `StreakCheatTest` | CheatSetStreak on live | unit | Rejected, no change | ST2, ST3 | TEST-04, TEST-11 |
| `StreakCheatTest` | CheatShiftDay on live | unit | Rejected, no change | ST2 | TEST-04, TEST-11 |
| `StreakCheatTest` | CheatSetStreak with count 10001 | unit | `OUT_OF_RANGE`, no change | none | TEST-03 |
| `StreakCheatTest` | CheatShiftDay by 1 day off live | unit | The acting player's day moves and another player's day does not | ST2 | TEST-02, TEST-11 |
| `StreakAdminTest` | AdminSetStreak on live without `confirm` | unit | `CONFIRM_REQUIRED`, no change | none | TEST-03 |
| `StreakAdminTest` | AdminSetStreak with count -1 | unit | `OUT_OF_RANGE`, no change | none | TEST-03 |
| `StreakAdminTest` | AdminSetStreak without `streakCount`, and again without `lastClaimDay` | unit | `OUT_OF_RANGE` each time, no change | none | TEST-03, ADMIN-06 |
| `StreakAdminTest` | Replay of one AdminSetStreak request id | unit | One change and one audit row | none | TEST-09 |
| `StreakAdminTest` | Offline AdminSetStreak whose CAS fails after it applied | unit | The retry re-reads, one change and one audit row | none | TEST-09, MN-04 |
| `StreakAdminTest` | Offline AdminSetStreak whose CAS fails before it applied | unit | The retry applies it, one change and one audit row | none | TEST-09, MN-04 |
| `StreakAdminTest` | A login on a second node during an offline AdminSetStreak | unit | The login answers retry-later until the edit ends, then loads the repaired state | none | TEST-13, ADMIN-02 |
| `StreakAdminTest` | AdminSetStreak for an online 1.4.0 player | unit | One StreakState push to the target with the stored `streakCount` and `lastClaimDay` | none | TEST-01 |
| `StreakAdminTest` | Push to a 1.3.0 player | unit | No StreakState push | none | TEST-07 |
| `StreakConfigTest` | Valid file | unit | Loads, and the day index has 7 entries | RW1, RW7 | TEST-05 |
| `StreakConfigTest` | A reward for day 8 | unit | Load fails and names the file and the key | F1 | TEST-05 |
| `StreakConfigTest` | Day 3 missing | unit | Load fails and names the file and the key | RW3 | TEST-05 |
| `StreakConfigTest` | Unknown item id | unit | Load fails and names the file and the key | RW1 | TEST-05 |
| `StreakConfigTest` | A day 1 reward with amount 0 | unit | Load fails and names the file and the key | RW1 | TEST-05 |
| `StreakConfigTest` | `unlockLevel` 0 | unit | Load fails and names the file and the key | ST1 | TEST-05 |
| `StreakConfigTest` | Extra key | unit | Load succeeds and ignores a key it does not know | none | TEST-05, BG-08 |
| `StreakStateCompatTest` | No document | compatibility | Defaults apply, and migration runs once | none | TEST-06, BG-09 |
| `StreakStateCompatTest` | Unknown field | compatibility | A save keeps the field | none | TEST-06, BG-02 |

## Design coverage

| Design id | Spec rows | Tests |
| --- | --- | --- |
| SM1 | KPI query SM1, action `streak_claim` extra `rewardDay` | `ClaimStreakRewardTest` metric rows |
| ST1 | ClaimStreakReward check 3, GetStreakState `unlockLevel`, transition from ST1 | `ClaimStreakRewardTest` player below level 5 |
| ST2 | Timed field `lastClaimDay`, transition to ST2 | `GetStreakStateTest` unlocked player on an unclaimed day |
| ST3 | ClaimStreakReward check 4, timed field `lastClaimDay` | `ClaimStreakRewardTest` second claim on the same day with a new request id |
| R1 | ClaimStreakReward effect, timed field `lastClaimDay` | `ClaimStreakRewardTest` claim after a missed day |
| R2 | ClaimStreakReward effect through F1 | `ClaimStreakRewardTest` claim after a day 7 claim |
| F1 | ClaimStreakReward effect, GetStreakState `rewardDay` | `ClaimStreakRewardTest` claim on the day after a claim |
| RW1 | Config `rewards`, ClaimStreakReward effect | `ClaimStreakRewardTest` first claim on a new state |
| RW2 | Config `rewards`, ClaimStreakReward effect | `ClaimStreakRewardTest` claim on the day after a claim |
| RW3 | Config `rewards`, ClaimStreakReward effect | `StreakConfigTest` day 3 missing |
| RW4 | Config `rewards`, ClaimStreakReward effect | `StreakConfigTest` valid file |
| RW5 | Config `rewards`, ClaimStreakReward effect | `StreakConfigTest` valid file |
| RW6 | Config `rewards`, ClaimStreakReward effect | `StreakConfigTest` valid file |
| RW7 | Config `rewards`, ClaimStreakReward effect | `ClaimStreakRewardTest` claim after a day 7 claim |
| TM1 | Server day definition, ClaimStreakReward check 4, transition from ST3 | `ClaimStreakRewardTest` claim at 00:00:01 after a claim at 23:59:59 |
| TM2 | Config `isActive`, check 1 of both commands | `ClaimStreakRewardTest` feature inactive |
| EC1 | ClaimStreakReward check 4 and effect | `ClaimStreakRewardTest` claim at 00:00:01 after a claim at 23:59:59 |
| UI1 | GetStreakState, ClaimStreakReward | `GetStreakStateTest` unlocked player on an unclaimed day |
| UI2 | GetStreakState `unlockLevel`, `lastClaimDay`, and `serverTime`, from which the client derives the dot | `GetStreakStateTest` unlocked player on an unclaimed day |
| Q1 | Header, answered, used by TM1 and EC1 | none |
````
