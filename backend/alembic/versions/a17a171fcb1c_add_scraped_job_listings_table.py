"""add scraped job listings table

Revision ID: a17a171fcb1c
Revises: 000000000001
Create Date: 2026-08-03 00:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "a17a171fcb1c"
down_revision = "000000000001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "scraped_job_listings",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("company", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("location", sa.String(), nullable=True),
        sa.Column("source", sa.String(), nullable=True),
        sa.Column("external_id", sa.String(), nullable=True),
        sa.Column("search_term", sa.String(), nullable=True),
        sa.Column("job_type", sa.String(), nullable=True),
        sa.Column("salary_range", sa.String(), nullable=True),
        sa.Column("posted_at", sa.String(), nullable=True),
        sa.Column("required_skills", sa.JSON(), nullable=False),
        sa.Column("seniority", sa.String(), nullable=True),
        sa.Column("min_experience_years", sa.Integer(), nullable=True),
        sa.Column("max_experience_years", sa.Integer(), nullable=True),
        sa.Column("scraped_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("url"),
    )
    op.create_index(
        op.f("ix_scraped_job_listings_id"), "scraped_job_listings", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_scraped_job_listings_url"), "scraped_job_listings", ["url"], unique=True
    )
    op.create_index(
        op.f("ix_scraped_job_listings_source"), "scraped_job_listings", ["source"], unique=False
    )
    op.create_index(
        op.f("ix_scraped_job_listings_seniority"),
        "scraped_job_listings",
        ["seniority"],
        unique=False,
    )
    op.create_index(
        op.f("ix_scraped_job_listings_status"), "scraped_job_listings", ["status"], unique=False
    )


def downgrade():
    op.drop_index(op.f("ix_scraped_job_listings_status"), table_name="scraped_job_listings")
    op.drop_index(op.f("ix_scraped_job_listings_seniority"), table_name="scraped_job_listings")
    op.drop_index(op.f("ix_scraped_job_listings_source"), table_name="scraped_job_listings")
    op.drop_index(op.f("ix_scraped_job_listings_url"), table_name="scraped_job_listings")
    op.drop_index(op.f("ix_scraped_job_listings_id"), table_name="scraped_job_listings")
    op.drop_table("scraped_job_listings")
