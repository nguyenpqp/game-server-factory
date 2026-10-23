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

A shared pool, such as free seats or stock, belongs in Redis for its whole life. A node that checks the pool out into memory at boot and writes it back at shutdown hands the same seat to two players.

**Check.** List every `static` field in the feature package. Each one is `final` and immutable, or it is the config snapshot reference. A boot step that loads shared data into memory for later write-back is a finding.

- needs: none

### MN-02 Only the user actor on the user's owner node touches that user's live state, and any other reader works from a snapshot built on that actor or from a private copy of the stored document, which may reject an action but never grant one.

**Why.** Two threads or two nodes that write one user's live state race, and the last save wins. A private copy can be one save cycle old and misses every claim made since, so it can say no but not yes.

Do:

```java
UserActor owner = UserActor.of(targetId);
owner.submit(() -> reply(viewer, VisitView.snapshot(owner.state())));

// A visitor on another node reads a private copy plus the shared claim keys.
GardenView copy = GardenView.of(KvStore.load(targetId), Claims.openHelps(targetId));
if (copy.helpsToday() >= config.maxHelps()) return ErrorCode.LIMIT_REACHED;   // a copy may refuse
// Whether the ask is still open is decided by the shared claim, never by the copy.
```

Don't:

```java
UserState target = OnlineUsers.get(targetId).state();
target.garden().water(plotId);

if (KvStore.load(targetId).ask(askId).isOpen()) grantHelpReward(helperId);   // stale copy grants
```

**Check.** Find every place the feature reads another user's state, and confirm it runs on that user's actor or reads a private copy. A grant decided from a private copy, rather than from the owner or a shared claim, is a finding.

- needs: CAP-OWNERSHIP, CAP-ACTOR

### MN-03 A change to another user's state goes to that user's owner through the durable inbox or cross-node delivery, even when the owner is this node, never through a direct load and save.

**Why.** A direct load and save on a non-owner node is overwritten by the owner's next save. A local shortcut skips the owner's ordering and sees a context that may be about to move.

Do:

```java
Inbox.append(targetId, new HelpEntry(helperId, plotId, traceId));

// Several buyers race for one sale: claim, then append, then cost.
ClaimVerdict claim = Claims.claim(saleKey(sellerId, saleId), buyerId);
if (claim != ClaimVerdict.WON) return claim == ClaimVerdict.LOST ? ErrorCode.SOLD_OUT : ErrorCode.RETRY_LATER;
if (!Inbox.append(sellerId, new SoldEntry(saleId, buyerId, traceId))) {
    Claims.release(saleKey(sellerId, saleId), buyerId);
    return ErrorCode.RETRY_LATER;
}
inventory.take(price, Reason.BUY_SALE, traceId);   // checked earlier, taken last
```

Don't:

```java
UserState target = KvStore.load(targetId);
target.addHelp(helperId);
KvStore.save(targetId, target);

inventory.take(price, Reason.BUY_SALE, traceId);   // the loser of the race pays too
Claims.claim(saleKey(sellerId, saleId), buyerId);
```

When users race for one shared thing, the actor claims it in Redis first, appends the entry second, releases the claim when the append fails, and takes its own cost last. The owner applies the entry, saves, and then gives the claim a TTL longer than any stale read. It never deletes the claim, because a reader with an old copy would claim again. The owner's own actions on the thing take the same claim.

**Check.** Search for loads of a user id other than the acting user, followed by a save. Each is a finding, and so is a direct call into the target's state because the target is on this node. For a contested thing, confirm the order claim, append, cost, the release on a failed append, and that settling retires the claim instead of deleting it.

- needs: CAP-CROSSNODE, CAP-INBOX

### MN-04 A stored document that several users or nodes write is updated with CAS and a bounded retry on a version mismatch, the change is applied to a fresh copy that shares no object with live state, and a timeout or error is an unknown outcome that is re-read, never re-applied.

**Why.** Two writers that read the same version and both set it lose one of the writes. A timed-out write may have landed, so applying the change again grants twice. A change made to a shared live object stays even when the write fails.

Do:

