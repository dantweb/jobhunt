from __future__ import annotations

from pathlib import Path

import pytest

from jobhunt.cv.reader import CvReader
from jobhunt.exceptions import CvReadError, MissingCvError
from tests.unit._fakes import write_minimal_pdf


def test_reads_pdf_text(tmp_path: Path) -> None:
    pdf = write_minimal_pdf(tmp_path / "cv.pdf", "Test Candidate\nSenior Backend Engineer")
    text = CvReader().read(pdf)
    assert "Test Candidate" in text
    assert "Engineer" in text


def test_missing_path_raises_missing_cv_error(tmp_path: Path) -> None:
    with pytest.raises(MissingCvError):
        CvReader().read(tmp_path / "absent.pdf")


def test_unreadable_bytes_raises_cv_read_error(tmp_path: Path) -> None:
    bogus = tmp_path / "broken.pdf"
    bogus.write_bytes(b"this is not a pdf")
    with pytest.raises(CvReadError):
        CvReader().read(bogus)
