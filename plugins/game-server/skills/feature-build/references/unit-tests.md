# Unit tests

Tests come first in each slice. They call the pure core with in-memory state, an injected clock, and an injected RNG, so they run with no network, socket, or database (TEST-01). Each test class runs with the profile's `test_one_cmd`.

The real test framework, the in-memory state builders, and the hooks that set config, time, random numbers, environment, and metric capture come from the profile's CAP-UNITTEST entry. When the entry has no way to build per-user state without a database, CAP-UNITTEST is `partial`. The slice stops at gate 3 when CAP-UNITTEST is `missing`, or when it is `partial` and its `blocker` line names a rule that the slice's rows cite.

## Layout

- Tests live under `test_root`, in the same package as the code under `feature_root`, so they can call package-private `process`, `parse`, and `setForTest`.
- One test class per command, named after it, such as `BuyShopItemTest`.
- One class for the config, such as `EventShopConfigTest`.
- One class for the cheats, such as `EventShopCheatTest`.
- One class for stored-data compatibility, such as `EventShopStateCompatTest`.
- One class per HTTP endpoint and per inbox entry type.
- The class names and cases match the rows of the spec's Test plan.

## Fixtures

```java
class BuyShopItemTest {
    static final long NOW = 1_767_225_600_000L;
    static final String TRACE = "trace-1";

    EventShopConfig previous;
    EventShopConfig cfg;
    EventShopState state;
    FakeInventory inv;

    @BeforeEach
    void setUp() {
        previous = EventShopConfig.current();
        cfg = EventShopConfig.parse(Fixtures.read("event-shop.valid.json"));
        EventShopConfig.setForTest(cfg);
        state = new EventShopState();
        state.migrate(NOW);
        inv = new FakeInventory().give("gem", 100);
    }

    @AfterEach
    void restore() {
        EventShopConfig.setForTest(previous);
    }

    Outcome buy(String requestId, String itemId, int quantity, String clientVersion, long now) {
        BuyRequest req = new BuyRequest(Errors.OK, requestId, itemId, quantity);
        return BuyShopItem.process(state, cfg, inv, req, ClientVersion.parse(clientVersion), now, TRACE);
    }
}
```

- Time is a fixed `long`. A time case passes a different `now`, such as `NOW + DAY_MS`. No test sleeps or reads the real clock (TEST-02).
- Random draws come from a seeded or scripted `GameRandom` that the test passes to `process`, so each random outcome has its own test (TEST-02).
- The config comes from a fixture JSON file through the real `parse`, so every test also runs validation.
- `FakeInventory` implements the core's `Inventory` interface in memory and records each change with its reason and trace id. When the project ships its own test inventory, use that instead.
- A test that sets global state, such as the config instance, the clock offset, or the environment, restores it in `@AfterEach` (TEST-11).

## Cases per command

```java
@Test
void buysOneItemAndRecordsTheDay() {
    Outcome out = buy("req-00001", "potion", 1, "1.5.0", NOW);

    assertEquals(Errors.OK, out.error());
    assertEquals(90, inv.count("gem"));
    assertEquals(1, inv.count("potion"));
    assertEquals(Map.of("gem", 90L, "potion", 1L), out.balances());
    assertEquals(1, state.boughtOn("potion", ServerClock.dayOf(NOW)));
    assertEquals(List.of("EVENT_SHOP_BUY"), inv.reasons());
    assertEquals(Set.of(TRACE), inv.traceIds());
}

@Test
void rejectsWhenDailyLimitIsReached() {
    for (int i = 0; i < 3; i++)
        buy("req-0000" + i, "potion", 1, "1.5.0", NOW);
    String before = Json.write(state);
    int gems = inv.count("gem");

    Outcome out = buy("req-00009", "potion", 1, "1.5.0", NOW);

    assertEquals(Errors.DAILY_LIMIT, out.error());
    assertEquals(3, out.boughtToday());
    assertEquals(before, Json.write(state));
    assertEquals(gems, inv.count("gem"));
}

@Test
void limitResetsOnTheNextServerDay() {
    for (int i = 0; i < 3; i++)
        buy("req-0000" + i, "potion", 1, "1.5.0", NOW);

    assertEquals(Errors.OK, buy("req-00009", "potion", 1, "1.5.0", NOW + DAY_MS).error());
}

@Test
void replayOfOneRequestIdGrantsOnce() {
    Outcome first = buy("req-00001", "potion", 1, "1.5.0", NOW);
    Outcome second = buy("req-00001", "potion", 1, "1.5.0", NOW);

    assertEquals(first, second);
    assertEquals(1, inv.count("potion"));
    assertEquals(90, inv.count("gem"));
}

@Test
void refundsTheCostWhenTheGrantFails() {
    inv.failNextAdd();

    Outcome out = buy("req-00001", "potion", 1, "1.5.0", NOW);

    assertEquals(Errors.GRANT_FAILED, out.error());
    assertEquals(100, inv.count("gem"));
    assertEquals(List.of("EVENT_SHOP_BUY", "EVENT_SHOP_BUY_REFUND"), inv.reasons());
}
```