```java
for (int i = 0; i < 5; i++) {
    Versioned<Guild> doc = KvStore.gets(guildKey);                  // a fresh copy each try
    if (doc.value().hasMember(userId)) return ErrorCode.SUCCESS;     // an earlier try landed
    doc.value().addMember(userId);
    CasResult result = KvStore.cas(guildKey, doc.value(), doc.cas());
    if (result == CasResult.WRITTEN) return ErrorCode.SUCCESS;
    // MISMATCH and UNKNOWN both re-read, and the check above stops a second apply.
}
return ErrorCode.RETRY_LATER;
```

Don't:

```java
Guild guild = KvStore.get(guildKey);
guild.addMember(userId);
KvStore.set(guildKey, guild);

try {
    KvStore.cas(key, liveConfig.withSchedule(s), cas);   // edits the live object
} catch (TimeoutException e) {
    KvStore.cas(key, liveConfig.withSchedule(s), cas);   // re-applies blind
}
```

Logs, pushes, and grants happen after the write is confirmed, never inside the retry loop. A shared write reports written, unchanged, or failed, and an admin command shows that result.

**Check.** For each shared document, find who writes it. More than one writer means every write uses CAS with a retry limit. Read each catch block inside a CAS loop: a path that applies the change again without re-reading is a finding, and so is a change made to an object the live state also holds.

- needs: CAP-CAS

### MN-05 Cluster-wide state lives in Redis and changes through atomic commands or Lua scripts, never through a read-modify-write in Java, and a script rechecks every fact the caller decided on and updates derived indexes in the same call.

**Why.** A Java read, change, and write on Redis loses updates when two nodes run it at once. A fact checked in Java can change on another node before the write, and an index updated in a second call drifts from its source.

Do:

```java
long left = RedisOps.decrBy("{sale:42}:stock", 1);
if (left < 0) {
    RedisOps.incrBy("{sale:42}:stock", 1);
    return ErrorCode.SOLD_OUT;
}

// The script gets the role the caller saw and refuses when it changed.
long code = RedisOps.eval(KICK_SCRIPT, List.of(guildKey, membersKey, searchKey),
        List.of(String.valueOf(targetId), expectedRole.name()));
if (code == KickScript.ROLE_CHANGED) return ErrorCode.RETRY;
```

Don't:

```java
long stock = Long.parseLong(RedisOps.get("{sale:42}:stock"));
RedisOps.set("{sale:42}:stock", String.valueOf(stock - 1));

if (guild.roleOf(targetId) == Role.MEMBER) RedisOps.srem(membersKey, targetId);   // checked in Java
RedisOps.zincrby(searchKey, -1, guildId);                                           // second call
```

**Check.** Find each Redis `get` whose result feeds a later `set` on the same key. Replace it with an atomic command or a script. For each script, every precondition the Java side checked has a twin inside the script, and every index derived from the changed keys changes in the same script. A periodic job that rebuilds an index is a sign of drift.

- needs: CAP-REDIS

### MN-06 Every key that a Redis script touches is passed in KEYS, and on Redis Cluster the keys that one command or script touches together share a hash tag.

**Why.** Redis Cluster routes a call by its declared keys, so a key built inside a script is invisible to routing, and keys in different slots fail the call. The profile's CAP-REDIS entry says whether Redis runs as one instance or as a cluster.

Do:

```java
String board = "{guild:" + guildId + "}:board";
String members = "{guild:" + guildId + "}:members";
RedisOps.eval(MOVE_SCRIPT, List.of(board, members), args);
```

Don't:

```java
RedisOps.eval(MOVE_SCRIPT, List.of("board:" + guildId, "members:" + guildId), args);
// or a script that builds "members:" .. ARGV[1] inside Lua
```

**Check.** No key name is concatenated inside a script. When CAP-REDIS says cluster, all keys of one script, transaction, or multi-key command carry the same `{...}` tag. A global index and per-entity keys cannot share a slot, so on a cluster the spec says how that call is split.

- needs: CAP-REDIS

### MN-07 A cluster-wide job stays correct when two nodes run it at once: a lease or lock only saves duplicate work, the job rechecks it between units, each unit is claimed or idempotent, a job that pays from data that still changes pays from one stored copy of it, and a job for data only the new version knows does not depend on a lease the old version can hold.

