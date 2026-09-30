"""Command-line interface.

mdconv report.pdf notes.docx page.html -o out/
mdconv https://example.com/news --stdout
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import urlparse

from .engine import DEFAULT_TIMEOUT, ConversionEngine, ConversionError

__all__ = ["main"]


def _is_url(source: str) -> bool:
    return urlparse(source).scheme.lower() in ("http", "https", "file", "data")


def output_path_for(source: str, outdir: Path) -> Path:
    """Where the .md for a given source (path or URL) should be written."""
    if _is_url(source):
        name = Path(urlparse(source).path).stem or "index"
    else:
        name = Path(source).stem
    return outdir / f"{name}.md"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mdconv",
        description="Convert documents (PDF, HTML, DOCX, ...) to Markdown using markitdown.",
    )
    parser.add_argument(
        "sources",
        nargs="+",
        metavar="FILE_OR_URL",
        help="files to convert, or http(s):// URLs",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("."),
        help="directory for the .md files (default: current directory)",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="print Markdown to stdout instead of writing files",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"URL fetch timeout in seconds (default: {DEFAULT_TIMEOUT})",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    engine = ConversionEngine(timeout=args.timeout)
    failures = 0

    if not args.stdout:
        args.output_dir.mkdir(parents=True, exist_ok=True)

    for source in args.sources:
        try:
            markdown = (
                engine.convert_url(source)
                if _is_url(source)
                else engine.convert_path(source)
            )
        except ConversionError as exc:
            print(f"error: {exc}", file=sys.stderr)
            failures += 1
            continue

        if args.stdout:
            print(markdown)
            continue

        target = output_path_for(source, args.output_dir)
        # Never write a converted document over one of its own inputs.
        if not _is_url(source) and target.resolve() == Path(source).resolve():
            target = target.with_suffix(".converted.md")
        target.write_text(markdown, encoding="utf-8")
        print(f"{source} -> {target}  ({len(markdown)} chars)")

    if args.stdout:
        return 1 if failures else 0

    print(f"Done: {len(args.sources) - failures} converted, {failures} failed.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
