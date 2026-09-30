"""Web API tests (Flask test client — no server process needed)."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from mdconv import ConversionEngine
from mdconv.server import create_app
from tests.fixtures import write_samples


@pytest.fixture(scope="module")
def client():
    app = create_app(ConversionEngine())
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture(scope="module")
def samples(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    return write_samples(tmp_path_factory.mktemp("web_samples"))


def upload(client, files: dict[str, bytes], urls: list[str] | None = None):
    data = {
        "files": [(io.BytesIO(payload), name) for name, payload in files.items()],
        "urls": urls or [],
    }
    return client.post("/api/convert", data=data, content_type="multipart/form-data")


def test_index_is_the_upload_page(client) -> None:
    page = client.get("/")
    assert page.status_code == 200
    assert b"Drop files here" in page.data
    assert b"/api/convert" in page.data


def test_health(client) -> None:
    body = client.get("/api/health").get_json()
    assert body["ok"] is True


def test_converts_an_uploaded_document(client, samples: dict[str, Path]) -> None:
    response = upload(client, {"book.docx": samples["book.docx"].read_bytes()})
    assert response.status_code == 200
    results = response.get_json()["results"]
    assert len(results) == 1
    assert results[0]["ok"] is True
    assert results[0]["name"] == "book.docx"
    assert "Contract Heading" in results[0]["markdown"]
    assert results[0]["chars"] > 0


def test_converts_several_files_in_one_request(
    client, samples: dict[str, Path]
) -> None:
    files = {
        "page.html": samples["page.html"].read_bytes(),
        "report.pdf": samples["report.pdf"].read_bytes(),
    }
    results = upload(client, files).get_json()["results"]
    assert [r["ok"] for r in results] == [True, True]
    assert any("Welcome aboard" in r["markdown"] for r in results)
    assert any("PDF body text" in r["markdown"] for r in results)


def test_failed_conversion_is_reported_per_file(
    client, samples: dict[str, Path]
) -> None:
    files = {
        "junk.dat": samples["junk.dat"].read_bytes(),
        "notes.md": samples["notes.md"].read_bytes(),
    }
    results = upload(client, files).get_json()["results"]
    by_name = {r["name"]: r for r in results}
    assert by_name["junk.dat"]["ok"] is False
    assert "not supported" in by_name["junk.dat"]["error"]
    assert by_name["notes.md"]["ok"] is True  # one bad file never kills the batch


def test_bad_url_is_reported_not_crashed(client) -> None:
    results = upload(client, {}, urls=["notaurl"]).get_json()["results"]
    assert results[0]["ok"] is False
    assert "http" in results[0]["error"]


def test_empty_request_is_rejected(client) -> None:
    response = client.post("/api/convert", data={})
    assert response.status_code == 400
    assert "Nothing to convert" in response.get_json()["error"]


def test_oversized_upload_returns_json_413(client, samples: dict[str, Path]) -> None:
    client.application.config["MAX_CONTENT_LENGTH"] = 64  # smaller than the payload
    try:
        response = upload(client, {"page.html": samples["page.html"].read_bytes()})
        assert response.status_code == 413
        assert "too large" in response.get_json()["error"].lower()
    finally:
        client.application.config["MAX_CONTENT_LENGTH"] = 64 * 1024 * 1024
