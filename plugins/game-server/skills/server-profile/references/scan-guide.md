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
- Read the command classes and find the method that each command or request handler class declares as its entry point. Set `lint.command_method` to a regex for that method name, such as `handle\w*`.
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
- Read the login path for blocking database reads. `rg -n "\.get\(\)|\.join\(\)|\.await\(|\.sync\(\)|Thread\.sleep"` inside classes on that path. The results feed `lint.blocking_calls`. Leave a synchronous Redis call out of it when the CAP-REDIS entry records that call as the project's pattern, with its timeout and circuit breaker, so a review does not flag every feature that uses it.

### CAP-OWNERSHIP

- Search for a record of which node holds a user. `rg -n -i "owner|lease|lock.*user|userNode|sessionNode|fencing|fence"` in the login and logout code.
- Check what stops a second node from saving the same user. No owner field and no CAS on save means missing or partial.
- Read every save path, including autosave and shutdown save, and find the ownership check before the write. Read what the check returns on a Redis error, and what the node does once its own heartbeat lapses. A check that maps an error to "owned" with no heartbeat bound is partial.
- Read the login takeover. A takeover that waits a fixed time and then takes the user from a live owner is partial. Read the release: a delete of the owner record, instead of a released marker, is partial.

### CAP-DRAIN

- Search the shutdown path. `rg -n "addShutdownHook|@PreDestroy|destroy\(|shutdown\(|drain|readiness|/health|/alive|/ready"`.
- Read whether it closes listeners first, waits for queued commands, awaits every save result, and reports not ready while draining.
- Read what happens when a final save fails: whether the node keeps ownership and retries, what limits each kind of failure has, and whether login and shutdown see the pending save.
- Find the order in which shutdown removes the heartbeat and leases, and whether a `finally` block covers it. Find the boot failure path: `rg -n "System\.exit|halt\("` near the boot entry point. A boot that logs an error and keeps running is partial.
- Find the readiness signal and read when it turns true. A log line or a flag set before listeners are bound is partial.

### CAP-USERSTORE

- Search for the document store client. `rg -n "couchbase|CouchbaseClient|Collection\.(upsert|get)|MemcachedClient|spymemcached|\.set\(|\.gets\("`.
- Find the document key format. A class name inside the key breaks stored data on rename.
- Read the serializer. `rg -n "ObjectMapper|Gson|JsonIgnoreProperties|FAIL_ON_UNKNOWN|JsonAnySetter"`. A serializer that drops unknown fields on load is partial.
- Find the code that keeps unknown fields, if any, and list its callers. Record which documents use it and whether it keeps nested fields or only top-level ones.
- Find the changed flag and the save cycle. Check that a failed write is reported and the flag is not cleared before the write is confirmed. Find the hook that runs after load, which is where lazy migration goes.

### CAP-CAS

- Search for CAS calls. `rg -n "\.gets\(|\.cas\(|getAndLock|replace\(.*cas|casMismatch|CasMismatch|OptimisticLock"`.
- Count blind writes against CAS writes with `rg -c`. Mostly blind sets means partial.
- Look for a retry helper with a bounded attempt count, and for an add that fails when the key exists (`\.add\(`, `insert\(`).
- Read the catch blocks of the retry helper. A timeout or error that loops back and applies the change again is partial. Check that the change runs on the copy the read returned, not on a live object.

### CAP-REDIS

- Search for the client. `rg -n "io\.lettuce|redis\.clients\.jedis|Redisson|RedisClusterClient|JedisPool|StatefulRedis"`.
- Search for Lua and atomic commands. `rg -n "eval\(|evalsha|RedisScript|\.incr\(|\.setnx\(|SET.*NX|hsetnx|zadd"`.
- Find out whether the deployment is one instance or a cluster, from the client class, the deploy config, or the docs. Check key naming for hash tags, such as `{user:123}:inbox`, when it is a cluster. Check that scripts get every key in KEYS.
- Check that calls use a timeout and are not issued on the actor thread. When they are by design, find the circuit breaker.
- Read the wrapper's error path. A helper that returns null or an empty value on error is partial, because callers cannot tell "absent" from "down". Record the eviction policy and persistence from the Redis config or docs.

### CAP-IDGEN

- Search for id generators. `rg -n -i "snowflake|idgenerator|nextId|\.incr\(|AtomicLong.*id|sequence"`.
- Find where the node bits come from. Config that two nodes can share, or an in-process counter saved on a timer, is partial.
- For a counter in Redis or the store, read what an increment does when the key is missing. Creating it from zero is partial.

### CAP-INVENTORY

