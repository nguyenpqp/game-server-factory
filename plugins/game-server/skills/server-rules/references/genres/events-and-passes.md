# Events and passes

Read this note when players make progress inside a time window, such as a limited event, missions, point milestones, a battle pass with free and paid tracks, or a login calendar. How to use it is in the [genre notes index](index.md). Rule ids refer to the [rule index](../index.md).

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

- The client reports progress or a mission as done. Progress comes from actions the server ran (AUTH-01).
- One action counts twice, because the command that caused it grants nothing itself and so has no request id (AUTH-08).
- A milestone claim trusts the client's count, or skips the check that the milestone is reached and not yet claimed (AUTH-06).
- A retried claim pays twice (AUTH-08).
- The window or a reset is checked with the client's time, the JVM clock, or the JVM's zone, or a player who changes zone passes the same reset twice (AUTH-02, CFG-04).

### Config

- The window, the missions, the milestones, and the rewards are in code (CFG-04, CFG-05). Each mission and milestone is a row with an id (CFG-06, CFG-10).
- Milestones out of order, a reward with an unknown item id, or a window that ends before it starts passes the load (CFG-02).

### Modularity

- The event imports the features whose actions count, such as battles or the shop (MOD-01).
- Progress that pays a reward travels on a best-effort message, which can drop it. Send it through the event's contract (MOD-02).

### Multi-node and rollout

- A claim mark and the reward it pays are saved apart (MN-12).
- A repeat of the event reuses the progress and claims of the last one. Progress and claims carry the id of the event's occurrence (MN-14).
- Progress lands after the end, or on the next occurrence. The write rechecks the window and the occurrence (AUTH-06, MN-05, MN-14).
- A reset or an end runs on a timer in memory. Ready and expired come from stored times when the state is read (MN-11).
- The server pushes the start or the end to every client at once, or a reward depends on that push arriving (PERF-07, SYNC-04).
- Two nodes mail the unclaimed rewards at the end at once. The job stays correct when it runs twice, delivers through the inbox, and runs in batches (MN-03, MN-07, PERF-07).
- The end-of-event mail sends a reward that the player claims at the same moment, so it pays twice. The mail goes through the inbox, and the owner applies it against the claim mark (MN-02, MN-03).
- A pass bought with real money is granted by the payment callback directly, or twice. It checks the product and the price, locks on the transaction id, and goes through the inbox (HTTP-04, HTTP-05, HTTP-06).
- A new event type reaches an old client, or changes the meaning of an old config key (BG-07, BG-08).

### Tests and metrics

- Each window edge, each daily reset, and each late join has a test with injected time (TEST-02).
- Each mission and milestone step is a funnel step with its own action (MET-05).
