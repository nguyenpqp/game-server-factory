# Decisions template

The file `docs/game-server/decisions.md` in the target game server repository records the Core blockers risks that the developer accepts for every feature. `feature-spec` applies them when it writes Core blockers, and `feature-build` rechecks them at gate 3. Rule ids refer to the [rule index](../../server-rules/references/index.md). Capability ids and statuses refer to the [profile template](../../server-profile/references/profile-template.md).

## Who writes it

Only the developer adds or changes a decision. `feature-spec` adds a row when the developer accepts a Core blockers row for every feature, and the developer may edit the file by hand. `server-profile` never writes it.

A decision holds an acceptance only. A descope drops design ids of one feature, so it stays in that feature's spec.

## Format

The file has a title and one table with these columns, in this order. The separator row follows the header row. Keep every decision in that one table, with no blank line between rows, because a blank line ends a Markdown table and the rows after it are no longer part of it.

```markdown
# Project decisions

| Id | Capability | Profile status | Rules | Deployment fact | How it bounds the failure | Accepted by | Date |
| --- | --- | --- | --- | --- | --- | --- | --- |
| D1 | CAP-OWNERSHIP | missing | MN-02 | One game process per realm, and a deploy stops the old process before the new one starts | No second node can load the player, so no stale copy can save over a change | <name> | 2026-10-22 |
```

| Column | Value |
| --- | --- |
| `Id` | `D` and a number with no leading zero, unique in the file. A removed row's id is never reused. |
| `Capability` | One capability id, such as `CAP-OWNERSHIP`. |
| `Profile status` | `partial` or `missing`, the capability's status in the profile when the developer accepted the risk. |
| `Rules` | The accepted rule ids, separated by commas. Each one is a rule that the capability blocks in the profile. A `missing` capability blocks every rule whose `needs:` line in the rule index names it. A `partial` capability blocks the rules on its `blocker` line. Never PERF-01, because whether a blocking call harms other players depends on the call site, so each spec accepts it per call site. |
| `Deployment fact` | A fact about how the project runs, such as the number of nodes per realm or how a deploy stops a node. |
| `How it bounds the failure` | How the fact prevents or bounds the failure of each listed rule. A critical rule needs this link, as `feature-spec` requires for any accepted critical rule. |
| `Accepted by` | The developer's name. |
| `Date` | The date of the acceptance, as `YYYY-MM-DD`. |

## When a decision applies

Read the file against the format above and the current profile before you use a decision. When the title or the header row does not match the format, no decision in the file resolves anything, so ask the developer to fix the file. A decision resolves a Core blockers row only when every item holds.

1. The decision follows the format. Its id is unique, its capability and rule ids exist, its status is `partial` or `missing`, and PERF-01 is not among its rules.
2. It names the row's capability.
3. Its `Profile status` equals the capability's status in the current profile.
4. Its `Rules` include every rule in the row's `Rules blocked` cell.
5. Its bound covers the failure in the row's `What fails for players` cell.

The row's resolution is then `accepted by <name> (D<n>): <deployment fact>, so <bound>`, with the name, fact, and bound copied from the decision. A row that no decision covers in full stays `open`.

## Stale decisions

A decision is stale, and resolves nothing, when its `Profile status` differs from the profile or when the profile no longer blocks one of its rules. This happens after a core change and a new profile. Tell the developer which decision is stale and why. The developer re-decides it. They update the status, the rules, and the fact, or remove the row. A decision whose capability is now `present` is no longer needed, and the developer can remove it.

A gap can change while the status and the blocked rules stay the same. After a core change, read each decision's fact and bound against the new profile entry, and tell the developer about one that no longer fits.
