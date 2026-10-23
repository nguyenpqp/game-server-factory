# PvP and matchmaking

Read this note when players fight or compete against each other, live or against a stored defense, and the server picks opponents, such as an arena, a duel, a raid on another player's base, or a ranked queue. How to use it is in the [genre notes index](index.md). Rule ids refer to the [rule index](../index.md).

## Questions for the design

- Is a fight live between two players, or against a stored defense of a player who may be offline?
- How are opponents picked: by rating, level, bracket, or at random? What happens when no opponent fits after a wait?
- How does a result change the rating? Is there a floor, a decay, or a placement period?
- What does a fight cost, such as tickets or energy, and is it returned on a draw, an abandon, or a disconnect?
- What does the winner gain and the loser lose, and can a defender lose resources while offline?
- Is a defender protected after a defeat, and for how long?
- How many fights per day, and are there revenge fights?
- Do repeated fights between the same two players pay full rewards and rating?
- What does the player see of a past fight: a result, a log, or a replay?

## Traps

### Server authority and anti-cheat

- The client reports the winner, the damage, or the rewards. The server decides the result from inputs it checks, or simulates the fight itself (AUTH-01). A fight that runs only on the client gives a result the server cannot trust, and the spec lists that on its Accepted risks line.
- The server simulates with a random source of its own instead of the injected RNG, so a fight cannot be replayed or tested (AUTH-03).
- The request names an opponent that the server did not offer or store for this player, such as a revenge target, or a result names a fight the player was not in (AUTH-05).
- A result is sent twice, or for a fight that already ended or timed out (AUTH-06, AUTH-08).
- One player holds two queue entries and is matched against themselves (AUTH-06, MN-05).
- The fight's start, duration, or timeout comes from client time (AUTH-02).
- The ticket is taken, and the fight fails to start, so the player pays for nothing (AUTH-07).
- Two players, or one player with an alt account, trade wins to farm rewards or rating, and nothing can find them. Each fight row names both players, so a query finds repeated pairs (MET-07). A cap on repeated pairs that the design sets comes from config (CFG-05).

### Config

- Rating constants, brackets, costs, rewards, and protection times are in code (CFG-05). Each bracket and each reward is a row with an id, and each reward is one `{id, amount}` record (CFG-09, CFG-10).

### Modularity

- The fight reads another feature's data, such as hero stats, by importing that feature. It reads through the feature's contract (MOD-01).
- A win that feeds a ranking or a pass rides a droppable event (MOD-02).

### Multi-node and rollout

- The attacker's command changes the defender's rating or resources directly, while the defender's owner runs on another node. The defender's losses go through the durable inbox (MN-02, MN-03).
- The loot comes from the attacker's copy of the defender's state, so the attacker gains what the defender already spent. The attacker gains only what the defender's owner removed, sent back through the attacker's inbox (MN-02, MN-03).
- Two attackers hit the same defender at once, and both pass the protection. The hit is one atomic claim on shared state, and an unknown result grants nothing (MN-05, MN-13).
- Two nodes write the state of one live fight (MN-04, MN-05).
- The timeout on one node settles a fight while the result command settles it on another (MN-07, MN-14).
- The matchmaking queue lives in one node's memory (MN-01). A shared queue pops in atomic steps (MN-05).
- Every queued player writes one queue key (PERF-08).
- A dead node leaves queue entries for players who are gone (MN-10).
- A fight id comes from an in-process counter (MN-08).
- An abandoned fight ends on a timer in memory. Expiry comes from the stored start time when the state is read (MN-11).
- A reply sends a whole replay (PERF-04).
- Fight logs or replays in a player's state grow without a cap (PERF-06).
- An old client and a new client are matched under different fight rules (BG-07).

### Tests and metrics

- Each fight outcome has a test with a fixed RNG, and the same inputs give the same result (TEST-02).
- Two attackers on one defender have a test with two instances over one store (TEST-13).
- Each fight writes one action row with its result, and each gain and loss is logged with its reason (MET-01, MET-04).
