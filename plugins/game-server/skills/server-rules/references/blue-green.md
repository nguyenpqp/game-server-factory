# Blue-green and client compatibility rules

These are the `BG` rules from [the rule index](index.md), which also gives each rule's severity. During a rollout the old and the new server version run against the same data, and old clients stay connected to both. The examples use generic names. The project profile supplies the real classes.

### BG-01 Stored data in Couchbase and Redis changes only by added fields and keys, never by a removed, renamed, or retyped one.

**Why.** The old version still reads the same documents, so a renamed field reads as empty and its next save wipes the value.

Do:

```java
class GardenState {
    int level;
    long xp;          // added, old servers ignore it
}
```

Don't:

```java
class GardenState {
    int gardenLevel;  // renamed from level
    String xp;        // retyped from long
}
```

**Check.** Diff each stored class and Redis key layout. Any removed, renamed, or retyped field or key is a finding. Removing a whole stored type, such as the documents of a retired feature, happens only in a maintenance deploy. A format change that the old version cannot read falls under BG-12.

- needs: CAP-USERSTORE

### BG-02 A document that two server versions can write during one rollout keeps every field the writing version does not know, at every level where new fields go, and a document that only its owner writes either does the same or adds fields only, with the rollback loss stated in the spec.

**Why.** An old node that rewrites a shared document drops the field the new version just wrote, and CAS cannot see it because the writes are not concurrent. A per-user document that only its owner writes loses new fields only when users move back to the old version.

Do:

```java
class GardenState {
    int level;
    Map<String, Object> unknown = new HashMap<>();   // the codec fills it on decode
}
String saved = Codec.encode(state);                  // and writes it back on encode
```

Don't:

```java
class GardenState {
    int level;                                       // the codec skips unknown keys
}
String saved = Codec.encode(state);                  // so the save drops them
```

**Check.** For each changed stored class, name its writers across versions. A document that both versions write needs a keep-unknown write path and a round-trip test that loads a document with an extra field, at the level the new field uses, and saves it back intact. When the codec keeps only top-level unknown fields, new fields go at the top level. A document that only its owner writes needs the same path or the rollback note in the spec. The profile's CAP-USERSTORE entry says which documents keep unknown fields and how deep.

- needs: CAP-USERSTORE

### BG-03 A changed meaning gets a new field or a new command id, and an existing or retired id never takes a new meaning.

**Why.** An old client or server reads the reused id with the old meaning and acts on the wrong data.

Do:

```java
static final short CLAIM_REWARD = 4101;
static final short CLAIM_REWARD_V2 = 4105;  // new rules, new id
```

Don't:

```java
static final short CLAIM_REWARD = 4101;     // now claims all tiers at once
```

**Check.** For each changed command, field, or enum value, ask whether an old peer would misread it. If so, it needs a new id. A retired feature keeps its ids and packet shapes and answers with its "not opened" values, because old clients still send them.

- needs: CAP-COMMAND, CAP-USERSTORE

### BG-04 New response and push fields are appended and optional, and existing fields keep their position, type, and meaning.

**Why.** An old client parses fields by position or key and breaks on a moved or retyped field.

Do:

```java
resp.putInt("level", state.level());
resp.putLong("xp", state.xp());
resp.putInt("streak", state.streak());   // appended
```

Don't:

```java
resp.putInt("streak", state.streak());   // inserted first
resp.putString("level", "L" + state.level());
```

**Check.** Compare the response writer before and after the diff. Old fields stay in place with the same type, and new fields come last.

- needs: CAP-RESPONSE

### BG-05 A new request field is optional, and a request without it behaves as it did before the change.

**Why.** Old clients never send the new field, so a required field rejects every old client.

Do:

```java
int amount = req.has("amount") ? req.readInt("amount") : 1;
```

Don't:

```java
int amount = req.readInt("amount");   // fails when the field is absent
```

