# Weekly challenge design

## Sources

| Id | Input | Kind | Notes |
| --- | --- | --- | --- |
| S1 | `gdd/weekly-challenge.pptx` | slide deck | 8 slides |
| S2 | `gdd/weekly-balance.xlsx` | spreadsheet | sheets Tiers, Settings |

Scope: server-only

## Overview

Players earn points from daily tasks and collect tier rewards during a weekly window. The feature gives mid-level players a reason to return every day of the week.

### Success measures

- SM1: The share of daily active players who reach tier 2 in a week. Source: S1 slide 2.

## Gameplay loop

1. The player completes tasks during the week.
2. Each task adds points to the weekly total.
3. The player claims every tier reward whose point threshold the total has reached.

## Parts

- **Point counter**. Sums the points a player earned this week. Rules: R1.
- **Tier track**. Three rewards that unlock at rising point totals. Rewards: RW1, RW2.

## Worked example

A level 9 player earns 60 points on Monday and 50 points on Tuesday. The total is 110 points. Tier 1 needs 100 points, so the player claims 500 gold. Tier 2 needs 250 points, so it stays locked.

## Other features

- Inventory: tier rewards add gold and items to the player's storage. Source: S1 slide 6.

## States

| Id | State | What the player sees | Enters when | Leaves when | Source |
| --- | --- | --- | --- | --- | --- |
| ST1 | Locked | No challenge icon in the lobby | The player is below level 8 | The player reaches level 8 | S1 slide 3 |
| ST2 | Active | The challenge icon with a point bar | The weekly window is open and the player is level 8 or more | The window closes | S1 slide 3 |

## Rules

### R1: Points reset each week

- Description: The weekly total goes back to 0 when a new window opens.
- Condition: A new weekly window starts.
- Effect: The total becomes 0 and every tier becomes unclaimed.
- Edge cases: None.
- Example: A player with 300 points and an unclaimed tier 2 loses both when the window rolls over.
- Source: S1 slide 4.

## Formulas

### F1: Claimable tiers

```text
input:  totalPoints, tierThreshold[tier]
output: claimableTiers
formula:
  claimableTiers = tiers where tierThreshold[tier] <= totalPoints and tier is unclaimed
```

- Edge cases: None.
- Example: totalPoints 110 with thresholds 100 and 250 gives tier 1.
- Source: S2 Tiers!A2:A4.

## Rewards

| Id | Reward | Contents | Granted when | Limit | Source |
| --- | --- | --- | --- | --- | --- |
| RW1 | Tier 1 reward | 500 gold | The total reaches 100 points and the player claims | Once per week | S2 Tiers!A2:C2 |
| RW2 | Tier 2 reward | 1 rare chest | The total reaches 250 points and the player claims | Once per week | S2 Tiers!A3:C3 |

## Timing

| Id | Timing | Value | Measured in | Source |
| --- | --- | --- | --- | --- |
| TM1 | Window start | Monday 00:00 | Server timezone | S1 slide 4 |
| TM2 | Window length | 7 days | Server time | S2 Settings!B4 |

## Edge cases

### EC1: Claim after the window closes

- Scenario: The player taps claim at the moment the window closes.
- Handling: The claim counts if the server received it before the boundary.
- Related: R1, TM1.
- Source: answer Q2.

## Config tables

### `weekly-challenge.json`

- Source sheets: S2 Tiers, S2 Settings.
- Draft: `config/weekly-challenge.json`, relative to this file.
- Shape: an object with `unlockLevel`, `limits`, and a `tiers` list.

| Key | Meaning | Type | Example | Allowed values | Source |
| --- | --- | --- | --- | --- | --- |
| `unlockLevel` | Level at which the challenge unlocks | integer | 8 | 1 or more | S2 Settings!B2 |
| `limits.claimsPerWeek` | Claims allowed per tier | integer | 1 | 1 or more | S1 slide 5 |
| `tiers[].points` | Points the tier needs | integer | 100 | 1 or more, rising | S2 Tiers!A2:A4 |
| `tiers[].reward` | Reward item id | string | gold | known item ids | S2 Tiers!B2:B4 |
| `tiers[].premium` | Whether the tier needs the premium pass | boolean | false | true or false | S2 Tiers!C2:C4 |

- Cross-row checks: `tiers[].points` rises with each entry.

## UI touchpoints

| Id | Screen or moment | The player sees | The player can do | Changes without player action | Source |
| --- | --- | --- | --- | --- | --- |
| UI1 | Challenge panel | Point bar and three tier rewards | Claim a ready tier | The bar fills when a task completes elsewhere | S1 slide 6 |

## Glossary

### Tier

- Definition: One reward step on the weekly track, unlocked by a point total.
- Aliases: milestone.
- Notes: None.

## Open questions

### Blocker

#### Q1: Does the window follow server time or player time?

- Source: S1 slide 4 says local Monday, and S2 Settings!B3 names the server timezone.
- Status: open
- Interim default: Server time.
- Affects: R1, TM1.

### Important

#### Q2: What happens to a claim sent at the boundary?

- Source: S1 slide 4.
- Status: answered on 2026-03-02: The claim counts if the server received it before the boundary.
- Interim default: Reject the claim.
- Affects: EC1.

### Minor

#### Q3: Should the panel show the next window's start?

- Source: S1 slide 6.
- Status: skipped by Dana on 2026-03-02
- Interim default: Hide it.
- Affects: UI1.

### Undefined terms

None.
