# HTTP callback rules

These are the `HTTP` rules from [the rule index](index.md), which also gives each rule's severity. The HTTP channel serves outside callers, such as payment providers, that never log in to the game. The examples use generic names. The project profile supplies the real classes.

### HTTP-01 An HTTP endpoint serves only callers that cannot log in to the game channel, such as payment providers and platform webhooks.

**Why.** An HTTP endpoint skips login, sessions, the actor, and rate limits, so every player action there is a bypass.

Do:

```java
http.post("/callback/payment", PaymentCallback::handle);
```

Don't:

```java
http.post("/api/claimReward", req -> ClaimCore.claim(req.param("userId")));
```

**Check.** For each new endpoint, name the outside caller. A game client as the caller is a finding.

- needs: CAP-HTTP

### HTTP-02 Each request's signature is verified over the raw body with a per-environment secret, and a stale timestamp is rejected, before any effect.

**Why.** An unsigned or replayed callback lets anyone grant themselves a purchase.

Do:

```java
byte[] body = req.rawBody();
String expected = Hmac.sha256Hex(Env.get().secret("payment.callback"), body);
if (!MessageDigest.isEqual(expected.getBytes(UTF_8), req.header("X-Signature").getBytes(UTF_8))) {
    return Http.status(401);
}
if (Math.abs(ServerClock.now() - req.longHeader("X-Timestamp")) > MAX_SKEW_MS) {
    return Http.status(401);
}
```

Don't:

```java
Json json = Json.parse(req.rawBody());
String expected = Hmac.sha256Hex(SECRET, json.toString());   // re-serialized body
if (!expected.equals(req.header("X-Signature"))) return Http.status(401);
```

**Check.** Confirm the signature uses the raw bytes, a secret from environment config, a constant-time compare, and a timestamp window, all before any effect.

- needs: CAP-HTTP, CAP-ENV

### HTTP-03 On live, the caller allowlist is non-empty, and an empty allowlist rejects every call.

**Why.** An allowlist that means allow all when empty opens the endpoint to everyone after one config slip.

Do:

```java
Set<String> allow = Env.get().allowlist("payment.callback");
if (!allow.contains(req.remoteIp())) {   // an empty set rejects every caller
    return Http.status(403);
}
```

Don't:

```java
if (!allow.isEmpty() && !allow.contains(req.remoteIp())) {
    return Http.status(403);
}
```

**Check.** Read the allowlist branch and confirm an empty list on live rejects the call. Check the live environment config has entries.

- needs: CAP-HTTP, CAP-ENV

### HTTP-04 Each callback takes an idempotency lock on the external transaction id before any effect, keeps it on success, and releases it on failure.

**Why.** Providers resend callbacks, so without the lock one payment delivers twice.

Do:

```java
String lock = "{pay:" + txId + "}:lock";
if (!RedisOps.setNx(lock, traceId, LOCK_TTL)) {
    return alreadyHandled(txId);
}
try {
    deliver(callback, traceId);
} catch (RuntimeException e) {
    RedisOps.del(lock);
    throw e;
}
```

Don't:

```java
deliver(callback, traceId);
RedisOps.set("{pay:" + txId + "}:done", "1");
```

**Check.** Confirm the lock is taken before any effect, kept after success, and released on each failure path.

- needs: CAP-REDIS

### HTTP-05 A callback never changes user state directly, and it delivers through the user's durable inbox, which the owner applies once.

**Why.** The HTTP thread does not own the user, so a direct write races the owner and can be lost.

Do:

```java
Inbox.append(userId, new PurchaseEntry(txId, productId, traceId));
CrossNode.notifyOwner(userId);
```

Don't:

```java
UserState state = KvStore.load(userId);
state.addGems(product.gems());
KvStore.save(userId, state);
```

**Check.** Confirm the callback writes only the inbox, and the inbox apply on the owner skips an entry id it has applied.

- needs: CAP-INBOX

### HTTP-06 A callback checks the business payload, such as the user id, product id, price, currency, and expiry, against server data before delivery.

**Why.** A valid signature proves the sender, not that the price and product match what the server sells.

Do:

```java
Product product = ShopConfig.get().productsById().get(callback.productId());
if (product == null
        || product.priceMinor() != callback.amountMinor()
        || !product.currency().equals(callback.currency())
        || callback.expiresAt() < ServerClock.now()) {
    return reject(callback, ErrorCode.INVALID_PARAM);
}
```

Don't:

```java
Inbox.append(callback.userId(), new PurchaseEntry(callback.txId(), callback.productId(), traceId));
```

**Check.** Confirm each payload field is compared with server config or stored data before the inbox write.

- needs: CAP-CONFIG

### HTTP-07 Every callback writes a metric row with the transaction id, the user id, the result, and the trace id.

**Why.** Payment support starts from the transaction id, and a missing row means a lost purchase cannot be traced.

Do:

```java
MetricLogger.system("payment_callback", traceId,
    Extras.of("txId", txId, "userId", userId, "result", error));
```

Don't:

```java
if (error == ErrorCode.SUCCESS) log.info("paid " + txId);
```

**Check.** Confirm each exit of the callback, including rejects, writes one row with all four fields.

- needs: CAP-METRIC, CAP-TRACEID

### HTTP-08 The response status tells the caller whether to retry, and a duplicate of a delivered call gets a success answer.

**Why.** A provider that gets an error for a delivered call retries forever, and one that gets success for a failure never retries.

Do:

```java
if (alreadyDelivered(txId)) return Http.status(200);
if (transientFailure) return Http.status(503);
if (invalidPayload) return Http.status(400);
return Http.status(200);
```

Don't:

```java
return Http.status(200);   // on every path
```

**Check.** Map each exit of the callback to its status, and confirm duplicates get success and transient errors get a retry status.

- needs: CAP-HTTP
