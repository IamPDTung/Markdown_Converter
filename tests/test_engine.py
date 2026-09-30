"""Engine-level tests: every supported format plus the error paths."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from mdconv import ConversionEngine, ConversionError
from tests.fixtures import write_samples


@pytest.fixture(scope="module")
def engine() -> ConversionEngine:
    return ConversionEngine()


@pytest.fixture(scope="module")
def samples(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    return write_samples(tmp_path_factory.mktemp("samples"))


# --------------------------------------------------------------- happy path


def test_html_to_markdown(engine: ConversionEngine, samples: dict[str, Path]) -> None:
    markdown = engine.convert_path(samples["page.html"])
    assert "# Welcome aboard" in markdown
    assert "**intro**" in markdown
    assert "* alpha" in markdown  # markitdown emits `*` style bullets


def test_docx_to_markdown(engine: ConversionEngine, samples: dict[str, Path]) -> None:
    markdown = engine.convert_path(samples["book.docx"])
    assert "Contract Heading" in markdown
    assert "obligor shall deliver" in markdown


def test_pdf_to_markdown(engine: ConversionEngine, samples: dict[str, Path]) -> None:
    markdown = engine.convert_path(samples["report.pdf"])
    assert "PDF body text" in markdown


def test_pptx_to_markdown(engine: ConversionEngine, samples: dict[str, Path]) -> None:
    markdown = engine.convert_path(samples["deck.pptx"])
    assert "Slide Title" in markdown
    assert "Bullet one" in markdown


def test_xlsx_to_markdown(engine: ConversionEngine, samples: dict[str, Path]) -> None:
    markdown = engine.convert_path(samples["figures.xlsx"])
    assert "widgets" in markdown
    assert "42" in markdown


def test_csv_and_txt_and_md(engine: ConversionEngine, samples: dict[str, Path]) -> None:
    assert "ada" in engine.convert_path(samples["data.csv"])
    assert "Plain text line one" in engine.convert_path(samples["readme.txt"])
    assert "# Plain markdown" in engine.convert_path(samples["notes.md"])


def test_upload_from_stream(engine: ConversionEngine, samples: dict[str, Path]) -> None:
    """The web path: bytes arrive as a stream, not as a saved file."""
    data = samples["book.docx"].read_bytes()
    markdown = engine.convert_upload("contract.docx", io.BytesIO(data))
    assert "Contract Heading" in markdown


def test_upload_errors_name_the_original_file(engine: ConversionEngine) -> None:
    """Errors must say what the user uploaded, not the temp staging name."""
    with pytest.raises(ConversionError) as excinfo:
        engine.convert_upload("weird.dat", io.BytesIO(bytes(range(256)) * 8))
    assert "weird.dat" in str(excinfo.value)
    assert "upload.dat" not in str(excinfo.value)


# --------------------------------------------------------------- error paths


def test_missing_file(engine: ConversionEngine, tmp_path: Path) -> None:
    with pytest.raises(ConversionError, match="No such file"):
        engine.convert_path(tmp_path / "ghost.pdf")


def test_empty_file(engine: ConversionEngine, tmp_path: Path) -> None:
    empty = tmp_path / "empty.txt"
    empty.touch()
    with pytest.raises(ConversionError, match="empty"):
        engine.convert_path(empty)


def test_unsupported_format(engine: ConversionEngine, samples: dict[str, Path]) -> None:
    with pytest.raises(ConversionError) as excinfo:
        engine.convert_path(samples["junk.dat"])
    assert "not supported" in str(excinfo.value)


def test_directory_rejected(engine: ConversionEngine, tmp_path: Path) -> None:
    with pytest.raises(ConversionError, match="Not a file"):
        engine.convert_path(tmp_path)


def test_url_scheme_rejected(engine: ConversionEngine) -> None:
    with pytest.raises(ConversionError, match="http"):
        engine.convert_url("ftp://example.com/file.docx")


def test_errors_are_actionable(engine: ConversionEngine) -> None:
    """Every ConversionError should say what went wrong, without a traceback."""
    for call in (
        lambda: engine.convert_path("/definitely/not/here.pdf"),
        lambda: engine.convert_url("notaurl"),
    ):
        with pytest.raises(ConversionError) as excinfo:
            call()
        message = str(excinfo.value)
        assert message and "\n" not in message
