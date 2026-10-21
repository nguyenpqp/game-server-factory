package com.example.game.feature.demo;

import java.util.Random;
import java.util.concurrent.ThreadLocalRandom;

final class ForbiddenRandom {
    int seeded() { return new Random(7).nextInt(10); } // EXPECT: AUTH-03
    double unit() { return Math.random(); } // EXPECT: AUTH-03
    int shared() { return ThreadLocalRandom.current().nextInt(10); } // EXPECT: AUTH-03
}
