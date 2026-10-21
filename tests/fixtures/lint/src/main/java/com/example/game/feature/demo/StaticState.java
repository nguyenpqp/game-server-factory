package com.example.game.feature.demo;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicReference;

final class StaticState {
    private static int counter; // EXPECT: MN-01
    private static final Map<Long, String> CACHE = new HashMap<>(); // EXPECT: MN-01
    private static final List<String> NAMES = new ArrayList<>(); // EXPECT: MN-01
    static final ConcurrentHashMap<Long, Integer> SEEN = new ConcurrentHashMap<>(); // EXPECT: MN-01
    static final int[] SLOTS = {1, 2, 3}; // EXPECT: MN-01
    static volatile Object snapshot; // EXPECT: MN-01
    static final AtomicReference<Object> HOLDER = new AtomicReference<>(); // EXPECT: MN-01
    private static final Map<String, Integer> WRAPPED = // EXPECT: MN-01
        new HashMap<>();
    static FeatureConfig plain; // EXPECT: MN-01

    static final class Inner {
        private static long hits; // EXPECT: MN-01
    }

    static final class LimitsConfig {
        static volatile Map<String, Integer> limits; // EXPECT: MN-01
    }

    static int helper() { return counter; }
}
