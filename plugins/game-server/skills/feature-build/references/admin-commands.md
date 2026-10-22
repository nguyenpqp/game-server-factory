# Admin commands

Each feature ships admin commands that read and repair its per-user state for support (ADMIN-08). An admin command acts on another user's data, so it follows the same ownership rules as a cross-user change.

The real admin session, the routing to the target user's owner, the audit record, and the body format come from the profile's CAP-ADMIN entry. The owner lookup comes from CAP-OWNERSHIP, delivery to the owner from CAP-CROSSNODE, and the offline write from CAP-CAS.

## The flow

1. The admin channel checks the admin session on every request (ADMIN-01). Feature code does not log admins in. It relies on the core's check, and it reads the admin's identity and permission from the session.
2. The command checks its permission, its target, its ranges, and its referenced ids before any effect, as a gameplay command does (ADMIN-06).
3. A command that changes the user runs on the target user's owner actor. When the user is offline, it updates the stored document with a CAS write and a bounded retry (ADMIN-02).
4. On live, a destructive command, such as a reset or an overwrite, requires `confirm` set to true, or the spec blocks it on live (ADMIN-04).
5. A retry with the same `requestId` has no second effect (ADMIN-07).
6. Every mutating command writes one audit row with the admin, the target, the requested and the applied change, the result, and the trace id (ADMIN-03).

## A repair command

```java
public final class AdminSetPurchases implements AdminCommand {
    static final String ACTION = "admin_event_shop_set";

    @Override
    public void handle(AdminSession admin, AdminRequest req) {
        String traceId = TraceIds.next();
        SetPurchases cmd = SetPurchases.parse(req);
        int error = SetPurchases.check(cmd, admin, EventShopConfig.current(), Env.isLive());
        if (error != Errors.OK) {
            finish(admin, req, cmd, null, null, error, traceId);
            return;
        }
        UserActor.submitTo(cmd.userId(),
                actor -> apply(admin, req, cmd, actor.state(EventShopState.class), traceId),
                () -> applyOffline(admin, req, cmd, traceId));
    }

    static void apply(AdminSession admin, AdminRequest req, SetPurchases cmd,
                      EventShopState state, String traceId) {
        Snapshot before = Snapshot.of(state);
        int error = SetPurchases.applyTo(state, cmd, ServerClock.now(cmd.userId()));
        if (error == Errors.OK)
            state.markChanged();
        finish(admin, req, cmd, before, Snapshot.of(state), error, traceId);
    }

    static void applyOffline(AdminSession admin, AdminRequest req, SetPurchases cmd, String traceId) {
        KvStore.casUpdate(EventShopState.key(cmd.userId()), EventShopState.class, 5, state -> {
            state.migrate(ServerClock.now(cmd.userId()));
            return SetPurchases.applyTo(state, cmd, ServerClock.now(cmd.userId()));
        }, (before, after, error) -> finish(admin, req, cmd, before, after, error, traceId));
    }

    static void finish(AdminSession admin, AdminRequest req, SetPurchases cmd,
                       Snapshot before, Snapshot after, int error, String traceId) {
        AdminAudit.write(admin, cmd.userId(), ACTION, cmd, after, error, traceId);
        MetricLogger.userAction(cmd.userId(), ACTION, error, traceId, admin.name());
        req.reply(error, new Result(before, after));
    }
}
```

- `check` returns `PERMISSION_DENIED` without the spec's permission, `USER_NOT_FOUND` for an unknown user, `OUT_OF_RANGE` for a bad value, and `CONFIRM_REQUIRED` on live when `confirm` is not true. Each is an error code from the spec's API entry.
- `parse` keeps a missing field apart from its zero value, such as a boxed `Integer` left null, and `check` returns `OUT_OF_RANGE` for a missing required field, as for a bad value. A primitive default of 0 would pass the range check and set the count to zero (ADMIN-06).
- `UserActor.submitTo` runs the change on the owner's actor, on whichever node owns the user. Its second argument runs when the user is offline. The admin's own thread never touches the target's live state (MN-02).
- The offline path loads the stored document, runs the same migration as a login, applies the same domain method, and writes with CAS. A conflict reloads and retries, up to the bound (MN-04).
- `SetPurchases.applyTo` calls the document's own methods, so a repair keeps the feature's invariants.
- Idempotency. `applyTo` stores the request id in the document's recent results and returns the first result on a repeat, as a gameplay command does. A read-only command needs no request id.
- `finish` runs on every path. It writes the audit row, one action row under the command's own action name with the trace id, and the reply, so admin changes show up in the same metric tables as gameplay (ADMIN-03, MET-01, MET-02).
- The audit row holds no secret and no token (MET-09).

The routing is the place where a new admin command is most often forgotten. When the profile's CAP-ADMIN entry names a table or switch that maps each per-user command to its target user, add the new command there. A command that is missing from it runs on the admin's thread and races the owner.

## A read command

A read command, such as `AdminGetPurchases`, returns a snapshot that the owner builds on its actor, or a private load of the stored document when the user is offline. It writes no audit row unless the profile's CAP-ADMIN entry audits reads too. It needs `support read` or the permission that the spec names.

## The API spec entry

Each admin command has an entry in the spec's Admin commands and API spec section, with its permission, request fields, response fields, and errors (ADMIN-05). The request and response bodies in code match that entry field by field. When the profile's CAP-ADMIN entry names a separate API document or an admin web repository, add the entry or the screen there too, in that file's format. Without one, the spec's entry is the API spec.
