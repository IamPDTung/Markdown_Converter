"""URL conversion tests — the network layer is mocked, so these never dial out.

Guards two real bugs found during development:
  * markitdown's own fetch has no timeout, so the engine fetches for itself;
  * `requests.SSLError` is not exported at the top level of `requests`.
"""

from __future__ import annotations

import pathlib

import pytest
import requests

from mdconv import ConversionEngine, ConversionError
from mdconv.engine import _SYSTEM_CA_BUNDLES

ARTICLE_URL = "https://example.test/some/article"

SYSTEM_CA = next((p for p in _SYSTEM_CA_BUNDLES if pathlib.Path(p).is_file()), None)


def html_response(
    body: str = "<html><head><title>T</title></head>"
    "<body><h1>Headline from the web</h1></body></html>",
) -> requests.Response:
    response = requests.Response()
    response.status_code = 200
    response.url = ARTICLE_URL
    response.headers["Content-Type"] = "text/html; charset=utf-8"
    response._content = body.encode()
    # markitdown reads through iter_content(); with the body pre-loaded it must
    # be flagged as consumed, otherwise requests tries to read response.raw.
    response._content_consumed = True
    return response


def test_url_is_fetched_with_a_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def fake_get(url: str, **kwargs: object) -> requests.Response:
        seen["url"] = url
        seen.update(kwargs)
        return html_response()

    monkeypatch.setattr("mdconv.engine.requests.get", fake_get)
    engine = ConversionEngine(timeout=11)

    assert "Headline from the web" in engine.convert_url(ARTICLE_URL)
    assert seen["url"] == ARTICLE_URL
    assert seen.get("timeout") == 11  # markitdown's own fetch has none
    assert seen.get("stream") is True


def test_ssl_failure_falls_back_to_the_system_ca_bundle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if SYSTEM_CA is None:
        pytest.skip("no system CA bundle on this machine")

    attempts: list[object] = []

    def fake_get(_url: str, **kwargs: object) -> requests.Response:
        attempts.append(kwargs.get("verify", True))
        if len(attempts) == 1:
            raise requests.exceptions.SSLError("self-signed certificate in chain")
        return html_response()

    monkeypatch.setattr("mdconv.engine.requests.get", fake_get)

    markdown = ConversionEngine().convert_url(ARTICLE_URL)
    assert "Headline from the web" in markdown
    assert attempts == [True, SYSTEM_CA]


def test_ssl_failure_without_a_usable_bundle_reports_a_ca_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_get(_url: str, **_kwargs: object) -> requests.Response:
        raise requests.exceptions.SSLError("self-signed certificate in chain")

    monkeypatch.setattr("mdconv.engine.requests.get", fake_get)
    monkeypatch.setattr("mdconv.engine._SYSTEM_CA_BUNDLES", ())

    with pytest.raises(ConversionError) as excinfo:
        ConversionEngine().convert_url(ARTICLE_URL)
    assert "certificate" in str(excinfo.value)


def test_timeout_becomes_an_actionable_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(_url: str, **_kwargs: object) -> requests.Response:
        raise requests.exceptions.Timeout("read timed out")

    monkeypatch.setattr("mdconv.engine.requests.get", fake_get)

    with pytest.raises(ConversionError, match="timed out after 30s"):
        ConversionEngine().convert_url(ARTICLE_URL)


def test_http_error_status_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(_url: str, **_kwargs: object) -> requests.Response:
        response = requests.Response()
        response.status_code = 404
        response.url = ARTICLE_URL
        response._content = b"not found"
        return response

    monkeypatch.setattr("mdconv.engine.requests.get", fake_get)

    with pytest.raises(ConversionError) as excinfo:
        ConversionEngine().convert_url(ARTICLE_URL)
    assert "404" in str(excinfo.value)
