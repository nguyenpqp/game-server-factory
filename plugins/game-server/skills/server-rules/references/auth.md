# Server authority and input rules

These are the `AUTH` rules from [the rule index](index.md), which also gives each rule's severity. The examples use generic names. The project profile supplies the real classes.

### AUTH-01 The client sends intents only, and the server computes every result, cost, and reward.

**Why.** Any value the client sends can be forged, so a client-computed reward is a free reward.

Do:

```java
int slot = req.readInt("slot");
Reward reward = FeatureConfig.get().rewardFor(state.level(slot));
inventory.add(reward, Reason.HARVEST, traceId);
```

Don't:

```java
int gold = req.readInt("gold");
inventory.addGold(gold, Reason.HARVEST, traceId);
```

**Check.** Read the request decoder and confirm that no field holds an amount, a cost, a result, or a reward.

- needs: CAP-COMMAND

### AUTH-02 Game logic reads time only from the server clock, passed into the core as a parameter, and turns it into a date only with the zone that CAP-CLOCK names.

**Why.** Client time and node-local calls are forgeable or skewed, and a core that reads the clock itself cannot be tested. A date built in the JVM's default zone moves the day boundary on a node or a test machine set to another zone.

Do:

```java
long now = ServerClock.now();
Result result = HarvestCore.process(state, config, slot, now);
LocalDate today = Instant.ofEpochMilli(now).atZone(ServerClock.zone()).toLocalDate();
```

Don't:

```java
boolean ready = System.currentTimeMillis() >= plot.readyAt();
LocalDate today = Instant.ofEpochMilli(now).atZone(ZoneId.systemDefault()).toLocalDate();
```

**Check.** Search the feature package for `currentTimeMillis`, `Instant.now`, `LocalDate.now`, `new Date()`, and the other calls in the profile's `lint.forbidden_time`. Then find each place that turns time into a date, a day, or an hour, such as `atZone`, `ofInstant`, `Calendar`, or a date format, and confirm it takes the zone from CAP-CLOCK. A call that names no zone, such as `ZoneId.systemDefault()`, `TimeZone.getDefault()`, or `Calendar.getInstance()`, uses the JVM's zone.

- needs: CAP-CLOCK

### AUTH-03 Game logic draws random numbers only from the injected server RNG.

**Why.** A private `Random` cannot be seeded in tests, and a client-sent seed lets the player pick the outcome.

Do:

```java
int roll = rng.nextInt(table.totalWeight());
Drop drop = table.pick(roll);
```

Don't:

```java
int roll = new Random().nextInt(table.totalWeight());
```

**Check.** Search the feature package for `new Random(`, `Math.random(`, and `ThreadLocalRandom`, and confirm the core takes the RNG as a parameter.

- needs: CAP-RNG

### AUTH-04 Every request field is checked for presence, type, range, length, and allowed values before any state change, and every amount computed from it stays within its type.

**Why.** An unchecked negative count or out-of-range index turns into free items or a crash on the actor thread. A count inside its own range can still multiply a price past the limit of its type, and the product wraps to a small or negative cost.

Do:

```java
int count = req.readInt("count");
if (count < 1 || count > config.maxBatch()) {
    return ErrorCode.INVALID_PARAM;
}
```

Don't:

```java
int count = req.readInt("count");
inventory.take(seedId, count, Reason.PLANT, traceId);
```

Bound each field so that every amount computed from it fits its type with the largest config values, such as a price times the largest count. The config check at load caps the config side of that product (CFG-02). Where no bound proves that the result fits, compute it with `Math.multiplyExact` or `Math.addExact` before the first change, and return an error on the exception. A sum into a stored balance needs the same bound, and CAP-INVENTORY's add gives it when it refuses a total past the limit of its type.

**Check.** For each field in the decoder, find the guard that bounds it before the first mutation. For each amount computed from a field, such as a cost times a count, find the bound that keeps it within its type, or the exact arithmetic call.

- needs: CAP-COMMAND, CAP-ERRORS

### AUTH-05 Every object a request names, such as an item, a slot, or a target user, is checked to belong to or be reachable by the acting user.

**Why.** A request that names another player's slot or a locked item must not act on it.

Do:

```java
Plot plot = state.plot(slotId);
if (plot == null) {
    return ErrorCode.NOT_FOUND;
}
```

Don't:

```java
Plot plot = PlotStore.byId(slotId);
plot.harvest(now);
```

**Check.** Confirm that every id in the request resolves through the acting user's state or an explicit reachability check, such as a friend list.

- needs: CAP-USERSTORE

