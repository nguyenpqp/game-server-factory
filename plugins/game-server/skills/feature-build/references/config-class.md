# Config class

Each feature reads its balance from its own JSON file (CFG-01). The config class loads the file, validates it, and publishes one immutable snapshot. A command reads the snapshot once and uses it from start to end (CFG-03).

The real loader, the config directory, the JSON parser, and the reload hook come from the profile's CAP-CONFIG entry. Environment values, such as secrets and allowlists, come from CAP-ENV.

## The class

```java
public final class EventShopConfig {
    static final String FILE = "event-shop.json";

    private static volatile EventShopConfig current;

    private final boolean isActive;
    private final long startMs;
    private final long endMs;
    private final ClientVersion minClientVersion;
    private final Map<String, ShopItem> itemsById;

    private EventShopConfig(RawEventShop raw, Map<String, ShopItem> itemsById) {
        this.isActive = raw.isActive;
        this.startMs = raw.startMs;
        this.endMs = raw.endMs;
        this.minClientVersion = ClientVersion.parse(raw.minClientVersion);
        this.itemsById = Map.copyOf(itemsById);
    }

    public static EventShopConfig current() {
        return current;
    }

    public static void load(FeatureConfig loader) {
        current = parse(loader.read(FILE));
    }

    static EventShopConfig parse(String json) {
        RawEventShop raw = FeatureConfig.fromJson(json, RawEventShop.class);
        return validate(raw);
    }

    static void setForTest(EventShopConfig cfg) {
        current = cfg;
    }

    public boolean isActive(long now) {
        return isActive && now >= startMs && now < endMs;
    }

    public ShopItem item(String id) {
        return itemsById.get(id);
    }

    public ClientVersion minClientVersion() {
        return minClientVersion;
    }
}
```

- `current` is the only mutable static field in the feature (MN-01). `load` builds a whole new snapshot and swaps the reference once, so a reload never leaves a half-built config visible.
- This field is the one mutable static that MN-01 allows. Name the snapshot class with the `Config` suffix, so a reader sees at once that the field holds the config snapshot.
- Every field is `final`, and every collection is a copy made with `Map.copyOf` or `List.copyOf`. Nothing hands out a mutable view.
- `isActive(now)` combines the `isActive` flag with the time window, against the `now` that the command passed in (CFG-04, AUTH-06). A feature with no window drops `startMs` and `endMs`.
- `item(id)` is a map read from an index built at load (PERF-05). Stored data and client packets name entries by this stable id, never by list position (CFG-06).
- Balance numbers, such as prices, limits, rewards, and durations, are keys in the file (CFG-05).
- `setForTest` lets a unit test install a config. The test restores the previous value afterward (TEST-11). Keep it package-private.

## The raw form and validation

```java
static final class RawEventShop {
    boolean isActive;
    long startMs;
    long endMs;
    String minClientVersion = "0.0.0";
    List<RawShopItem> items;
}

static EventShopConfig validate(RawEventShop raw) {
    if (raw.endMs <= raw.startMs)
        throw new ConfigException(FILE, "endMs", "must be after startMs");
    if (raw.items == null || raw.items.isEmpty())
        throw new ConfigException(FILE, "items", "must not be empty");
    Map<String, ShopItem> byId = new HashMap<>();
    for (RawShopItem it : raw.items) {
        String key = "items[" + it.id + "]";
        if (it.id == null || it.id.isBlank())
            throw new ConfigException(FILE, "items[].id", "must not be blank");
        if (byId.containsKey(it.id))
            throw new ConfigException(FILE, key, "duplicate id");
        if (it.dailyLimit < 1)
            throw new ConfigException(FILE, key + ".dailyLimit", "must be 1 or more");
        if (it.maxPerBuy < 1 || it.maxPerBuy > it.dailyLimit)
            throw new ConfigException(FILE, key + ".maxPerBuy", "must be 1 to dailyLimit");
        checkRecord(key + ".price", it.price);
        checkRecord(key + ".reward", it.reward);
        if ((long) it.price.amount() * it.maxPerBuy > Integer.MAX_VALUE
                || (long) it.reward.amount() * it.maxPerBuy > Integer.MAX_VALUE)
            throw new ConfigException(FILE, key + ".maxPerBuy", "times the price or the reward overflows an int");
        byId.put(it.id, ShopItem.from(it));
    }
    return new EventShopConfig(raw, byId);
}

static void checkRecord(String key, Amount record) {
    if (record == null || !ItemCatalog.isKnown(record.id()))
        throw new ConfigException(FILE, key + ".id", "must name a known item");
    if (record.amount() < 1)
        throw new ConfigException(FILE, key + ".amount", "must be 1 or more");
}
```

- Validation runs at load and at reload, never on the first command. A bad file fails startup or the reload, and the message names the file and the key (CFG-02). A failed reload keeps the old snapshot.
- Each check matches a row of the spec's Config schema. Each `Validation` cell becomes one `if`, and each `Index built at load` cell becomes one map.
- Check every referenced id against the catalog it points into, such as item ids, so a typo fails at load.
- Cap each config value that a request field multiplies, so the largest product fits its type, such as the price and the reward times `maxPerBuy` (AUTH-04).
- Every cost and reward is one `{id, amount}` record, such as `"price": { "id": "gem", "amount": 10 }`, read into one record type, so a change of currency is a data edit (CFG-09). A list of records holds a cost or a reward of several items.
- A table of rows is a list whose rows carry an `id`, even when the design has one row today. An option that is not offered is an omitted key, and validation rejects a zero amount, because zero reads as free. Every shop item here has a price and a reward, so `checkRecord` rejects a missing record, and a record that may be left out gets a null check instead. No string packs a list, such as `gold:400;potion:3`, and no key repeats a value that another table owns (CFG-10).
- A known reward type is not enough. `validate` rejects any reward type whose grant can be partial, capped, silently empty, or written without a metric row and trace id (CFG-02, MET-03, MET-04). The profile's CAP-INVENTORY entry names the types whose grant is safe. When it does not say, allow only the types whose grant path you read, and list the reward types you allowed under Follow-ups in the slice report.
- The JSON parser ignores keys it does not know, so an old server reads a file that has a newer key (BG-08). A key that the new version adds is optional, and its default lives on the raw field, like `minClientVersion` above. When the project's parser fails on unknown keys, CAP-CONFIG is `partial`. The slice stops at gate 3 when CAP-CONFIG is `missing`, or when it is `partial` and its `blocker` line names a rule that the slice's rows cite.
- A key never changes meaning. A new meaning gets a new key (BG-08).
- Secrets, allowlists, and endpoints do not go in this file. Read them from the environment config that CAP-ENV names (CFG-07).

## Registration

Call `load` where the profile's CAP-CONFIG entry loads feature configs at startup, and in its reload hook when the project has one. When the project has no reload, a config change needs a restart, and the snapshot shape still holds.
