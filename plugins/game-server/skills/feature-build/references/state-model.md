# State model

Per-user feature state is one stored document per user, written only by that user's owner actor (MN-02). Two server versions read and write the same documents during a rollout, so the document changes only by added fields (BG-01).

The real document store, the serializer, the after-load hook, and the save cycle come from the profile's CAP-USERSTORE entry. CAS writes come from CAP-CAS.

## The document

```java
public final class EventShopState {
    static final int SCHEMA_VERSION = 2;
    static final int MAX_RESULTS = 20;

    int schemaVersion;
    long purchaseDay = -1;
    Map<String, Integer> boughtByItem = new HashMap<>();
    List<StoredResult> recentResults = new ArrayList<>();
    long lastBuyAtMs;

    public static String key(long userId) {
        return "event_shop_" + userId;
    }

    int boughtOn(String itemId, long day) {
        return day == purchaseDay ? boughtByItem.getOrDefault(itemId, 0) : 0;
    }

    void recordPurchase(String itemId, long day, int quantity) {
        if (day != purchaseDay) {
            purchaseDay = day;
            boughtByItem.clear();
        }
        boughtByItem.merge(itemId, quantity, Integer::sum);
    }

    Outcome resultOf(String requestId) {
        for (StoredResult r : recentResults)
            if (r.requestId.equals(requestId))
                return r.outcome();
        return null;
    }

    void rememberResult(String requestId, Outcome out) {
        recentResults.add(new StoredResult(requestId, out));
        if (recentResults.size() > MAX_RESULTS)
            recentResults.remove(0);
    }
}
```

- The key is a fixed string plus the user id. It never contains a Java class name, so a rename does not orphan stored data (BG-01).
- Every field has a default that matches the spec's `Default when absent` column. A document written before the field existed loads with that default.
- Every list and map has a cap or a reset rule (PERF-06). `recentResults` keeps the last 20 entries. `boughtByItem` resets when the day changes and holds at most one entry per config item.
- Methods on the document carry the rules, such as the day reset in `recordPurchase`. Commands, cheats, and admin repairs all call these methods, so every path keeps the same invariants (CHEAT-06).
- The fields hold ids from config, never list positions (CFG-06).

## Additive changes only

- Add a field with a default. Never remove, rename, or retype a field (BG-01). A field that is no longer used stays in the class, unread.
- A changed meaning gets a new field, and the old field keeps its old meaning (BG-03). For example, when a count becomes a count per item, add `boughtByItem` and keep the old `boughtToday` as it was.
- The serializer keeps every field that the running version does not know, and writes it back on save (BG-02). This is the core's job, through CAP-USERSTORE. When the profile shows that the serializer drops unknown fields, the slice stops at gate 3. Do not add a feature-local workaround, such as a hand-written map of extra fields, unless the profile's CAP-USERSTORE entry names that map as the project's way.

## Lazy migration

```java
void migrate(long now) {
    if (schemaVersion < 1) {
        boughtByItem = boughtByItem == null ? new HashMap<>() : boughtByItem;
        recentResults = recentResults == null ? new ArrayList<>() : recentResults;
        schemaVersion = 1;
    }
    if (schemaVersion < 2) {
        lastBuyAtMs = 0;
        schemaVersion = 2;
    }
}
```

- `migrate` runs on the owner actor, in the after-load hook that CAP-USERSTORE names, before the first command (BG-09).
- Each step runs only when `schemaVersion` is below its target, so a second run changes nothing. The version only increases.
- A step derives its result from the stored data, never from the step's own earlier run, so a crash in the middle leaves a document that the next load migrates again.
- Each step matches a row of the spec's Migrations table.
- A newer server may have written a higher `schemaVersion`. Leave it as it is, and keep the fields this version does not know.
- Call `markChanged` after a migration that changed the document, so the save cycle writes it.

## Timestamps instead of timers

```java
boolean cooldownOver(long now, long cooldownMs) {
    return now >= lastBuyAtMs + cooldownMs;
}
```

A timed effect, such as a cooldown, an expiry, or a ready time, is a stored timestamp compared with `now` when the state is read (MN-11). Never schedule an in-memory timer for it. A timer dies when the node drains, and the user reconnects to another node.

## Who writes the document

- Only the user's owner actor touches the live document (MN-02). Code on another user's thread never reads or writes it directly.
- A change to another user goes to that user's owner through CAP-CROSSNODE, or into that user's durable inbox through CAP-INBOX (MN-03).
- A document that several users or nodes write, such as a shared group record, uses a CAS read and write with a bounded retry from CAP-CAS, never a blind set (MN-04).
- Cluster-wide counters and boards live in Redis and change through atomic commands or a Lua script from CAP-REDIS (MN-05). Keys that one command or script touches share a hash tag (MN-06).
- The hash tag names the entity that one command touches, such as one group, never the whole feature. A tag shared by every user's keys puts them all on one Redis Cluster slot. A key that every active user writes is sharded or batched (PERF-08).

The real Redis client comes from the profile's CAP-REDIS entry. The calls below show the shape. `redis` is a `RedisOps`.

```java
String tag = "{shop_group:" + groupId + "}";
long sold = redis.incrBy(tag + ":sold:" + itemId, quantity);
boolean first = redis.setNx(tag + ":first_buyer:" + itemId, String.valueOf(userId), ttlMs);
```

A Redis call is I/O. Run it off the actor thread through CAP-ACTOR's async path and continue on the actor with the result (PERF-01). Count it in the spec's performance budget (PERF-02).
