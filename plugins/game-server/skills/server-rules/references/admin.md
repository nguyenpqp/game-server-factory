# Admin command rules

These are the `ADMIN` rules from [the rule index](index.md), which also gives each rule's severity. Admin commands let operators and support staff read and repair player data on live. The examples use generic names. The project profile supplies the real classes.

### ADMIN-01 Every admin command requires an authenticated admin session, checked on each request.

**Why.** A check only at login lets a revoked or downgraded session keep running admin commands.

Do:

```java
AdminSession admin = AdminAuth.require(session);
if (admin == null || !admin.can(Permission.EDIT_USER)) {
    return ErrorCode.UNAUTHORIZED;
}
```

Don't:

```java
if (session.wasAdminAtLogin()) {
    applyEdit(req);
}
```

**Check.** Confirm every admin command calls the admin auth check and the permission check before any read or write.

- needs: CAP-ADMIN

### ADMIN-02 An admin command that changes a user's state runs on that user's owner, or with CAS on the stored document when the user is offline.

**Why.** An admin write from another thread or node races the owner's save and is lost.

Do:

```java
if (Ownership.isOnline(targetId)) {
    CrossNode.submitToOwner(targetId, s -> StreakCore.setStreak(s, streak));
} else {
    KvStore.casUpdate(userKey(targetId), s -> StreakCore.setStreak(s, streak), 5);
}
```

Don't:

```java
UserState s = KvStore.load(targetId);
s.streak = streak;
KvStore.save(targetId, s);
```

**Check.** For each mutating admin command, find the route to the owner and the CAS path for offline users.

- needs: CAP-ADMIN, CAP-OWNERSHIP, CAP-CROSSNODE, CAP-CAS

### ADMIN-03 Every mutating admin command writes an audit row with the admin, the target, the requested and applied change, the result, and the trace id.

**Why.** Support must answer who changed a player's data, when, and why.

Do:

```java
MetricLogger.audit(admin.name(), targetId, "streak_set",
    Extras.of("requested", streak, "applied", s.streak()), error, traceId);
```

Don't:

```java
log.info("streak set for " + targetId);
```

**Check.** Confirm each mutating admin command writes one audit row on success and on failure with every listed field.

- needs: CAP-ADMIN, CAP-METRIC, CAP-TRACEID

### ADMIN-04 On live, a destructive admin command, such as a delete, a reset, or an overwrite of user data, is blocked or requires an explicit confirmation field.

**Why.** One mistyped user id on a reset command wipes a real player's progress.

Do:

```java
if (Env.isLive() && !String.valueOf(targetId).equals(req.readString("confirmUserId"))) {
    return ErrorCode.CONFIRM_REQUIRED;
}
```

Don't:

```java
StreakCore.reset(state);
```

**Check.** List the destructive admin commands and confirm each has a live block or a confirmation field.

- needs: CAP-ADMIN, CAP-ENV

### ADMIN-05 Each admin command has an entry in the feature's admin API spec with its request fields, response fields, errors, and required permission.

**Why.** Tool builders and support staff call admin commands from the spec, not from the code.

Do:

```java
// Spec row: streak.set, request {userId, streak}, response {streak},
// errors {NOT_FOUND, INVALID_PARAM}, permission EDIT_USER.
static final short ADMIN_STREAK_SET = 9101;
```

Don't:

```java
static final short ADMIN_STREAK_SET = 9101;   // no spec entry
```

**Check.** Match each admin command in the diff to a row in the spec's admin API table.

- needs: CAP-ADMIN

### ADMIN-06 An admin command validates its target, ranges, and referenced ids before any effect, as a gameplay command does.

**Why.** An admin typo with no validation writes invalid state that the game cannot load.

Do:

```java
if (!KvStore.exists(userKey(targetId))) return ErrorCode.NOT_FOUND;
if (streak < 0 || streak > config.maxStreak()) return ErrorCode.INVALID_PARAM;
```

Don't:

```java
CrossNode.submitToOwner(targetId, s -> s.streak = req.readInt("streak"));
```

**Check.** Confirm each admin command checks the target and every field before the first effect.

- needs: CAP-ADMIN, CAP-ERRORS

### ADMIN-07 A retried mutating admin command has no second effect.

**Why.** Admin tools retry on timeout, so an additive grant pays out twice.

Do:

```java
// An absolute set is safe to repeat.
StreakCore.setStreak(state, streak);
// An additive grant applies each request id once.
if (!state.appliedAdminRequests().add(requestId)) return ErrorCode.SUCCESS;
inventory.addGems(amount, Reason.ADMIN_GRANT, traceId);
```

Don't:

```java
inventory.addGems(amount, Reason.ADMIN_GRANT, traceId);
```

**Check.** For each mutating admin command, ask what a second identical call does, and find the absolute set or the request id guard.

- needs: CAP-ADMIN

### ADMIN-08 Each feature ships admin commands that read and repair its per-user state for support.

**Why.** Without them support edits the database by hand, which skips validation, the owner, and the audit row.

Do:

```java
static final short ADMIN_STREAK_GET = 9100;
static final short ADMIN_STREAK_SET = 9101;
static final short ADMIN_STREAK_RESET = 9102;
```

Don't:

```java
// Support fixes streaks by editing the document in the database console.
```

**Check.** Confirm the feature has an admin read of its state and a repair command for each support case in the spec.

- needs: CAP-ADMIN
