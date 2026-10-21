# Tickets: game server feature skills plugin

Intent: `docs/intents/game-server-plugin.md`. Spec branch: `feat/game-server-plugin`. Ticket branches: `feat/game-server-plugin--tNN`.

Every path below is relative to the repository root. The plugin root is `plugins/game-server/`.

## Shared rules for every ticket

- Verify runs from the ticket worktree root. `GSS_DENYLIST` holds the absolute path of the local denylist file. The coordinator's brief gives the value.
- Cite only rule ids listed in `plugins/game-server/skills/server-rules/references/index.md` and capability ids listed in `plugins/game-server/skills/server-profile/references/profile-template.md`. If you need a rule or capability that is not listed, report it as a follow-up. Do not add ids.
- Write skill text in English. Java examples use generic names (`UserActor`, `KvStore`, `FeatureConfig`). Never use an internal project's class names, paths, hosts, or terms. The denylist scan fails the ticket otherwise.
- Tests use Python `unittest` and the standard library. A test that needs a missing third-party package or binary calls `self.skipTest` with the package name.
- Each test file loads the script it tests by file path with `importlib.util`. There is no package `__init__.py` under `tests/`.

## T01. Scaffold the marketplace and the plugin validator

- **Builds.** A developer can add the repo as a Claude Code marketplace and run one command that checks the plugin's structure, links, ids, and private terms.
- **Blocked by.** None.
- **Writes.** `.claude-plugin/marketplace.json`, `plugins/game-server/.claude-plugin/plugin.json`, `scripts/validate_plugin.py`, `tests/test_validate_plugin.py`.
- **Acceptance.**
  - `marketplace.json` has `name: game-server-factory`, an `owner`, and one plugin `game-server` with `source: ./plugins/game-server` and a description.
  - `plugin.json` has `name`, `description`, `author`, `license`, and `keywords`. It has no `version`, so installs track the commit.
  - The validator checks these items and prints `path:line: message` for each failure, exiting 1 if any failure exists:
    - both manifests parse and carry the fields above;
    - each `plugins/game-server/skills/<dir>/SKILL.md` has frontmatter whose `name` equals `<dir>` and whose `description` is non-empty and at most 1024 characters;
    - `disable-model-invocation: true` appears only on `server-profile`;
    - every relative Markdown link and every inline-code path that starts with `references/`, `scripts/`, `prompts/`, or `../` resolves from the file that contains it;
    - every token matching `\b(AUTH|MN|BG|PERF|CFG|MET|CHEAT|ADMIN|HTTP|TEST)-\d{2}\b` in any plugin file is defined as a heading in `skills/server-rules/references/index.md`, and the check is skipped while that file does not exist;
    - every token matching `\bCAP-[A-Z]+\b` is defined as a heading in `skills/server-profile/references/profile-template.md`, and the check is skipped while that file does not exist;
    - no file tracked by git contains an absolute home path (`/Users/<name>/`, `/home/<name>/`) or a private key block;
    - no file tracked by git contains a denylist term, matched case-insensitively on word boundaries. The term list comes from `--denylist <file>` or the `GSS_DENYLIST` environment variable. Without either, the validator prints a warning that the private-term scan was skipped.
  - A skill directory without `SKILL.md` gives a warning, not a failure.
  - Tests cover each failure kind with a temporary fixture tree, plus one clean tree that passes.
- **Verify.** `python3 -m unittest discover -s tests && python3 scripts/validate_plugin.py --denylist "$GSS_DENYLIST"`

## T02. Write the shared contracts

