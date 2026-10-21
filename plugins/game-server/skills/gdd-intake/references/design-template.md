# Design template

`gdd-intake` writes one `design.md` per feature in this format. `feature-spec` reads it as its description of the feature and writes the [spec](../../feature-spec/references/spec-template.md) from it. The file records what the player sees, does, and gets, with a source for every requirement.

The default path in the target repository is `docs/game-server/features/<feature>/design.md`, where `<feature>` is the feature name in kebab case. Draft config JSON built from the GDD's balance sheets goes in `docs/game-server/features/<feature>/config/`.

## What the design leaves out

The design holds no server design. It names no command ids, request or response fields, classes, storage keys, Redis structures, threads, metric tables, cheat commands, or admin commands. `feature-spec` decides those from this file and the project profile.

When the GDD itself prescribes a server mechanism, such as "store the streak in Redis", the design records it as an open question that cites the source. `feature-spec` then weighs it against the rules.

## Filling rules

- Keep every `##` heading of the skeleton, in its order. Write `None.` under a section that has no content. Never delete a heading.
- Give every requirement an id from [Requirement ids](#requirement-ids). Ids number from 1 for each prefix, and a deleted id is never reused. `feature-spec` cites these ids, and the coverage report maps each one to code or tests.
- End every requirement with a `Source:` line in a format from [Source citations](#source-citations). A requirement with no source is an assumption, so it goes under Open questions with its interim default.
- Write every number with its unit, such as `24 h`, `3 per day`, or `500 gold`. A number that design may tune names its config key from Config tables.
- Write TBD, TODO, and FIXME only under Open questions.
- Write in English. Keep in-game names as the GDD spells them, and give each one a Glossary entry.

## Requirement ids

| Prefix | Kind | Section |
| --- | --- | --- |
| `SM<n>` | success measure | Overview |
| `ST<n>` | player state | States |
| `R<n>` | rule | Rules |
| `F<n>` | formula | Formulas |
| `RW<n>` | reward | Rewards |
| `TM<n>` | timing | Timing |
| `EC<n>` | edge case | Edge cases |
| `UI<n>` | UI touchpoint | UI touchpoints |
| `Q<n>` | open question | Open questions |

## Source citations

Each input gets an id in the Sources table, such as `S1`. A citation names the id and the place inside that input.

| Input | Format | Example |
| --- | --- | --- |
| Slide deck | `S<n> slide <k>` | `S1 slide 4` |
| Document, PDF, or Markdown | `S<n> § <heading>` | `S2 § Rewards` |
| Spreadsheet | `S<n> <sheet>!<range>` | `S3 Rewards!A2:D8` |
| Image | `S<n>` | `S4` |
| Feature prompt | `prompt` | `prompt` |
| Answer from the designer or developer | `answer Q<n>` | `answer Q2` |

When two sources disagree, the requirement cites the one the designer confirmed. Until then, an open question cites both.

## Skeleton

The skeleton uses a daily login streak as its example. Replace every example row.

````markdown
# <Feature name> design

## Sources

| Id | Input | Kind | Notes |
| --- | --- | --- | --- |
| S1 | `gdd/login-streak.pptx` | slide deck | 12 slides |
| S2 | `gdd/login-streak-balance.xlsx` | spreadsheet | sheets Rewards, Settings |

Scope: <server-only, full-stack, or logic-only>

## Overview

<One or two paragraphs. What the player does, why the feature exists, and which players get it, such as an unlock level or a player segment.>

### Success measures

- SM1: The share of daily active players who claim the day 7 reward at least once a week. Source: S1 slide 2.

## Gameplay loop

1. The player opens the game on a new day.
2. The streak panel shows today's reward as ready.
3. The player claims it, and the streak count goes up by 1.

## Parts

- **Streak counter**. Counts the days in a row on which the player claimed. Rules: R1, R2.
- **Reward track**. Seven daily rewards that repeat after day 7. Rewards: RW1 to RW7.

## Worked example

A player at level 6 claims on Monday and Tuesday. On Tuesday the streak shows day 2 and grants the day 2 reward. The player skips Wednesday. On Thursday the streak restarts at day 1, and the panel shows the day 1 reward as ready.

## Other features

- Inventory: rewards add gold and items to the player's storage. Source: S1 slide 7.
- Quests: a claim counts toward the quest "Log in 5 days". Source: S1 slide 9.

## States

| Id | State | What the player sees | Enters when | Leaves when | Source |
| --- | --- | --- | --- | --- | --- |
| ST1 | Locked | No streak icon in the lobby | The player is below level 5 | The player reaches level 5 | S1 slide 3 |
| ST2 | Ready | A red dot on the streak icon | A new day starts and today is unclaimed | The player claims | S1 slide 5 |
| ST3 | Claimed | Today's reward shows a check mark | The player claims | The next day starts | S1 slide 5 |

## Rules

### R1: Streak breaks after a missed day

- Description: A day with no claim resets the streak.
- Condition: The last claim was before yesterday.
- Effect: The next claim counts as day 1.
- Edge cases: None.
- Example: Claims on day 1 and day 2, none on day 3. The claim on day 4 grants the day 1 reward.
- Source: S1 slide 5.

## Formulas

### F1: Reward day

```text
input:  streakCount (claims in a row, before this claim)
output: rewardDay
formula:
  rewardDay = (streakCount mod 7) + 1
```

- Edge cases: None.
- Example: streakCount 9 gives rewardDay 3.
- Source: S2 Settings!B4.

## Rewards

| Id | Reward | Contents | Granted when | Limit | Source |
| --- | --- | --- | --- | --- | --- |
| RW1 | Day 1 reward | 500 gold | The player claims on reward day 1 | Once per day | S2 Rewards!A2:D2 |
| RW7 | Day 7 reward | 1 rare chest | The player claims on reward day 7 | Once per day | S2 Rewards!A8:D8 |

## Timing

| Id | Timing | Value | Measured in | Source |
| --- | --- | --- | --- | --- |
| TM1 | Day boundary | 00:00 | Server timezone | S1 slide 5 |
| TM2 | Feature window | Always on | Server time | S1 slide 2 |

## Edge cases

### EC1: Claim across the day boundary

- Scenario: The player opens the panel at 23:59 and taps claim at 00:01.
- Handling: The claim counts for the new day.
- Related: R1, TM1.
- Source: answer Q1.

## Config tables

### `login-streak.json`

- Source sheets: S2 Rewards, S2 Settings.
- Draft: `config/login-streak.json`, relative to this file.
- Shape: an object with `unlockLevel` and a `rewards` list.

| Key | Meaning | Type | Example | Allowed values | Source |
| --- | --- | --- | --- | --- | --- |
| `unlockLevel` | Level at which the streak unlocks | integer | 5 | 1 or more | S2 Settings!B2 |
| `rewards[].day` | Reward day of this entry | integer | 1 | 1 to 7, each once | S2 Rewards!A2:A8 |
| `rewards[].items` | Items the entry grants | list of item and amount | 500 gold | known item ids, amount 1 or more | S2 Rewards!B2:D8 |

- Cross-row checks: the `rewards` list has exactly one entry per day from 1 to 7.

## UI touchpoints

| Id | Screen or moment | The player sees | The player can do | Changes without player action | Source |
| --- | --- | --- | --- | --- | --- |
| UI1 | Streak panel | Current day, the seven rewards, time until the next day | Claim today's reward | The countdown reaches zero and the next reward becomes ready | S1 slide 6 |
| UI2 | Lobby icon | A red dot while a claim is ready | Open the streak panel | The dot appears at the day boundary | S1 slide 6 |

## Glossary

### Streak

- Definition: The number of days in a row on which the player claimed.
- Aliases: login chain.
- Notes: None.

## Open questions

### Blocker

#### Q1: Which day does a claim at 00:01 count for?

- Source: S1 slide 5 shows a local midnight reset, and S2 Settings!B3 names the server timezone.
- Status: open
- Interim default: The server day.
- Affects: R1, TM1, EC1.

### Important

None.

### Minor

None.

### Undefined terms

- `bonus day`: appears in S1 slide 8 with no definition.
````

## Section guide

| Section | Holds |
| --- | --- |
| Sources | Every input, with its id, path, and kind, and the scope that the developer chose. |
| Overview | The player-facing purpose and audience, and the success measures that the design team uses to judge the feature. |
| Gameplay loop | The main flow from start to reward, as numbered steps. |
| Parts | The parts of the feature, each linked to its rules and rewards. |
| Worked example | One player's path through the feature with real numbers. |
| Other features | What passes between this feature and other features, as the player sees it, such as currencies, items, quest progress, or unlocks. |
| States | Every state the player can be in for this feature, and what moves the player in and out of it. |
| Rules | Each rule with its condition, effect, edge cases, example, and source. |
| Formulas | Each calculation, with inputs, output, an example with numbers, and a source. |
| Rewards | Every reward, with its contents, trigger, and limit. |
| Timing | Day boundaries, windows, cooldowns, durations, and the clock each one uses. |
| Edge cases | Cases that cross several rules, such as a claim at the day boundary or a level-up mid-action. |
| Config tables | The balance data from the GDD, per config file, with each key's meaning, type, example, and allowed values. |
| UI touchpoints | Each screen, badge, popup, or notice that shows feature data, what the player can do there, and what changes while the player watches. |
| Glossary | Domain terms only. Config keys, expressions, and literal values get no entry. |
| Open questions | Unanswered questions in three tiers. Blocker questions stop `feature-spec`. Important questions need an answer before release. Minor questions can wait. Each question cites its source and gives an interim default. |

An open question's status is `open`, `skipped by <name> on <date>`, or `answered on <date>: <answer>`. An answered question keeps its id, and the requirements it settles cite `answer Q<n>` as their source.

A workflow that runs its own interview uses Open questions as its list of gaps.
