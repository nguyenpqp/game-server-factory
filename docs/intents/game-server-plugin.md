# Game server feature skills plugin

## Problem

The owner wants "bộ skill vibe code Java cho game server, đầu vào là GDD hoặc prompt mô tả tính năng. đầu ra là code server có đầy đủ unit test, metric log" (a skill set that turns a GDD or a feature prompt into Java server code with full unit tests and metric logs).

The target servers serve hundreds of thousands to millions of users on mobile. Every feature must run on many server nodes, survive blue-green deployment, and stay compatible with old clients during rollout ("tương thích ngược với client cũ khi rollout"). The server decides every result. Design changes often, so features must be modular with config kept in separate, editable files. Each feature ships cheat packets for client testing (blocked on live) and admin commands.

The skills that exist today live inside one internal reference project. They name its classes and paths directly. None of them mentions multi-node safety, blue-green, or client compatibility.

## Outcome

- A Claude Code marketplace `game-server-factory` holds one plugin `game-server` with six skills: `server-rules`, `server-profile`, `gdd-intake`, `feature-spec`, `feature-build`, and `feature-review`.
- `python3 -m unittest discover -s tests` and `python3 scripts/validate_plugin.py --denylist <local denylist>` pass on the branch. The validator checks frontmatter, relative links, rule ids, and the private-term denylist.
- `claude --plugin-dir plugins/game-server` loads all six skills.
- An acceptance run on the internal reference project uses a copy of its source with one shipped feature removed. It starts from that feature's original GDD and produces a profile, a design, a feature spec, and Java code with unit tests and metric log calls. `feature-review` reports no Critical finding, and `lint_feature.py` reports no error. A coverage report maps every requirement in the original design to generated code or tests.
- Compile and test execution of the generated Java are NOT VERIFIED in the acceptance run. The owner dropped the build step because this machine has no JDK or Gradle.

## Surfaces

- Server developers who use Claude Code, either plain or with the nstack workflow plugin.
- Each target game server repository. The skills read it through its profile at `docs/game-server/profile.md`.
- nstack Interview, Spec build, and Feature playbooks. They reach these skills through description triggers and absolute paths in delegate briefs.

## Constraints

- Feature work only. The skills reuse the project's existing core (network, login, sessions, DB clients) and tie to no framework. The core provides a login-gated socket channel and one HTTP channel.
- Storage is Couchbase and Redis only. Couchbase access uses whatever client the project has (memcached protocol for now). Any other tool needs the developer's approval first.
- Server-authoritative. The client sends intents, never results.
- Performance first. The design target is about 100k peak CCU and about 1M DAU.
- One world on N peer nodes behind a load balancer. One node owns a user at a time.
- Blue-green uses drain and reconnect. Two server versions and older clients must work against the same data during rollout.
- Skills are written in English and target Java. Claude Code only.
- The public repository holds no internal project names, class names, hostnames, secrets, or GDD content. A local denylist check enforces this.
- When the core lacks a capability that a rule needs, the skills report a blocker with the smallest core change and stop for the developer.

## Out of scope

- Writing or rewriting a core: networking, login, DB clients, user ownership leases.
- Client code, deploy tooling (load balancer switch, orchestration), and new load test tools.
- Codex skills, languages other than Java, and the superpowers workflow.
- Changes to the internal reference project or its existing skills.
- An orchestrator or entry-point skill. Workflows drive; these skills supply domain knowledge.

## Decisions

### The owner's

- Separate repository and marketplace, local at `~/Workspace/game-server-skills`, remote `github.com/nguyenpqp/game-server-factory` (public).
- Domain skills only, no entry skill.
- Features only, on the project's existing core.
- Multi-server means one world on N peer nodes.
- Blue-green drains and reconnects online players. Old clients stay compatible during rollout.
- GDD input comes as a folder of pptx, docx, xlsx, and images, as Markdown, or as Excel balance sheets. A plain feature prompt is also valid input.
- English skill text, Claude Code only, Java only.
- Couchbase through whatever client the project already uses.
- About 100k peak CCU and 1M DAU.
- Missing core capability means a blocker plus a proposal, not a workaround.
- Port the existing GDD-to-design skill into the plugin.
- Skills trigger from their description. Skills that write files into the target repo run only on explicit request.
- Support nstack and plain Claude Code.
- Verification is unit tests, an E2E bot when the project has one, and a performance budget per command.
- Admin is server commands plus an API spec. Admin web UI only when the profile declares an admin web repo.
- Metric is a metric spec, logger calls, and KPI queries.
- Leave the reference project's skills untouched.
- Internal content stays local and gitignored.
- No build step in the acceptance run.

### Mine

- The profile is a registry of core capabilities with fixed ids (`CAP-*`). Each entry has a status (present, partial, missing), the concrete API, a snippet, and a file path.
- Rules have fixed ids by group: `AUTH`, `MN`, `BG`, `PERF`, `CFG`, `MET`, `CHEAT`, `ADMIN`, `HTTP`, `TEST`. Spec, build, review, and lint cite rules by id. A test fails on any cited id missing from the index.
- Cheat handlers are not registered on live, and each cheat command also checks the environment at the point of mutation.
- Background jobs that must run once per cluster hold a lease. Redis keys use hash tags so multi-key operations work on Redis Cluster.
- Feature config loads into an immutable snapshot that is validated before use, so hot reload stays possible.
- Stored data changes only by adding fields. A changed meaning gets a new field or a new command id. New response fields are appended and optional. New features gate on client version through `CAP-CLIENTVER`.
- Plugin tests use Python `unittest` because `pytest` is not installed.
- The Spec build playbook runs the work as the tickets in `docs/intents/game-server-plugin-tickets.md`.
- No `gh` CLI is installed, so delivery pushes the branch and links the GitHub compare page.

## Open questions

- The owner answered "Cần sửa vài điểm" (needs some fixes) at confirmation without saying which points. Work continues on the defaults above under the owner's goal. Each correction amends this file when it arrives.
- The GDD converter scripts may need Python packages or LibreOffice that this machine lacks. Their tests skip with a stated reason when a dependency is missing.