- **Builds.** Every later skill reads the same three formats (profile, design, feature spec) and cites one fixed set of rule ids.
- **Blocked by.** T01.
- **Writes.** `plugins/game-server/skills/server-rules/references/index.md`, `plugins/game-server/skills/server-profile/references/profile-template.md`, `plugins/game-server/skills/gdd-intake/references/design-template.md`, `plugins/game-server/skills/feature-spec/references/spec-template.md`.
- **Acceptance.**
  - `index.md` lists every rule id the plugin will use, grouped as `AUTH`, `MN`, `BG`, `PERF`, `CFG`, `MET`, `CHEAT`, `ADMIN`, `HTTP`, `TEST`. Each id is a heading `### <ID> <one-line rule>`, followed by a severity (`critical`, `important`, `minor`) and the `CAP-*` ids it depends on. The list is complete, so later tickets add no ids. It covers at least these topics:
    - `AUTH`: client sends intents only; server time; server RNG; validate every field and range; ownership checks; check before take, refund on partial failure; idempotent requests that hold a request id; rate limits on costly commands.
    - `MN`: no process-local shared mutable state; one owner node per user; cross-user writes through the owner or CAS; global state in Redis with atomic operations and hash tags; once-per-cluster jobs under a lease; ids from Redis `INCR` or a unique-node snowflake; no node-local caches without invalidation.
    - `BG`: additive data changes only; unknown fields survive load and save; new or changed meaning gets a new field or command id; appended optional response fields; old clients keep working; client version gates new features; config readable by both versions; lazy, idempotent, versioned migration; saves are complete before handover.
    - `PERF`: no blocking I/O on the user actor thread; bounded DB and Redis calls per command; no N+1 calls; payload size budget; O(1) config lookups from prebuilt indexes; bounded per-user memory.
    - `CFG`: one config file per feature; validate at load and fail fast; immutable snapshot; `isActive` flag and time window; no hard-coded balance numbers.
    - `MET`: one row per user action, including failures; trace id on every row and every currency or inventory change; currency source and sink logged; funnel steps; KPI queries.
    - `CHEAT`: not registered on live; environment check at the mutation; logged like normal actions.
    - `ADMIN`: authenticated; runs on the target user's owner; audited; destructive commands blocked or confirmed on live; API spec.
    - `HTTP`: only for calls that cannot log in; signature check; non-empty allowlist on live; idempotency lock; delivery through a durable per-user inbox.
    - `TEST`: test the pure core without network; negative and cheat cases; time and RNG injected; config validation tests; compatibility tests for old data and old clients.
  - `profile-template.md` defines the profile file `docs/game-server/profile.md`:
    - YAML frontmatter with these keys: `profile_version`, `language`, `build_cmd`, `test_cmd`, `test_one_cmd` (takes `{class}`), `source_root`, `test_root`, `feature_root`, `generated_paths`, and `lint` with sub-keys `time_call`, `forbidden_time`, `random_call`, `forbidden_random`, `env_live_check`, `metric_call`, `trace_id_call`, `cheat_marker`, and `blocking_calls`;
    - one heading `### CAP-<NAME>` per capability. It covers at least these: command channel and ids, response and push, user actor execution, user ownership across nodes, per-user storage, CAS writes, Redis access, cross-node delivery, durable inbox, config loading, environment, cheat channel, admin channel, HTTP channel, metric logger, trace id, server time, RNG, error codes, cluster-wide job lease, unique ids, client version, unit test support, E2E bot, generated files, and build;
    - for each capability: what it must provide, the status values `present`, `partial`, and `missing`, and the fields an entry fills (`api`, `snippet`, `file`, and `blocker` plus `proposal` when not present).
  - `design-template.md` is the output format of `gdd-intake` and the input of `feature-spec`. It holds player-facing behavior, rules, states, rewards, timing, config tables, UI touchpoints the server must serve, open questions with source citations, and a glossary. It holds no server design.
  - `spec-template.md` has fixed sections: commands, pushes, state model, config schema, metric events and KPI queries, cheat commands, admin commands and API spec, HTTP endpoints, multi-node analysis, blue-green and client compatibility matrix, performance budget per command, core blockers, and test plan. Each row lists the rule ids it satisfies.
  - The validator passes on the branch.
- **Verify.** `python3 -m unittest discover -s tests && python3 scripts/validate_plugin.py --denylist "$GSS_DENYLIST"`

## T03. Write the rulebook skill

