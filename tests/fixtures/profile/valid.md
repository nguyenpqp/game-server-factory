---
profile_version: 1
language: 'java'
build_cmd: 'gradle build -x test'
test_cmd: 'gradle test'
test_one_cmd: 'gradle test --tests {class}'
source_root: 'src/main/java'
test_root: 'src/test/java'
feature_root: 'src/main/java/com/example/game/feature'
generated_paths:
  - 'src/main/java/com/example/game/generated'
lint:
  time_call: 'ServerClock\.now\('
  forbidden_time:
    - 'System\.currentTimeMillis\('
    - 'Instant\.now\('
    - 'LocalDate(Time)?\.now\('
    - 'new Date\(\)'
  random_call: 'GameRandom\.next\w*\('
  forbidden_random:
    - 'new Random\('
    - 'Math\.random\('
    - 'ThreadLocalRandom'
  env_live_check: 'Env\.isLive\(\)'
  metric_call: 'MetricLogger\.userAction\('
  trace_id_call: 'TraceIds\.next\('
  cheat_marker: '@CheatCommand'
  blocking_calls:
    - 'Thread\.sleep\('
    - '\.join\(\)'
    - '\.await\('
    - '\.block\(\)'
---

# Game server profile

### CAP-COMMAND Command channel and ids

- status: present
- api: `ExampleCommand.call()` is the entry point for feature code.
- file: `src/main/java/com/example/core/ExampleCommand.java`
- snippet:

```java
Object value = ExampleCommand.call();
```

### CAP-RESPONSE Response and push

- status: present
- api: `ExampleResponse.call()` is the entry point for feature code.
- file: `src/main/java/com/example/core/ExampleResponse.java`
- snippet:

```java
Object value = ExampleResponse.call();
```

### CAP-ERRORS Error codes

- status: present
- api: `ExampleErrors.call()` is the entry point for feature code.
- file: `src/main/java/com/example/core/ExampleErrors.java`
- snippet:

```java
Object value = ExampleErrors.call();
```

### CAP-CLIENTVER Client version

- status: partial
- api: `ExampleClientver.call()` is the entry point for feature code.
- file: `src/main/java/com/example/core/ExampleClientver.java`
- snippet:

```java
Object value = ExampleClientver.call();
```

- blocker: BG-07 cannot be met for part of the cases.
- proposal: Extend the existing class to cover the remaining cases.

### CAP-ACTOR User actor execution

- status: present
- api: `ExampleActor.call()` is the entry point for feature code.
- file: `src/main/java/com/example/core/ExampleActor.java`
- snippet:

```java
Object value = ExampleActor.call();
```

### CAP-OWNERSHIP User ownership across nodes

- status: present
- api: `ExampleOwnership.call()` is the entry point for feature code.
- file: `src/main/java/com/example/core/ExampleOwnership.java`
- snippet:

```java
Object value = ExampleOwnership.call();
```

### CAP-DRAIN Drain and handover

- status: missing
- blocker: BG-10 cannot be met. The core has no such part, so a rollout can duplicate or lose player value.
- proposal: Add one small helper class in the core that provides it, with a unit test.

### CAP-USERSTORE Per-user storage

- status: present
- api: `ExampleUserstore.call()` is the entry point for feature code.
- file: `src/main/java/com/example/core/ExampleUserstore.java`
- snippet:

```java
Object value = ExampleUserstore.call();
```

### CAP-CAS CAS writes

- status: present
- api: `ExampleCas.call()` is the entry point for feature code.
- file: `src/main/java/com/example/core/ExampleCas.java`
- snippet:

```java
Object value = ExampleCas.call();
```

### CAP-REDIS Redis access

- status: present
- api: `ExampleRedis.call()` is the entry point for feature code.
- file: `src/main/java/com/example/core/ExampleRedis.java`
- snippet:

```java
Object value = ExampleRedis.call();
```

### CAP-IDGEN Unique ids

- status: present
- api: `ExampleIdgen.call()` is the entry point for feature code.
- file: `src/main/java/com/example/core/ExampleIdgen.java`
- snippet:

```java
Object value = ExampleIdgen.call();
```

### CAP-INVENTORY Currency and inventory

- status: present
- api: `ExampleInventory.call()` is the entry point for feature code.
- file: `src/main/java/com/example/core/ExampleInventory.java`
- snippet:

