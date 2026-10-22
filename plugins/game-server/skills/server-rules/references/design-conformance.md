# Design conformance rules

These are the `DES` rules from [the rule index](index.md), which also gives each rule's severity. They compare the code with the feature's `design.md` from `gdd-intake`, and with the decisions recorded about it. The spec is a step between the two, so a review reads the design itself and does not trust the spec to carry every requirement. The examples use a three-milestone progress chain and generic names.

### DES-01 Every design id in server scope has code and a test, or a recorded descope as a Core blockers row, an open question, or a client-only id.

**Why.** A requirement that no one built and no one descoped ships as a silent gap, and players miss what the design promised.

Do:

```java
// UI4: progress shows on the panel in real time. Spec: Push ProgressChanged.
void onProgress(UserActor actor, ChainState state, int amount, long now) {
    ChainCore.addProgress(state, amount, now);
    actor.push(Push.of(Pushes.CHAIN_PROGRESS).put("progress", state.progress()));
}
```

Don't:

```java
// UI4 asks for a real-time progress push. The code sends none,
// and no Core blockers row or open question records the drop.
void onProgress(UserActor actor, ChainState state, int amount, long now) {
    ChainCore.addProgress(state, amount, now);
}
```

**Check.** List every id in `design.md`. Match each one to code `file:line` and a test, or to the Core blockers row, the open question, or the client-only reason that records why the server does not build it.

- needs: none

### DES-02 The code's behavior and numbers equal the design's rules, state transitions, end conditions, limits, rewards, costs, durations, and counts, and config values equal the design's tables or the sheets they cite.

**Why.** A wrong end condition, reward, cost, or count grants or takes the wrong player value, and the code still passes tests written from the same mistake.

Do:

```java
// R5: the chain ends when milestone 3 is claimed.
if (milestoneId == config.finalMilestoneId()) {
    state.endChain(now);
}
```

```json
"milestoneTargets": [10, 25, 50]
```

Don't:

```java
// Ends only after all three milestones are claimed, so a player who
// claims milestone 3 first keeps the chain open.
if (state.claimedMilestones().size() == config.milestones().size()) {
    state.endChain(now);
}
```

```json
"milestoneTargets": [10, 20, 50]
```

**Check.** For each rule, state, formula, reward, timing, and edge case row, read the code that implements it and compare each condition and number with the design. Compare each config value with the design's Config tables, or with the sheet range a row cites.

- needs: none

### DES-03 Every settled decision holds in the code, including each answered question's answer, each skipped question's interim default, and each Core blockers resolution, and a descoped id has no half-built code.

**Why.** A settled decision is a promise to the designer, and code that drifts from it reopens a question that someone already closed.

Do:

```java
// Q2 answered on <date>: a claim after the event ends is rejected.
if (now >= config.endAt()) {
    return Errors.FEATURE_CLOSED;
}
```

Don't:

```java
// Q2 was answered "rejected", but the code still grants after the end.
if (now >= config.endAt() + config.graceMillis()) {
    return Errors.FEATURE_CLOSED;
}
```

**Check.** For each Q row, read its status and confirm the code follows the answer or the interim default. For each Core blockers resolution, confirm the code matches it. For each descoped id, confirm the code has no handler, field, or config key for it.

- needs: none
