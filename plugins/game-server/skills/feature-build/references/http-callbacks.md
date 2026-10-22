# HTTP callbacks

An HTTP endpoint serves only callers that cannot log in to the game channel, such as a payment provider or a platform webhook (HTTP-01). The callback never changes user state. It checks the call, takes an idempotency lock, and appends an entry to the user's durable inbox. The user's owner applies the entry once (HTTP-05).

The real HTTP server comes from the profile's CAP-HTTP entry, the secret and the allowlist from CAP-ENV, the lock from CAP-REDIS, and the inbox from CAP-INBOX.

## The order of checks

1. The caller IP is on the allowlist. On live, an empty allowlist rejects every call (HTTP-03).
2. The signature over the raw body matches, with the per-environment secret, and the timestamp is fresh (HTTP-02).
3. The payload matches server data, such as the user id, the product id, the price, the currency, and the expiry (HTTP-06).
4. The idempotency lock on the external transaction id is free (HTTP-04).
5. The inbox append succeeds, and the owner gets a notice.

Nothing before step 4 has an effect, so a rejected call needs no cleanup.

## The handler

```java
public final class ShopPaymentCallback implements HttpEndpoint {
    static final String ACTION = "event_shop_payment_callback";
    static final long MAX_AGE_MS = 300_000;
    static final long LOCK_TTL_MS = 86_400_000;

    private final RedisOps redis;
    private final Inbox inbox;

    ShopPaymentCallback(RedisOps redis, Inbox inbox) {
        this.redis = redis;
        this.inbox = inbox;
    }

    @Override
    public HttpReply handle(HttpCall call) {
        String traceId = TraceIds.next();
        Verdict v;
        try {
            v = process(call, PaymentEnv.current(), ShopCatalog.current(), redis, inbox,
                    Env.isLive(), ServerClock.now(), traceId);
        } catch (RuntimeException e) {
            MetricLogger.exception(0, ACTION, traceId, e);
            v = Verdict.retry("exception");
        }
        MetricLogger.userAction(v.userId(), ACTION, v.code(), traceId, v.transactionId(), v.reason());
        return HttpReply.status(v.status());
    }

    static Verdict process(HttpCall call, PaymentEnv env, ShopCatalog catalog, RedisOps redis,
                           Inbox inbox, boolean live, long now, String traceId) {
        if (live && env.allowlist().isEmpty())
            return Verdict.forbidden("empty allowlist");
        if (!env.allowlist().isEmpty() && !env.allowlist().contains(call.remoteIp()))
            return Verdict.forbidden("caller not allowed");
        String signature = call.header("X-Signature");
        String expected = Hmac.sha256Hex(env.secret(), call.rawBody());
        if (signature == null
                || !MessageDigest.isEqual(expected.getBytes(UTF_8), signature.getBytes(UTF_8)))
            return Verdict.unauthorized("bad signature");
        PaymentNotice p = PaymentNotice.parse(call.rawBody());
        if (p == null || Math.abs(now - p.timestampMs()) > MAX_AGE_MS)
            return Verdict.badRequest("bad or stale payload");
        Product product = catalog.product(p.productId());
        if (product == null || product.priceMinor() != p.amountMinor()
                || !product.currency().equals(p.currency()))
            return Verdict.badRequest("payload does not match product", p);

        String lockKey = "{pay:" + p.transactionId() + "}:lock";
        if (!redis.setNx(lockKey, "pending:" + traceId, LOCK_TTL_MS)) {
            String held = redis.get(lockKey);
            return held != null && held.startsWith("done")
                    ? Verdict.duplicate(p)
                    : Verdict.retry("in flight", p);
        }
        boolean appended = inbox.append(p.userId(),
                InboxEntry.of(p.transactionId(), ShopPurchaseEntry.TYPE,
                        Map.of("reward", product.reward().encode(), "traceId", traceId)));
        if (!appended) {
            redis.del(lockKey);
            return Verdict.retry("inbox append failed", p);
        }
        redis.set(lockKey, "done:" + traceId, LOCK_TTL_MS);
        CrossNode.notifyOwner(p.userId(), Inbox.NOTICE);
        return Verdict.delivered(p);
    }
}
```

- The comparison of signatures is constant-time, with `MessageDigest.isEqual`. A plain `equals` leaks timing.
- `call.rawBody()` is the exact bytes the caller signed. Never sign a re-serialized object.
- The secret, the allowlist, and the endpoint live in environment config, apart from the feature's balance file (CFG-07). The real names come from CAP-ENV.
- The lock is a Redis `SET NX` with a TTL, keyed by the external transaction id. It is kept on success and released when the delivery fails, so the caller's retry runs again (HTTP-04). A lock left `pending` by a crash expires with its TTL, and the inbox entry id stops a second effect if the first append did land.
- The status answers the caller's retry question (HTTP-08). Delivered and duplicate answer 200. A bad payload answers 400. A bad signature answers 401. A forbidden caller answers 403. An in-flight duplicate, a failed append, or an exception answers 503, so the caller retries.
- The metric row holds the transaction id, the user id, the result, and the trace id (HTTP-07). It never holds the secret, the signature, the raw body, or payment credentials (MET-09).
- `ServerClock.now()` here is node time with no user offset, because no user session exists yet.
- The handler runs on an HTTP worker thread, not on a user actor. The Redis and inbox calls are I/O, and they must not run on any user actor thread (PERF-01). A blocking call in this class is expected. Keep it, and report it under Sweep as kept.

## The inbox entry

```java
public final class ShopPurchaseEntry implements InboxEntryHandler {
    public static final String TYPE = "event_shop_purchase";

    @Override
    public int apply(UserActor actor, InboxEntry entry) {
        EventShopState state = actor.state(EventShopState.class);
        if (state.hasApplied(entry.id()))
            return Errors.OK;
        Reward reward = Reward.decode(entry.getString("reward"));
        String traceId = entry.getString("traceId");
        actor.inventory().add(reward, "EVENT_SHOP_PURCHASE", traceId);
        state.markApplied(entry.id());
        state.markChanged();
        MetricLogger.userAction(actor.userId(), "event_shop_purchase_apply", Errors.OK, traceId,
                entry.id());
        return Errors.OK;
    }
}
```

- The entry id is the external transaction id, so a second append of the same payment is a duplicate that the apply skips.
- The callback writes the reward into the entry from server data, after the payload check. The apply then needs no catalog lookup, and a config change between the callback and the login cannot change what the player bought.
- The owner applies the entry on its actor thread, at login or on the notice. It records the applied id in the user's document, in a capped list, so a replay after a crash has no second effect (TEST-09). The entry carries the callback's trace id, so the grant and the callback rows join on one id (MET-03).
- Register the entry type with CAP-INBOX at startup. The core's drain removes an entry only after its effect is saved, and it leaves an entry of a type it does not know in the inbox for a newer version (BG-11). Both are CAP-INBOX duties. When the profile shows either one missing, the slice stops at gate 3.
- A new entry type is a new string. An existing type never changes the meaning of its fields (BG-03).