- Search for currency and item methods. `rg -n "\b(spend|take|consume|deduct|add|grant|give)\w*\((.*)(Item|Currency|Gold|Gem|Coin)"`.
- Check that each change takes a reason and a trace id, writes a metric row, and rejects unknown ids and non-positive amounts. Find a multi-item check-then-take.

### CAP-CROSSNODE

- Search for messaging between nodes. `rg -n "pubsub|PUBLISH|subscribe|RedisPubSub|rpc|grpc|NodeMessage|remoteUser|forward"`.
- Check that a message runs on the target user's executor on the owner node.
- Read the receive path for a message type with no handler, and read what each message carries. A payload that exists only in the message is partial, because pub/sub drops messages on reconnect. Find the periodic sweep that covers a lost message.

### CAP-INBOX

- Search for a per-user queue of pending grants or events. `rg -n -i "inbox|mailbox|pending(Events|Rewards|Grants)|outbox"`.
- Check that appends use CAS, and that the owner drains the queue at login and while the user is online.
- Read the drain from removal to the confirmed save. Record whether it applies then removes, or removes first, and what happens when the save fails or the node is no longer the owner. Check that an unknown entry type stays in place.

### CAP-LEASE

- Search for scheduled jobs. `rg -n "@Scheduled|scheduleAtFixedRate|scheduleWithFixedDelay|Timer\(|Quartz|CronTrigger"`.
- For each job, look for a lease or lock around it. `rg -n "SET.*NX.*PX|tryLock|acquireLease|JobLease|RLock"`. Jobs on every node with no lease make the capability missing.
- Read how a job learns that it still holds the lease, and which clock the validity uses. Look for per-job locks beside the cluster lease.

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
- Find the clock that heartbeat and lease freshness use. `rg -n "nanoTime|monotonic"` in the cluster code. Wall time there is partial.

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
- Find the application logger that feature code uses for errors and warnings. `rg -n "getLogger\(|LoggerFactory|LogManager|Logger\.get"`. Record the call that gives a feature its logger, and the config that sets a level per logger name.

### CAP-TRACEID

- Search for the minting call. `rg -n -i "traceId|trace_id|nextTrace"`. The call pattern becomes `lint.trace_id_call`.
- Check that the node bits are unique per running process, and that currency, inventory, and metric calls accept the id.

### CAP-UNITTEST

- Search the build file for the test framework. `rg -n "junit|jupiter|testng|useJUnitPlatform"`.
- Read two existing tests. Check whether per-user state can be built in memory without a database, and which hooks inject time, random numbers, config, and environment.
- Find the in-memory store fake, if any, and read whether its CAS token changes on every write and whether it can fail a write after or before applying it.
- Check whether the test command needs a local Redis: find tests that connect to Redis and whether they skip when it is down. Find the key prefix and wipe helper they use.

### CAP-BOT

- Search for a scripted client. `rg -n -l -i "loadtest|fakeclient|e2e|simulator|bot"` over the tree and the docs.
- Check that it logs in, sends commands, and checks responses against scenarios stored as files. A client that only sends load is partial.
- Look for a two-process drill. `rg -n -l -i "drill|two.?servers|suspend|CLIENT PAUSE"` over the tree, the tools, and the docs. Record what faults it injects and whether it can run two different builds.

### CAP-MODULE

- Find where features register at startup. `rg -n "register(Feature|Module)|implements \w*(Feature|Module)\b|new \w+(Feature|Module)\(\)"` near the startup path.
- Count imports across features. For each package under `feature_root`, run `rg -n "^import .*\.<feature root package>\.\w+\." <feature dir>` and keep the hits that name another feature's package.
- Find contract packages, such as interfaces that one feature implements and others call. `rg -n "interface \w+(Contract|Api|Port|Service)\b"`. A package of such interfaces and their value types, outside every feature package, is a contract package.
- Find events. `rg -n "publish\(|emit\(|EventBus|@Subscribe|addListener"`. Read whether a handler runs before or after the reply, in which order, and whether a failed or undeliverable event is dropped.
- Set `lint.allowed_import` to the prefix of the contract packages. Leave it empty only when the project has no contract package, because every import across features is then a finding with no fix to point to. CAP-MODULE is then `partial` or `missing`, and a review judges MOD-01 from the code alone.

### CAP-GENERATED

- Search for generated markers. `rg -n -il "generated|auto-generated|do not edit"`.
- Search the build file and scripts for the exporter. Record the source it reads and the command that regenerates the files. A generator outside the repository with no written command is partial.

### CAP-BUILD

- Read the build file and CI config for the JDK version, the build tool version, and the commands. `rg -n "sourceCompatibility|JavaVersion|jvmToolchain|<maven.compiler|<release>"`.
- Check whether `test_cmd` needs a running external service. If it does, the capability is partial.
