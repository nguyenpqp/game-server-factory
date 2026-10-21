package com.example.game.feature.demo;

import java.time.Instant;
import java.time.LocalDateTime;
import java.util.Date;

final class ForbiddenTime {
    long wall() { return System.currentTimeMillis(); } // EXPECT: AUTH-02
    Instant instant() { return Instant.now(); } // EXPECT: AUTH-02
    LocalDateTime local() { return LocalDateTime.now(); } // EXPECT: AUTH-02
    Date date() { return new Date(); } // EXPECT: AUTH-02
    long fromParameter(long now) { return now; }
}