**Why.** A lease can lapse mid-run, and then two nodes run the job, so only a per-unit claim keeps a reward paid once. The cluster lease may sit on the old version for hours, so a job that only the new config knows would never run.

Do:

```java
if (!EventLock.tryAcquire(eventId, ttlMs)) { retryLater(eventId); return; }   // any version that knows the event
try {
    for (long userId : winners) {
        if (!EventLock.stillHeld(eventId)) return;
        if (!RedisOps.hsetnx(paidKey(eventId), String.valueOf(userId), traceId)) continue;   // paid before
        if (!Inbox.append(userId, new TopRewardEntry(eventId, rankOf(userId), traceId)))
            RedisOps.hdel(paidKey(eventId), String.valueOf(userId));                      // retried later
    }
} finally {
    if (allPaid(eventId)) markDone(eventId); else retryLater(eventId);
}
```

Don't:

```java
scheduler.everyMonday(() -> payWeeklyRanking());

if (LeaderLease.isHeld()) payAll(winners);   // checked once, no per-user claim
```

A job that pays by rank, or by any value that can still change, first stores its input once under the occurrence id, such as the final ranking of a season. Every unit and every retry pays from that stored copy, never from the live board, so a late write or a removed entry cannot shift ranks during the payout.

Run a periodic job much more often than its period, and decide what is due from stored state, so a restart or a lease move cannot skip a run. Set the done marker only when no unit failed, and schedule the retry in a `finally` block.

**Check.** List every scheduled task in the feature. Each cluster-wide one takes a lease or a lock, rechecks it between units, and claims or idempotently writes each unit. Name the lease a job uses: a job for data that only the new version has must not wait for the cluster lease. Compare the tick with the job's period. For a job that pays by rank or by a changing value, find the stored copy it pays from.

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

**Check.** Find every new id the feature mints and trace it to Redis `INCR`, the store's shared counter, or the cluster snowflake. An increment that creates a missing counter from zero reissues ids after a key loss, so the profile's CAP-IDGEN entry says how the counter refuses that.

- needs: CAP-IDGEN

### MN-09 A node-local cache of shared data has a stated staleness bound and an invalidation path, unless a stale value only errs on the safe side.

**Why.** A cache without invalidation keeps serving old data on some nodes after another node changes it.

Do:

```java
// Staleness bound is 30 s, and a change also publishes an invalidation.
Cache<Long, GuildView> views = Cache.expireAfterWrite(Duration.ofSeconds(30));
CrossNode.subscribe("guild-changed", id -> views.invalidate(id));

// Bound only: a miss reads the store, so a stale entry can only delay an unban.
Cache<Long, Boolean> bannedOnly = Cache.expireAfterWrite(Duration.ofSeconds(60));
```

Don't:

```java
private final Map<Long, GuildView> views = new HashMap<>();
```

**Check.** For each cache, find its expiry and the message that invalidates it, and confirm the spec states the bound. A cache with a bound and no invalidation passes only when the spec says why a stale value errs on the safe side.

- needs: CAP-CROSSNODE, CAP-REDIS

### MN-10 Pushes to another user and checks of another user's online status go through the ownership record and cross-node delivery, never through a node-local session map, and a user counts as online only while the owner record exists and its node's heartbeat is current.

**Why.** A local session map sees only users on this node, so it reports a friend on another node as offline. A crashed node leaves its owner records until they expire, so its users would read as online.

Do:

```java
CrossNode.push(friendId, new GiftArrivedPush(senderId));
boolean online = Ownership.isOnline(friendId);   // owner record plus the owner's heartbeat
```

Don't:

```java
Session session = LocalSessions.get(friendId);
if (session != null) session.send(new GiftArrivedPush(senderId));
```

**Check.** Search for session lookups by a user id other than the acting user. Confirm the online check the feature uses reads the owner's heartbeat as well as the owner record.

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

### MN-12 Fields that must change together live in one stored document, or in documents that CAP-USERSTORE saves in one atomic write, because documents that save on their own can be split by a crash.

