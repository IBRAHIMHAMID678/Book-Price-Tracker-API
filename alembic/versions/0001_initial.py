"""0001_initial

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-29 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "scrape_runs",
        sa.Column(
            "id", sa.BigInteger(), sa.Identity(always=False), primary_key=True, autoincrement=True
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.Text(), server_default="running", nullable=False),
        sa.Column("pages_requested", sa.Integer(), nullable=True),
        sa.Column("books_seen", sa.Integer(), server_default="0", nullable=False),
        sa.Column("inserted", sa.Integer(), server_default="0", nullable=False),
        sa.Column("updated", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('running','succeeded','failed')",
            name="scrape_runs_status_check",
        ),
    )

    op.create_table(
        "scrape_errors",
        sa.Column(
            "id", sa.BigInteger(), sa.Identity(always=False), primary_key=True, autoincrement=True
        ),
        sa.Column(
            "run_id",
            sa.BigInteger(),
            sa.ForeignKey("scrape_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("stage", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_table(
        "books",
        sa.Column(
            "id", sa.BigInteger(), sa.Identity(always=False), primary_key=True, autoincrement=True
        ),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("currency", sa.CHAR(length=3), server_default="GBP", nullable=False),
        sa.Column("rating", sa.SmallInteger(), nullable=False),
        sa.Column("in_stock", sa.Boolean(), nullable=False),
        sa.Column("stock_count", sa.Integer(), nullable=True),
        sa.Column("availability_raw", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("upc", sa.Text(), nullable=True),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "scraped_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("source_url", name="books_source_url_key"),
        sa.CheckConstraint("price >= 0", name="books_price_check"),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name="books_rating_check"),
        sa.CheckConstraint("stock_count >= 0", name="books_stock_count_check"),
    )

    op.create_index("books_category_idx", "books", ["category"])
    op.create_index("books_price_idx", "books", ["price"])
    op.create_index("books_rating_idx", "books", ["rating"])
    op.create_index("books_created_idx", "books", [sa.text("id DESC")])


def downgrade() -> None:
    op.drop_index("books_created_idx", table_name="books")
    op.drop_index("books_rating_idx", table_name="books")
    op.drop_index("books_price_idx", table_name="books")
    op.drop_index("books_category_idx", table_name="books")
    op.drop_table("books")
    op.drop_table("scrape_errors")
    op.drop_table("scrape_runs")
