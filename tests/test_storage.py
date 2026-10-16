from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from test_domain import make_bundle

from ta_mcp.repository import ReviewConflict, ReviewRepository
from ta_mcp.scoring import ScoreCalculator


def test_migration_roundtrip_and_idempotent_finalization(tmp_path: Path) -> None:
    """Catch lost Decimal values, missing foreign keys, and overwritten history."""
    bundle = make_bundle()
    payload = bundle.model_dump(mode="json")
    payload["summary"] = ScoreCalculator.calculate(bundle).model_dump(mode="json")
    bundle = type(bundle).model_validate(payload)
    repository = ReviewRepository(tmp_path / "reviews.sqlite", tmp_path / "reports")
    saved = repository.save(bundle)
    assert saved.json_path.is_file()
    assert saved.markdown_path.is_file()
    assert (saved.json_path.parent / "COMPLETED").is_file()
    reopened = ReviewRepository(tmp_path / "reviews.sqlite", tmp_path / "reports")
    assert reopened.load(bundle.run.id) == bundle
    assert reopened.save(bundle).json_path == saved.json_path
    assert "NOT_VERIFIABLE" in saved.markdown_path.read_text()
    assert "0" in saved.markdown_path.read_text()
    changed = bundle.model_dump(mode="json")
    changed["assessments"][0]["explanation"] = "Different review content"
    with pytest.raises(ReviewConflict):
        reopened.save(type(bundle).model_validate(changed))
    with repository.engine.begin() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
        assert connection.execute(text("PRAGMA integrity_check")).scalar_one() == "ok"
        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    "INSERT INTO criterion_requirements (criterion_id, requirement_id) "
                    "VALUES ('missing', 'missing')"
                )
            )
    assert not list((tmp_path / "reports").glob(".stage-*"))


def test_frozen_child_collections_cannot_change_history(tmp_path: Path) -> None:
    """Catch later runs adding requirements to an already frozen assignment."""
    from uuid import uuid4

    from ta_mcp.domain import ReviewBundle

    repository = ReviewRepository(tmp_path / "audit.sqlite", tmp_path / "reports")
    original = make_bundle()
    repository.save(original)
    payload = original.model_dump(mode="json")
    extra_requirement = {
        **payload["requirements"][0],
        "id": str(uuid4()),
        "code": "R2",
        "points": None,
    }
    payload["requirements"].append(extra_requirement)
    payload["criterion_requirements"].append(
        {
            "criterion_id": str(original.criteria[0].id),
            "requirement_id": extra_requirement["id"],
        }
    )
    payload["run"]["id"] = str(uuid4())
    payload["assessments"][0]["review_run_id"] = payload["run"]["id"]
    payload["assessments"][0]["id"] = str(uuid4())
    with pytest.raises(ReviewConflict):
        repository.save(ReviewBundle.model_validate(payload))
    loaded = repository.load(original.run.id)
    assert len(loaded.requirements) == 1
    assert loaded.summary is not None
    assert loaded.summary.maximum_possible_score == 10


def test_output_symlink_cannot_redirect_finalization(tmp_path: Path) -> None:
    """Catch report directory links causing writes outside the output boundary."""
    from ta_mcp.domain import ReviewBundle
    from ta_mcp.reporting import render_json, render_markdown

    original = make_bundle()
    bundle = ReviewBundle.model_validate(
        {**original.model_dump(), "summary": ScoreCalculator.calculate(original)}
    )
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "review.json").write_text(render_json(bundle))
    (outside / "review.md").write_text(render_markdown(bundle))
    output = tmp_path / "reports"
    output.mkdir()
    (output / str(bundle.run.id)).symlink_to(outside, target_is_directory=True)
    repository = ReviewRepository(tmp_path / "audit.sqlite", output)
    with pytest.raises((ReviewConflict, ValueError)):
        repository.save(bundle)
    assert not (outside / "COMPLETED").exists()
