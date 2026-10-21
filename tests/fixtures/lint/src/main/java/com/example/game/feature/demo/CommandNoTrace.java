package com.example.game.feature.demo;

final class OpenHandler { // EXPECT: MET-02
    Result handle(UserActor user, OpenRequest request) {
        MetricLogger.userAction(user, "open", 0);
        return Result.ok();
    }
}