### AUTH-06 Every precondition, such as feature active, unlocked, legal state transition, or cooldown over, is checked against server state before any change.

**Why.** A client can send any command at any time, so its UI state proves nothing.

Do:

```java
if (!config.isOpen(now)) return ErrorCode.FEATURE_NOT_ACTIVE;
if (state.level() < config.unlockLevel()) return ErrorCode.LOCKED;
if (now < state.nextClaimAt()) return ErrorCode.COOLDOWN;
```

Don't:

```java
// The button is hidden until the cooldown ends.
grantDailyReward(state, now);
```

**Check.** List the states the design allows for the command and find a server-side guard for each excluded state.

- needs: CAP-CONFIG, CAP-CLOCK

### AUTH-07 A command checks every cost in full before it takes any, takes it after any shared claim the action needs, and refunds what it took when a later step definitely fails or throws.

**Why.** Taking the first cost and then failing on the second loses player value with nothing in return. A shared write that times out may have landed, so a blind refund pays the player back for something they got. A step that throws after the take loses the cost the same way, and one that throws after the grant but before the request id is stored lets a retry grant again.

Do:

```java
if (!inventory.canTake(costs)) return ErrorCode.NOT_ENOUGH_ITEM;
inventory.take(costs, Reason.CRAFT, traceId);
if (!inventory.add(product, Reason.CRAFT, traceId)) {
    inventory.add(costs, Reason.CRAFT_REFUND, traceId);
    return ErrorCode.STORAGE_FULL;
}
```

Don't:

```java
inventory.take(gold, Reason.CRAFT, traceId);
inventory.take(wood, Reason.CRAFT, traceId);
```

When the effect is a write to shared state, such as a guild or a sale, claim or reserve the shared side first and take the cost last. A definite failure after the take refunds. An unknown outcome logs the case for repair and does not refund.

The runner that catches an exception only logs it, so a throw after the first change leaves the command half applied. Run the work that can throw before the first change, such as lookups, arithmetic, and building the result. After the first change, run only in-memory writes that cannot throw, such as storing the request id. A change to the player's own state that can throw, such as a grant that throws on a full storage instead of returning false, is caught at the call, which undoes what ran and rethrows, so the runner still writes the exception row. A shared write that throws has an unknown outcome, so it logs the case for repair as above and does not refund. A grant of several items that throws partway leaves the first items granted, so CAP-INVENTORY's add of several items adds nothing when any item fails, or the undo also removes what the grant added.

**Check.** Find the full check before the first take, and a refund on every definite failure path after it. Then find each call after the first change that can throw, and confirm that it runs before the change instead, or that its catch undoes what ran. For a shared effect, confirm the claim comes before the take, and that a timeout path logs instead of refunding.

- needs: CAP-INVENTORY

### AUTH-08 A command whose retry would grant value twice carries a request id, and the server applies each request id at most once per user.

**Why.** Mobile clients resend on reconnect, so a non-idempotent claim pays out twice.

Do:

```java
String requestId = req.readString("requestId");
Result stored = state.resultOf(requestId);
if (stored != null) {
    return stored;
}
Result result = claim(state, config, now, traceId);
state.rememberResult(requestId, result);
```

Don't:

```java
state.addGems(config.packGems());
```

**Check.** For each command that grants value, ask what a resend after a lost response does, and find the request id guard.

- needs: CAP-COMMAND, CAP-USERSTORE

### AUTH-09 A command that reads the database, touches other users, or fans out has a per-user rate limit, and excess calls get an error with no effect.

**Why.** One scripted client looping a costly command can load the database for every player.

Do:

```java
if (!state.rateLimit("visit").tryAcquire(now, config.visitPerMinute())) {
    return ErrorCode.TOO_MANY_REQUESTS;
}
```

Don't:

```java
UserSnapshot target = KvStore.load(targetId);
```

**Check.** Mark each command that does I/O or touches other users, and find its limit and its error code.

- needs: CAP-CLOCK, CAP-ERRORS

### AUTH-10 A rejected command changes no state and returns an error code specific to the failure.

**Why.** A half-applied rejection corrupts state, and a generic error hides the cause from the client and from metrics.

Do:

```java
ErrorCode error = validate(state, req, now);
if (error != ErrorCode.SUCCESS) {
    return error;
}
apply(state, req, now);
```

Don't:

```java
state.setStep(state.step() + 1);
if (!config.hasStep(state.step())) {
    return ErrorCode.FAIL;
}
```

**Check.** Confirm that every `return` with an error comes before the first mutation and names a distinct code.

- needs: CAP-ERRORS
