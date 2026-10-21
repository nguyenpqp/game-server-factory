package com.example.game.feature.demo;

final class ClaimHandler { // EXPECT: MET-01 MET-02
    Result handle(UserActor user, ClaimRequest request) {
        return Result.ok();
    }
}
