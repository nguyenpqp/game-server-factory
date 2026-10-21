# Feature config rules

These are the `CFG` rules from [the rule index](index.md), which also gives each rule's severity. Design changes often, so balance lives in config files that designers edit. The examples use generic names. The project profile supplies the real classes.

### CFG-01 Each feature keeps its config in its own file.

**Why.** A shared file couples features, so one designer's edit can break another feature's load.

Do:

```java
FeatureConfig config = FeatureConfig.load(Path.of("config/feature/harvest.json"));
```

Don't:

```java
int harvestXp = GlobalConfig.get().getInt("harvestXp");   // one file for every feature
```

**Check.** Confirm the feature reads one config file of its own, and that no other feature reads it.

- needs: CAP-CONFIG

### CFG-02 Config is validated at load, and an invalid file fails startup or the reload with the file and key named, never the first command.

**Why.** A bad value found on the first command fails for players on live, and a vague error slows the fix.

Do:

```java
static FeatureConfig parse(String file, Json json) {
    FeatureConfig c = new FeatureConfig(json);
    if (c.maxStreak < 1) {
        throw new ConfigException(file + ": maxStreak must be >= 1, got " + c.maxStreak);
    }
    return c;
}
```

Don't:

```java
Reward reward = config.rewards().get(day);   // NullPointerException on the first claim
```

**Check.** Find the validate step in the loader, and confirm each key has a range or reference check that names the file and key.

- needs: CAP-CONFIG

### CFG-03 Loaded config is an immutable snapshot that one reference swap replaces whole, and each command reads one snapshot from start to end.

**Why.** A reload that edits fields in place lets a command read half old and half new values.

Do:

```java
private static volatile FeatureConfig current;

static void reload(FeatureConfig next) { current = next; }

ErrorCode handle(UserState state, Request req, long now) {
    FeatureConfig config = current;   // one read per command
    return HarvestCore.process(state, config, req, now);
}
```

Don't:

```java
current.rewards.clear();
current.rewards.addAll(newRewards);
```

**Check.** Confirm the config class has only final fields and unmodifiable collections, and that the command reads the reference once.

- needs: CAP-CONFIG

### CFG-04 Each feature config has an `isActive` flag and, when the feature is time-bound, a start and an end time checked against server time.

**Why.** Operations must be able to turn a feature off or schedule it without a new build.

Do:

```java
boolean isOpen(long now) {
    return isActive && now >= startMs && now < endMs;
}
```

Don't:

```java
if (LocalDate.now().getMonthValue() == 12) {
    // winter event
}
```

**Check.** Find the `isActive` flag and the time window in the config, and their check at the start of each command.

- needs: CAP-CONFIG, CAP-CLOCK

### CFG-05 Balance numbers, such as costs, rewards, rates, limits, and durations, come from config, never from constants in code.

**Why.** Designers retune balance often, and a number in code needs a build and a deploy to change.

Do:

```java
long growMs = config.cropsById().get(cropId).growMs();
```

Don't:

```java
private static final long GROW_MS = 4 * 60 * 60 * 1000L;
```

**Check.** Search the feature for numeric literals other than 0 and 1, and confirm none is a cost, reward, rate, limit, or duration.

- needs: CAP-CONFIG

### CFG-06 Stored data and client packets refer to config entries by stable id, never by list position.

**Why.** A designer who inserts a row shifts every position, so stored data points at the wrong entry.

Do:

```java
state.setCropId(crop.id());
CropDef crop = config.cropsById().get(state.cropId());
```

Don't:

```java
state.setCropIndex(config.crops().indexOf(crop));
CropDef crop = config.crops().get(state.cropIndex());
```

**Check.** Find every config reference in stored state and packets, and confirm it is an id field from the config row.

- needs: CAP-CONFIG

### CFG-07 Environment-specific values, such as secrets, allowlists, and endpoints, live in environment config, apart from the feature's balance file.

**Why.** Balance files are shared across environments and edited by designers, so a secret there leaks and a live endpoint reaches test.

Do:

```java
String secret = Env.get().secret("payment.callback");
```

Don't:

```java
String secret = config.getString("callbackSecret");   // read from the balance file
```

**Check.** Read the feature config file and confirm it holds no secret, host, allowlist, or per-environment switch.

- needs: CAP-ENV, CAP-CONFIG

### CFG-08 Generated files change only through their generator and its source, never by hand.

**Why.** The next generator run overwrites a hand edit, so the change disappears in a later build.

Do:

```java
// Add the command id to the generator's source sheet, then run the generator.
short id = Commands.HARVEST_CLAIM;
```

Don't:

```java
// Hand edit inside a generated file.
public static final short HARVEST_CLAIM = 4102;
```

**Check.** Compare the diff with the profile's `generated_paths`. A change there needs a matching change in the generator source.

- needs: CAP-GENERATED
