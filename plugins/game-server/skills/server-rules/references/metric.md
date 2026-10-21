# Metric rules

These are the `MET` rules from [the rule index](index.md), which also gives each rule's severity. Metric rows answer support tickets and KPI questions, so every action must be traceable. The examples use generic names. The project profile supplies the real classes.

### MET-01 Every user action command writes exactly one user action row, on success and on each failure, with the result code.

**Why.** Without failure rows nobody can tell why players fail, and duplicate rows inflate counts.

Do:

```java
ErrorCode error = ErrorCode.NOT_INIT;
try {
    error = HarvestCore.process(state, config, req, now);
} finally {
    MetricLogger.userAction(user, "harvest_claim", error, traceId, extras);
}
```

Don't:

```java
ErrorCode error = HarvestCore.process(state, config, req, now);
if (error == ErrorCode.SUCCESS) {
    MetricLogger.userAction(user, "harvest_claim", error, traceId, extras);
}
```

**Check.** Trace each return path of the command and confirm it passes one `userAction` call with the result code. The feature-review linter flags command classes with no metric call.

- needs: CAP-METRIC, CAP-ERRORS

### MET-02 Each user action mints one trace id, and every metric row that the action writes carries it.

**Why.** The trace id is the only way to join the rows of one action across tables during a support case.

Do:

```java
String traceId = TraceIds.next();
MetricLogger.userAction(user, "craft", error, traceId, extras);
MetricLogger.system("craft_queue", traceId, queueExtras);
```

Don't:

```java
MetricLogger.userAction(user, "craft", error, TraceIds.next(), extras);
MetricLogger.system("craft_queue", TraceIds.next(), queueExtras);
```

**Check.** Confirm the command calls `TraceIds.next()` once and passes that value to every row. The feature-review linter flags command classes with no trace id.

- needs: CAP-TRACEID, CAP-METRIC

### MET-03 Every currency and inventory change carries the trace id of the action that caused it.

**Why.** A gem change without a trace id cannot be tied to the purchase or reward that caused it.

Do:

```java
inventory.spendGems(cost, Reason.SPEEDUP, traceId);
```

Don't:

```java
inventory.spendGems(cost);
```

**Check.** Find every call that changes currency or items, and confirm each passes the action's trace id.

- needs: CAP-INVENTORY, CAP-TRACEID

### MET-04 Every currency and item source and sink is logged with its amount and a reason constant unique to the feature action.

**Why.** Economy reports group by reason, so a shared or missing reason hides where currency enters and leaves.

Do:

```java
inventory.add(Item.GOLD, reward, Reason.HARVEST_CLAIM, traceId);
inventory.take(Item.SEED, 1, Reason.HARVEST_PLANT, traceId);
```

Don't:

```java
inventory.add(Item.GOLD, reward, Reason.OTHER, traceId);
```

**Check.** Find every source and sink in the feature, and confirm each uses its own reason constant that no other action uses.

- needs: CAP-INVENTORY, CAP-METRIC

### MET-05 Each funnel step of the feature has its own metric action, so a query can count drop-off between steps.

**Why.** One action name for every step hides where players stop.

Do:

```java
MetricLogger.userAction(user, "streak_open", error, traceId, extras);
MetricLogger.userAction(user, "streak_claim", error, traceId, extras);
```

Don't:

```java
MetricLogger.userAction(user, "streak", error, traceId, extras);
```

**Check.** Match the funnel in the spec to the action names in code, one action per step.

- needs: CAP-METRIC

### MET-06 The spec ships a KPI query for each success measure of the feature, written against the profile's metric tables.

**Why.** A feature without a ready query ships with no way to judge whether it worked.

Do:

```sql
SELECT CAST(time AS DATE) AS day, COUNT(DISTINCT user_id) AS claimers
FROM user_action
WHERE action = 'streak_claim' AND result = 0
GROUP BY day;
```

Don't:

```java
// KPI: claim rate. Query to be written after launch.
```

**Check.** For each success measure in the spec, find its query and confirm the table, action names, and columns exist.

- needs: CAP-METRIC

### MET-07 New metric data goes into free extra fields, never into new fixed columns, and the spec states the meaning of each extra.

**Why.** A new fixed column breaks the pipeline that maps columns by position into the warehouse.

Do:

```java
Extras extras = Extras.of("day", day, "rewardId", reward.id());
MetricLogger.userAction(user, "streak_claim", error, traceId, extras);
```

Don't:

```java
MetricLogger.userAction(user, "streak_claim", error, traceId, day, reward.id());   // new columns
```

**Check.** Confirm the row layout is unchanged and each extra has a line in the spec's metric table.

- needs: CAP-METRIC

### MET-08 An unexpected exception writes an exception row with the trace id, and the command still answers with an error code.

**Why.** A swallowed exception leaves no trace, and a command with no reply leaves the client waiting.

Do:

```java
try {
    error = HarvestCore.process(state, config, req, now);
} catch (Exception e) {
    MetricLogger.exception(user, "harvest_claim", traceId, e);
    error = ErrorCode.EXCEPTION;
}
send(user, Response.of(cmdId, error));
```

Don't:

```java
try {
    error = HarvestCore.process(state, config, req, now);
} catch (Exception e) {
    e.printStackTrace();
    return;
}
```

**Check.** Find the catch in the command, and confirm it writes an exception row with the trace id and still sends a reply.

- needs: CAP-METRIC, CAP-TRACEID, CAP-ERRORS

### MET-09 Metric rows and logs never contain secrets, tokens, signatures, or payment credentials.

**Why.** Metric data is copied to many systems and read by many people, so a token in a row is a leaked token.

Do:

```java
Extras extras = Extras.of("txId", callback.transactionId(), "product", callback.productId());
```

Don't:

```java
Extras extras = Extras.of("body", rawBody, "signature", request.header("X-Signature"));
```

**Check.** Read every extra and log line in the diff, and confirm none holds a token, signature, secret, raw callback body, or card data.

- needs: CAP-METRIC
