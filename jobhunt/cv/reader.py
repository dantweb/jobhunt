from __future__ import annotations

from pathlib import Path

import pdfplumber

from jobhunt.exceptions import CvReadError, MissingCvError


class CvReader:
    def read(self, path: Path) -> str:
        if not path.exists():
            raise MissingCvError(str(path))
        try:
            with pdfplumber.open(path) as pdf:
                pages = [page.extract_text() or "" for page in pdf.pages]
        except Exception as exc:
            raise CvReadError(f"failed to read {path}: {exc}") from exc
        text = "\n".join(pages).strip()
        if not text:
            raise CvReadError(f"no extractable text in {path}")
        return text
