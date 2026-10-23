# Guilds and groups

Read this note when players belong to a shared group, such as a guild, a clan, an alliance, a party, or a friend list.

## Questions for the design

- How does a player join: apply and wait for approval, join freely, or by invite? Is there a wait before joining another group after leaving?
- How many members can a group hold, and how does the limit grow?
- Which roles exist, and what may each do: accept, kick, promote, change settings, spend shared resources?
- What does the group own together, such as a treasury, a level, buildings, or shared items? How is it filled, and who may spend it?
- What do donations and group rewards pay, and what does a player who joins or leaves mid-period get?
- Can members ask each other for items, and how often?
- What happens when the leader leaves or stops playing, and when a group disbands?
- For friends: how many, mutual or one-way, and what can friends send each other?

## Traps

### Server authority and anti-cheat

- A request names a member, a role, or a group that the player has no right over.
- A kick or a promotion runs on a role that changed a moment before, such as a leader who was just replaced. The shared write rechecks the role.
- A donation amount is negative, or large enough to wrap the treasury.
- The donor pays, and the write to the group fails, or the group is credited and the node crashes before the donor pays. Take the cost and record the pending donation in one save, credit the group idempotently by the request id, and retry an unknown result. Refund only when the group definitely refused it.
- A retried donation or a retried accept applies twice.
- A player leaves and rejoins to collect join rewards again, because the wait after leaving is not stored.
- A player floods join requests, invites, or item requests to many players.

### Config

- The member limit, the level table, donation limits, and wait times are in code. Each level and each reward is a row with an id.

### Modularity

- Other features read membership or roles by importing the guild package. They call the guild contract.
- A group reward that pays members rides a droppable event. It goes to each member's durable inbox.

### Multi-node and rollout

- Members on different nodes write the group document by a plain load and save, so one change overwrites another.
- Two officers on two nodes spend the treasury at once, and both spends pass.
- A player joins two groups at once on two nodes, or a group passes its member limit. The shared write rechecks the limit and the player's current group. On Redis Cluster, the keys one script touches share a hash tag.
- An accept or a kick writes the other player's record of the group directly. The shared write goes first, and the player's record follows through that player's inbox.
- A crash between the shared write and the inbox delivery leaves the player's record and the member list disagreeing, and actions trust the stale side. Actions read membership from the group, and the player's record is repaired from it, by the owner at load or by the feature's admin repair.
- Several members fill one item request at once, and each pays. Claim the request, deliver through the inbox, then take the cost.
- A kicked member keeps acting through a node's cached membership.
- A message to members goes through a node-local session map, so members on other nodes miss it.
- A group id comes from an in-process counter.
- A disband deletes the group's keys, so a late write creates the group again. It stores a closed marker.
- A periodic group reward pays from a member list that still changes, or runs twice on two nodes.
- A player who switches groups between two payouts is paid by both. Each payout is claimed per player and period, not per group.
- A member list, a request list, or a log in the group document grows without a cap, or is sent to the client whole. A message or a reward to every member runs inside one command.
- The group document gains fields while the old server version still writes it, and the old version drops them.

### Tests and metrics

- Concurrent joins, kicks, and donations from two nodes have a test with two instances over one store.
- Each donation and each group reward is logged with its reason and the trace id.
