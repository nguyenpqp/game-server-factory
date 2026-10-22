# Performance rules

These are the `PERF` rules from [the rule index](index.md), which also gives each rule's severity. The design target is about 100k peak CCU and 1M DAU. The examples use generic names. The project profile supplies the real classes.

### PERF-01 The user actor thread never blocks on I/O, a sleep, or a lock held across I/O.

**Why.** An actor thread serves many users, so one blocked call stalls every user mapped to it.

Do:

```java
KvStore.getAsync(targetKey).thenAccept(doc ->
    actor.submit(() -> finishVisit(user, doc, traceId)));
```

Don't:

```java
UserSnapshot doc = KvStore.getAsync(targetKey).join();
Thread.sleep(50);
```

**Check.** Search the command path for `.join()`, `.get()` on futures, `.await(`, `.block()`, `Thread.sleep(`, and synchronous DB calls. The feature-review linter flags the profile's blocking calls. The core's own ownership checks and confirmed handover saves, which the profile's CAP-OWNERSHIP and CAP-DRAIN entries record, are not feature findings. A feature's synchronous Redis call on the actor thread passes only when the profile's CAP-REDIS entry records that pattern with a timeout and a circuit breaker, and the spec's performance budget counts the call.

- needs: CAP-ACTOR

### PERF-02 Each command makes a bounded number of database and Redis calls, stated in the spec's performance budget.

**Why.** At 100k CCU an extra call per command multiplies into a large load on the database.

Do:

```java
// Budget for this command is 1 Redis call (spec, performance budget).
long rank = RedisOps.zrevrank("{board:" + boardId + "}", userKey);
```

Don't:

```java
RedisOps.get(a);
RedisOps.get(b);
KvStore.get(c);   // calls grow with each change, no stated budget
```

**Check.** Count the DB and Redis calls on each path of the command and compare them with the spec's budget row.

- needs: CAP-USERSTORE, CAP-REDIS

### PERF-03 No database or Redis call runs inside a loop over items, users, or rows, and batch reads use multi-get, pipelining, or one script.

**Why.** A call per loop item turns one command into hundreds of round trips.

Do:

```java
Map<Long, FriendView> views = KvStore.multiGet(friendKeys);
```

Don't:

```java
for (long friendId : friendIds) {
    views.put(friendId, KvStore.get(friendKey(friendId)));
}
```

**Check.** Look inside every loop on the command path for a DB or Redis call.

- needs: CAP-USERSTORE, CAP-REDIS

### PERF-04 Each response and push stays within its byte budget, and lists sent to the client are capped or paginated.

**Why.** An unbounded list grows with the player's history and makes slow, large packets on mobile networks.

Do:

```java
List<LogEntry> page = state.history().page(cursor, config.pageSize());
resp.putList("entries", page);
resp.putInt("nextCursor", cursor + page.size());
```

Don't:

```java
resp.putList("entries", state.history().all());
```

**Check.** For each list in a response or push, find its cap or page size and the spec's byte budget.

- needs: CAP-RESPONSE

### PERF-05 Config lookups on the command path are constant-time reads from indexes built at load.

**Why.** A linear scan of a config list on every command wastes CPU at high request rates.

Do:

```java
// Built once in FeatureConfig.load().
Map<Integer, CropDef> cropsById = crops.stream().collect(toMap(CropDef::id, c -> c));
CropDef crop = config.cropsById().get(cropId);
```

Don't:

```java
CropDef crop = config.crops().stream().filter(c -> c.id() == cropId).findFirst().orElse(null);
```

**Check.** Search the command path for stream filters or loops over config lists.

- needs: CAP-CONFIG

### PERF-06 Per-user state has a stated size bound, and every list or map in it has a cap or an eviction rule.

**Why.** A list that only grows makes the user's document slower to load and save until it hits the store's size limit.

Do:

```java
state.history().add(entry);
if (state.history().size() > config.maxHistory()) {
    state.history().removeFirst();
}
```

Don't:

```java
state.history().add(entry);
```

**Check.** For each collection in the stored state, find its cap or eviction rule, and the spec's size bound.

- needs: CAP-USERSTORE

### PERF-07 A command pushes to or changes at most a stated number of other users, and larger fan-out runs as a batched job.

**Why.** A guild-wide push from one command can block the sender's actor and flood other nodes.

Do:

```java
if (members.size() <= config.maxDirectFanout()) {
    members.forEach(id -> CrossNode.push(id, push));
} else {
    FanoutJob.enqueue(guildId, push, traceId);
}
```

Don't:

```java
for (long id : allGuildMembers) {
    CrossNode.push(id, push);
}
```

**Check.** Find every loop that pushes to or changes other users, and confirm its bound or its batched job.

- needs: CAP-CROSSNODE

### PERF-08 No single Redis key takes a write from every active user on the command path, so hot counters and boards are sharded or batched.

**Why.** One hot key lands on one Redis shard, which becomes the cluster's bottleneck.

Do:

```java
int shard = (int) (userId % SHARDS);
// The shard number sits inside the hash tag, so shards spread over cluster slots.
RedisOps.incrBy("{event:" + eventId + ":" + shard + "}:joined", 1);
```

Don't:

```java
RedisOps.incrBy("event:joined", 1);
```

**Check.** For each Redis write on the command path, ask how many users write that key, and look for sharding or batching.

- needs: CAP-REDIS
