# GDD docx and xlsx convert with a proven renderer

## Problem

`gdd-intake` converts docx and xlsx with its own standard-library parser. An xlsx file becomes one CSV per sheet plus a Markdown notes file per sheet, so the agent reads a sheet in two places. The docx output drops bold and italic, hyperlinks, table of contents links, list numbers, and hidden text.

The owner has a GDD pipeline in another project whose docx and xlsx converters already turn that project's real GDD files into Markdown. The owner wants those converters here as they are, so every GDD file reaches the agent as Markdown.

## Outcome

- The other project's converters ship in `gdd-intake/scripts/` unchanged: `convert_docx.py`, `convert_xlsx.py`, `requirements.txt`, and the `gddlib` modules they import (`__init__`, `common`, `docx`, `markdown`, `xlsx`).
- `convert_office.py` hands each docx and xlsx to them. Each becomes `raw/<name>.md`, named after the source file. A docx keeps headings, inline styles, lists, tables, hyperlinks, table of contents links, and images, which go to `raw/assets/`. A workbook has one `## Sheet:` section per sheet with its range and one table, and a cell with a formula shows the formula. No CSV is written.
- docx and xlsx convert before the other inputs, so a copied text file with the same name gets `_` added. Names compare without case, as on a macOS or Windows disk. A docx and an xlsx with one name cannot both convert, and the second is reported to be renamed. A symlinked docx or xlsx converts, as other inputs do, and its output is named after the file it points to.
- The converter needs `python-docx` and `openpyxl`. When either is missing, it skips the docx and xlsx files with the install command, as it does for PDF and PyMuPDF. pptx, PDF, text, and images convert as before.
- The other project's sync tools stay out: its manifest of source hashes, progress checkpoints, verifier scripts, and image description pass. The copied `gddlib` modules still hold the verifier and image description functions those tools call, and nothing in the plugin calls them.
- The plugin's own docx and xlsx parsers, now unused, are removed.
- The `gdd-intake` skill, its prompts, `README.md`, and `docs/usage.md` describe the new output and the install step. The config draft step works out the value of a formula cell.
- The other project's docx tests run here. `python3 -m unittest discover -s tests` passes with both packages installed and without them, where the docx and xlsx tests skip. `python3 scripts/validate_plugin.py --denylist <local denylist>` passes.

## Surfaces

- Agents and developers who run `gdd-intake` on GDD files.
- `gdd-intake/scripts/`, `gdd-intake/SKILL.md` and prompts, `README.md`, `docs/usage.md`, and the tests in this repository.

## Constraints

- No internal project name, path, or GDD content lands in a tracked file. The validator's denylist scan passes.
- pptx and PDF conversion stay as they are.
- The skills only help an agent write correct game server code. They never organize agents or the order of execution.
- No change lands on `main` without the owner's approval.

## Out of scope

- The other project's sync tools, as listed above.
- docx comments, headers, and footers, and the cell values behind xlsx formulas, which the copied converters do not render.
- CSV files in the input folder, which still pass through as they are.
- Flaws inside the copied converters, which stay as copied: a docx without pictures still gets an empty folder under `raw/assets/`, and a sheet cell's link target is not escaped.
- Clearing old outputs from the work folder on a rerun. The converter never did, and a docx changed between runs now also leaves its old picture folder under `raw/assets/`.

## Decisions

### The owner's

- Every GDD file converts to Markdown, spreadsheets included.
- Copy the other project's docx and xlsx converters as they are, with no rewrite. This drops the plugin's docx comments, headers, and footers and the xlsx cell values, and it needs `python-docx` and `openpyxl`.

### Mine

- `convert_office.py` keeps the one-command entry point and calls the copied converters, so the skill still converts a folder in one step.
- The copied docx test file gets a header that skips it without python-docx and puts `gddlib` on the import path. Its tests are unchanged.
- A missing package skips its files with the install command instead of failing the run, so a folder with slides and a PDF still converts.

## Open questions

- None.
