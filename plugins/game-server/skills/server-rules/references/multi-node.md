# Multi-node rules

These are the `MN` rules from [the rule index](index.md), which also gives each rule's severity. One world runs on N peer nodes, and one node owns a user at a time. The examples use generic names. The project profile supplies the real classes.

### MN-01 Feature code holds no game or user state in static fields, singletons, or node-wide maps, and its only mutable static field is the config snapshot reference that a reload swaps.

**Why.** Each node has its own copy of a static map, so players on different nodes see different worlds.

Do:

```java
public final class HarvestFeature {
    private static volatile FeatureConfig config;
    // Per-user data lives in the user's stored state, shared data in Redis.
}
```

Don't:

```java
private static final Map<Long, Integer> todayClaims = new ConcurrentHashMap<>();
```

**Check.** List every `static` field in the feature package. Each one is `final` and immutable, or it is the config snapshot reference. The feature-review linter flags static mutable collections.

- needs: none

### MN-02 Only the user actor on the user's owner node touches that user's live state, and any other reader works from a snapshot built on that actor or from a private load of the stored document.

**Why.** Two threads or two nodes that write one user's live state race, and the last save wins.

Do:

```java
UserActor owner = UserActor.of(targetId);
owner.submit(() -> reply(viewer, VisitView.snapshot(owner.state())));
```

Don't:

```java
UserState target = OnlineUsers.get(targetId).state();
target.garden().water(plotId);
```

**Check.** Find every place the feature reads another user's state, and confirm it runs on that user's actor or reads a private copy.

- needs: CAP-OWNERSHIP, CAP-ACTOR

### MN-03 A change to another user's state goes to that user's owner through cross-node delivery or the durable inbox, never through a direct load and save.

**Why.** A direct load and save on a non-owner node is overwritten by the owner's next save.

Do:

```java
Inbox.append(targetId, new HelpEntry(helperId, plotId, traceId));
```

Don't:

```java
UserState target = KvStore.load(targetId);
target.addHelp(helperId);
KvStore.save(targetId, target);
```

**Check.** Search for loads of a user id other than the acting user, followed by a save. Each is a finding.

- needs: CAP-CROSSNODE, CAP-INBOX

### MN-04 A stored document that several users or nodes write is updated with CAS and a bounded retry, never with a blind set.

**Why.** Two writers that read the same version and both set it lose one of the writes.

Do:

```java
for (int i = 0; i < 5; i++) {
    Versioned<Guild> doc = KvStore.gets(guildKey);
    doc.value().addMember(userId);
    if (KvStore.cas(guildKey, doc.value(), doc.cas())) return ErrorCode.SUCCESS;
}
return ErrorCode.CONFLICT;
```

Don't:

```java
Guild guild = KvStore.get(guildKey);
guild.addMember(userId);
KvStore.set(guildKey, guild);
```

**Check.** For each shared document, find who writes it. More than one writer means every write uses CAS with a retry limit.

- needs: CAP-CAS

### MN-05 Cluster-wide state lives in Redis and changes through atomic commands or Lua scripts, never through a read-modify-write in Java.

**Why.** A Java read, change, and write on Redis loses updates when two nodes run it at once.

Do:

```java
long left = RedisOps.decrBy("{sale:42}:stock", 1);
if (left < 0) {
    RedisOps.incrBy("{sale:42}:stock", 1);
    return ErrorCode.SOLD_OUT;
}
```

Don't:

```java
long stock = Long.parseLong(RedisOps.get("{sale:42}:stock"));
RedisOps.set("{sale:42}:stock", String.valueOf(stock - 1));
```

**Check.** Find each Redis `get` whose result feeds a later `set` on the same key. Replace it with an atomic command or a script.

- needs: CAP-REDIS

### MN-06 Redis keys that one command or script touches together share a hash tag.

**Why.** On Redis Cluster a script or multi-key command fails when its keys sit in different slots.

Do:

```java
String board = "{guild:" + guildId + "}:board";
String members = "{guild:" + guildId + "}:members";
RedisOps.eval(MOVE_SCRIPT, List.of(board, members), args);
```

Don't:

```java
RedisOps.eval(MOVE_SCRIPT, List.of("board:" + guildId, "members:" + guildId), args);
```

**Check.** For each script, transaction, or multi-key command, confirm that all keys carry the same `{...}` tag.

- needs: CAP-REDIS

### MN-07 A job that must run once per cluster runs only while it holds a lease, and it checks the lease token before each write.

**Why.** Without a lease every node runs the job, so each player gets the weekly reward once per node.

Do:

```java
Lease lease = JobLease.tryAcquire("weekly-rank", ttlMs);
if (lease == null) return;
for (Batch batch : batches) {
    if (!lease.stillHeld()) return;
    payBatch(batch);
}
```

Don't:

```java
scheduler.everyMonday(() -> payWeeklyRanking());
```

**Check.** List every scheduled task in the feature, and confirm each cluster-wide one takes a lease and checks it before writing.

- needs: CAP-LEASE

### MN-08 Ids that must be unique across the cluster come from Redis `INCR` or a snowflake with unique node bits, never from an in-process counter.

**Why.** Two nodes with their own counters hand out the same id, and a restart reuses ids.

Do:

```java
long tradeId = RedisOps.incr("{ids}:trade");
```

Don't:

```java
private static final AtomicLong nextTradeId = new AtomicLong();
long tradeId = nextTradeId.incrementAndGet();
```

**Check.** Find every new id the feature mints and trace it to Redis `INCR` or the cluster snowflake.

- needs: CAP-IDGEN

### MN-09 A node-local cache of shared data has an invalidation path and a stated staleness bound.

**Why.** A cache without invalidation keeps serving old data on some nodes after another node changes it.

Do:

```java
// Staleness bound is 30 s, and a change also publishes an invalidation.
Cache<Long, GuildView> views = Cache.expireAfterWrite(Duration.ofSeconds(30));
CrossNode.subscribe("guild-changed", id -> views.invalidate(id));
```

Don't:

```java
private final Map<Long, GuildView> views = new HashMap<>();
```

**Check.** For each cache, find its expiry and the message that invalidates it, and confirm the spec states the bound.

- needs: CAP-CROSSNODE, CAP-REDIS

### MN-10 Pushes to another user and checks of another user's online status go through the ownership record and cross-node delivery, never through a node-local session map.

**Why.** A local session map sees only users on this node, so it reports a friend on another node as offline.

Do:

```java
CrossNode.push(friendId, new GiftArrivedPush(senderId));
boolean online = Ownership.isOnline(friendId);
```

Don't:

```java
Session session = LocalSessions.get(friendId);
if (session != null) session.send(new GiftArrivedPush(senderId));
```

**Check.** Search for session lookups by a user id other than the acting user.

- needs: CAP-OWNERSHIP, CAP-CROSSNODE

### MN-11 A timed per-user effect, such as an expiry, a ready time, or a deadline, is derived from a stored timestamp when the state is read, never from an in-memory timer.

**Why.** An in-memory timer dies with the node or on handover, so the effect never fires.

Do:

```java
plot.setReadyAt(now + crop.growMs());
boolean ready = now >= plot.readyAt();
```

Don't:

```java
scheduler.schedule(() -> plot.setReady(true), crop.growMs(), MILLISECONDS);
```

**Check.** Find every per-user timer or delayed task in the feature. Each one becomes a stored timestamp checked on read.

- needs: CAP-CLOCK, CAP-USERSTORE