- **Builds.** Any agent that designs, writes, or reviews game server feature code loads one rulebook and gets a concrete do and don't for each rule.
- **Blocked by.** T02.
- **Writes.** `plugins/game-server/skills/server-rules/SKILL.md`, `plugins/game-server/skills/server-rules/references/*.md` except that `index.md` keeps every id and one-line rule unchanged. T03 may add links in it.
- **Acceptance.**
  - `SKILL.md` triggers on designing, writing, or reviewing Java game server features: commands, persistence, Redis, config, metrics, cheats, admin, HTTP callbacks, multi-node, blue-green, and client compatibility. It routes to one reference file per group.
  - Each rule id in `index.md` has a section in its group file with the rule, a one-line reason, a short Java do and don't, how a reviewer checks it, and the capabilities it needs.
  - The rulebook adds no ids.
- **Verify.** `python3 -m unittest discover -s tests && python3 scripts/validate_plugin.py --denylist "$GSS_DENYLIST"`

## T04. Write the profile skill and its checker

- **Builds.** On explicit request, a developer gets `docs/game-server/profile.md` for their Java game server. It shows how the core provides each capability and which missing capabilities block multi-node or blue-green safety.
- **Blocked by.** T02.
- **Writes.** `plugins/game-server/skills/server-profile/SKILL.md`, `plugins/game-server/skills/server-profile/references/scan-guide.md`, `plugins/game-server/skills/server-profile/scripts/check_profile.py`, `tests/test_check_profile.py`, `tests/fixtures/profile/**`.
- **Acceptance.**
  - `SKILL.md` has `disable-model-invocation: true`. It scans the repo read-only and writes only the profile file. It never edits core code.
  - `scan-guide.md` gives search recipes per capability for a typical Java server (Netty or NIO handlers, executors, memcached or Couchbase clients, Lettuce or Jedis, JSON config loaders, log4j or slf4j metric writers).
  - `check_profile.py <profile>` exits 1 when a frontmatter key from the template is missing, a capability heading is missing, a status is invalid, or a non-present capability lacks `blocker` and `proposal`. It prints `path:line: message`.
  - Tests cover a valid profile and each failure kind.
- **Verify.** `python3 -m unittest discover -s tests && python3 scripts/validate_plugin.py --denylist "$GSS_DENYLIST"`

## T05. Port the GDD intake skill

- **Builds.** A developer hands over a GDD folder (pptx, docx, xlsx, pdf, images, Markdown) or a plain feature prompt. They get a `design.md` in the T02 format, draft config JSON, and a list of open questions that cite GDD sections.
- **Blocked by.** T02.
- **Writes.** `plugins/game-server/skills/gdd-intake/**` except `references/design-template.md`, `tests/test_gdd_intake.py`, `tests/fixtures/gdd/**`.
- **Acceptance.**
  - The skill ports the source skill whose path the brief gives: conversion, extraction, refinement, lint, self-review, and JSON emit. It is rewritten in English and drops every project-specific default and sample.
  - A plain prompt skips conversion and produces the same `design.md` format.
  - Open questions go into `design.md`. When a workflow runs its own interview, the skill hands the questions to it. Otherwise it asks the user.
  - Script tests build their fixtures at test time from the standard library, or skip with the missing dependency named.
- **Verify.** `python3 -m unittest discover -s tests && python3 scripts/validate_plugin.py --denylist "$GSS_DENYLIST"`

## T06. Write the feature spec skill

- **Builds.** From a `design.md` or a prompt plus the project profile, an agent writes a server feature spec in the T02 format. It also slices the spec into tickets for nstack Spec build, or into an ordered task list for plain Claude Code.
- **Blocked by.** T02.
- **Writes.** `plugins/game-server/skills/feature-spec/**` except `references/spec-template.md`.
- **Acceptance.**
  - `SKILL.md` triggers on turning a game feature design, GDD, or prompt into a server design or implementation plan. It requires the profile and points to `server-profile` when the profile is missing.
  - The skill fills every template section, cites rule ids per row, and lists core blockers with the smallest core change. It stops for the developer when a blocker exists.
  - `references/slicing.md` gives the ticket fields that nstack Spec build uses (Builds, Blocked by, Writes, Acceptance, Verify). It puts shared shapes first: command ids, the state model, and the config schema.
  - `references/worked-example.md` shows a complete spec for a generic feature, a daily login streak with rewards.
