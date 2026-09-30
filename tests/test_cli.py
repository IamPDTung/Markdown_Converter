"""CLI tests: batch mode and output-dir handling."""

from __future__ import annotations

from pathlib import Path

import pytest

from mdconv.cli import main, output_path_for
from tests.fixtures import write_samples


@pytest.fixture(scope="module")
def samples(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    return write_samples(tmp_path_factory.mktemp("cli_samples"))


def test_output_path_for_files_and_urls() -> None:
    assert output_path_for("docs/report.pdf", Path("/tmp")) == Path("/tmp/report.md")
    assert output_path_for("https://x.test/blog/post.html", Path(".")) == Path(
        "post.md"
    )
    assert output_path_for("https://x.test/", Path(".")) == Path("index.md")


def test_batch_conversion_into_output_dir(
    samples: dict[str, Path], tmp_path: Path
) -> None:
    out = tmp_path / "out"
    code = main([str(samples["page.html"]), str(samples["notes.md"]), "-o", str(out)])
    assert code == 0
    assert "# Welcome aboard" in (out / "page.md").read_text()
    assert "# Plain markdown" in (out / "notes.md").read_text()


def test_failure_sets_exit_code_and_keeps_going(
    samples: dict[str, Path], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(
        [str(tmp_path / "missing.pdf"), str(samples["readme.txt"]), "-o", str(tmp_path)]
    )
    captured = capsys.readouterr()
    assert code == 1
    assert "No such file" in captured.err
    assert (tmp_path / "readme.md").exists()  # the good input still converted


def test_stdout_mode(
    samples: dict[str, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    code = main([str(samples["readme.txt"]), "--stdout"])
    captured = capsys.readouterr()
    assert code == 0
    assert "Plain text line one" in captured.out


def test_never_overwrites_its_own_input(tmp_path: Path) -> None:
    source = tmp_path / "self.md"
    source.write_text("# Self referential\n")
    assert main([str(source), "-o", str(tmp_path)]) == 0
    assert source.read_text() == "# Self referential\n"  # untouched
    assert (tmp_path / "self.converted.md").exists()
