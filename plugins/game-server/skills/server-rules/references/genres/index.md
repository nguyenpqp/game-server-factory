# Genre notes

Some kinds of feature recur across games, such as a leaderboard, a gacha, a shop, or a timed event. Each recurs with the same gaps in its design and the same breaks in its server code. A genre note lists both, so an agent asks the right questions and avoids the known breaks. A note never prescribes a design. The game's design decides how the feature works, and the note only names what that design must settle and what the code must not get wrong.

## How to use a note

Read every note whose "Read when" line matches the feature. A feature can match several notes, such as an event with a leaderboard and a shop.

- **Questions for the design.** Each one is about what the player sees, does, or gets, so `gdd-intake` can ask it. A question that the sources answer is settled. A question they leave open is a gap.
- **Traps.** Each trap names a break and the rule ids that cover it. The traps are grouped by the four things that come first for every feature: server authority and anti-cheat, config, modularity, and multi-node safety with rollout. A last group names the tests and metrics that matter most for the genre. `feature-spec` designs each matching row so the trap cannot happen, and `feature-review` looks for each trap in the code.

The rule index stays the authority. A trap only points at a rule. When a case needs a rule that the index lacks, report it as a gap, as the `server-rules` skill says.

## Notes

| Note | Read when the feature has |
| --- | --- |
| [Rankings and seasons](rankings-and-seasons.md) | Players ranked against each other by a score, such as a leaderboard, a ladder, a tournament, or a season with rewards by rank |
| [Randomness and gacha](randomness-and-gacha.md) | A random outcome that carries value, such as a gacha, a loot box, a random drop, a wheel, or a craft that can fail |
| [Economy and exchange](economy-and-exchange.md) | Currency or items that are bought, sold, sent, or traded, such as a shop with limits, rotating offers, mail with attachments, gifts, trades, or a real money purchase |
| [Events and passes](events-and-passes.md) | Progress inside a time window, such as a limited event, missions, point milestones, a battle pass, or a login calendar |
| [Guilds and groups](guilds-and-groups.md) | Players in a shared group, such as a guild, a clan, an alliance, a party, or a friend list |
| [PvP and matchmaking](pvp-and-matchmaking.md) | Players who fight or compete against each other, live or against a stored defense, with opponents the server picks |
