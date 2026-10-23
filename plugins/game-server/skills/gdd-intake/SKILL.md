---
name: gdd-intake
description: Turns game design material into a clear, sourced feature design that server work can start from. Use when a developer hands over a game design document (GDD), feature slides (pptx), docx notes, an xlsx balance sheet, a PDF export, Markdown, images, or just a feature prompt, and the feature needs to be understood before server code is designed or written. Converts office files to Markdown with a bundled script, pulls out the rules, formulas, rewards, timing, states, and edge cases with their sources, surfaces the gaps as questions for the developer, and drafts config from the balance sheets.
---

# GDD intake

The goal is one design document that says what the player sees, does, and gets, precisely enough that two engineers would build the same feature from it. It is the contract the server code is later checked against, so it has to be faithful to the source material and honest about what the source leaves open.

## Reading office files

GDDs arrive as slides, documents, sheets, and PDFs. Convert them to Markdown first with the bundled converter, which keeps slide order, tables, speaker notes, sheet cells and their formulas, and images:

```
python3 -I ${CLAUDE_SKILL_DIR}/scripts/convert_office.py <input folder> <work folder>
```

Read the `conversion-manifest.md` it writes. It lists what it converted, skipped, and could not read. Tell the developer about anything skipped:

- docx needs `python-docx`, xlsx needs `openpyxl`, and PDF needs `pymupdf`. Install them with `python3 -m pip install python-docx openpyxl pymupdf`, without `--user`, because `-I` hides user packages.
- Legacy `.doc`, `.ppt`, and `.xls` files, SmartArt, and vector drawings are not read. Ask for a modern format or a PNG export when they carry rules or numbers.

Keep the work folder out of git, because converted text may hold content the team does not want committed. A prompt with no files needs no conversion.

## What a good design has

- **Player terms only.** It describes rules, numbers, states, timing, rewards, and edge cases as the player experiences them. It names no commands, classes, storage keys, or metrics. Those are server decisions made later.
- **Traceable.** Each requirement has a short id and cites where it came from: a slide, a page, a heading, a sheet range, the prompt, or the developer's answer. Reviewers use these ids to check the code against the design.
- **Exact numbers.** Costs, rewards, rates, limits, durations, and counts are copied exactly. A sheet cell with a formula is worked out from the cells it names. Tables of balance values become draft config files, marked as drafts.
- **Gaps are questions, not guesses.** Where the source is silent, vague, or contradicts itself, write an open question with its source, how much it matters, and a sensible default to use if nobody answers. Questions that affect player value, fairness, or what gets built matter most. Never fill a gap by inventing a rule.
- **Edge cases are asked about.** Think about what the source rarely says: what a player who is offline at the end gets, what happens at a period boundary or a time zone change, what happens on a retry or a disconnect mid-action, ties, caps, and what an old client sees. If the feature matches a genre note in the `server-principles` skill, its questions are a good checklist.
- **Scope is explicit.** Say whether the work is server only or also covers the client, and mark requirements that have no server effect.

## Working with the developer

Ask the open questions that matter, most important first, and offer the default and one or two alternatives the sources suggest. Record each answer, or that the developer chose the default, in the document, so later work does not ask again. Minor questions can stay open. If a workflow the developer uses runs its own interview, hand the questions to it instead of asking twice.

When the design is large, a fresh reader is useful: have someone who did not write it (a subagent, if available) compare it against the sources and look for dropped rules, wrong numbers, and invented content.

Put the design and the config drafts where the project keeps its docs.

When done, tell the developer where the design and drafts are, how many questions remain open and how serious they are, and anything the conversion could not read.
