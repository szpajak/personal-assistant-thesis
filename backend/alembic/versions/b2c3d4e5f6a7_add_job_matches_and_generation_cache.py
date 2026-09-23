"""add job_matches and generation_cache tables

Revision ID: b2c3d4e5f6a7
Revises: a17a171fcb1c
Create Date: 2026-08-11 00:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

revision = "b2c3d4e5f6a7"
down_revision = "a17a171fcb1c"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "job_matches",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("person_id", sa.String(), nullable=False),
        sa.Column("job_id", sa.String(), nullable=False),
        sa.Column("job_tier", sa.String(), nullable=False),
        sa.Column("match_score", sa.Integer(), nullable=False),
        sa.Column("quick_score", sa.Integer(), nullable=False),
        sa.Column("matching_skills", sa.JSON(), nullable=False),
        sa.Column("missing_skills", sa.JSON(), nullable=False),
        sa.Column("justification", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("profile_fingerprint", sa.String(), nullable=False),
        sa.Column("matched_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("person_id", "job_id", name="uq_job_matches_person_job"),
    )
    op.create_index("ix_job_matches_person_id", "job_matches", ["person_id"])
    op.create_index("ix_job_matches_job_id", "job_matches", ["job_id"])

    op.create_table(
        "generation_cache",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("person_id", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("subject_id", sa.String(), nullable=False),
        sa.Column("profile_fingerprint", sa.String(), nullable=False),
        sa.Column("payload_text", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "person_id",
            "kind",
            "subject_id",
            name="uq_generation_cache_person_kind_subject",
        ),
    )
    op.create_index("ix_generation_cache_person_id", "generation_cache", ["person_id"])

    # Partial unique index for (source, external_id) when external_id is present.
    op.create_index(
        "uq_scraped_job_listings_source_external_id",
        "scraped_job_listings",
        ["source", "external_id"],
        unique=True,
        postgresql_where=sa.text(
            "external_id IS NOT NULL AND external_id <> '' AND source IS NOT NULL"
        ),
    )


def downgrade():
    op.drop_index(
        "uq_scraped_job_listings_source_external_id",
        table_name="scraped_job_listings",
    )
    op.drop_index("ix_generation_cache_person_id", table_name="generation_cache")
    op.drop_table("generation_cache")
    op.drop_index("ix_job_matches_job_id", table_name="job_matches")
    op.drop_index("ix_job_matches_person_id", table_name="job_matches")
    op.drop_table("job_matches")
