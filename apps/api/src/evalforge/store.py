"""SQLAlchemy store for checks + review queue + labeled examples.

Backed by Postgres in prod, can run against SQLite in unit tests if needed.
The schema is intentionally narrow so testcontainers + in-memory both work.
"""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    DateTime,
    String,
    Text,
    and_,
    create_engine,
    select,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from evalforge.schemas import AxisScore, CheckRecord, ReviewLabel


class Base(DeclarativeBase):
    pass


class CheckRow(Base):
    __tablename__ = "checks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    prompt_version: Mapped[str] = mapped_column(String(64), index=True)
    output_text: Mapped[str] = mapped_column(Text)
    flagged: Mapped[bool] = mapped_column(index=True)
    axes_json: Mapped[list[dict[str, object]]] = mapped_column(JSON)
    review_label: Mapped[str] = mapped_column(
        String(32), default=ReviewLabel.UNREVIEWED.value, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LabeledExampleRow(Base):
    """Reviewer-corrected examples that feed back into the quality scorer."""

    __tablename__ = "labeled_examples"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    prompt_version: Mapped[str] = mapped_column(String(64), index=True)
    output_text: Mapped[str] = mapped_column(Text)
    correct_label: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


def _default_db_url() -> str:
    return os.environ.get("EVALFORGE_DB_URL", "sqlite+pysqlite:///:memory:")


def make_engine(url: str | None = None) -> Engine:
    url = url or _default_db_url()
    connect_args: dict[str, object] = {}
    engine_kwargs: dict[str, object] = {"future": True}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        # In-memory SQLite needs a single shared connection across threads,
        # otherwise every checkout gets a fresh empty database.
        if ":memory:" in url or url.endswith(":memory:"):
            from sqlalchemy.pool import StaticPool

            engine_kwargs["poolclass"] = StaticPool
    engine = create_engine(url, connect_args=connect_args, **engine_kwargs)
    Base.metadata.create_all(engine)
    return engine


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


def _row_to_record(row: CheckRow) -> CheckRecord:
    axes_payload: object = row.axes_json
    if isinstance(axes_payload, str):
        axes_payload = json.loads(axes_payload)
    assert isinstance(axes_payload, list)
    axes = [AxisScore.model_validate(a) for a in axes_payload]
    return CheckRecord(
        id=uuid.UUID(row.id),
        prompt_version=row.prompt_version,
        output_text=row.output_text,
        flagged=row.flagged,
        axes=axes,
        review_label=ReviewLabel(row.review_label),
        created_at=row.created_at if row.created_at is not None else datetime.now(UTC),
        reviewed_at=row.reviewed_at,
    )


class Store:
    """High-level persistence facade."""

    def __init__(self, session_factory: sessionmaker[Session]):
        self._session_factory = session_factory

    def insert_check(
        self,
        *,
        check_id: uuid.UUID,
        prompt_version: str,
        output_text: str,
        flagged: bool,
        axes: list[AxisScore],
        created_at: datetime | None = None,
    ) -> CheckRecord:
        created_at = created_at or datetime.now(UTC)
        axes_payload = [a.model_dump(mode="json") for a in axes]
        with self._session_factory() as sess:
            row = CheckRow(
                id=str(check_id),
                prompt_version=prompt_version,
                output_text=output_text,
                flagged=flagged,
                axes_json=axes_payload,
                review_label=ReviewLabel.UNREVIEWED.value,
                created_at=created_at,
            )
            sess.add(row)
            sess.commit()
            sess.refresh(row)
            return _row_to_record(row)

    def list_recent(self, limit: int = 50) -> list[CheckRecord]:
        with self._session_factory() as sess:
            stmt = select(CheckRow).order_by(CheckRow.created_at.desc()).limit(limit)
            rows = sess.execute(stmt).scalars().all()
            return [_row_to_record(r) for r in rows]

    def list_queue(self, limit: int = 100) -> list[CheckRecord]:
        with self._session_factory() as sess:
            stmt = (
                select(CheckRow)
                .where(
                    and_(
                        CheckRow.flagged.is_(True),
                        CheckRow.review_label == ReviewLabel.UNREVIEWED.value,
                    )
                )
                .order_by(CheckRow.created_at.asc())
                .limit(limit)
            )
            rows = sess.execute(stmt).scalars().all()
            return [_row_to_record(r) for r in rows]

    def get(self, check_id: uuid.UUID) -> CheckRecord | None:
        with self._session_factory() as sess:
            row = sess.get(CheckRow, str(check_id))
            return _row_to_record(row) if row else None

    def review(self, check_id: uuid.UUID, label: ReviewLabel) -> CheckRecord:
        if label == ReviewLabel.UNREVIEWED:
            raise ValueError("cannot transition back to unreviewed")
        with self._session_factory() as sess:
            row = sess.get(CheckRow, str(check_id))
            if row is None:
                raise KeyError(str(check_id))
            current = ReviewLabel(str(row.review_label))
            if current != ReviewLabel.UNREVIEWED:
                # idempotent: re-applying the same label is fine, changing is not.
                if current != label:
                    raise ValueError(
                        f"check {check_id} already reviewed as {current.value}, cannot change to {label.value}"
                    )
            row.review_label = label.value
            row.reviewed_at = datetime.now(UTC)
            sess.commit()
            sess.refresh(row)
            record = _row_to_record(row)

        if label == ReviewLabel.FALSE_POSITIVE:
            # The reviewer says: not actually flagged. Store as a labeled example.
            self._insert_labeled_example(
                prompt_version=record.prompt_version,
                output_text=record.output_text,
                correct_label="not_flagged",
            )
        elif label == ReviewLabel.FALSE_NEGATIVE:
            self._insert_labeled_example(
                prompt_version=record.prompt_version,
                output_text=record.output_text,
                correct_label="flagged",
            )
        return record

    def _insert_labeled_example(
        self, *, prompt_version: str, output_text: str, correct_label: str
    ) -> None:
        with self._session_factory() as sess:
            sess.add(
                LabeledExampleRow(
                    id=str(uuid.uuid4()),
                    prompt_version=prompt_version,
                    output_text=output_text,
                    correct_label=correct_label,
                    created_at=datetime.now(UTC),
                )
            )
            sess.commit()

    def sample_labeled_examples(self, prompt_version: str, k: int = 3) -> list[tuple[str, str]]:
        """Return up to k (output_text, correct_label) pairs for few-shot prompting."""
        with self._session_factory() as sess:
            stmt = (
                select(LabeledExampleRow)
                .where(LabeledExampleRow.prompt_version == prompt_version)
                .order_by(LabeledExampleRow.created_at.desc())
                .limit(k)
            )
            rows = sess.execute(stmt).scalars().all()
            return [(str(r.output_text), str(r.correct_label)) for r in rows]

    def prompt_version_stats(self) -> list[dict[str, object]]:
        """Per-prompt-version axis pass rates for the dashboard compare page."""
        with self._session_factory() as sess:
            rows = sess.execute(select(CheckRow)).scalars().all()
        groups: dict[str, list[CheckRecord]] = {}
        for r in rows:
            rec = _row_to_record(r)
            groups.setdefault(rec.prompt_version, []).append(rec)
        out: list[dict[str, object]] = []
        for version, records in sorted(groups.items()):
            total = len(records)
            quality_pass = sum(
                1 for r in records for ax in r.axes if ax.axis.value == "quality" and not ax.flagged
            )
            safety_pass = sum(
                1 for r in records for ax in r.axes if ax.axis.value == "safety" and not ax.flagged
            )
            mod_pass = sum(
                1
                for r in records
                for ax in r.axes
                if ax.axis.value == "moderation" and not ax.flagged
            )
            out.append(
                {
                    "prompt_version": version,
                    "total": total,
                    "quality_pass_rate": quality_pass / total if total else 0.0,
                    "safety_pass_rate": safety_pass / total if total else 0.0,
                    "moderation_pass_rate": mod_pass / total if total else 0.0,
                }
            )
        return out

    def clear(self) -> None:
        """Test helper. Wipes both tables."""
        with self._session_factory() as sess:
            sess.query(CheckRow).delete()
            sess.query(LabeledExampleRow).delete()
            sess.commit()


def make_store(url: str | None = None) -> Store:
    engine = make_engine(url)
    factory = make_session_factory(engine)
    return Store(factory)


def chunked(items: Iterable[CheckRecord], n: int) -> Iterable[list[CheckRecord]]:
    """Small util used by the dashboard live feed."""
    buf: list[CheckRecord] = []
    for it in items:
        buf.append(it)
        if len(buf) >= n:
            yield buf
            buf = []
    if buf:
        yield buf