**Check.** For each new request field, find its default and a test that decodes a request without it.

- needs: CAP-COMMAND

### BG-06 A client older than the change keeps the old behavior of every existing command and never receives a packet it cannot parse.

**Why.** Old clients stay online during the whole rollout, and an unknown packet can crash or desync them.

Do:

```java
if (session.clientVersion() >= config.minClientForStreak()) {
    send(user, new StreakPush(state.streak()));
}
```

Don't:

```java
send(user, new StreakPush(state.streak()));
```

**Check.** Walk the compatibility matrix in the spec and confirm each new push or changed reply has an old-client branch. A new error code counts too. A new code on an existing command, or on the login or reconnect path, reaches every old client, so the spec says how an old client reacts to it.

- needs: CAP-CLIENTVER, CAP-RESPONSE

### BG-07 The server gates each new feature and each changed behavior on the client version that the session reported at login.

**Why.** A server-side switch alone turns the feature on for old clients that cannot show it.

Do:

```java
if (session.clientVersion() < config.minClientVersion()) {
    return ErrorCode.CLIENT_TOO_OLD;
}
```

Don't:

```java
if (!config.isActive()) {
    return ErrorCode.FEATURE_NOT_ACTIVE;
}
```

**Check.** Find the version gate on each new command and changed behavior, and confirm the minimum version comes from config.

- needs: CAP-CLIENTVER

### BG-08 Feature config is readable by both the old and the new server version, so new keys are optional with defaults and no key changes meaning.

**Why.** Both versions load the same config during rollout, so a required new key stops the old version from starting.

Do:

```java
int maxStreak = json.has("maxStreak") ? json.getInt("maxStreak") : 7;
```

Don't:

```java
int maxStreak = json.getInt("maxStreak");
// or: "duration" changed from seconds to minutes
```

The config of an event that is already running does not change during a rolling deploy, because both versions read it at once. Shared runtime config kept in the store follows BG-02 as well.

**Check.** Load the new config with the old loader and the old config with the new loader in a test.

- needs: CAP-CONFIG

### BG-09 Data migration is idempotent and derives its result only from stored data: per-user data migrates lazily on the owner at load, and shared data migrated at boot is written only where the target is absent, so two nodes booting at once and every later boot are safe.

**Why.** A bulk migration races live writes, and a migration that runs twice or reads its own partial output corrupts data. A boot step that overwrites resets live counters each time another node boots.

Do:

```java
if (state.schema < 2) {
    state.xp = state.legacyPoints * 10;
    state.schema = 2;
    state.markChanged();
}
```

Don't:

```java
for (long userId : allUserIds()) {
    UserState s = KvStore.load(userId);
    s.xp = s.legacyPoints * 10;
    KvStore.save(userId, s);
}
KvStore.set(counterKey(code), code.legacyUsed());   // at boot, resets a live counter
```

A schema version field is one way to make a step idempotent, not the only one. A boot step for shared data writes with add-if-absent:

```java
SeedResult seeded = KvStore.addIfAbsent(counterKey(code), code.legacyUsed());   // never overwrites
if (seeded == SeedResult.FAILED) throw new BootFailure("seed " + code.id());      // BG-13
```

**Check.** Each migration step runs on the owner at load, or at boot with add-if-absent writes. A test runs it twice on one fixture, and once on data a newer version already migrated, and compares the results.

- needs: CAP-USERSTORE

### BG-10 A draining node refuses new logins, finishes every queued command, and confirms every save before it releases user ownership, and when the final save fails it keeps ownership, retries, and makes the user's next login wait.

**Why.** If ownership moves before the last save lands, the new owner loads stale data and the player loses progress. A release that deletes the owner record lets a paused old node claim the user again and save over newer data.

Do:

```java
actor.stopAccepting();
actor.awaitQueueEmpty();
StoreWrite saved = KvStore.save(userId, state).confirm();
if (saved != StoreWrite.WRITTEN) {
    pendingFinalSaves.add(userId);   // login answers retry-later, shutdown waits
    retryFinalSave(userId);          // ownership stays with this node
    return;
}
Ownership.release(userId);           // writes a released marker, never a delete
```

Don't:

```java
Ownership.release(userId);
KvStore.saveAsync(userId, state);
```

**Check.** Read the feature's shutdown or handover hook and confirm it saves and waits for the result before release. The core owns the failure path, which the profile's CAP-DRAIN entry records: retry limits per kind of failure, a give-up that still releases, and the pending mark that login and shutdown read.

- needs: CAP-DRAIN, CAP-OWNERSHIP, CAP-USERSTORE

### BG-11 An inbox entry of a type the node does not know stays in the inbox unchanged for a newer version, and a cross-node message carries only a signal, so a node may ignore a message type it does not know.

**Why.** An old node that drops an unknown entry loses a purchase or a gift that a new node sent. Pub/sub drops messages during reconnects anyway, so anything that must arrive goes into the inbox first, and the message only wakes the owner.

Do:

```java
InboxHandler handler = handlers.get(entry.type());
if (handler == null) {
    return Applied.KEEP;   // never removed, not even to be added back
}
// The payload is in the inbox before the message, which only wakes the owner.
Inbox.append(userId, entry);
CrossNode.signal(userId, Signal.INBOX);
```

Don't:

```java
InboxHandler handler = handlers.get(entry.type());
if (handler == null) {
    inbox.remove(entry.id());
    inbox.append(entry);   // lost when this append fails
}
CrossNode.send(userId, new GiftMessage(gift));   // the gift exists only in the message
```

Every refresh that a message triggers also runs on a periodic sweep, so a lost message only delays it. Store inbox payloads as raw text, so every version writes them back unchanged. A shared log that every node replays, such as a market stream, skips an entry it cannot read without blocking, and is trimmed by an age no shorter than the life of what it carries.

**Check.** Find the inbox dispatch, and confirm an unknown type is kept, not removed or acknowledged. For each cross-node send, find the inbox write before it and the sweep that covers a lost message.

- needs: CAP-INBOX, CAP-CROSSNODE

### BG-12 A change to a stored format that the old version cannot read is a one-way door: it ships only in a maintenance deploy, and the spec gives the manual rollback step.

**Why.** Once a key is converted, the old version fails every read of it, so a rollback during a rolling deploy breaks every node still running the old version.

Do:

```java
// Spec, Blue-green: id counters move from a number to a string. One-way.
// Maintenance deploy. Rollback: convert the counter keys back by hand before the old build starts.
KvStore.set(counterKey, String.valueOf(next));
```

Don't:

```java
// Shipped in a rolling deploy: old nodes now fail to parse the counter.
KvStore.set(counterKey, String.valueOf(next));
```

**Check.** For each changed key or document format, ask whether the old version can still read it. If not, the spec marks the release as a maintenance deploy and gives the rollback step.

- needs: CAP-USERSTORE

### BG-13 A feature step that runs at boot, such as a config load, a seed, or a shared-data migration, stops the boot when it fails, so a node never runs or reports healthy with that step undone.

**Why.** A node that boots past a failed step serves players on missing data, can hold leases and claims, and looks healthy to peers that only check its heartbeat.

Do:

```java
static void onBoot() {
    FeatureConfig.loadOrThrow();   // a bad file throws
    GiftCounters.seedOrThrow();    // a failed write throws
}                                  // the core's boot catches it, logs, and exits the process
```

Don't:

```java
try {
    GiftCounters.seed();
} catch (Exception e) {
    log.warn("seed failed", e);    // the node boots on half-seeded counters
}
```

**Check.** Find every boot hook of the feature. Each failure reaches the core's boot failure path, which the profile's CAP-DRAIN entry says exits the process.

- needs: CAP-DRAIN
