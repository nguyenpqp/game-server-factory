# Decisions template

The file `docs/game-server/decisions.md` in the target game server repository records the Core blockers risks that the developer accepts for every feature. `feature-spec` applies them when it writes Core blockers, and `feature-build` rechecks them at gate 3. Rule ids refer to the [rule index](../../server-rules/references/index.md). Capability ids and statuses refer to the [profile template](../../server-profile/references/profile-template.md).

## Who writes it

Only the developer adds or changes a decision. `feature-spec` adds a row when the developer accepts a Core blockers row for every feature, and the developer may edit the file by hand. `server-profile` never writes it.

A decision holds an acceptance only. A descope drops design ids of one feature, so it stays in that feature's spec.

## Format

The file has a title and one table with these columns, in this order.

```markdown
# Project decisions

| Id | Capability | Profile status | Rules | Deployment fact | How it bounds the failure | Accepted by | Date |
| --- | --- | --- | --- | --- | --- | --- | --- |
| D1 | CAP-OWNERSHIP | missing | MN-02 | One game process per realm, and a deploy stops the old process before the new one starts | No second node can load the player, so no stale copy can save over a change | <name> | 2026-10-22 |
```

| Column | Value |
| --- | --- |
| `Id` | `D` and a number, unique in the file. A removed row's id is never reused. |
| `Capability` | One capability id, such as `CAP-OWNERSHIP`. |
| `Profile status` | `partial` or `missing`, the capability's status in the profile when the developer accepted the risk. |
| `Rules` | The accepted rule ids, separated by commas. The `needs:` line of each rule in the rule index names the capability. Never PERF-01, because whether a blocking call harms other players depends on the call site, so each spec accepts it per call site. |
| `Deployment fact` | A fact about how the project runs, such as the number of nodes per realm or how a deploy stops a node. |
| `How it bounds the failure` | How the fact prevents or bounds the failure of each listed rule. A critical rule needs this link, as `feature-spec` requires for any accepted critical rule. |
| `Accepted by` | The developer's name. |
| `Date` | The date of the acceptance, as `YYYY-MM-DD`. |

## When a decision applies

A decision resolves a Core blockers row only when every item holds.

1. It names the row's capability.
2. Its `Profile status` equals the capability's status in the current profile.
3. Its `Rules` include every rule in the row's `Rules blocked` cell.
4. Its bound covers the failure in the row's `What fails for players` cell.

The row's resolution is then `accepted by <name> (D<n>): <deployment fact>, so <bound>`, with the name, fact, and bound copied from the decision. A row that no decision covers in full stays `open`.

## Stale decisions

A decision whose `Profile status` differs from the profile is stale, and it resolves nothing. This happens after a core change and a new profile. The developer re-decides it: they update the status and the fact, or remove the row. A decision whose capability is now `present` is no longer needed, and the developer can remove it.