**Why.** A document that saves on its own can land while another does not, so a crash or a failed write between two saves keeps one change and loses the other, such as a cost recorded while the item it bought is missing.

Do:

```java
// The plot and its harvest record change together, so they share one document.
GardenState garden = actor.state(GardenState.class);
garden.harvest(plotId, now);
garden.markChanged();
```

Don't:

```java
plots.clear(plotId);              // saved with PlotState
harvests.add(plotId, now);        // saved with HarvestState, at another time
plots.markChanged();
harvests.markChanged();
```

Don't split one invariant across documents to keep each one small. Split a document only when each part stays consistent on its own.

A feature cannot move its fields into the core's documents, so a change that spans both, such as a grant through CAP-INVENTORY and the feature's record of the claim, relies on CAP-USERSTORE to save every changed document of the player in one atomic write. When the profile's CAP-USERSTORE entry names MN-12 on its blocker line, the spec lists MN-12 in Core blockers.

**Check.** For each command that changes more than one stored document, ask what a crash after the first save leaves behind. When it breaks an invariant or loses player value, the fields belong in one document, or in documents that CAP-USERSTORE saves in one atomic write.

- needs: CAP-USERSTORE

### MN-13 Every check or write against Redis, the store, or a cluster primitive tells yes, no, and unknown apart, and an unknown result never turns into a definite answer that grants, denies, or hides player value.

**Why.** A Redis timeout read as "not found" or "full" tells a player a guild is full, skips a refund, or lets a claim succeed twice.

Do:

```java
ClaimVerdict claim = Claims.claim(key, userId);    // WON, LOST, or FAULT
switch (claim) {
    case WON -> deliver(entry);
    case LOST -> { return ErrorCode.ALREADY_TAKEN; }
    case FAULT -> { return ErrorCode.RETRY_LATER; }
}
```

Don't:

```java
Long size = RedisOps.scardOrNull(membersKey);       // null on error
if (size == null || size >= cap) return ErrorCode.GUILD_FULL;
```

Claims and logins answer retry-later on an unknown result. A display, such as an online dot, may degrade to a safe default.

**Check.** Find each Redis or store call whose wrapper returns null, false, or empty on error, and trace how the caller maps that value. A mapping to a definite refusal, to "absent", "offline", or "already claimed", or to an empty list that hides value is a finding.

- needs: CAP-REDIS

### MN-14 Claims, counters, and events about a shared thing that can close or be created again carry the id of that occurrence, and closing it stores an explicit closed marker instead of deleting the key.

**Why.** Without the occurrence id a stale event matches a new cycle and a recreated code inherits the old counts. A deleted key reads the same as one that never existed, so a stale copy looks open.

Do:

```java
String key = "help:" + ownerId + ":" + askId;        // askId is new for every request
RedisOps.set(key, "closed", CLAIM_RETIRE_TTL);        // closing leaves a marker
String used = "code:" + code + ":" + generation + ":used";   // a recreated code starts at zero
```

Don't:

```java
String key = "help:" + ownerId;                       // one key for every request
RedisOps.del(key);                                    // closed reads like never opened
```

Data from before the change that has no occurrence id gets a fixed id, such as `legacy`, so a stale event about it cannot match a later occurrence.

**Check.** For each shared thing that can close, end, or be deleted and recreated, confirm its keys include the occurrence id. Find every branch where a missing key means "open" or "zero", and confirm closing writes a marker.

- needs: CAP-REDIS

### MN-15 A buffered or late write that a former owner can flush after a handover cannot move shared state backward, because it is a monotone write or carries a version check.

**Why.** A node that loses a user can still flush a buffered score or count, and a plain write then replaces the new owner's newer value.

Do:

```java
RedisOps.zaddGt(boardKey, score, String.valueOf(userId));   // only raises the score
```

Don't:

```java
RedisOps.zadd(boardKey, score, String.valueOf(userId));     // a late flush lowers it
```

An absolute override, such as an admin reset, first discards the pending buffered writes for that key.

**Check.** Find every write that is buffered, asynchronous, or flushed at shutdown or on a timer. Each one is monotone, such as `ZADD GT` or a max merge, or it compares a version.

- needs: CAP-REDIS
