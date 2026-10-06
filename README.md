# MD Converter

Convert documents to Markdown — **PDF, HTML, DOCX, PPTX, XLSX, CSV, images, text** — with a
web page where you upload the file and download the `.md`.

The conversion engine is
[`microsoft/markitdown`](https://github.com/microsoft/markitdown);
this project is a thin wrapper around it (uploads, batch mode, output handling, UI).
It never parses document formats itself.

## Install

The distribution name is `mdconv-cli` (`mdconv` was taken on PyPI). Debian and
Ubuntu make the system `pip` refuse installs (PEP 668), so use pipx or a venv:

```bash
pipx install mdconv-cli          # recommended — isolated, puts the commands on PATH
```

or from a checkout:

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
```

Either way you get two commands: `mdconv` (CLI) and `mdconv-web` (web page).

## Quickstart

```bash
mdconv-web                 # → http://127.0.0.1:8000
```

From a checkout without activating the venv, use `.venv/bin/mdconv-web`.

Open <http://127.0.0.1:8000>, drop one or more files (or paste a URL), press
**Convert to Markdown**, then copy or download the result. Files are converted
locally and never leave the machine.

```
Usage: mdconv-web [-h] [--host HOST] [--port PORT] [--debug]
```

## Command line

```bash
mdconv report.pdf notes.docx -o out/      # batch → out/report.md, out/notes.md
mdconv https://example.com/news --stdout  # print Markdown to stdout
```

* `-o, --output-dir DIR` — where `.md` files are written (default: current directory).
* `--stdout` — print instead of writing files.
* `--timeout N` — URL fetch timeout in seconds (default: 30).
* Exit code `1` if any input failed; failures never abort the rest of the batch.
* A converted file never overwrites its own input (`self.md` → `self.converted.md`).

## HTTP API

The UI in `mdconv/static/index.html` talks to one endpoint:

```bash
curl -F "files=@report.pdf" -F "files=@page.html" http://127.0.0.1:8000/api/convert
curl -F "urls=https://example.com/news" http://127.0.0.1:8000/api/convert
```

```json
{
  "results": [
    {"name": "report.pdf", "ok": true, "markdown": "# ...", "chars": 4210, "ms": 318},
    {"name": "junk.dat",   "ok": false, "error": "junk.dat: file type is not supported by markitdown"}
  ]
}
```

One bad file never fails the batch — each result carries its own `ok`/`error`.
Uploads are capped at 64 MB (JSON `413` if exceeded).

## Supported inputs

| Format | How |
| --- | --- |
| PDF | `pdfminer.six` / `pdfplumber` |
| HTML (files & URLs) | `beautifulsoup4` + `markdownify` |
| DOCX / PPTX / XLSX | `mammoth` / `python-pptx` / `openpyxl` |
| CSV / TSV / plain text / Markdown | built in |
| EPUB, ODT, Outlook `.msg`, YouTube transcripts, … | markitdown extras |

### Known limits (be aware)

* **PDF fidelity** — markitdown output is optimised for text extraction and LLM
  input, not for pixel-perfect layout. Tables and multi-column layouts can come
  out rough. This is upstream behaviour and intentionally not "fixed" here with
  competing libraries.
* **OCR** — markitdown 0.1.x has *no local OCR*: a scanned/image-only PDF
  converts to empty Markdown (the UI shows a warning). OCR is only available via
  Azure Document Intelligence if you configure its credentials.
* **URLs** — fetched with a 30 s timeout. If you sit behind a TLS-intercepting
  proxy and get certificate errors, point `REQUESTS_CA_BUNDLE` at your corporate
  CA (the engine already falls back to the system CA bundle automatically).

## Project layout

```
mdconv/
├── engine.py           # ConversionEngine — thin wrapper around markitdown
├── cli.py              # mdconv  (batch conversion)
├── server.py           # mdconv-web (Flask app + /api/convert)
└── static/index.html   # upload page (single self-contained file)
tests/                  # engine, API and CLI tests
```

`ConversionEngine` is the only place that talks to markitdown. It stages uploads
into a temp file (markitdown picks a converter from the extension), serialises
conversions, and maps markitdown's exceptions to actionable messages.

See **[GUIDE.md](GUIDE.md)** for how the pieces fit together, plus the dev and
release workflows.

## Tests

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/python -m pytest     # 32 tests
```

Sample documents (HTML, DOCX, PDF, PPTX, XLSX, …) are generated at runtime by
`tests/fixtures.py`, so no binary files live in the repository.

## License

[MIT](LICENSE)
