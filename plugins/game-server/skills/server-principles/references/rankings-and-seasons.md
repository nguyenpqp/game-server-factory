# Rankings and seasons

Read this note when players are ranked against each other by a score, such as a leaderboard, a ladder, a tournament, or a season that pays rewards by rank.

## Questions for the design

- What score ranks the players? Can it only rise, or can it fall?
- How are equal scores ordered: by who reached the score first, by a second value, or as a shared rank?
- What period does a board cover? When does it close, and in which time zone?
- What happens to a score when the period closes: a reset, a carry over, or a decay?
- Who is on one board: every player, a bracket by level or region, a group of a fixed size, or friends? How is a group formed, and can a player change group?
- Which ranks earn rewards, and what does each band pay?
- How does a player who is offline at the close receive the reward, and until when?
- What does the player see: the top ranks, their own rank, the players near them?
- What happens to the entry of a banned or deleted player, and to the ranks below it?

## Traps

### Server authority and anti-cheat

- The client sends a score or a score change. The server computes the score from the actions it ran itself.
- A retried request adds the same points twice.
- A tie is ordered by a time the client sent, or by the JVM clock. Use the server clock.
- The board closes or resets in a zone that the server does not name, or a player who changes zone passes the same reset twice.
- A request names a board, a group, or a season the player does not belong to.
- Points land after the board closed, or before it opened.

### Config

- The period, the close time, the group size, and the reward bands are in code. Each band is a row with an id, and each reward is one `{id, amount}` record.
- Bands with a gap or an overlap pass the load. Check that the bands cover the paid ranks once each.
- Stored entries and claims refer to a season by its list position.

### Modularity

- The feature that earns the points, such as battles, imports the ranking package.
- Points that decide a reward travel on a best-effort message, which can drop them. Send them through the ranking contract.

### Multi-node and rollout

- The board lives in a node's memory, so each node ranks a different board.
- A shared board changes by a read, a change in Java, and a write, so two nodes overwrite each other's points.
- The atomic update loses the tie order, so equal scores sort by chance.
- Every active player writes one global key.
- A failed write to the board reads as "not ranked".
- Two nodes run the season close at once, and players get the rank reward twice. The close stays correct when it runs twice, and each player's reward is claimed once per season id.
- The close pays from a board that still changes, so a late write or a removed entry shifts the ranks during the payout, and one player is paid twice or skipped.
- The close loads and saves each winner's document directly. Rewards reach players through the durable inbox, and a large close runs as a batched job.
- A write from the old season lands on a closed board. The write rechecks that the season is open, and the close stores a closed marker.
- A board page or a neighbor list has no size cap, or reads one entry per call.

### Tests and metrics

- Each tie rule and each band edge has a test with injected time.
- The rank rewards are logged as sources with their own reason.
