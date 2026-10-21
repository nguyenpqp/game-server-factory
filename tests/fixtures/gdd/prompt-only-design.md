# Daily gift design

## Sources

None.

Scope: logic-only

## Overview

Each player gets one free gift per day from the lobby. The gift gives new players a daily reason to open the game.

### Success measures

- SM1: The share of daily active players who claim the gift. Source: prompt.

## Gameplay loop

1. The player opens the lobby on a new day.
2. The player taps the gift.
3. The gift adds 100 gold to the player's storage.

## Parts

- **Gift**. One claim per player per day. Rules: R1. Rewards: RW1.

## Worked example

A player claims the gift on Monday at 09:00 and receives 100 gold. The player taps the gift again at 09:05 and nothing happens.

## Other features

None.

## States

None.

## Rules

### R1: One claim per day

- Description: A player can claim the gift once per calendar day.
- Condition: The player has not claimed since the last day boundary.
- Effect: The gift grants its reward and marks today as claimed.
- Edge cases: None.
- Example: A second tap on the same day grants nothing.
- Source: prompt.

## Formulas

None.

## Rewards

| Id | Reward | Contents | Granted when | Limit | Source |
| --- | --- | --- | --- | --- | --- |
| RW1 | Daily gift | 100 gold | The player claims | Once per day | prompt |

## Timing

| Id | Timing | Value | Measured in | Source |
| --- | --- | --- | --- | --- |
| TM1 | Day boundary | 00:00 | Server timezone | prompt |

## Edge cases

None.

## Config tables

None.

## UI touchpoints

None.

## Glossary

None.

## Open questions

### Blocker

None.

### Important

#### Q1: Which timezone defines the day boundary?

- Source: prompt.
- Status: open
- Interim default: The server timezone.
- Affects: R1, TM1.

### Minor

None.

### Undefined terms

None.