Write these cases for every command.

- The main flow, asserting the response fields, the state change, and each inventory change with its reason and trace id (MET-03, MET-04). The response fields include the post-change values the command changed (SYNC-02).
- One negative case per row of the spec's Checks table. It asserts the error code, the stored values that the spec's `Reject` line names, an unchanged state, and an unchanged inventory (TEST-03, AUTH-10, SYNC-02). Compare the serialized state before and after, so a stray change to any field fails the test.
- Each time case with the clock injected, such as before the window, after it, the day boundary, and a cooldown that is not over (TEST-02).
- Each random outcome with the RNG scripted (TEST-02).
- A replay of one request id that asserts one effect (TEST-09).
- A grant failure that asserts the refund, for each command that takes a cost (AUTH-07).
- For a claim or grant command, a claim in each terminal state of the feature, such as finished, expired, or closed, that asserts the error code and no grant (AUTH-06).
- A request from an old client that lacks the new fields, decoded through `parse`, that asserts the old behavior (TEST-07). When the feature's minimum client is newer than the session's, assert `CLIENT_TOO_OLD` and no change (BG-07).

## Metric rows

Assert one action row per command call, on success and on each error, with the action name, the result code, the trace id, and the extras from the spec (TEST-08, MET-01). Use the capture hook that the profile's CAP-UNITTEST or CAP-METRIC entry names, around the shell's `run`. A profile with no capture hook has CAP-UNITTEST as `partial`. The slice stops at gate 3 when CAP-UNITTEST is `missing`, or when it is `partial` and its `blocker` line names a rule that the slice's rows cite. When the spec's Core blockers row for it is resolved, assert the outcome fields that the row is built from, and name that row in the slice report. Never add a static list of rows to feature code to make the test possible (MN-01).

## Cheats

```java
@Test
void cheatIsRejectedOnLive() {
    String before = Json.write(state);

    int error = CheatSetPurchases.process(state, cfg, "potion", 2, true, NOW);

    assertEquals(Errors.INVALID_ACTION, error);
    assertEquals(before, Json.write(state));
}
```

Each cheat has a live case that asserts the rejection and no change (TEST-04), and an off-live case that asserts the state it sets.

## Config validation

```java
@Test
void rejectsMaxPerBuyAboveDailyLimit() {
    ConfigException e = assertThrows(ConfigException.class,
            () -> EventShopConfig.parse(Fixtures.read("event-shop.max-per-buy-too-high.json")));

    assertEquals("event-shop.json", e.file());
    assertEquals("items[potion].maxPerBuy", e.key());
}

@Test
void ignoresAKeyItDoesNotKnow() {
    EventShopConfig parsed = EventShopConfig.parse(Fixtures.read("event-shop.extra-key.json"));

    assertNotNull(parsed.item("potion"));
}
```

