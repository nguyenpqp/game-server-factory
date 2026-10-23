# PvP and matchmaking

Read this note when players fight or compete against each other, live or against a stored defense, and the server picks opponents, such as an arena, a duel, a raid on another player's base, or a ranked queue.

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

- The client reports the winner, the damage, or the rewards. The server decides the result from inputs it checks, or simulates the fight itself. A fight that runs only on the client gives a result the server cannot trust, so say that risk out loud before building it.
- The server simulates with a random source of its own instead of the injected RNG, so a fight cannot be replayed or tested.
- The request names an opponent that the server did not offer or store for this player, such as a revenge target, or a result names a fight the player was not in.
- A result is sent twice, or for a fight that already ended or timed out.
- One player holds two queue entries and is matched against themselves.
- The fight's start, duration, or timeout comes from client time.
- The ticket is taken, and the fight fails to start, so the player pays for nothing.
- Two players, or one player with an alt account, trade wins to farm rewards or rating, and nothing can find them. Each fight row names both players, so a query finds repeated pairs. A cap on repeated pairs that the design sets comes from config.

### Config

- Rating constants, brackets, costs, rewards, and protection times are in code. Each bracket and each reward is a row with an id, and each reward is one record in the shared cost-and-reward shape.

### Modularity

- The fight reads another feature's data, such as hero stats, by importing that feature. It reads through the feature's contract.
- A win that feeds a ranking or a pass rides a droppable event.

### Multi-node and rollout

- The attacker's command changes the defender's rating or resources directly, while the defender's owner runs on another node. The defender's losses go through the durable inbox.
- The loot comes from the attacker's copy of the defender's state, so the attacker gains what the defender already spent. The attacker gains only what the defender's owner removed, sent back through the attacker's inbox.
- Two attackers hit the same defender at once, and both pass the protection. The hit is one atomic claim on shared state, and an unknown result grants nothing.
- Two nodes write the state of one live fight.
- The timeout on one node settles a fight while the result command settles it on another.
- The matchmaking queue lives in one node's memory. A shared queue pops in atomic steps.
- Every queued player writes one queue key.
- A dead node leaves queue entries for players who are gone.
- A fight id comes from an in-process counter.
- An abandoned fight ends on a timer in memory. Expiry comes from the stored start time when the state is read.
- A reply sends a whole replay.
- Fight logs or replays in a player's state grow without a cap.
- An old client and a new client are matched under different fight rules.

### Tests and metrics

- Each fight outcome has a test with a fixed RNG, and the same inputs give the same result.
- Two attackers on one defender have a test with two instances over one store.
- Each fight writes one action row with its result, and each gain and loss is logged with its reason.
