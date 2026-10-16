from alembic import op

from ta_mcp.db import Base

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the initial normalized local review audit schema."""
    Base.metadata.create_all(op.get_bind())
    immutable_tables = [
        "assignment_documents",
        "assignment_requirements",
        "submissions",
        "submission_files",
        "grading_policies",
        "grading_rubrics",
        "rubric_criteria",
        "criterion_requirements",
        "penalty_rules",
        "penalty_rule_requirements",
        "check_executions",
        "evidence",
        "source_file_evidence",
        "check_evidence",
        "observation_evidence",
        "criterion_assessments",
        "assessment_evidence",
        "penalty_applications",
        "penalty_application_evidence",
        "review_artifacts",
        "trace_events",
    ]
    for table in immutable_tables:
        for action in ("UPDATE", "DELETE"):
            op.execute(
                f"CREATE TRIGGER freeze_{table}_{action.lower()} "
                f"BEFORE {action} ON {table} "
                "BEGIN SELECT RAISE(ABORT, 'Immutable review history'); END"
            )


def downgrade() -> None:
    """Remove the initial schema when explicitly requested through Alembic."""
    Base.metadata.drop_all(op.get_bind())