- **Verify.** `python3 -m unittest discover -s tests && python3 scripts/validate_plugin.py --denylist "$GSS_DENYLIST"`

## T07. Write the feature build skill

- **Builds.** An agent implements one spec slice in the target project's idiom: unit tests first, then command, state, config, metric, cheat, admin, and registration code.
- **Blocked by.** T02.
- **Writes.** `plugins/game-server/skills/feature-build/**`.
- **Acceptance.**
  - `SKILL.md` triggers on implementing a game server feature, command, or spec slice in Java. It requires the profile and the spec, and it writes code only through the profile's idioms.
  - References cover these shapes:
    - the command shape: parse, validate, process on a pure core, respond, and log with the trace id;
    - the config class: load, validate, and an immutable snapshot;
    - state classes with additive fields and lazy migration;
    - cheat and admin commands;
    - HTTP callbacks through the durable inbox;
    - the unit test layout, with injected time and RNG and with negative and cheat cases.
  - The skill names the profile's `test_one_cmd` as the check after each slice. It reports the check as unrun when the build tool is missing.
- **Verify.** `python3 -m unittest discover -s tests && python3 scripts/validate_plugin.py --denylist "$GSS_DENYLIST"`

## T08. Write the feature review skill and its linter

- **Builds.** An agent reviews a feature diff against the rulebook. A linter catches the deterministic rule breaks first.
- **Blocked by.** T02.
- **Writes.** `plugins/game-server/skills/feature-review/**`, `tests/test_lint_feature.py`, `tests/fixtures/lint/**`.
- **Acceptance.**
  - `SKILL.md` triggers on reviewing game server feature code or a diff. It runs the linter, reviews against rule ids, and reports findings with severity, rule id, `file:line`, and a concrete failure scenario. A Critical finding needs a reachable trigger.
  - `scripts/lint_feature.py --profile <profile> <paths...>` reads the `lint` keys from the profile frontmatter. It reports `path:line: <RULE-ID> message` and exits 1 on any error. It checks at least these:
    - forbidden time calls;
    - forbidden RNG calls;
    - static mutable collections or fields in feature code;
    - cheat classes without the live environment check;
    - command classes without a metric call or a trace id;
    - blocking calls.
  - Every rule id the linter reports exists in the index.
  - Tests run the linter on Java fixtures that break each check, and on one clean fixture.
- **Verify.** `python3 -m unittest discover -s tests && python3 scripts/validate_plugin.py --denylist "$GSS_DENYLIST"`

## T09. Write the README and usage guides

- **Builds.** A new developer installs the marketplace and uses the skills with nstack or plain Claude Code.
- **Blocked by.** T03, T04, T05, T06, T07, T08.
- **Writes.** `README.md`, `docs/usage-nstack.md`, `docs/usage-plain.md`.
- **Acceptance.**
  - `README.md` covers what the plugin is for, the install commands (`/plugin marketplace add`, `/plugin install game-server@game-server-factory`, or `claude --plugin-dir plugins/game-server`), the six skills, and the order of use: profile, intake, spec, build, review.
  - `docs/usage-nstack.md` shows how the skills plug into nstack:
    - Interview reads `design.md` as its answer sheet;
    - Spec build uses the slicing output;
    - every delegate brief names the absolute `SKILL.md` paths;
    - review runs `feature-review`.
  - `docs/usage-plain.md` shows the same flow in a plain Claude Code chat.
- **Verify.** `python3 -m unittest discover -s tests && python3 scripts/validate_plugin.py --denylist "$GSS_DENYLIST"`
