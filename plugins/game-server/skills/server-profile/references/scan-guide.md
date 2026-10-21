# Scan guide

Search recipes for filling the profile of a Java game server. The patterns use `rg` regex syntax and cover the usual libraries, so adapt them to the project's own names once you find the first hit. The statuses and the "Must provide" lists are in `profile-template.md`.

## How to scan

- Start from the build file (`build.gradle.kts`, `build.gradle`, or `pom.xml`) and the class with the `main` method. Follow the startup path. Most capabilities are wired there.
- Prefer a search that finds a call site over one that finds a definition. A class that nothing calls is not a capability.
- Ignore test sources and generated sources unless the capability is about them.
- Record the first working example call in the project. That becomes the `snippet`.
- Run `rg -c` first when a pattern may match thousands of lines, then narrow it.

## Frontmatter

| Keys | Where to look |
| --- | --- |
| `build_cmd`, `test_cmd`, `test_one_cmd` | The build file, CI config, and the README. For Gradle, `gradle test --tests {class}`. For Maven, `mvn -Dtest={class} test`. |
| `source_root`, `test_root` | The `sourceSets` block of the build file, or the Maven default `src/main/java` and `src/test/java`. Some projects use `src` and `test`. |
| `feature_root` | The parent directory of the packages that hold one feature each. Find the package of the newest feature. |
| `generated_paths` | `rg -il "generated|do not edit"` over source files, plus build file tasks that run an exporter. |
| `lint.*` | Fill after the capabilities below, from the call you chose as the example. Escape regex characters for a literal call, such as `ServerClock\.now\(`. |

## Capabilities

### CAP-COMMAND

- Search for the registration of handlers at startup. `rg -n "addRequestHandler|registerHandler|\.register\(|ChannelInboundHandler|SimpleChannelInboundHandler|extends \w*Handler"`.
- Search for the decoder. `rg -n "ByteBuf|ByteBuffer|readInt\(|readShort\(|readUtf|decode\("`. Check what happens when a field is absent.
- Search for the id table. `rg -n "static final (short|int) \w*(CMD|_ID)"`, or a generated class of ids. Note whether blocks of ids are reserved per feature.

### CAP-RESPONSE

- Search for the call handlers use to answer. `rg -n "sendResponse|writeAndFlush|\.send\(|respond\("`.
- Search for pushes by user id. `rg -n "pushTo|sendToUser|broadcast|push\("`. Read whether it reaches a user on another node.
- Read the encoder. Keyed or length-prefixed fields tolerate appended fields. Fixed positional fields do not.

### CAP-ERRORS

- Search for an error code table. `rg -n "enum \w*Error|class \w*Error\w*|static final (short|int) \w*(ERROR|FAIL|INVALID)"`.
- Count the generic codes. Many features sharing one failure code is the usual partial.

### CAP-CLIENTVER

- Search the login or handshake path. `rg -n "clientVersion|buildNumber|protocolVersion|appVersion|minVersion"`.
- Read the check. A comparison that always returns true, or a version that is read and dropped, is partial.

### CAP-ACTOR

- Search for executors. `rg -n "newSingleThreadExecutor|Executors\.new|ExecutorService|EventLoopGroup|DefaultEventExecutor|Disruptor|ScheduledExecutorService"`.
- Find how a user maps to a thread, usually `hash(userId) % n`. Find the call that submits work to another user's executor.
- Read the login path for blocking database reads. `rg -n "\.get\(\)|\.join\(\)|\.await\(|\.sync\(\)|Thread\.sleep"` inside classes on that path. The results feed `lint.blocking_calls`.

### CAP-OWNERSHIP

- Search for a record of which node holds a user. `rg -n -i "owner|lease|lock.*user|userNode|sessionNode|fencing|fence"` in the login and logout code.
- Check what stops a second node from saving the same user. No owner field and no CAS on save means missing or partial.

### CAP-DRAIN

- Search the shutdown path. `rg -n "addShutdownHook|@PreDestroy|destroy\(|shutdown\(|drain|readiness|/health|/alive|/ready"`.
- Read whether it closes listeners first, waits for queued commands, awaits every save result, and reports not ready while draining.

### CAP-USERSTORE

- Search for the document store client. `rg -n "couchbase|CouchbaseClient|Collection\.(upsert|get)|MemcachedClient|spymemcached|\.set\(|\.gets\("`.
- Find the document key format. A class name inside the key breaks stored data on rename.
- Read the serializer. `rg -n "ObjectMapper|Gson|JsonIgnoreProperties|FAIL_ON_UNKNOWN|JsonAnySetter"`. A serializer that drops unknown fields on load is partial.
- Find the changed flag and the save cycle. Check that a failed write is reported and the flag is not cleared before the write is confirmed. Find the hook that runs after load, which is where lazy migration goes.

### CAP-CAS

- Search for CAS calls. `rg -n "\.gets\(|\.cas\(|getAndLock|replace\(.*cas|casMismatch|CasMismatch|OptimisticLock"`.
- Count blind writes against CAS writes with `rg -c`. Mostly blind sets means partial.
- Look for a retry helper with a bounded attempt count, and for an add that fails when the key exists (`\.add\(`, `insert\(`).

### CAP-REDIS

- Search for the client. `rg -n "io\.lettuce|redis\.clients\.jedis|Redisson|RedisClusterClient|JedisPool|StatefulRedis"`.
- Search for Lua and atomic commands. `rg -n "eval\(|evalsha|RedisScript|\.incr\(|\.setnx\(|SET.*NX|hsetnx|zadd"`.
- Check key naming for hash tags, such as `{user:123}:inbox`, when the deployment is a cluster. Check that calls use a timeout and are not issued on the actor thread.

