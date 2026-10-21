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

**Check.** Diff each stored class and Redis key layout. Any removed, renamed, or retyped field or key is a finding.

- needs: CAP-USERSTORE, CAP-REDIS

### BG-02 Loading and saving a document keeps every field that the running server version does not know.

**Why.** An old node that drops unknown fields on save erases the data the new version just wrote.

Do:

```java
class GardenState {
    int level;
    @JsonAnySetter @JsonAnyGetter
    Map<String, Object> unknown = new HashMap<>();
}
```

Don't:

```java
mapper.configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false);
// unknown fields are read, then dropped on the next save
```

**Check.** Confirm the stored class keeps unknown fields, and that a round-trip test loads a document with an extra field and saves it back intact.

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

**Check.** For each changed command, field, or enum value, ask whether an old peer would misread it. If so, it needs a new id.

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

**Check.** Walk the compatibility matrix in the spec and confirm each new push or changed reply has an old-client branch.

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

**Check.** Load the new config with the old loader and the old config with the new loader in a test.

- needs: CAP-CONFIG

### BG-09 Data migration runs lazily on the owner at load, is idempotent, and records a per-document schema version that only increases.

**Why.** A bulk migration races live writes, and an unversioned one runs twice or skips users.

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
```

**Check.** Find the schema version field and confirm each migration step checks it, sets it, and runs on the owner at load.

- needs: CAP-USERSTORE

### BG-10 A draining node finishes every queued command and confirms every save before it releases user ownership.

**Why.** If ownership moves before the last save lands, the new owner loads stale data and the player loses progress.

Do:

```java
actor.stopAccepting();
actor.awaitQueueEmpty();
KvStore.save(userId, state).confirm();
Ownership.release(userId);
```

Don't:

```java
Ownership.release(userId);
KvStore.saveAsync(userId, state);
```

**Check.** Read the feature's shutdown or handover hook and confirm it saves and waits for the result before release.

- needs: CAP-DRAIN, CAP-OWNERSHIP, CAP-USERSTORE

### BG-11 A node that meets an inbox entry or cross-node message of a type it does not know puts or leaves it unchanged in the user's inbox, so a newer version applies it later.

**Why.** An old node that drops an unknown entry loses a purchase or a gift that a new node sent.

Do:

```java
InboxHandler handler = handlers.get(entry.type());
if (handler == null) {
    return Applied.KEEP;   // left in the inbox for a newer node
}
// A cross-node message of an unknown type goes into the inbox the same way.
if (!handlers.containsKey(msg.type())) Inbox.append(msg.userId(), msg.asEntry());
```

Don't:

```java
InboxHandler handler = handlers.get(entry.type());
if (handler == null) {
    inbox.remove(entry.id());
}
```

**Check.** Find the inbox and message dispatch, and confirm an unknown type is kept, not removed or acknowledged.

- needs: CAP-INBOX, CAP-CROSSNODE
