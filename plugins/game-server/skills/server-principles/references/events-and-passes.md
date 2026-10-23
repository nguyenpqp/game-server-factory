# Events and passes

Read this note when players make progress inside a time window, such as a limited event, missions, point milestones, a battle pass with free and paid tracks, or a login calendar.

## Questions for the design

- When does the event start and end, and in which time zone? Is the window the same for every player, or does it start when a player unlocks it?
- Which actions count as progress, and does an action from before the start count?
- Do missions reset daily or weekly, at what time, in which time zone, and what happens to a missed day?
- After the end, can a player still claim earned rewards, and for how long? Are unclaimed rewards sent by mail?
- For a pass: does a player who buys it late get the paid rewards of levels already passed? Can levels be bought?
- When the event repeats, does progress carry over, or start again?
- What happens to a player who joins late, or who reaches the unlock during the event?

## Traps

### Server authority and anti-cheat

- The client reports progress or a mission as done. Progress comes from actions the server ran.
- One action counts twice, because the command that caused it grants nothing itself and so has no request id.
- A milestone claim trusts the client's count, or skips the check that the milestone is reached and not yet claimed.
- A retried claim pays twice.
- The window or a reset is checked with the client's time, the JVM clock, or the JVM's zone, or a player who changes zone passes the same reset twice.

### Config

- The window, the missions, the milestones, and the rewards are in code. Each mission and milestone is a row with an id.
- Milestones out of order, a reward with an unknown item id, or a window that ends before it starts passes the load.

### Modularity

- The event imports the features whose actions count, such as battles or the shop.
- Progress that pays a reward travels on a best-effort message, which can drop it. Send it through the event's contract.

### Multi-node and rollout

- A claim mark and the reward it pays are saved apart.
- A repeat of the event reuses the progress and claims of the last one. Progress and claims carry the id of the event's occurrence.
- Progress lands after the end, or on the next occurrence. The write rechecks the window and the occurrence.
- A reset or an end runs on a timer in memory. Ready and expired come from stored times when the state is read.
- The server pushes the start or the end to every client at once, or a reward depends on that push arriving.
- Two nodes mail the unclaimed rewards at the end at once. The job stays correct when it runs twice, delivers through the inbox, and runs in batches.
- The end-of-event mail sends a reward that the player claims at the same moment, so it pays twice. The mail goes through the inbox, and the owner applies it against the claim mark.
- A pass bought with real money is granted by the payment callback directly, or twice. It checks the product and the price, locks on the transaction id, and goes through the inbox.
- A new event type reaches an old client, or changes the meaning of an old config key.

### Tests and metrics

- Each window edge, each daily reset, and each late join has a test with injected time.
- Each mission and milestone step is a funnel step with its own action.
