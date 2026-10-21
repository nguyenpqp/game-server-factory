package com.example.game.feature.demo;

import static java.util.Map.entry;

import java.util.Map;
import java.util.concurrent.atomic.AtomicReference;
import java.util.regex.Pattern;

// System.currentTimeMillis() and new Random() in a comment are not findings.
/*
 * Thread.sleep(5);
 * private static int notReal;
 */
final class Clean {
    private static final int MAX_ITEMS = 10;
    private static final String NAME = "Math.random( and Thread.sleep( in a string";
    private static final Pattern ID = Pattern.compile("[a-z]+");
    private static final Map<String, Integer> LIMITS = Map.of("a", 1, "b", 2);
    private static final String BLOCK = """
        new Random(1) inside a text block
        """;
    private static final char QUOTE = '"';

    static {
        assert MAX_ITEMS > 0;
    }

    static int limit(String key) {
        return LIMITS.get(key);
    }

    long read(long now) {
        return ServerClock.now() + now;
    }

    int roll() {
        return GameRandom.nextInt(6);
    }

    static final class ClaimService {
        private static volatile ClaimConfig current;
        static final AtomicReference<ClaimConfig> REF = new AtomicReference<>();
    }

    @CheatCommand
    static final class GrantCheat {
        Result apply(UserActor user, int amount) {
            if (Env.isLive()) {
                return Result.rejected();
            }
            user.add(amount);
            return Result.ok();
        }
    }

    static final class ClaimHandler {
        Result handle(UserActor user, ClaimRequest request) {
            String trace = TraceIds.next();
            MetricLogger.userAction(user, "claim", 0, trace);
            return Result.ok();
        }
    }
}
