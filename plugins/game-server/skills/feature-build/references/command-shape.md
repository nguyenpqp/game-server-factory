# Command shape

One class per client command. The class has two layers.

- `handle` and `run` are the shell. They decode the request, mint the trace id, read the clock, call the core, send the response, and write the metric row. Only the shell touches actor, session, and network types.
- `process` is the pure core. It takes plain inputs and returns an outcome, so a unit test calls it with no network, socket, or database (TEST-01).

The example is an event shop purchase, `BuyShopItem`. It has a cost, a reward, a daily limit, a request id, and one request field that a newer client added. Replace each generic name with the profile's API, as the table in the skill file says.

## The shell

```java
public final class BuyShopItem {
    static final String ACTION = "event_shop_buy";
    static final String REASON = "EVENT_SHOP_BUY";
    static final String REFUND = "EVENT_SHOP_BUY_REFUND";

    public static void handle(UserActor actor, Request raw) {
        String traceId = TraceIds.next();
        Outcome out = run(actor, raw, traceId);
        Response.of(CmdIds.EVENT_SHOP_BUY, out.error())
                .put(Keys.SHOP_ITEM_ID, out.shopItemId())
                .put(Keys.BOUGHT_TODAY, out.boughtToday())
                .send(actor);
        MetricLogger.userAction(actor.userId(), ACTION, out.error(), traceId,
                out.shopItemId(), out.quantity(), out.boughtToday());
    }

    static Outcome run(UserActor actor, Request raw, String traceId) {
        try {
            BuyRequest req = BuyRequest.parse(raw);
            return process(actor.state(EventShopState.class), EventShopConfig.current(),
                    actor.inventory(), req, actor.clientVersion(),
                    ServerClock.now(actor.userId()), traceId);
        } catch (RuntimeException e) {
            MetricLogger.exception(actor.userId(), ACTION, traceId, e);
            return Outcome.error(Errors.SERVER_ERROR);
        }
    }
}
```

- `handle` runs on the acting user's actor thread, on the node that owns the user (MN-02). It makes no blocking call (PERF-01).
- One trace id per action. The same id goes to the metric row, the exception row, and every inventory change (MET-02, MET-03).
- Every path writes exactly one action row with its result code, including a parse failure and an exception (MET-01). An exception also writes an exception row, and the client still gets an error code (MET-08).
- `run` reads the config snapshot once and passes it down, so the whole command sees one snapshot (CFG-03).
- `ServerClock.now(userId)` includes the user's cheat time offset off live, and it is plain server time on live (AUTH-02, CHEAT-07).
- The response appends new fields after the existing ones, and a new field is optional for the client (BG-04). Keep lists in the response capped by a number from the spec (PERF-04).
- The extras of the metric row are the ones that the spec's Actions table lists, in its order. New data goes into extras, never into a new fixed column (MET-07).

The real APIs come from CAP-COMMAND for `Request`, CAP-RESPONSE for `Response`, CAP-ACTOR for `UserActor`, CAP-TRACEID for `TraceIds`, CAP-CLOCK for `ServerClock`, CAP-METRIC for `MetricLogger`, and CAP-ERRORS for `Errors`.

## Parse

```java
record BuyRequest(int error, String requestId, String shopItemId, int quantity) {
    static BuyRequest parse(Request raw) {
        String requestId = raw.getString(Keys.REQUEST_ID, null);
        String shopItemId = raw.getString(Keys.SHOP_ITEM_ID, null);
        // Clients before 1.5.0 do not send a quantity and always buy one.
        int quantity = raw.getInt(Keys.QUANTITY, 1);
        if (requestId == null || requestId.length() < 8 || requestId.length() > 64)
            return invalid();
        if (shopItemId == null || shopItemId.isEmpty() || shopItemId.length() > 32)
            return invalid();
        if (quantity < 1)
            return invalid();
        return new BuyRequest(Errors.OK, requestId, shopItemId, quantity);
    }

    static BuyRequest invalid() {
        return new BuyRequest(Errors.INVALID_REQUEST, null, null, 0);
    }
}
```

- Parse checks presence, type, length, and the ranges that need no config (AUTH-04). Ranges that come from config, such as the largest quantity, are checks in `process`.
- A field that a newer client added has a default that gives the old behavior, so an old client's request still works (BG-05, TEST-07).
- The decoder must report a missing field as absent. When the project's decoder throws or reads garbage on a missing field, CAP-COMMAND is `partial`. The slice stops at gate 3 when CAP-COMMAND is `missing`, or when it is `partial` and its `blocker` line names a rule that the slice's rows cite.
- The request carries intents only, such as which item and how many. It never carries a price, a reward, or a result (AUTH-01).

## The pure core

