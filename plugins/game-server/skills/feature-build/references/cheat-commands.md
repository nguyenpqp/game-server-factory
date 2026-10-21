# Cheat commands

Cheats let testers put an account into any state the client needs to test (CHEAT-05). They must never run on live. Two guards stop them, and each guard holds alone.

1. The cheat handler is not registered when the server runs on live (CHEAT-01).
2. Each cheat checks the environment again at the point of mutation and rejects the request on live (CHEAT-02).

The real cheat channel and the cheat marker come from the profile's CAP-CHEAT entry. The live check comes from CAP-ENV, and the per-user time offset from CAP-CLOCK.

## Registration

```java
if (!Env.isLive())
    cheatRouter.register(CmdIds.CHEAT_EVENT_SHOP_SET, CheatSetPurchases::handle);
```

- The cheat handler and classes live apart from the gameplay commands, in their own class or package (CHEAT-03).
- Use the profile's one call for "is this live". Never gate on a config flag such as an "enable cheats" switch, because a live config can set it by mistake.

## A cheat class

```java
@CheatCommand
public final class CheatSetPurchases {
    static final String ACTION = "cheat_event_shop_set";

    public static void handle(UserActor actor, Request raw) {
        String traceId = TraceIds.next();
        int error;
        try {
            error = process(actor.state(EventShopState.class), EventShopConfig.current(),
                    raw.getString(Keys.SHOP_ITEM_ID, null), raw.getInt(Keys.COUNT, -1),
                    Env.isLive(), ServerClock.now(actor.userId()));
        } catch (RuntimeException e) {
            MetricLogger.exception(actor.userId(), ACTION, traceId, e);
            error = Errors.SERVER_ERROR;
        }
        Response.of(CmdIds.CHEAT_EVENT_SHOP_SET, error).send(actor);
        MetricLogger.userAction(actor.userId(), ACTION, error, traceId);
    }

    static int process(EventShopState state, EventShopConfig cfg, String itemId, int count,
                       boolean live, long now) {
        if (live)
            return Errors.INVALID_ACTION;
        ShopItem item = cfg.item(itemId);
        if (item == null)
            return Errors.UNKNOWN_SHOP_ITEM;
        if (count < 0 || count > item.dailyLimit())
            return Errors.INVALID_REQUEST;
        state.setPurchases(item.id(), ServerClock.dayOf(now), count);
        state.markChanged();
        return Errors.OK;
    }
}
```

- The class carries the profile's cheat marker, here `@CheatCommand` (CHEAT-03). The linter in `feature-review` looks for it.
- `process` takes the live flag as a parameter and rejects first, before any read or change. The shell passes `Env.isLive()`, and a unit test passes `true` to prove the rejection (CHEAT-02, TEST-04).
- The cheat validates its input like a gameplay command, and it changes state through the document's own methods, such as `setPurchases`, so the result keeps the feature's invariants (CHEAT-06).
- It writes a metric row under its own action name with a trace id, on success and on error, like a gameplay command (CHEAT-04).
- It never grants currency or items outside CAP-INVENTORY. A cheat that gives items calls the same inventory add with a cheat reason and the trace id.

## Time cheats

```java
static int shiftDays(UserClockOffset offset, int days, boolean live) {
    if (live)
        return Errors.INVALID_ACTION;
    if (days < 1 || days > 30)
        return Errors.INVALID_REQUEST;
    offset.add(days * DAY_MS);
    return Errors.OK;
}
```

A time cheat moves server time for the acting user only, through the per-user offset that CAP-CLOCK provides (CHEAT-07). Other users and other nodes keep real time. On live, `ServerClock.now(userId)` ignores the offset. When the profile has no per-user offset, CAP-CLOCK is `partial`, and time cheats stop at gate 3. Never move the node's clock.

## Coverage of the design's states

The spec's Cheat commands table lists, for each design state, the cheat that reaches it. Build every row. A row that names an existing project cheat, such as a level cheat, needs no new code.
