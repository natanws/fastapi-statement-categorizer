from collections.abc import Iterator
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    create_engine,
    func,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


class ImportBatch(Base):
    """One uploaded file. Counts make re-imports visible: a second upload reports duplicates."""

    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    account: Mapped[str] = mapped_column(String(64))
    filename: Mapped[str] = mapped_column(String(255))
    file_format: Mapped[str] = mapped_column(String(8))
    rows_total: Mapped[int]
    rows_new: Mapped[int]
    rows_duplicate: Mapped[int]
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    account: Mapped[str] = mapped_column(String(64), index=True)
    posted_on: Mapped[date] = mapped_column(Date, index=True)
    description: Mapped[str] = mapped_column(String(255))
    # Money is never a float: Numeric/Decimal keeps cents exact.
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    # Same file imported twice -> same fingerprints -> the unique index rejects duplicates.
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True)
    category: Mapped[str | None] = mapped_column(String(64), default=None, index=True)
    # Explains the category: which rule set it, or "manual" when a person did. Manual categories
    # are never overwritten by re-running the rules.
    category_source: Mapped[str | None] = mapped_column(String(8), default=None)
    rule_id: Mapped[int | None] = mapped_column(
        ForeignKey("rules.id", ondelete="SET NULL"), default=None
    )
    batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id"))


class Rule(Base):
    """Categorization rule. Rules run in priority order (lowest first); the first match wins."""

    __tablename__ = "rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    category: Mapped[str] = mapped_column(String(64))
    priority: Mapped[int] = mapped_column(default=100)
    match_type: Mapped[str] = mapped_column(String(8))  # "contains" or "regex"
    pattern: Mapped[str] = mapped_column(String(200))
    direction: Mapped[str] = mapped_column(String(8), default="any")  # debit | credit | any
    min_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), default=None)
    max_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), default=None)
    enabled: Mapped[bool] = mapped_column(default=True)


def make_engine(url: str) -> Engine:
    if url == "sqlite://":
        # In-memory database (tests): one shared connection, or each session sees an empty DB.
        return create_engine(url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args)


class Database:
    def __init__(self, url: str) -> None:
        self.engine = make_engine(url)
        self._sessions = sessionmaker(self.engine, expire_on_commit=False)

    def create_schema(self) -> None:
        Base.metadata.create_all(self.engine)

    def session(self) -> Iterator[Session]:
        with self._sessions() as session:
            yield session
