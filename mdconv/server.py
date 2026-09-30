"""Web UI: serves the upload page and converts documents on request.

mdconv-web            # http://127.0.0.1:8000
mdconv-web --port 9000 --host 0.0.0.0
"""

from __future__ import annotations

import argparse
import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from .engine import ConversionEngine, ConversionError

__all__ = ["create_app", "main"]

STATIC_DIR = Path(__file__).parent / "static"
MAX_UPLOAD_MB = 64


def create_app(engine: ConversionEngine | None = None) -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024
    engine = engine or ConversionEngine()
    log = logging.getLogger("mdconv")

    def attempt(subject: str, action: Callable[[], str]) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            markdown = action()
        except ConversionError as exc:
            log.info("conversion failed: %s", exc)
            return {"name": subject, "ok": False, "error": str(exc)}
        except Exception:
            log.exception("unexpected failure while converting %s", subject)
            return {"name": subject, "ok": False, "error": "Unexpected server error."}
        return {
            "name": subject,
            "ok": True,
            "markdown": markdown,
            "chars": len(markdown),
            "ms": round((time.perf_counter() - started) * 1000),
            "empty": not markdown.strip(),
        }

    @app.get("/")
    def index() -> Any:
        return send_from_directory(STATIC_DIR, "index.html")

    @app.get("/api/health")
    def health() -> Any:
        return jsonify(ok=True, engine="markitdown")

    @app.post("/api/convert")
    def convert() -> Any:
        uploads = [f for f in request.files.getlist("files") if f.filename]
        urls = [u.strip() for u in request.form.getlist("urls") if u.strip()]
        # tolerate the singular field name too
        single = (request.form.get("url") or "").strip()
        if single and single not in urls:
            urls.append(single)

        if not uploads and not urls:
            return jsonify(
                error="Nothing to convert: choose a file or paste a URL."
            ), 400

        results: list[dict[str, Any]] = []
        for storage in uploads:
            name = secure_filename(storage.filename) or "upload"
            results.append(attempt(name, _staged(storage, name, engine)))
        for url in urls:
            results.append(attempt(url, _u(url, engine)))
        return jsonify(results=results)

    @app.errorhandler(413)
    def too_large(_error: Exception) -> Any:
        return jsonify(
            error=f"Upload too large — the limit is {MAX_UPLOAD_MB} MB."
        ), 413

    return app


def _staged(
    storage: FileStorage, name: str, engine: ConversionEngine
) -> Callable[[], str]:
    """Build an action that converts one uploaded file through the engine."""

    def action() -> str:
        storage.stream.seek(0)
        return engine.convert_upload(name, storage.stream)

    return action


def _u(url: str, engine: ConversionEngine) -> Callable[[], str]:
    """Build an action that converts one URL (binds `url` by value)."""
    return lambda: engine.convert_url(url)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mdconv-web", description="Run the MD Converter web UI."
    )
    parser.add_argument(
        "--host", default="127.0.0.1", help="bind address (default: 127.0.0.1)"
    )
    parser.add_argument("--port", type=int, default=8000, help="port (default: 8000)")
    parser.add_argument("--debug", action="store_true", help="Flask debug mode")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    app = create_app()
    print(
        f"MD Converter is running on http://{args.host}:{args.port}/  (Ctrl+C to stop)"
    )
    app.run(host=args.host, port=args.port, debug=args.debug, threaded=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
