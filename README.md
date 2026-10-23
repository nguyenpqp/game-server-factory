# game-server-factory

A Claude Code marketplace with one plugin, `game-server`. The plugin gives an agent the principles for building Java game server features that are server-authoritative, safe on many nodes, safe through blue-green deploys with old clients, configurable, modular, and observable.

The skills hold principles, not procedures or templates. They explain what good feature code looks like and why, and leave the agent to apply them to the project in front of it. Feature code is written through the core the server already has. When the core lacks something a principle needs, the agent names the gap and proposes the smallest core change instead of working around it.

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

## The three skills

| Skill | Use it when | What it gives the agent |
| --- | --- | --- |
| `server-principles` | Planning, building, changing, or reviewing any game server feature | Fourteen principles with their reasons, under a stability-first stance: work through the core, the server decides, value moves exactly once, no node is special, two versions and old clients at once, numbers live in config, features are independent modules, bounded cost, the client can catch up, every action can be traced, tools for testers and support, tests prove behavior, code is typed and quiet, and build what the design says. Plus genre notes for rankings, gacha, economy, events, guilds, and PvP, each listing design questions and code traps. |
| `gdd-intake` | A developer hands over a GDD (pptx, docx, xlsx, PDF, Markdown, images) or a feature prompt | A converter from office files to Markdown, and what a good feature design has: player terms only, traceable requirements, exact numbers, and gaps raised as questions instead of guesses. |
| `feature-review` | Reviewing feature code, a pull request, or a diff | How to review against the design and the principles, and what a finding needs: severity, location, the principle it breaks, and a concrete failure scenario. |

The skills do not prescribe a workflow, branch strategy, or file layout. Use them in a plain chat or under any workflow plugin.

## Check this repository

Run these from the repository root. Both run on Python 3 alone, and the converter tests for docx and xlsx need python-docx and openpyxl.

```
python3 -m unittest discover -s tests
python3 scripts/validate_plugin.py --denylist /path/to/denylist.txt
```

The unit tests cover the validator and the `gdd-intake` converter. A test that needs a package or program the machine lacks skips and names it.

The validator checks the manifests, each skill's frontmatter, every relative link, and the tracked files for absolute home paths and private keys. It also scans the tracked files for terms from a denylist. The denylist is a plain text file with one term per line. The public repository must hold no internal project names, class names, hosts, or GDD content, so each maintainer keeps the list of those terms in a local file that is never committed. The validator fails if a tracked file contains any listed term, matched without regard to case. Pass the file with `--denylist` or set `GSS_DENYLIST`. Without either, the validator warns that it skipped the private-term scan.

`gdd-intake` reads docx with python-docx and xlsx with openpyxl (`python3 -m pip install python-docx openpyxl`). PyMuPDF is optional and reads PDF files. For pptx it needs nothing beyond Python 3.
