package com.example.game.feature.demo;

final class Blocking {
    void run(Thread worker, Future<String> future, Latch latch, Mono<String> mono) throws Exception {
        Thread.sleep(10); // EXPECT: PERF-01
        worker.join(); // EXPECT: PERF-01
        latch.await(1, SECONDS); // EXPECT: PERF-01
        mono.block(); // EXPECT: PERF-01
        String joined = String.join(",", "a", "b");
    }
}
