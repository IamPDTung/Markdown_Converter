# AGENTS.md

## Repository status

- Greenfield: only an empty initial commit exists. There is no code, manifest, test, or build config yet — create them as part of the task instead of assuming a layout.
- Branch layout:
  - `Research-Technical` — current branch in this session.
  - `lookdown` — checked out in a separate Orca worktree at `/home/tommy/.orca/workspaces/MD_Converter/lookdown`. Do not commit to it from this session; it changes independently.
  - `main` — empty, unused.
- No git remote: commits are local-only until a remote is added.

## Project goal (decided)

Build a tool whose primary function is converting files to Markdown.

- Language: **Python**.
- Interface: **CLI only** for now (no REST API, web UI, or library packaging unless asked).
- Launch input formats: **PDF, HTML (local files and URLs), DOCX, images/scanned PDFs (OCR)**.

## Stack (decided)

- **Use [`microsoft/markitdown`](https://github.com/microsoft/markitdown) as the conversion engine — do not write custom per-format converters.**
  - Install with `pip install 'markitdown[all]'`, or only the extras needed (e.g. `markitdown[pdf,docx]`).
  - CLI: `markitdown file.pdf -o out.md`. Python API: `MarkItDown().convert(path).markdown`.
  - Our project is a thin CLI wrapper around it (batch mode, output-dir handling, polish) — keep our own logic out of format parsing.
- Known markitdown caveats: PDF/OCR fidelity is its weak point (README says output is for LLM/text-analysis, not high-fidelity human display). Do not "fix" this by adding competing libraries (pymupdf4llm, mammoth, ocrmypdf, etc.) — discuss with the user first.
