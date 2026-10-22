# Client sync rules

These are the `SYNC` rules from [the rule index](index.md), which also gives each rule's severity. The server holds the truth, and the client shows a copy of it. These rules keep that copy correct after a reconnect, a lost reply, or a change the client did not make. They cover replies and pushes to the game client. Admin API responses serve support tools and are out of scope. The examples use generic names. The project profile supplies the real classes.

### SYNC-01 Each client-facing feature has a read command that returns all of its client-visible state, so a reconnected or desynced client rebuilds its view from that one reply.

**Why.** A client that reconnects, misses a reply, or reopens a screen has no other way back to the server's state, so it keeps showing a wrong view until the player logs in again.

Do:

```java
// GetStreakState returns every client-visible field of the feature.
Response.of(CmdIds.STREAK_STATE_GET, Errors.OK)
        .put(Keys.SERVER_TIME, now)
        .put(Keys.STREAK_COUNT, state.streakCount())
        .put(Keys.LAST_CLAIM_DAY, state.lastClaimDay())
        .send(actor);
```

Don't:

```java
// The only copy of the state goes out in a push at login, so a client that
// reconnects or misses the push has nothing to rebuild from.
actor.push(Push.of(Pushes.STREAK_STATE).put(Keys.STREAK_COUNT, state.streakCount()));
```

Don't split the view so that one screen needs several reads, or leave out a part that the client shows. A feature whose only client data is static config and one action needs no read command.

**Check.** List what the feature's screens show. Find one read command whose reply carries all of it, with the server time.

- needs: CAP-COMMAND, CAP-RESPONSE

### SYNC-02 A mutating reply carries server time and the absolute post-change value of only what the command changed, and a reject carries the same fields with their current values.

**Why.** A delta is wrong as soon as a reply is lost or applied twice, and a reply that also restates untouched values can overwrite a newer copy, so the client shows a balance or a count the server does not hold.

Do:

```java
Response.of(CmdIds.EVENT_SHOP_BUY, out.error())
        .put(Keys.SERVER_TIME, now)
        .put(Keys.BOUGHT_TODAY, out.boughtToday())
        .put(Keys.BALANCES, out.balances())   // post-change amounts of the items it moved
        .send(actor);
```

Don't:

```java
Response.of(CmdIds.EVENT_SHOP_BUY, out.error())
        .put(Keys.SPENT, out.price().amount())   // a delta, wrong after a lost or repeated reply
        .put(Keys.WALLET, inv.all())             // every balance, also the ones it did not touch
        .send(actor);
```

Don't answer a reject with the error code alone when the command reads state that the client may hold wrong. The reject carries the current values of the fields the command would change, so the client resyncs from it.

**Check.** For each mutating command, list the fields and balances it changes. The reply carries server time and the post-change value of each one, and nothing else of the state. Each error path carries the same fields with the stored values.

- needs: CAP-RESPONSE, CAP-CLOCK

### SYNC-03 A reply or push carries the stored instant of each timer, never a boolean derived from stored state or both ends of one timer.

**Why.** A derived value is a second copy of the truth that can disagree with the stored value it came from, such as a ready flag that is false while the ready time has passed.

Do:

```java
Response.of(CmdIds.PLOT_INFO, Errors.OK)
        .put(Keys.SERVER_TIME, now)
        .put(Keys.READY_AT, plot.readyAt())   // the instant the state stores
        .send(actor);
```

Don't:

```java
Response.of(CmdIds.PLOT_INFO, Errors.OK)
        .put(Keys.PLANTED_AT, plot.plantedAt())
        .put(Keys.READY_AT, plot.readyAt())             // the second end of one timer
        .put(Keys.READY, now >= plot.readyAt())         // a boolean derived from it
        .send(actor);
```

**Check.** For each reply and push field, find the stored field it comes from. A boolean that compares stored values, config, or server time, and a second instant of a timer that already ships one, are findings.

- needs: CAP-RESPONSE

### SYNC-04 A push reports only a change that the client did not cause, and it is best effort, so no delivery of value depends on it.

**Why.** A client that caused a change reads it from its own reply, so a push for it only adds load, and an offline or reconnecting player misses every push, so value that exists only in a push is lost.

Do:

```java
// Another player's gift: stored in the target's inbox first, then a best-effort notice.
Inbox.append(targetId, new GiftEntry(senderId, giftId, traceId));
CrossNode.push(targetId, new GiftArrivedPush(senderId));
```

Don't:

```java
// The gift exists only in the push, so an offline player never gets it.
CrossNode.push(targetId, new GiftArrivedPush(senderId, giftId));
```

Don't push after the player's own command or at login. The reply carries the change, and the client reads the read command when it starts or reconnects (SYNC-01). A change the client can compute from stored values and server time, such as a countdown that reaches zero, needs no push either.

**Check.** For each push, name the change it reports and who caused it. The acting player's own command, a login, and a time the client can compute are findings. Confirm that what the push reports is also stored, in the user's state or the durable inbox, before the push is sent.

- needs: CAP-RESPONSE, CAP-INBOX
