from __future__ import annotations

from pathlib import Path

from jobhunt.cv.profile_seeder import ProfileSeeder
from jobhunt.models import ProfileDraft
from tests.unit._fakes import FakeCvReader, FakeLLMProvider


def test_seed_reads_cv_and_calls_llm(tmp_path: Path) -> None:
    expected = ProfileDraft(
        min_salary_eur=95000,
        allowed_locations=["remote", "munich"],
        seniority=["senior"],
        stack_must_haves=["python"],
    )
    llm = FakeLLMProvider(profile=expected)
    reader = FakeCvReader(text="DERIVED CV TEXT")
    seeder = ProfileSeeder(llm=llm, reader=reader)
    cv_path = tmp_path / "cv.pdf"
    cv_path.write_bytes(b"unused - fake reader")
    draft = seeder.seed(cv_path)
    assert draft == expected
    assert reader.calls == [cv_path]
    assert llm.profile_calls == ["DERIVED CV TEXT"]
