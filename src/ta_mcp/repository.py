import shutil
import sqlite3
import tempfile
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, event, inspect, select, update
from sqlalchemy.orm import Session

from ta_mcp.db import ArtifactRecord, RunRecord
from ta_mcp.domain import ReviewArtifact, ReviewBundle, RunState
from ta_mcp.mappers import insert_bundle, insert_entity, load_bundle
from ta_mcp.reporting import content_digest, render_json, render_markdown
from ta_mcp.scoring import ScoreCalculator


class ReviewConflict(ValueError):
    """Conflicting reuse of an immutable review or entity identity."""


@dataclass(frozen=True)
class SavedReview:
    """Final report paths and content identity."""

    json_path: Path
    markdown_path: Path
    digest: str


def enable_foreign_keys(connection: sqlite3.Connection, record: object) -> None:
    """Enable referential integrity on every SQLite connection."""
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA busy_timeout=10000")


def create_review_engine(database: Path) -> Engine:
    """Configure a local SQLite engine without creating persistent files."""
    engine = create_engine(f"sqlite:///{database}")
    event.listen(engine, "connect", enable_foreign_keys)
    return engine


def migrate(engine: Engine) -> None:
    """Upgrade the local audit schema through its packaged Alembic migration."""
    configuration = Config()
    configuration.set_main_option(
        "script_location", str(Path(__file__).parent / "migrations")
    )
    with engine.begin() as connection:
        configuration.attributes["connection"] = connection
        command.upgrade(configuration, "head")


class ReviewRepository:
    """Normalized immutable persistence and recoverable report finalization."""

    def __init__(self, database: Path, output: Path) -> None:
        self.database = database.resolve()
        self.output = output.resolve()
        self.engine = create_review_engine(self.database)

    def save(self, bundle: ReviewBundle) -> SavedReview:
        """Validate, persist, and finalize one immutable review idempotently.

        Normalized rows are committed pending finalization, then files are staged
        and renamed under a SQLite write lock before database finalization. A final
        marker is published last. Retrying the identical bundle repairs interrupted
        finalization; a different digest never overwrites history.

        Args:
            bundle: Complete review with verified normalized references.

        Returns:
            Final JSON and Markdown paths and the canonical JSON digest.
        """
        bundle = ReviewBundle.model_validate_json(bundle.model_dump_json())
        bundle = ReviewBundle.model_validate(
            {**bundle.model_dump(), "summary": ScoreCalculator.calculate(bundle)}
        )
        if bundle.run.state not in {RunState.COMPLETED, RunState.NEEDS_REVIEW}:
            raise ValueError("Only finalized grading decisions may be saved")
        json_text = render_json(bundle)
        markdown_text = render_markdown(bundle)
        digest = content_digest(json_text)
        final = self.output / str(bundle.run.id)
        if final.is_symlink():
            raise ReviewConflict("Report directory cannot be a symbolic link")
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self.output.mkdir(parents=True, exist_ok=True)
        migrate(self.engine)
        with self.engine.connect() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            with Session(bind=connection) as session:
                existing = session.get(RunRecord, bundle.run.id)
                if existing and existing.content_digest != digest:
                    raise ReviewConflict(
                        "Review ID already exists with different content"
                    )
                if existing is None:
                    try:
                        insert_bundle(session, bundle, digest)
                        for format_name, filename, content in (
                            ("json", "review.json", json_text),
                            ("markdown", "review.md", markdown_text),
                        ):
                            artifact = ReviewArtifact(
                                review_run_id=bundle.run.id,
                                format=format_name,
                                relative_path=f"{bundle.run.id}/{filename}",
                                sha256=content_digest(content),
                            )
                            insert_entity(session, ArtifactRecord, artifact)
                        session.flush()
                    except ValueError as error:
                        raise ReviewConflict(str(error)) from error
                connection.commit()
        stage: Path | None = None
        try:
            with self.engine.connect() as connection:
                connection.exec_driver_sql("BEGIN IMMEDIATE")
                if final.is_symlink():
                    raise ReviewConflict("Report directory cannot be a symbolic link")
                for abandoned in self.output.glob(f".stage-{bundle.run.id}-*"):
                    if abandoned.is_dir() and not abandoned.is_symlink():
                        shutil.rmtree(abandoned)
                if final.exists():
                    for filename, content in (
                        ("review.json", json_text),
                        ("review.md", markdown_text),
                    ):
                        path = final / filename
                        if (
                            path.is_symlink()
                            or not path.is_file()
                            or content_digest(path.read_text())
                            != content_digest(content)
                        ):
                            raise ReviewConflict(
                                "Existing report files disagree with immutable database"
                            )
                else:
                    stage = Path(
                        tempfile.mkdtemp(
                            prefix=f".stage-{bundle.run.id}-", dir=self.output
                        )
                    )
                    (stage / "review.json").write_text(json_text, encoding="utf-8")
                    (stage / "review.md").write_text(markdown_text, encoding="utf-8")
                    stage.rename(final)
                    stage = None
                connection.execute(
                    update(RunRecord)
                    .where(RunRecord.id == bundle.run.id)
                    .values(is_finalized=True)
                )
                connection.commit()
            marker = final / "COMPLETED"
            temporary_marker = final / f".complete-{uuid4()}"
            temporary_marker.write_text(digest + "\n", encoding="utf-8")
            temporary_marker.replace(marker)
        finally:
            if stage is not None:
                shutil.rmtree(stage)
        return SavedReview(final / "review.json", final / "review.md", digest)

    def matches_existing(self, bundle: ReviewBundle) -> bool:
        """Authorize an exact retry using trusted immutable database history."""
        if not self.database.is_file() or not inspect(self.engine).has_table(
            "review_runs"
        ):
            return False
        normalized = ReviewBundle.model_validate(
            {**bundle.model_dump(), "summary": ScoreCalculator.calculate(bundle)}
        )
        with Session(self.engine) as session:
            record = session.get(RunRecord, bundle.run.id)
            if record is None:
                return False
            if content_digest(render_json(normalized)) != record.content_digest:
                raise ReviewConflict("Review ID already exists with different content")
            return True

    def load(self, run_id: UUID) -> ReviewBundle:
        """Load finalized normalized records and verify their completion marker."""
        with Session(self.engine) as session:
            record = session.get(RunRecord, run_id)
            marker = self.output / str(run_id) / "COMPLETED"
            if marker.parent.is_symlink():
                raise ValueError("Report directory cannot be a symbolic link")
            if record is None or not record.is_finalized or not marker.is_file():
                raise ValueError("Review finalization is incomplete")
            if marker.read_text().strip() != record.content_digest:
                raise ValueError("Completion marker does not match database")
            bundle = load_bundle(session, run_id)
            if content_digest(render_json(bundle)) != record.content_digest:
                raise ValueError(
                    "Normalized records disagree with saved content digest"
                )
            for artifact in session.scalars(
                select(ArtifactRecord).where(ArtifactRecord.review_run_id == run_id)
            ):
                path = self.output / artifact.relative_path
                if (
                    path.is_symlink()
                    or not path.is_file()
                    or content_digest(path.read_text()) != artifact.sha256
                ):
                    raise ValueError("Final report checksum mismatch")
            return bundle
