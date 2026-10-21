---
name: gdd-intake
description: Turns game design material into a server-ready design.md. Use when a developer hands over a game design document (GDD), feature spec slides (pptx), docx notes, an xlsx balance sheet, a PDF export, Markdown, or just a plain feature prompt, and the feature needs a sourced, unambiguous description before server work starts. Converts the files, extracts rules, formulas, rewards, timing, states, and edge cases with requirement ids and source citations, lists open questions by severity, and drafts config JSON from the balance sheets. The next step is feature-spec.
---

# GDD intake

This skill turns design material into one `design.md` that says what the player sees, does, and gets. Every requirement has an id and a source. Every gap is an open question with an interim default. The output format is fixed by [the design template](references/design-template.md). Read the template before you write or edit a design.

The design holds no server design. It names no commands, classes, storage keys, or metrics. The `feature-spec` skill decides those from the design and the project profile, so hand it the finished design as the next step.

## Entry paths

- **Folder.** The developer gives a folder of pptx, docx, xlsx, PDF, Markdown, text, CSV, JSON, or image files. Run every step below.
- **Prompt.** The developer describes the feature in the chat. Skip step 1. Write `None.` under Sources, keep the `Scope:` line, and cite the text as `prompt`. A prompt is thin, so expect more open questions. Do not invent rules to fill the sections.

Ask for the feature name if it is missing, and use it in kebab case. Ask for the scope with AskUserQuestion when the developer has not said: `server-only` (recommended), `full-stack`, or `logic-only`.

## Where files go

| What | Path in the target repository |
| --- | --- |
| The design | `docs/game-server/features/<feature>/design.md` |
| Draft config JSON | `docs/game-server/features/<feature>/config/` |
| Work files (converted text, images, reports) | `.gdd-intake/<feature>/`, which should be gitignored |

`<skill dir>` below means the folder that holds this file. Run scripts as `python3 -I <skill dir>/scripts/<name>.py`.

## Pipeline

1. **Convert.** Run `scripts/convert_office.py <input folder> .gdd-intake/<feature>`. It reads docx, pptx, and xlsx with the Python standard library, copies raster images out, and copies text files as they are. Read `conversion-manifest.md` in the work folder and tell the developer what it lists. Three cases need the developer:
   - A PDF in `export_requests` needs PyMuPDF, which may be missing. Ask the developer to export the PDF to docx or Markdown into the input folder, then run the step again.
   - Legacy `.doc`, `.ppt`, and `.xls` files are skipped. Ask for a save as docx, pptx, or xlsx.
   - Charts, SmartArt, and vector drawings are not converted. If one carries rules or numbers, ask for a PNG export into the `images` folder of the work folder.
2. **Extract.** Follow [the extractor prompt](prompts/extractor-prompt.md). It reads everything and writes the first `design.md`, with open questions and an interim default for each. Use a fresh subagent when the harness has one, because the input can be large. A subagent cannot ask the user, which is why the questions land in the file.
3. **Lint.** Run `scripts/lint_design.py <design.md>`. It prints `path:line: message` and exits 1 on any problem. A design with open questions can pass. Do not skip this step when the draft looks right.
4. **Questions.** See the hand-off rule below. This step ends when every question is answered, skipped by the developer, or handed to a workflow that will bring the answers back.
5. **Refine.** Follow [the refiner prompt](prompts/refiner-prompt.md) in `apply-answers` mode, then lint again. If lint fails, run the refiner in `fix-lint` mode once and lint again. If it still fails, show the output to the developer and stop.
6. **Self-review.** Follow [the self-reviewer prompt](prompts/self-reviewer-prompt.md) with an agent that did not write the draft. It reads the design against its sources and writes a report. When the report is not ready, run the refiner in `fix-review` mode once, then lint and review again. If it is still not ready, show the report to the developer and let them decide.
7. **Emit JSON.** If the design has config tables, run `scripts/emit_json.py <design.md> --sheets .gdd-intake/<feature>`. It writes the files named on each Draft line. Drafts hold the Example values or the sheet values, so say that they are drafts. Skip `--sheets` for a prompt design.

Run the prompts as subagents when the harness has them, and follow them yourself when it does not. Pass absolute paths in the brief. Run lint and the emitter yourself, since they are scripts.

## Hand-off rule for open questions

The open questions in `design.md` are the list of gaps. They are the only place questions live.

- **A workflow runs its own interview.** For example the nstack Interview playbook. Stop after step 3 and give the workflow the Open questions section: each question with its id, tier, source, and interim default. The workflow asks, then returns the answers. Resume at step 5 with them.
- **No workflow interview.** Ask the developer yourself with AskUserQuestion, Blocker questions first, then Important. Show the question, its source, and the interim default, and offer the default plus one or two alternatives that the sources suggest. Minor questions can stay open. Do not ask a subagent to do this.

Record each outcome in the question's status line: `answered on <date>: <answer>`, or `skipped by <name> on <date>`. Dates are `YYYY-MM-DD`. A skipped question keeps its interim default. At the end, report how many questions are open in each tier, because `feature-spec` stops on open Blocker questions.

## Finish

Report these items:

- The path of `design.md` and the draft config files.
- The count of requirements by prefix, and the open questions by tier and status.
- The self-review verdict and any finding that stays unfixed.
- Anything the conversion could not read.

Then say that `feature-spec` is the next step.