### CAP-IDGEN

- Search for id generators. `rg -n -i "snowflake|idgenerator|nextId|\.incr\(|AtomicLong.*id|sequence"`.
- Find where the node bits come from. Config that two nodes can share, or an in-process counter saved on a timer, is partial.

### CAP-INVENTORY

- Search for currency and item methods. `rg -n "\b(spend|take|consume|deduct|add|grant|give)\w*\((.*)(Item|Currency|Gold|Gem|Coin)"`.
- Check that each change takes a reason and a trace id, writes a metric row, and rejects unknown ids and non-positive amounts. Find a multi-item check-then-take.

### CAP-CROSSNODE

- Search for messaging between nodes. `rg -n "pubsub|PUBLISH|subscribe|RedisPubSub|rpc|grpc|NodeMessage|remoteUser|forward"`.
- Check that a message runs on the target user's executor on the owner node.

### CAP-INBOX

- Search for a per-user queue of pending grants or events. `rg -n -i "inbox|mailbox|pending(Events|Rewards|Grants)|outbox"`.
- Check that appends use CAS, and that the owner drains the queue at login and while the user is online.

### CAP-LEASE

- Search for scheduled jobs. `rg -n "@Scheduled|scheduleAtFixedRate|scheduleWithFixedDelay|Timer\(|Quartz|CronTrigger"`.
- For each job, look for a lease or lock around it. `rg -n "SET.*NX.*PX|tryLock|acquireLease|JobLease|RLock"`. Jobs on every node with no lease make the capability missing.

### CAP-CONFIG

- Search for JSON loaders. `rg -n "readValue\(|fromJson\(|loadFromJson|JsonParser|conf/.*\.json|ConfigManager|preloadConfig"`.
- Check for a validate step that throws at startup, a published immutable snapshot, and a test hook such as `setInstanceForTest`. Note whether a reload exists or a restart is needed.

### CAP-ENV

- Search for the environment name. `rg -n -i "isLive|isProduction|environment|serverType|ServerType|env\.name|System\.getenv"`.
- Check where the value comes from. Players must not be able to change it. Look for a second flag that can enable live behavior, such as a cheat flag.

### CAP-CLOCK

- Search for the shared time call. `rg -n "class \w*(Clock|Time)\w*"` and the most common caller.
- Count direct calls. `rg -c "System\.currentTimeMillis|Instant\.now|LocalDate(Time)?\.now|new Date\(\)"`. These become `lint.forbidden_time`.
- Check that core logic takes `now` as a parameter, and that a per-user offset exists for cheats.

### CAP-RNG

- Search for random sources. `rg -n "new Random\(|Math\.random|ThreadLocalRandom|SecureRandom|class \w*Random\w*"`.
- A shared injectable class with a seedable test version is present. Direct static calls in game logic are partial. The direct calls become `lint.forbidden_random`.

### CAP-CHEAT

- Search for the cheat channel. `rg -n -i "cheat"` over source and config.
- Check registration. Find the place the handler is registered and whether the live environment skips it. Find the marker (an annotation or a base class) that every cheat class carries.

### CAP-ADMIN

- Search for the admin channel. `rg -n -i "admin"` over handlers, login code, and routes.
- Check authentication on every request, a second factor on live, routing of per-user commands to the target user's executor, audit records, and the body format. Note any admin web repository the README names.

### CAP-HTTP

- Search for the HTTP server. `rg -n "jetty|HttpServer|Undertow|NettyHttp|HttpServlet|@WebServlet|HttpHandler"`.
- Check signature verification, the caller allowlist and its value on live (an empty list that allows every caller is partial), an idempotency lock, and delivery through the durable inbox.

### CAP-METRIC

- Search for the logger. `rg -n "class \w*(Metric|Log)\w*"`, then `rg -n "log4j|slf4j|Logger\.|appender"`.
- Find the call that writes a user action row. Its call pattern becomes `lint.metric_call`. Check for a trace id column, system and exception rows, extra fields, and the queue behavior when it is full.
- Find where rows land and how they are queried, such as a log shipper and a table per log type.

### CAP-TRACEID

- Search for the minting call. `rg -n -i "traceId|trace_id|nextTrace"`. The call pattern becomes `lint.trace_id_call`.
- Check that the node bits are unique per running process, and that currency, inventory, and metric calls accept the id.

### CAP-UNITTEST

- Search the build file for the test framework. `rg -n "junit|jupiter|testng|useJUnitPlatform"`.
- Read two existing tests. Check whether per-user state can be built in memory without a database, and which hooks inject time, random numbers, config, and environment.

### CAP-BOT

- Search for a scripted client. `rg -n -l -i "loadtest|fakeclient|e2e|simulator|bot"` over the tree and the docs.
- Check that it logs in, sends commands, and checks responses against scenarios stored as files. A client that only sends load is partial.

### CAP-GENERATED

- Search for generated markers. `rg -n -il "generated|auto-generated|do not edit"`.
- Search the build file and scripts for the exporter. Record the source it reads and the command that regenerates the files. A generator outside the repository with no written command is partial.

### CAP-BUILD

- Read the build file and CI config for the JDK version, the build tool version, and the commands. `rg -n "sourceCompatibility|JavaVersion|jvmToolchain|<maven.compiler|<release>"`.
- Check whether `test_cmd` needs a running external service. If it does, the capability is partial.
