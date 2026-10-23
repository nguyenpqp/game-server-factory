# game-server-factory

A Claude Code marketplace with one plugin, `game-server`. The plugin turns a game design document (GDD) or a plain feature prompt into Java game server feature code, with unit tests and metric log calls, on the core your server already has.

It adds features only. It does not write or change your network layer, login, sessions, or database clients. When the core lacks something a rule needs, the skills report a blocker with the smallest core change and stop for you.

## What the plugin enforces

Every skill works to the same fixed rulebook. The rules come from these constraints.

- **Server-authoritative.** The client sends intents. The server computes every result, cost, and reward, using its own clock and its own random numbers.
- **Multi-node.** One world runs on many peer nodes behind a load balancer, and one node owns a user at a time. Feature code keeps no shared mutable state in the process. Cluster-wide state lives in Redis and changes in one atomic step. A Redis or store error is an unknown result, never a yes or a no. Cluster jobs stay correct when two nodes run them at once.
- **Blue-green with old clients.** Two server versions and older clients read the same data during a rollout. Stored data changes by adding fields only, and a format the old version cannot read needs a maintenance deploy. Cross-node messages carry signals, and anything that must arrive goes through the durable inbox. A failed boot step stops the boot. New features gate on the client version.
- **Couchbase and Redis only.** Per-user data goes through the Couchbase client your project already uses. Any other store needs your approval first.
- **Performance budget.** The design target is about 100k peak concurrent players and 1M daily players. Each command gets a budget for database and Redis calls, payload size, and per-user memory.
- **Config, metrics, cheats, admin.** Balance numbers live in one config file per feature. Every action writes a metric row with a trace id. Log lines go through the feature's logger at a level that matches the harm, and carry the user id and trace id. Every feature ships cheat commands that stay off live, and admin commands with an API spec.
- **Modular features.** Each feature imports only its own, shared, and contract packages. An effect on another feature that a reply depends on is a contract call, not an event.
- **Client in sync.** Each feature has a read command that rebuilds the client's view. A reply carries server time and the stored values it changed, never derived flags. A push reports only a change the client did not make, and no value depends on it.
- **True to the design.** The code builds every server-side requirement in the design, with the design's numbers, rules, and end conditions. It keeps every settled decision: answered questions, the defaults of skipped questions, and Core blockers resolutions. The review traces each design id to code and tests.

The rules are listed with ids in `plugins/game-server/skills/server-rules/references/index.md`. Specs and reviews cite them by id.

Genre notes in `plugins/game-server/skills/server-rules/references/genres/` cover rankings and seasons, randomness and gacha, economy and exchange, events and passes, guilds and groups, and PvP and matchmaking. Each lists the questions a design must answer and the traps the code falls into, and points each trap at its rules. The notes never prescribe a design, because designs vary from game to game.

## Install

Add the marketplace and install the plugin from inside Claude Code.

```
/plugin marketplace add nguyenpqp/game-server-factory
/plugin install game-server@game-server-factory
```

To add a local clone instead, pass its path to the first command.

```
/plugin marketplace add /path/to/game-server-factory
```

For a one-off session that loads the plugin straight from a clone, without installing it, start Claude Code with the plugin directory.

```
claude --plugin-dir plugins/game-server
```

The plugin manifest has no version, so an install tracks the commit of the marketplace.

## The six skills

| Skill | Runs when | Input | Output |
| --- | --- | --- | --- |
| `server-rules` | Triggers when you design, write, or review Java game server feature code | A rule id or a topic | The rule with a reason, a Java do and don't, and a reviewer check, or the genre note for a kind of feature. Writes no files. |
| `server-profile` | Explicit only (`/game-server:server-profile`) | The target server repository, read-only | `docs/game-server/profile.md`, which records how the core provides each capability and which gaps block multi-node or blue-green safety |
| `gdd-intake` | Triggers when you hand over a GDD folder, slides, docs, a balance sheet, or a feature prompt | A folder of pptx, docx, xlsx, PDF, Markdown, or images, or a prompt | `docs/game-server/features/<feature>/design.md` with sourced requirements and open questions, plus draft config JSON in the `config` folder beside it |
| `feature-spec` | Triggers when you want a server design or plan for a feature, or a change to a feature that has one | `design.md` or a prompt, plus the profile | `docs/game-server/features/<feature>/spec.md`. On request, also an ordered task list at `docs/game-server/features/<feature>/tasks.md` |
| `feature-build` | Triggers when you implement a feature, command, or spec slice | The profile, the spec, and one slice | Java code and unit tests for the slice, written through the core APIs the profile records, and a slice report |
| `feature-review` | Triggers when you review feature code or a diff | The code, the profile, the spec, and the design | A findings report with severity, rule id, `file:line`, and a failure scenario, plus a trace table from each design id to code and tests. It sweeps the added lines for call-shaped breaks first. |

`server-profile` is explicit only because it writes into your repository from a scan. Claude never starts it on its own, and a subagent will not pick it up from its description. The other five load from their descriptions.

## Order of use

1. **Profile.** Run `server-profile` once per server repository, and again when the core changes. The spec, build, and review skills stop without it.
2. **Intake.** Run `gdd-intake` on the GDD folder or the prompt. Answer the open questions it lists.
3. **Spec.** Run `feature-spec` on the design. If the spec lists a core blocker, the skill stops and you decide. A risk you accept for every feature goes to `docs/game-server/decisions.md`, and later specs do not stop on it. Confirm the spec. For a large feature, ask for a build plan.
4. **Build.** Run `feature-build` on the spec, one slice at a time for a large feature.
5. **Review.** Run `feature-review` over the finished branch.

`server-rules` is not a step. The other skills load it when they need a rule.

The skills work in a plain chat, across sessions, or under any workflow plugin. [Use the skills](docs/usage.md) walks through this order.

## Check this repository

Run these from the repository root. Both run on Python 3 alone, and the converter tests for docx and xlsx need python-docx and openpyxl.

```
python3 -m unittest discover -s tests
python3 scripts/validate_plugin.py --denylist /path/to/denylist.txt
```

The unit tests cover the validator and the `gdd-intake` converter. A test that needs a package or program the machine lacks skips and names it.

The validator checks the manifests, each skill's frontmatter, every relative link, every rule id and capability id against its index, and the tracked files for absolute home paths and private keys. It also scans the tracked files for terms from a denylist. The denylist is a plain text file with one term per line. The public repository must hold no internal project names, class names, hosts, or GDD content, so each maintainer keeps the list of those terms in a local file that is never committed. The validator fails if a tracked file contains any listed term, matched without regard to case. Pass the file with `--denylist` or set `GSS_DENYLIST`. Without either, the validator warns that it skipped the private-term scan.

`gdd-intake` reads docx with python-docx and xlsx with openpyxl (`python3 -m pip install python-docx openpyxl`). PyMuPDF is optional and reads PDF files. For pptx it needs nothing beyond Python 3.
