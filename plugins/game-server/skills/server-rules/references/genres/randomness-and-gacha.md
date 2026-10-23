# Randomness and gacha

Read this note when a random outcome carries value, such as a gacha, a loot box, a random drop, a wheel, a card pack, or a craft that can fail. How to use it is in the [genre notes index](index.md). Rule ids refer to the [rule index](../index.md).

## Questions for the design

- What can each pool give, and with what weight? Do the weights add up to a stated total?
- Is there a pity counter? After how many pulls does it pay, and does it reset on that hit or on any rare result?
- Is pity kept per pool, shared across banners, or carried to the next banner?
- Does a multi-pull guarantee something, such as one rare in ten?
- What does a duplicate turn into?
- What does one pull cost, does a multi-pull cost less, and are there free pulls with a cooldown?
- Must the game show the rates, and must the shown rates match the real ones exactly?
- What happens to unused tickets and pity progress when a banner ends? Does a rerun of a banner keep them?
- Is any prize limited across the whole server, and what does a pull get when it is gone?

## Traps

### Server authority and anti-cheat

- The client rolls the result, or sends a seed or a choice that decides it. The server draws from its own injected RNG (AUTH-01, AUTH-03).
- A player drops the connection after a pull and retries until the result is good. A retry returns the first result and never rolls again (AUTH-08).
- The roll or the grant fails after the cost is taken, and the player keeps neither. Check the whole cost first, and refund when a later step fails or throws (AUTH-07).
- The request picks the pull count. Only the counts the config offers pass the check (AUTH-04).
- A pull runs on a banner before it opens or after it ends (AUTH-06, CFG-04).

### Config

- Weights, pools, pity limits, and costs are in code (CFG-05).
- A pool with a zero or negative weight, an unknown item id, or a pity limit below 1 passes the load (CFG-02).
- One pull reads two config snapshots, so a reload mid-pull mixes the old and new tables (CFG-03).
- The pity counter refers to a pool by list position, so a new pool in the list moves every player's pity (CFG-06).
- The rates that the game shows are a second copy of the weights, so the two drift apart (CFG-10).
- The shown rates are rounded, or leave out pity and guarantees, so they differ from the real chance of each prize (DES-02).

### Modularity

- The pull grants items by writing another feature's state. It grants through the inventory contract with a reason of its own (MOD-01, MOD-02, MET-04).

### Multi-node and rollout

- The pity counter and the prize it pays are saved apart, so a crash between the saves loses one of them (MN-12).
- A rerun of a banner reuses the counts or the pity of the last run when the design does not carry them over (MN-14).
- A server-wide limited prize is counted in node memory, or by a read and a write, so it is given out more times than its stock (MN-01, MN-05).
- A failed stock check reads as "sold out" or as "won" (MN-13).
- New pity or banner state renames or retypes an old field (BG-01).

### Tests and metrics

- Each pity edge, each guarantee, and each duplicate rule has a test with a fixed RNG (TEST-02).
- Each pull writes one action row with its result, and each prize and cost is logged with its reason (MET-01, MET-04).
