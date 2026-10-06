# AGENTS.md

## Repository status

- Code exists (first code commit `74efddc`): `mdconv/` (engine, CLI, Flask server, HTML upload page), `tests/`, `pyproject.toml`, `README.md`. `.venv/` is local-only and git-ignored; run tests with `.venv/bin/python -m pytest`.
- Worktrees / branches (`git worktree list`):
  - `/home/tommy/.orca/workspaces/MD_Converter/Build-python-converter` — **this session**, branch `Build-python-converter` (tracks `origin/Build-python-converter`).
  - `/home/tommy/workspace/MD_Converter` — branch `Research-Technical`; its history is fully contained in `Build-python-converter`.
  - `/home/tommy/.orca/workspaces/MD_Converter/Build-UI` — has branch `main` checked out (still the empty initial commit locally).
  - Branch `Build-UI` (`ecdbade`) is not checked out anywhere.
- Remote: `origin` → `IamPDTung/Markdown_Converter` (public on GitHub). Pushed: `main` (= `74efddc`, the code, GitHub's default branch) and `Build-python-converter`.
  - **Push over SSH only**: this network returns a fake HTML page for HTTPS `git-receive-pack` and blocks SSH port 22, so the remote URL is `ssh://git@ssh.github.com:443/IamPDTung/Markdown_Converter.git`. Do not "fix" it back to HTTPS or `git@github.com:`.
  - Local `main` is behind remote `main`: fast-forward it from the worktree that has it checked out instead of force-updating it from here.

## Project goal (decided)

Build a tool whose primary function is converting files to Markdown.

- Language: **Python**.
- Interface: **CLI only** for now (no REST API, web UI, or library packaging unless asked).
- Launch input formats: **PDF, HTML (local files and URLs), DOCX, images/scanned PDFs (OCR)**.
- Update: the user later asked for a page where they can upload the document to convert, so a Flask web UI (`mdconv/server.py` + `mdconv/static/index.html`) now ships alongside the CLI.

## Stack (decided)

- **Use [`microsoft/markitdown`](https://github.com/microsoft/markitdown) as the conversion engine — do not write custom per-format converters.**
  - Install with `pip install 'markitdown[all]'`, or only the extras needed (e.g. `markitdown[pdf,docx]`).
  - CLI: `markitdown file.pdf -o out.md`. Python API: `MarkItDown().convert(path).markdown`.
  - Our project is a thin CLI wrapper around it (batch mode, output-dir handling, polish) — keep our own logic out of format parsing.
- Known markitdown caveats: PDF/OCR fidelity is its weak point (README says output is for LLM/text-analysis, not high-fidelity human display). Do not "fix" this by adding competing libraries (pymupdf4llm, mammoth, ocrmypdf, etc.) — discuss with the user first.
- Distribution: licensed MIT, published to PyPI as **`mdconv-cli`** (`mdconv` is taken by an unrelated package). The import package and CLI commands stay `mdconv` / `mdconv-web`.