One test loads a valid file. One test per validation rule loads a file that breaks only that rule, and asserts the file and the key in the error (TEST-05, CFG-02). One test loads a file with an extra key and asserts that it loads, so an old server reads a newer file (BG-08). When the config names reward types, one test loads a reward type that `validate` must reject, such as a capped or unlogged one, and asserts the key in the error (CFG-02).

## Stored-data compatibility

```java
@Test
void oldDocumentGetsDefaultsAndMigratesOnce() {
    EventShopState s = KvStoreForTest.decode(Fixtures.read("event-shop-state.v0.json"), EventShopState.class);

    s.migrate(NOW);
    String once = Json.write(s);
    s.migrate(NOW);

    assertEquals(EventShopState.SCHEMA_VERSION, s.schemaVersion);
    assertEquals(once, Json.write(s));
}

@Test
void saveKeepsFieldsFromANewerVersion() {
    String newer = Fixtures.read("event-shop-state.unknown-field.json");

    String saved = KvStoreForTest.encode(KvStoreForTest.decode(newer, EventShopState.class));

    assertTrue(saved.contains("\"giftWrapColor\":\"red\""));
}
```

Each stored document has a test that loads a document from before the change. A document that keeps unknown fields, per the profile's CAP-USERSTORE entry, also has a test that loads one with a field from a newer version and asserts that a save keeps it (TEST-06, BG-02, BG-09). Run both through the project's real serializer from CAP-USERSTORE, never a test-only JSON mapper, because the serializer is what drops or keeps fields.

When the document holds a nested type and CAP-USERSTORE says nested unknown fields are kept, the newer-version fixture also puts an unknown field inside the nested object, and the test asserts that a save keeps it (BG-02). When only top-level fields are kept, the test puts the unknown field at the top level, and new fields go there. When a stored map is keyed by an enum, one test loads a document whose map has a key that the running version does not know, and asserts that the load succeeds and a save keeps the entry (BG-01).

## Shared writes and two nodes

```java
@Test
void joinThatTimesOutAfterLandingAddsTheMemberOnce() {
    store.failNextCas(Applied.YES);                 // the write lands, then the call throws
    assertEquals(ErrorCode.SUCCESS, GuildCore.join(store, guildId, userId, NOW));
    assertEquals(1, store.guild(guildId).countOf(userId));
}

@Test
void secondNodeWithAStaleCopyCannotBuyASoldItem() {
    SaleService a = new SaleService(store, redis, NodeId.of("a"), clock);
    SaleService b = new SaleService(store, redis, NodeId.of("b"), clock);
    SaleView stale = b.view(sellerId);
    assertEquals(ErrorCode.SUCCESS, a.buy(buyer1, saleId, TRACE));
    assertEquals(ErrorCode.SOLD_OUT, b.buyFrom(stale, buyer2, saleId, TRACE));
}
```

- Each write that the feature retries has a test where the store applies the write and then fails, and one where it fails before applying, and each asserts exactly one effect (TEST-09, MN-04). Use the store fake from CAP-UNITTEST with its failure switches.
- Each shared document, counter, claim, queue, or cross-node push has a test with two instances over one store and one Redis, with different node ids, and shared documents get the stale-copy case (TEST-13).
- Each Redis result the feature maps has a test for the unknown case, which asserts retry-later and no change (MN-13).
- A test of a Redis script runs against a real Redis under a key prefix unique to the run and wipes it afterward (TEST-01). When CAP-UNITTEST records that the test command needs a local Redis, say so in the slice report.

## HTTP callbacks and inbox entries

For each endpoint, test each rejected call against its status code, with a bad signature, a stale timestamp, a caller not on the allowlist, an empty allowlist on live, and a payload that does not match the product. Then test a duplicate callback, and assert one inbox entry and a 200 answer (TEST-09, HTTP-08). For each inbox entry type, apply the same entry twice and assert one grant. Use the in-memory Redis and inbox fakes from CAP-UNITTEST when the profile names them.

## E2E bot

When the profile's CAP-BOT entry is `present`, add a bot scenario for each command's main flow, in the scenario format and directory that the entry names (TEST-10). Running it needs a live server, so the slice report lists it as unrun unless the developer runs it.
