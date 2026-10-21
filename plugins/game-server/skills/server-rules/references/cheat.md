# Cheat command rules

These are the `CHEAT` rules from [the rule index](index.md), which also gives each rule's severity. Cheat commands let testers put an account into any state. They must never run on live. The examples use generic names. The project profile supplies the real classes.

### CHEAT-01 Cheat command handlers are not registered when the server runs on live.

**Why.** An unregistered handler cannot be reached on live, even when a config flag is wrong.

Do:

```java
if (!Env.isLive()) {
    router.register(Commands.CHEAT_RANGE, HarvestCheatHandler.class);
}
```

Don't:

```java
router.register(Commands.CHEAT_RANGE, HarvestCheatHandler.class);
```

**Check.** Find where the feature registers its cheat handler, and confirm the registration sits inside a live check.

- needs: CAP-CHEAT, CAP-ENV

### CHEAT-02 Every cheat command checks the environment at the point of mutation and rejects the request on live.

**Why.** A second check at the mutation still holds when someone registers the handler on live by mistake.

Do:

```java
@CheatCommand
final class CheatSetStreak {
    static ErrorCode process(UserState state, int streak) {
        if (Env.isLive()) return ErrorCode.INVALID_ACTION;
        return StreakCore.setStreak(state, streak);
    }
}
```

Don't:

```java
@CheatCommand
final class CheatSetStreak {
    static ErrorCode process(UserState state, int streak) {
        if (!FeatureConfig.get().cheatEnabled()) return ErrorCode.FEATURE_NOT_ACTIVE;
        return StreakCore.setStreak(state, streak);
    }
}
```

**Check.** Confirm each cheat `process` starts with the profile's live check. The feature-review linter flags cheat classes without it.

- needs: CAP-ENV

### CHEAT-03 Cheat commands live in their own handler and classes, apart from gameplay commands, and each cheat class carries the profile's cheat marker.

**Why.** A cheat branch inside a gameplay handler cannot be left out on live, and the linter cannot find an unmarked cheat.

Do:

```java
@CheatCommand
final class CheatGrowAll { /* ... */ }
```

Don't:

```java
case Commands.HARVEST_CLAIM:
    if (req.readBool("skipTimer")) plot.setReadyAt(0);   // cheat inside gameplay
```

**Check.** Confirm that gameplay classes hold no cheat branch, and that every cheat class has the marker.

- needs: CAP-CHEAT

### CHEAT-04 Cheat commands write metric rows like gameplay commands, under their own action names and with a trace id.

**Why.** Test data from cheats must be separable from real play, and a cheat bug needs a trace like any other.

Do:

```java
String traceId = TraceIds.next();
ErrorCode error = CheatSetStreak.process(state, streak);
MetricLogger.userAction(user, "cheat_streak_set", error, traceId, Extras.of("streak", streak));
```

Don't:

```java
CheatSetStreak.process(state, streak);   // no row
```

**Check.** Confirm each cheat command writes one row with an action name that starts with the cheat prefix and carries a trace id.

- needs: CAP-METRIC, CAP-TRACEID

### CHEAT-05 Each feature ships cheat commands that put a test account into every state the client needs to test.

**Why.** Without them testers wait for real timers or grind for days to reach a state.

Do:

```java
@CheatCommand final class CheatSetStreak { /* any day 0..max */ }
@CheatCommand final class CheatSkipCooldown { /* claim now */ }
@CheatCommand final class CheatResetFeature { /* back to first open */ }
```

Don't:

```java
// Testers set the device clock forward.
```

**Check.** List the states in the spec's state model and match each to a cheat that reaches it.

- needs: CAP-CHEAT

### CHEAT-06 A cheat validates its input and changes state through the feature's own domain methods, so the result passes the feature's invariants.

**Why.** A cheat that writes fields directly can create states the real feature never reaches, so testers chase bugs that cannot happen.

Do:

```java
if (streak < 0 || streak > config.maxStreak()) return ErrorCode.INVALID_PARAM;
return StreakCore.setStreak(state, streak);
```

Don't:

```java
state.streak = req.readInt("streak");
state.lastClaimDay = -1;
```

**Check.** Confirm the cheat bounds its input and calls domain methods instead of setting fields.

- needs: CAP-CHEAT

### CHEAT-07 A time cheat shifts server time for the acting user only, through the server clock, so other users and other nodes keep real time.

**Why.** A global clock shift breaks every other tester's state and can trigger jobs on other nodes.

Do:

```java
ServerClock.setUserOffset(userId, offsetMs);
long now = ServerClock.now(userId);
```

Don't:

```java
ServerClock.setGlobalOffset(offsetMs);
```

**Check.** Confirm the time cheat stores an offset per user and that only that user's commands read it.

- needs: CAP-CLOCK
