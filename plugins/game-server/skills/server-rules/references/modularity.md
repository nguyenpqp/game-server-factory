# Modularity rules

These are the `MOD` rules from [the rule index](index.md), which also gives each rule's severity. Each feature is one package under the profile's `feature_root`. Features reach each other only through the contract packages that the profile's CAP-MODULE entry names, so each feature builds, tests, and ships on its own. The examples use generic names. The project profile supplies the real packages.

### MOD-01 Feature code imports only its own package, shared packages, and contract packages, never the package of another feature.

**Why.** An import of another feature's package couples the two features, so a change inside one breaks the build or the behavior of the other, and neither can be tested or reviewed alone.

Do:

```java
import com.example.game.contract.inventory.InventoryContract;
import com.example.game.shared.Money;
```

Don't:

```java
import com.example.game.feature.inventory.InventoryStore;     // the inventory feature's own class
import com.example.game.feature.inventory.InventoryConfig;    // its config, read from another feature
```

Don't reach the other feature's state through a shared helper either. A static lookup of its service from a handler hides the same coupling behind one more call.

**Check.** List the imports of every file in the feature. Each one names the feature's own package, a shared package, a contract package, or a library. The profile's `lint.allowed_import` names the imports that may cross features. Look also for names used fully qualified in code, which an import list does not show.

- needs: CAP-MODULE

### MOD-02 A cross-feature effect that the reply depends on is a synchronous contract call, an effect that pays player value is a contract call or a durable inbox entry, and an event carries only best-effort reactions whose loss costs no value.

**Why.** An event runs after the reply, in no fixed order, and can be dropped, so a reply that counts on it reports an effect that has not happened, such as an item granted before its price is taken.

Do:

```java
if (!inventory.take(userId, price, REASON, traceId)) {
    return Outcome.error(Errors.NOT_ENOUGH);
}
events.publish(new ItemBoughtEvent(userId, item.id(), traceId));   // a news feed line, best effort
return Outcome.ok(item.id());
```

Don't:

```java
events.publish(new SpendGemsEvent(userId, price, traceId));   // the debit runs later, or never
return Outcome.ok(item.id());
```

Don't treat an event as durable delivery to another user. A dropped event loses the effect, so value for another user goes through the durable inbox (MN-03).

The same holds for the same player. Progress that pays a reward later, such as points toward a milestone or a pass level, never rides only an event. Make it a contract call before the reply, or an entry in the player's durable inbox whose id comes from the action's request id, so a retry adds nothing new. The append is a change step, so AUTH-07 decides what a failed append does.

**Check.** For each event the feature publishes, confirm that the reply does not report its effect, and that a dropped event loses no value, for this player or another. For each cross-feature effect that the reply reports, find the contract call that completes before the reply is built.

- needs: CAP-MODULE
