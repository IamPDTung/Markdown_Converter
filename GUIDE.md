# MD Converter — How It Works

A guide to the moving parts and the workflows around them. The short version:
**markitdown does all format parsing; this project handles everything around it**
(input validation, URLs, uploads, batching, errors, UI) — see `AGENTS.md` for why.

## Big picture

```
        file ──────► convert_path ────┐
input ─ URL ──────► convert_url ──────┼──► markitdown ──► Markdown
        upload ───► convert_upload ───┘
                      (engine.py)        (upstream library)
```

Three front doors, one engine:

| File | Role |
| --- | --- |
| `mdconv/engine.py` | `ConversionEngine` — the **only** code that talks to markitdown |
| `mdconv/cli.py` | `mdconv` command — batch convert files/URLs to `.md` files |
| `mdconv/server.py` | `mdconv-web` — Flask app serving the page and `/api/convert` |
| `mdconv/static/index.html` | the upload page (one self-contained file, no build step) |
| `tests/` | pytest suite; sample documents are generated at runtime |

## The engine

`ConversionEngine` is the single choke point. Every input goes through one of:

* **`convert_path(path)`** — local file. Checks it exists, is a file, and is not
  empty; then hands the path to `markitdown.convert()`.
* **`convert_upload(filename, stream)`** — browser upload. The bytes are staged
  into a temp directory as `upload<ext>` because markitdown chooses its parser
  from the file extension; then it becomes a normal `convert_path`. The temp
  copy is deleted as soon as the conversion ends.
* **`convert_url(url)`** — remote document. Only `http`/`https` pass. The engine
  fetches the URL **itself** (markitdown's built-in fetch has no timeout) with a
  30 s timeout, a `mdconv/0.1` user agent, and `stream=True`. If TLS verification
  fails with certifi's CA bundle, it retries once with the system CA bundle
  (`REQUESTS_CA_BUNDLE`-style corporate proxies work out of the box).

Two things worth knowing:

* **One shared `MarkItDown` instance, lazily created, all conversions serialised
  behind a lock.** The web server runs threaded, so without the lock two uploads
  could interleave reads on one engine.
* **Every failure becomes a `ConversionError`** with a message a human can act
  on. `_run()` maps markitdown's exceptions (unsupported format, missing
  dependency, conversion failure), `requests` errors (timeout, SSL, network),
  and unexpected exceptions to that one type. Callers only handle
  `ConversionError` — nothing else escapes.

## CLI workflow

```bash
mdconv report.pdf notes.docx -o out/      # batch → out/report.md, out/notes.md
mdconv https://example.com/news --stdout  # print to stdout
```

1. Sources are converted **one by one**; a failure prints `error: ...` to
   stderr and the batch continues.
2. Output name: file → its stem; URL → last path segment's stem (or `index`);
   always `.md` inside `-o DIR` (created if missing).
3. A converted file never overwrites its own input (`self.md` →
   `self.converted.md`).
4. Exit code is `1` if anything failed, `0` otherwise — cron/CI friendly.

## Web workflow

1. `GET /` serves `static/index.html`. The page is plain HTML/CSS/JS, no build.
2. In the page: drop or pick one or more files, and/or paste URLs → **Convert to
   Markdown**.
3. JavaScript POSTs `multipart/form-data` (`files`, `urls`) to
   `POST /api/convert`. Flask converts each item and returns one result per
   item — `{name, ok, markdown?, error?, chars?, ms?, empty?}`. **One bad file
   never fails the batch.**
4. The UI shows one tab per result with a rendered preview, raw view, Copy, and
   Download `.md`. `empty: true` (a scanned/image-only PDF) triggers a warning
   instead of silently showing nothing.
5. Limits: uploads capped at 64 MB (`MAX_CONTENT_LENGTH`; a JSON `413` handler
   explains the rejection). Nothing is persisted server-side — uploads live only
   in temp dirs during the request.

## Dev workflow

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/python -m pytest        # 32 tests, ~7 s
.venv/bin/mdconv-web              # run the UI you are changing
```

* `tests/fixtures.py` generates minimal sample documents (PDF, DOCX, PPTX, XLSX,
  HTML, …) at runtime — **no binary fixtures in git**.
* `tests/test_url.py` mocks the network layer entirely; the suite never dials
  out. `tests/test_server.py` uses Flask's test client — no server process.
* Tests are grouped by seam: engine (`test_engine`), CLI (`test_cli`), web API
  (`test_server`), URL fetch (`test_url`).

## Release workflow

```bash
.venv/bin/python -m build         # sdist + wheel into dist/
.venv/bin/twine check dist/*      # metadata sanity
.venv/bin/twine upload dist/*     # PyPI; name: mdconv-cli, token as password
```

Version lives in `pyproject.toml`. Bump it, rebuild, upload, tag the commit.

## Rules of the road

* **Do not give markitdown a competitor.** No pymupdf4llm, mammoth, ocrmypdf,
  etc. Rough PDF/OCR output is upstream behaviour, discussed in `README.md`.
* **All engine errors leave as `ConversionError`.** Add a mapping in `_run()`
  when a new exception type shows up; never leak library exceptions to callers.
* **Keep `static/index.html` self-contained.** One file, no build step, no CDN.
