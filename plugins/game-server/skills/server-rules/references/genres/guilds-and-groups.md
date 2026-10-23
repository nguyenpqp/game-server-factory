# Guilds and groups

Read this note when players belong to a shared group, such as a guild, a clan, an alliance, a party, or a friend list. How to use it is in the [genre notes index](index.md). Rule ids refer to the [rule index](../index.md).

## Questions for the design

- How does a player join: apply and wait for approval, join freely, or by invite? Is there a wait before joining another group after leaving?
- How many members can a group hold, and how does the limit grow?
- Which roles exist, and what may each do: accept, kick, promote, change settings, spend shared resources?
- What does the group own together, such as a treasury, a level, buildings, or shared items? How is it filled, and who may spend it?
- What do donations and group rewards pay, and what does a player who joins or leaves mid-period get?
- Can members ask each other for items, and how often?
- What happens when the leader leaves or stops playing?
- For friends: how many, mutual or one-way, and what can friends send each other?

## Traps

### Server authority and anti-cheat

- A request names a member, a role, or a group that the player has no right over (AUTH-05).
- A kick or a promotion runs on a role that changed a moment before, such as a leader who was just replaced (AUTH-06).
- The donor pays, and the write to the group fails. Write the shared side first and take the cost last, and do not refund an unknown result (AUTH-07, MN-13).
- A retried donation or a retried accept applies twice (AUTH-08).
- A player floods join requests, invites, or item requests to many players (AUTH-09).

### Config

- The member limit, the level table, donation limits, and wait times are in code (CFG-05). Each level and each reward is a row with an id, and each reward is one `{id, amount}` record (CFG-09, CFG-10).

### Modularity

- Other features read membership or roles by importing the guild package. They call the guild contract (MOD-01).
- A group reward that pays members rides a droppable event. It goes to each member's durable inbox (MOD-02, MN-03).

### Multi-node and rollout

- Members on different nodes write the group document by a plain load and save, so one change overwrites another (MN-04).
- A player joins two groups at once on two nodes, or a group passes its member limit. The join is one atomic step on shared state that rechecks the limit and the player's current group (MN-05, MN-13).
- The player's own record of the group and the group's member list are written apart, so a crash leaves them disagreeing. One is the source of truth, and the other is repaired from it (MN-12, MN-13).
- A kicked member keeps acting through a node's cached membership (MN-09).
- A message to members goes through a node-local session map, so members on other nodes miss it (MN-10).
- A group id comes from an in-process counter (MN-08).
- A weekly group reward pays from a member list that still changes, or runs twice on two nodes (MN-07).
- A member list, a request list, or a log grows without a cap (PERF-06). A message or a reward to every member runs inside one command (PERF-07).

### Tests and metrics

- Concurrent joins, kicks, and donations from two nodes have a test with two instances over one store (TEST-13).
- Each donation and each group reward is logged with its reason and the trace id (MET-03, MET-04).
