# GDD docx and xlsx convert with a proven renderer

## Problem

`gdd-intake` converts docx and xlsx with its own standard-library parser. An xlsx file becomes one CSV per sheet plus a Markdown notes file per sheet, so the agent reads a sheet in two places. The docx output keeps headings, lists, tables, images, comments, and headers and footers, but drops bold and italic, hyperlinks, table of contents links, list numbers, and hidden text.

The owner has a GDD pipeline in another project whose docx and xlsx renderers already convert that project's real GDD files to Markdown. The owner wants those renderers here, so every GDD file reaches the agent as Markdown.

## Outcome

- The docx renderer from the other project converts each docx to `raw/doc_<base>.md`. It keeps document order, headings, paragraphs with bold, italic, and strikethrough, numbered and bulleted lists, tables, hyperlinks, table of contents links to headings, and every image occurrence. It skips hidden text.
- The docx output keeps this plugin's own parts. A nested table follows its outer table as a table of its own. Headers and footers, each distinct text once, and comments with the text they anchor to, close the file. Images go to the work folder's `images/` with the current names, linked as `../images/<name>`.
- The xlsx renderer from the other project converts each workbook to one `raw/sheet_<base>.md`, and no CSV. Each sheet is a `## Sheet: <name>` section with its used range, its state when hidden, and its merged ranges, then one table. Merged labels repeat in each cell of the range. A backslash, a pipe, and a line break in a cell are escaped. Cell hyperlinks are kept.
- The xlsx output keeps this plugin's own parts. The table shows each cell's last saved value, not its formula. Its first column is the sheet row number and its header names each column by letter, so a citation such as `Rewards!A2:D8` finds its cells. Formulas, with a shared formula block on one line, and comments follow the table under `### Formulas` and `### Comments`. A date cell reads as ISO 8601.
- The converter needs `python-docx` and `openpyxl`. When one is missing, the converter skips the files that need it and names the install command, as it does for PDF and PyMuPDF.
- The other project's sync workflow stays out: source hashes, provenance lines, staged asset folders, progress checkpoints, verifiers, and the image description pass.
- The `gdd-intake` skill, its prompts, `README.md`, and `docs/usage.md` describe the new output and the install step.
- `python3 -m unittest discover -s tests`, run where both packages are installed, and `python3 scripts/validate_plugin.py --denylist <local denylist>` pass. Without the packages, the docx and xlsx tests skip and name the package.

## Surfaces

- Agents and developers who run `gdd-intake` on GDD files.
- `gdd-intake/scripts/`, `gdd-intake/SKILL.md` and prompts, `README.md`, `docs/usage.md`, and `tests/test_gdd_intake.py` in this repository.

## Constraints

- No internal project name, path, or GDD content from the other project lands in a tracked file. The validator's denylist scan passes.
- pptx and PDF conversion stay as they are.
- The skills only help an agent write correct game server code. They never organize agents or the order of execution.
- No change lands on `main` without the owner's approval.

## Out of scope

- The other project's sync workflow, as listed above.
- Formula text in the xlsx table cells. The other project shows formulas there, but the config drafts need the values.
- CSV files in the input folder, which still pass through as they are.

## Decisions

### The owner's

- Every GDD file converts to Markdown, spreadsheets included.
- Take the docx and xlsx renderers from the other project, drop its sync parts, and keep this plugin's comments, headers and footers, values in the sheet table, and the formula list. The converter then needs `python-docx` and `openpyxl`.

### Mine

- Row numbers and column letters stay in the sheet table, unlike the other project, which uses the first row as the header. Design citations name sheet ranges, so the agent must find a cell by its address.
- One file per workbook, as in the other project, named `sheet_<base>.md` like the `doc_`, `slides_`, and `pdf_` outputs.
- A missing package skips its files with the install command instead of failing the run, so a folder with slides and a PDF still converts.

## Open questions

- None.