```java
Object value = ExampleInventory.call();
```

### CAP-CROSSNODE Cross-node delivery

- status: present
- api: `ExampleCrossnode.call()` is the entry point for feature code.
- file: `src/main/java/com/example/core/ExampleCrossnode.java`
- snippet:

```java
Object value = ExampleCrossnode.call();
```

### CAP-INBOX Durable inbox

- status: present
- api: `ExampleInbox.call()` is the entry point for feature code.
- file: `src/main/java/com/example/core/ExampleInbox.java`
- snippet:

```java
Object value = ExampleInbox.call();
```

### CAP-LEASE Cluster-wide job lease

- status: missing
- blocker: MN-07 cannot be met. The core has no such part, so a rollout can duplicate or lose player value.
- proposal: Add one small helper class in the core that provides it, with a unit test.

### CAP-CONFIG Config loading

- status: present
- api: `ExampleConfig.call()` is the entry point for feature code.
- file: `src/main/java/com/example/core/ExampleConfig.java`
- snippet:

```java
Object value = ExampleConfig.call();
```

### CAP-ENV Environment

- status: present
- api: `ExampleEnv.call()` is the entry point for feature code.
- file: `src/main/java/com/example/core/ExampleEnv.java`
- snippet:

```java
Object value = ExampleEnv.call();
```

### CAP-CLOCK Server time

- status: present
- api: `ExampleClock.call()` is the entry point for feature code.
- file: `src/main/java/com/example/core/ExampleClock.java`
- snippet:

```java
Object value = ExampleClock.call();
```

### CAP-RNG Random numbers

- status: present
- api: `ExampleRng.call()` is the entry point for feature code.
- file: `src/main/java/com/example/core/ExampleRng.java`
- snippet:

```java
Object value = ExampleRng.call();
```

### CAP-CHEAT Cheat channel

- status: present
- api: `ExampleCheat.call()` is the entry point for feature code.
- file: `src/main/java/com/example/core/ExampleCheat.java`
- snippet:

```java
Object value = ExampleCheat.call();
```

### CAP-ADMIN Admin channel

- status: present
- api: `ExampleAdmin.call()` is the entry point for feature code.
- file: `src/main/java/com/example/core/ExampleAdmin.java`
- snippet:

```java
Object value = ExampleAdmin.call();
```

### CAP-HTTP HTTP channel

- status: present
- api: `ExampleHttp.call()` is the entry point for feature code.
- file: `src/main/java/com/example/core/ExampleHttp.java`
- snippet:

```java
Object value = ExampleHttp.call();
```

### CAP-METRIC Metric logger

- status: present
- api: `ExampleMetric.call()` is the entry point for feature code.
- file: `src/main/java/com/example/core/ExampleMetric.java`
- snippet:

```java
Object value = ExampleMetric.call();
```

### CAP-TRACEID Trace id

- status: present
- api: `ExampleTraceid.call()` is the entry point for feature code.
- file: `src/main/java/com/example/core/ExampleTraceid.java`
- snippet:

```java
Object value = ExampleTraceid.call();
```

### CAP-UNITTEST Unit test support

- status: present
- api: `ExampleUnittest.call()` is the entry point for feature code.
- file: `src/main/java/com/example/core/ExampleUnittest.java`
- snippet:

```java
Object value = ExampleUnittest.call();
```

### CAP-BOT E2E bot

- status: partial
- api: `ExampleBot.call()` is the entry point for feature code.
- file: `src/main/java/com/example/core/ExampleBot.java`
- snippet:

```java
Object value = ExampleBot.call();
```

- blocker: TEST-10 cannot be met for part of the cases.
- proposal: Extend the existing class to cover the remaining cases.

### CAP-GENERATED Generated files

- status: present
- api: `ExampleGenerated.call()` is the entry point for feature code.
- file: `src/main/java/com/example/core/ExampleGenerated.java`
- snippet:

```java
Object value = ExampleGenerated.call();
```

### CAP-BUILD Build

- status: present
- api: `ExampleBuild.call()` is the entry point for feature code.
- file: `src/main/java/com/example/core/ExampleBuild.java`
- snippet:

```java
Object value = ExampleBuild.call();
```
