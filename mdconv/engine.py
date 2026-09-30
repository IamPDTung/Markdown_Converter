"""Conversion engine: a thin wrapper around microsoft/markitdown.

Everything about parsing individual formats (PDF, HTML, DOCX, ...) is
markitdown's job. This module only manages:

* lazy, thread-safe engine lifetime,
* staging uploads into a temp file with the right extension,
* fetching URLs ourselves (markitdown's own fetch has no timeout) and
  falling back to the system CA bundle when certifi rejects a corporate proxy,
* turning markitdown's exceptions into messages a human can act on.
"""

from __future__ import annotations

import shutil
import tempfile
import threading
from collections.abc import Callable
from pathlib import Path
from typing import BinaryIO, TypeVar
from urllib.parse import urlparse

import requests
from markitdown import (
    FileConversionException,
    MarkItDown,
    MarkItDownException,
    MissingDependencyException,
    UnsupportedFormatException,
)

__all__ = ["DEFAULT_TIMEOUT", "ConversionEngine", "ConversionError"]

DEFAULT_TIMEOUT = 30  # seconds; applies to URL fetches

# Common system CA bundles, used when certifi's bundle does not know the
# local (corporate / sandbox) certificate authority.
_SYSTEM_CA_BUNDLES = (
    "/etc/ssl/certs/ca-certificates.crt",
    "/etc/pki/tls/certs/ca-bundle.crt",
    "/etc/ssl/cert.pem",
)

T = TypeVar("T")


class ConversionError(Exception):
    """A conversion failure that we can explain to a human."""


class ConversionEngine:
    """Converts files and URLs to Markdown using markitdown."""

    def __init__(self, timeout: int = DEFAULT_TIMEOUT) -> None:
        self.timeout = timeout
        self._md: MarkItDown | None = None
        # markitdown instances are shared but conversions are serialised so a
        # busy web server cannot interleave reads on one engine.
        self._lock = threading.Lock()

    @property
    def markitdown(self) -> MarkItDown:
        """The underlying markitdown instance (created on first use)."""
        if self._md is None:
            self._md = MarkItDown()
        return self._md

    # ------------------------------------------------------------------ API

    def convert_path(self, path: str | Path, *, label: str | None = None) -> str:
        """Convert a local file to Markdown.

        `label` overrides the name used in messages — uploads are staged under
        a temporary name, but errors must name the file the user gave us.
        """
        path = Path(path).expanduser()
        subject = label or path.name
        if not path.exists():
            raise ConversionError(f"No such file: {path}")
        if not path.is_file():
            raise ConversionError(f"Not a file: {path}")
        if path.stat().st_size == 0:
            raise ConversionError(f"File is empty: {subject}")
        return self._run(lambda: self.markitdown.convert(path), subject)

    def convert_url(self, url: str) -> str:
        """Convert a remote document (or web page) to Markdown."""
        url = url.strip()
        scheme = urlparse(url).scheme.lower()
        if scheme not in ("http", "https"):
            raise ConversionError(
                f"Unsupported URL scheme {scheme or '(none)'!r} — use http:// or https://"
            )
        return self._run(
            lambda: self.markitdown.convert(self._fetch(url)),
            url,
        )

    def convert_upload(self, filename: str, stream: BinaryIO) -> str:
        """Convert an uploaded file (already opened by the caller) to Markdown.

        The file is staged under a temp name that keeps its extension, because
        markitdown picks a converter from the extension/mimetype.
        """
        suffix = Path(filename).suffix.lower()
        with tempfile.TemporaryDirectory(prefix="mdconv-") as tmp_dir:
            staged = Path(tmp_dir) / f"upload{suffix}"
            with staged.open("wb") as handle:
                shutil.copyfileobj(stream, handle)
            if staged.stat().st_size == 0:
                raise ConversionError("File is empty (0 bytes)")
            return self.convert_path(staged, label=Path(filename).name or staged.name)

    # ------------------------------------------------------------- internals

    def _run(self, action: Callable[[], T], subject: str) -> str:
        with self._lock:
            try:
                result = action()
            except ConversionError:
                raise
            except UnsupportedFormatException as exc:
                raise ConversionError(
                    f"{subject}: file type is not supported by markitdown "
                    f"(supported: PDF, HTML, DOCX, PPTX, XLSX, CSV, images, text, ...)"
                ) from exc
            except MissingDependencyException as exc:
                raise ConversionError(
                    f"{subject}: a required optional dependency is missing ({exc}). "
                    f"Install with: pip install 'markitdown[all]'"
                ) from exc
            except FileConversionException as exc:
                detail = str(exc).strip() or exc.__class__.__name__
                raise ConversionError(f"{subject}: {detail}") from exc
            except requests.Timeout as exc:
                raise ConversionError(
                    f"{subject}: timed out after {self.timeout}s"
                ) from exc
            except requests.exceptions.SSLError as exc:
                raise ConversionError(
                    f"{subject}: TLS certificate verification failed — if you are behind a "
                    f"corporate proxy, add its CA bundle to REQUESTS_CA_BUNDLE ({exc})"
                ) from exc
            except requests.RequestException as exc:
                raise ConversionError(
                    f"{subject}: could not fetch URL ({exc})"
                ) from exc
            except MarkItDownException as exc:
                detail = str(exc).strip() or exc.__class__.__name__
                raise ConversionError(f"{subject}: {detail}") from exc
            except (ValueError, OSError) as exc:
                detail = str(exc).strip() or exc.__class__.__name__
                raise ConversionError(f"{subject}: {detail}") from exc
            except Exception as exc:
                detail = str(exc).strip() or exc.__class__.__name__
                raise ConversionError(
                    f"{subject}: unexpected {exc.__class__.__name__}: {detail}"
                ) from exc

        markdown = getattr(result, "markdown", None)
        if markdown is None:
            raise ConversionError(f"{subject}: markitdown returned no Markdown")
        return markdown

    def _fetch(self, url: str) -> requests.Response:
        """Fetch a URL with a timeout, retrying with the system CA bundle."""
        try:
            response = self._get(url, verify=True)
        except requests.exceptions.SSLError:
            cafile = next((p for p in _SYSTEM_CA_BUNDLES if Path(p).is_file()), None)
            if cafile is None:
                raise
            response = self._get(url, verify=cafile)
        response.raise_for_status()
        return response

    def _get(self, url: str, *, verify: bool | str) -> requests.Response:
        headers = {"User-Agent": "mdconv/0.1 (+markitdown)"}
        if isinstance(verify, str):
            return requests.get(
                url, timeout=self.timeout, stream=True, verify=verify, headers=headers
            )
        return requests.get(url, timeout=self.timeout, stream=True, headers=headers)