```java
static Outcome process(EventShopState state, EventShopConfig cfg, Inventory inv,
                       BuyRequest req, ClientVersion client, long now, String traceId) {
    if (req.error() != Errors.OK)
        return Outcome.error(req.error());
    Outcome replay = state.resultOf(req.requestId());
    if (replay != null)
        return replay;
    if (!cfg.isActive(now))
        return Outcome.error(Errors.FEATURE_INACTIVE);
    if (client.isOlderThan(cfg.minClientVersion()))
        return Outcome.error(Errors.CLIENT_TOO_OLD);
    ShopItem item = cfg.item(req.shopItemId());
    if (item == null)
        return Outcome.error(Errors.UNKNOWN_SHOP_ITEM);
    if (req.quantity() > item.maxPerBuy())
        return Outcome.error(Errors.INVALID_REQUEST);
    long today = ServerClock.dayOf(now);
    int bought = state.boughtOn(item.id(), today);
    if (bought + req.quantity() > item.dailyLimit())
        return Outcome.error(Errors.DAILY_LIMIT);
    Cost cost = item.price().times(req.quantity());
    if (!inv.canTake(cost))
        return Outcome.error(Errors.NOT_ENOUGH);

    inv.take(cost, REASON, traceId);
    if (!inv.add(item.reward().times(req.quantity()), REASON, traceId)) {
        inv.add(cost, REFUND, traceId);
        return Outcome.error(Errors.GRANT_FAILED);
    }
    state.recordPurchase(item.id(), today, req.quantity());
    Outcome out = Outcome.ok(item.id(), req.quantity(), bought + req.quantity());
    state.rememberResult(req.requestId(), out);
    state.markChanged();
    return out;
}
```

- The checks run in the order of the spec's Checks table, and each returns its own error code (AUTH-06, AUTH-10). A rejected command returns before any change, so its state is the state it started with.
- The core takes `now` and, when it draws random numbers, a `GameRandom` parameter. It never reads a clock or a random source itself (AUTH-02, AUTH-03). `ServerClock.dayOf` is a pure conversion with the day-reset timezone from CAP-CLOCK, and it reads no clock.
- The client version gate uses the version that the session reported at login (BG-07). The real API comes from CAP-CLIENTVER.
- The config lookup `cfg.item(id)` is a map read from an index built at load (PERF-05). The price, the limit, and the reward come from config (CFG-05).
- Check before take. `canTake` checks the whole cost, and `take` runs only after every check passes (AUTH-07). CAP-INVENTORY's take of several items must take nothing when any item is short.
- Refund on partial failure. When the grant fails after the take, the core gives back what it took under its own refund reason with the same trace id, and returns an error (AUTH-07, MET-04). When the grant can throw, catch at the grant, refund, and rethrow, so `run` still writes the exception row.
- Each change carries a reason constant unique to this action and the trace id (MET-03, MET-04). The reasons are the ones in the spec's Currency and item changes table.
- `markChanged` runs after the last change, on success only. The save cycle of CAP-USERSTORE writes the document.

### Idempotent request id

A command whose retry would grant value twice carries a request id (AUTH-08). The state document keeps the results of the most recent request ids, with a cap from the spec, such as 20. A repeated id returns the stored result and changes nothing. The list lives in the stored document, so a retry after a reconnect to another node still finds it. [State model](state-model.md) shows the bounded list.

Only a success is stored. A rejected command changed nothing, so its retry runs the checks again.

### Rate limit

A command that reads the database, touches other users, or fans out also checks a per-user rate limit before any work (AUTH-09). Keep the window start and the count in the state document, compare them with `now`, and return the spec's rate-limit error with no effect. The limit numbers come from config.

## Outcome

```java
record Outcome(int error, String shopItemId, int quantity, int boughtToday) {
    static Outcome ok(String shopItemId, int quantity, int boughtToday) {
        return new Outcome(Errors.OK, shopItemId, quantity, boughtToday);
    }

    static Outcome error(int error) {
        return new Outcome(error, "", 0, 0);
    }
}
```

The outcome holds everything that the response and the metric row need. Tests assert on it directly.

## Pushes

A push to the acting player goes through CAP-RESPONSE after the response. A push to another user goes through the ownership record and cross-node delivery, never through a node-local session map (MN-10). Check the recipient's client version against the push's minimum client from the spec before sending (BG-06). A command that pushes to or changes other users stays under the spec's fan-out bound (PERF-07).

## Registration

Register the command where the profile's CAP-COMMAND entry says, under the command id from the generated files. The handler class stays stateless, because one instance serves every user (MN-01).

```java
router.register(CmdIds.EVENT_SHOP_BUY, BuyShopItem::handle);
```
