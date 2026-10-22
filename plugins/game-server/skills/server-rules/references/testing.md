# Test rules

These are the `TEST` rules from [the rule index](index.md), which also gives each rule's severity. Tests are the main proof that a feature keeps the other rules. The examples use JUnit 5 and generic names. The project profile supplies the real classes and the test command.

### TEST-01 The feature's core logic has unit tests that run without network, sockets, or a database.

**Why.** Tests that need a server or a database run rarely and fail for reasons unrelated to the feature.

Do:

```java
@Test
void claimGrantsDayReward() {
    UserState state = UserState.fresh();
    ErrorCode error = StreakCore.claim(state, testConfig(), DAY_1_NOON);
    assertEquals(ErrorCode.SUCCESS, error);
    assertEquals(1, state.streak());
}
```

Don't:

```java
@Test
void claimGrantsDayReward() {
    GameServer server = GameServer.start();
    TestClient client = server.connect("tester");
    client.send(Commands.STREAK_CLAIM);
}
```

**Check.** Confirm the feature's tests call the pure core directly and open no socket or database connection.

- needs: CAP-UNITTEST

### TEST-02 Tests inject time and random numbers, so every time window, cooldown, and random outcome has a deterministic test.

**Why.** A test that reads the real clock or an unseeded RNG passes or fails by chance.

Do:

```java
GameRandom rng = GameRandom.fixed(3);
Drop drop = LootCore.roll(table, rng);
assertEquals("rare_seed", drop.itemId());
assertEquals(ErrorCode.COOLDOWN, StreakCore.claim(state, config, END_OF_DAY - 1));
```

Don't:

```java
Thread.sleep(1000);
assertTrue(StreakCore.claim(state, config, System.currentTimeMillis()) == ErrorCode.SUCCESS);
```

**Check.** Confirm each time boundary and each random branch in the core has a test with a fixed time or a fixed RNG.

- needs: CAP-CLOCK, CAP-RNG, CAP-UNITTEST

### TEST-03 Each command has a negative test per validation and precondition failure that asserts the error code and unchanged state.

**Why.** Rejection paths are where exploits live, and a test that checks only the code misses a half-applied change.

Do:

```java
@Test
void claimDuringCooldownChangesNothing() {
    UserState before = state.copy();
    assertEquals(ErrorCode.COOLDOWN, StreakCore.claim(state, config, cooldownEnd - 1));
    assertEquals(before, state);
}
```

Don't:

```java
@Test
void claimFails() {
    assertNotEquals(ErrorCode.SUCCESS, StreakCore.claim(state, config, 0));
}
```

**Check.** List the command's guards and match each to a test that asserts its specific code and equal state.

- needs: CAP-UNITTEST, CAP-ERRORS

### TEST-04 Each cheat command has a test that proves it is rejected on live and changes nothing.

**Why.** The live check is the last guard against a cheat on live, so it needs a test that fails when someone removes it.

Do:

```java
@Test
void cheatRejectedOnLive() {
    Env.setForTest(Env.LIVE);
    UserState before = state.copy();
    assertEquals(ErrorCode.INVALID_ACTION, CheatSetStreak.process(state, 5));
    assertEquals(before, state);
}
```

Don't:

```java
@Test
void cheatSetsStreak() {
    assertEquals(ErrorCode.SUCCESS, CheatSetStreak.process(state, 5));
}
```

**Check.** Confirm each cheat class has a live test that asserts the error and unchanged state.

- needs: CAP-UNITTEST, CAP-ENV

### TEST-05 Config validation has a test for a valid file and a test for each invalid case that the validator rejects.

**Why.** A validator without tests drifts, and a bad file then reaches live.

Do:

```java
@Test
void rejectsZeroMaxStreak() {
    ConfigException e = assertThrows(ConfigException.class,
        () -> FeatureConfig.parse("streak.json", json("{\"maxStreak\": 0}")));
    assertTrue(e.getMessage().contains("maxStreak"));
}
```

Don't:

```java
@Test
void loads() {
    assertNotNull(FeatureConfig.parse("streak.json", validJson()));
}
```

**Check.** List the validator's checks and match each to a test that feeds a bad value and asserts the named key.

- needs: CAP-CONFIG, CAP-UNITTEST

### TEST-06 Compatibility tests load stored data from before the change and from a newer version with unknown fields, then assert that a save loses nothing.

**Why.** Old documents and newer-version documents both exist during rollout, and a lossy load corrupts one of them.

Do:

```java
@Test
void keepsUnknownFieldsOnSave() {
    String newer = "{\"level\":3,\"futureField\":{\"a\":1}}";
    UserState state = Codec.decode(newer);
    assertEquals(Json.parse(newer), Json.parse(Codec.encode(state)));
}
```

Don't:

```java
@Test
void roundTrip() {
    UserState state = UserState.fresh();
    assertEquals(state, Codec.decode(Codec.encode(state)));
}
```

**Check.** Find a test with a fixture from before the change and a test with an unknown field, both asserting nothing is lost.

- needs: CAP-USERSTORE, CAP-UNITTEST

### TEST-07 Compatibility tests decode old-client requests that lack the new fields and assert the old behavior and the old response layout.

**Why.** Old clients stay online during rollout, and only a test catches a new required field or a moved response field.

