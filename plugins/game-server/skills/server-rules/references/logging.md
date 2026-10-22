# Logging rules

These are the `LOG` rules from [the rule index](index.md), which also gives each rule's severity. Log lines are for the engineer who debugs a failure. Metric rows record player actions, and the MET rules cover them. The examples use generic names, with `FeatureLogs` for the logger factory. The project profile's CAP-METRIC entry supplies the real one.

### LOG-01 Feature code logs only through the logger that the profile's CAP-METRIC entry gives each feature, never through a print call or a logger it names itself.

**Why.** A print or a logger with a name of its own bypasses the log sink and the per-feature level config, so the line is missing, or cannot be turned up, when on-call needs it.

Do:

```java
private static final Logger log = FeatureLogs.of(EventShopFeature.class);
```

Don't:

```java
System.out.println("buy failed for " + userId);   // no level, no sink
private static final Logger log = LoggerFactory.getLogger(BuyShopItem.class);   // outside the feature's level config
```

Don't call `printStackTrace` or write a log file by hand either.

**Check.** Search the feature for `System.out`, `System.err`, `printStackTrace`, and logger factories other than the profile's. Each one is a finding.

- needs: CAP-METRIC

### LOG-02 Each log line's level follows its consequence, with error for a durable loss or a broken invariant, warn for a handled failure, info for a rare state change, and debug for tracing.

**Why.** The level decides who sees a line. An error for a handled failure teaches on-call to ignore errors, and a loss logged at debug is off in production.

Do:

```java
log.error("inbox append failed for user {} trace {}; the gift is not stored", targetId, traceId, e);
log.warn("gift push failed for user {} trace {}; the gift is stored in the inbox", targetId, traceId, e);
```

Don't:

```java
log.error("gift push failed for user {} trace {}", targetId, traceId, e);    // handled, nothing lost
log.debug("inbox append failed for user {} trace {}", targetId, traceId, e); // a loss, off in production
```

Don't leave out what the failure cost. A message that says whether the value was stored or lost tells the reader which level it needs.

**Check.** For each log call, name what failed and what it cost. Error means stored data or player value was lost or an invariant broke. Warn means the code handled the failure. Any other pairing is a finding.

- needs: CAP-METRIC

### LOG-03 A log call that reports an exception passes the exception as its last argument, never only its message.

**Why.** The message alone drops the stack trace and the cause chain, so the line says that something failed but not where.

Do:

```java
log.warn("grant failed for user {} trace {}; the cost was refunded", userId, traceId, e);
```

Don't:

```java
log.warn("grant failed: " + e.getMessage());   // the stack trace is gone
```

Don't build the message by string concatenation. Placeholders skip the formatting when the level is off.

**Check.** Find each log call inside a catch block. The caught exception is its last argument.

- needs: CAP-METRIC

### LOG-04 Each log line about a user's action carries the user id and the trace id of that action.

**Why.** Without the user id and the trace id, nobody can join the line to the player's support ticket or to the metric rows of the same action.

Do:

```java
log.warn("claim refund failed for user {} trace {}", userId, traceId, e);
```

Don't:

```java
log.warn("claim refund failed", e);   // no way to find the player or the metric rows
```

Don't log a token, a session key, or a payment credential to identify the player (MET-09). The user id is enough.

**Check.** For each log call on a command, job, callback, or inbox path, find the user id and the trace id among its arguments.

- needs: CAP-METRIC, CAP-TRACEID

### LOG-05 A command writes no log line on its success path.

**Why.** One line per successful command, times every player, floods the log and hides the lines that matter, and the metric row already records each success.

Do:

```java
MetricLogger.userAction(actor.userId(), ACTION, out.error(), traceId);   // each success is a metric row
```

Don't:

```java
log.info("user {} bought {}", userId, itemId);   // one line per success, per player
```

**Check.** Find the log calls on the success path of each command. Each one at info or above is a finding.

- needs: none

### LOG-06 Code comments, log messages, and exception messages cite no rule id and no document name, and state the reason in their own words.

**Why.** The reader of the code or the log has no rulebook open, and ids and file names change, so a cited id explains nothing and can later point at the wrong rule.

Do:

```java
// Reject on live before any state change, because a cheat must never run there.
if (Env.isLive()) return Errors.INVALID_ACTION;
```

Don't:

```java
// CHEAT-02, see cheat.md
if (Env.isLive()) return Errors.INVALID_ACTION;
throw new IllegalStateException("breaks MN-12, see multi-node.md");
```

**Check.** Search the comments, log messages, and exception messages in the diff for rule ids and document names. Each one is a finding.

- needs: none
