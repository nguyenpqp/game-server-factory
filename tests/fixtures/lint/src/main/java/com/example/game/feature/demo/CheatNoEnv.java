package com.example.game.feature.demo;

@CheatCommand
final class GrantCheat { // EXPECT: CHEAT-02
    void apply(UserActor user, int amount) {
        user.add(amount);
    }
}