Do:

```java
@Test
void oldClientRequestKeepsOldBehavior() {
    Request oldReq = Request.of(Commands.HARVEST_CLAIM, Map.of("slot", 2));
    Response resp = HarvestCommand.handleForTest(state, oldReq, NOW);
    assertEquals(List.of("error", "gold", "xp"), resp.fieldNames());
}
```

Don't:

```java
@Test
void claimWithAmount() {
    Request req = Request.of(Commands.HARVEST_CLAIM, Map.of("slot", 2, "amount", 3));
    assertEquals(ErrorCode.SUCCESS, HarvestCommand.handleForTest(state, req, NOW).error());
}
```

**Check.** For each changed command, find a test that sends the old request shape and asserts the old response layout.

- needs: CAP-COMMAND, CAP-UNITTEST

### TEST-08 Tests assert the metric rows of each command, on success and on failure, including the trace id.

**Why.** Metric calls break silently, and the gap shows only when someone needs the data.

Do:

```java
@Test
void failureWritesOneRowWithTraceId() {
    RecordingMetricLogger rows = RecordingMetricLogger.install();
    HarvestCommand.handleForTest(state, badRequest, NOW);
    assertEquals(1, rows.userActions().size());
    assertEquals(ErrorCode.INVALID_PARAM, rows.userActions().get(0).result());
    assertNotNull(rows.userActions().get(0).traceId());
}
```

Don't:

```java
@Test
void claim() {
    HarvestCommand.handleForTest(state, goodRequest, NOW);   // rows never checked
}
```

**Check.** Confirm each command has a success test and a failure test that read the recorded rows.

- needs: CAP-METRIC, CAP-UNITTEST

### TEST-09 Tests replay each idempotent request and each duplicate callback, and assert exactly one effect.

**Why.** Duplicate delivery is normal on mobile networks and payment providers, so a missing guard pays twice.

Do:

```java
@Test
void duplicateRequestGrantsOnce() {
    StreakCore.claim(state, config, NOW, "req-1");
    StreakCore.claim(state, config, NOW, "req-1");
    assertEquals(config.dayReward(1), state.gems());
}
```

Don't:

```java
@Test
void claimGrants() {
    StreakCore.claim(state, config, NOW, "req-1");
    assertEquals(config.dayReward(1), state.gems());
}
```

**Check.** For each command with a request id and each callback, find a test that sends it twice and asserts one effect.

- needs: CAP-UNITTEST

### TEST-10 When the project has an E2E bot, each command has a bot scenario for its main flow.

**Why.** Unit tests skip the decoder, the router, and the wire format, which only an end-to-end run covers.

Do:

```java
Scenario.named("streak_main")
    .cheat("cheat_streak_set", Map.of("streak", 6))
    .send(Commands.STREAK_CLAIM, Map.of("requestId", "bot-1"))
    .expect(Commands.STREAK_CLAIM, ErrorCode.SUCCESS);
```

Don't:

```java
// The bot covers login only; new commands are tested by hand.
```

**Check.** When the profile lists an E2E bot, match each new command to a scenario.

- needs: CAP-BOT

### TEST-11 A test that changes global state, such as the config instance, the clock, or the environment, restores it afterward.

**Why.** Leaked global state makes later tests pass or fail depending on run order.

Do:

```java
@AfterEach
void restore() {
    FeatureConfig.setInstanceForTest(null);
    ServerClock.resetForTest();
    Env.setForTest(Env.DEV);
}
```

Don't:

```java
@BeforeEach
void setUp() {
    Env.setForTest(Env.LIVE);   // never restored
}
```

**Check.** For each `setForTest` or global setter in a test class, find the matching restore in an `@AfterEach` or a `finally`.

- needs: CAP-UNITTEST

### TEST-12 Tests assert behavior through fakes that record effects, and no test covers a getter, a library's config parsing, framework behavior, a restated constant, or mock wiring.

**Why.** A test that cannot fail when the behavior breaks costs review and run time and gives false confidence, and a test pinned to wiring fails on every refactor while it catches no bug.

Do:

```java
@Test
void buyTakesThePriceOnce() {
    FakeInventory inv = new FakeInventory().give("gem", 100);

    BuyShopItem.process(state, cfg, inv, request("req-00001"), CLIENT, NOW, TRACE);

    assertEquals(List.of(new Change("gem", -10, "EVENT_SHOP_BUY", TRACE)), inv.changes());
}
```

Don't:

```java
@Test
void maxSlotsIsTen() {
    assertEquals(10, cfg.maxSlots());   // restates the config value
}

@Test
void buyCallsTake() {
    BuyShopItem.process(state, cfg, inventoryMock, request("req-00001"), CLIENT, NOW, TRACE);
    verify(inventoryMock).take(any(), any(), any());   // wiring, not the amount taken
}
```

Don't write a test per getter or setter, a test that the JSON library parses a plain config class, or a test of the framework's delivery or save cycle. Config validation is behavior and keeps its tests (TEST-05).

**Check.** For each new test, break the behavior it names and confirm that it fails, then change only the internals and confirm that it passes. A test that fails neither way, or that tests a getter, library parsing, framework behavior, a restated constant, or mock wiring, is a finding.

- needs: CAP-UNITTEST
