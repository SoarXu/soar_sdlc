from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Integer, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from app.services.project_data_purge_service import _delete_ids, _matching_ids, _null_references


class _Base(DeclarativeBase):
    pass


class _Row(_Base):
    __tablename__ = "project_data_purge_batch_rows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reference_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


@contextmanager
def _bound_parameter_counts(engine) -> Iterator[list[int]]:
    counts: list[int] = []

    def capture(_conn, _cursor, _statement, parameters, _context, executemany):
        if executemany:
            counts.extend(len(row) for row in parameters)
        else:
            counts.append(len(parameters))

    event.listen(engine, "before_cursor_execute", capture)
    try:
        yield counts
    finally:
        event.remove(engine, "before_cursor_execute", capture)


def _session_with_rows() -> tuple[Session, object]:
    engine = create_engine("sqlite:///:memory:")
    _Base.metadata.create_all(engine)
    db = Session(engine, autoflush=False)
    db.add_all(_Row(id=value, reference_id=value) for value in range(1, 1201))
    db.commit()
    return db, engine


def test_matching_ids_batches_large_value_sets() -> None:
    db, engine = _session_with_rows()
    try:
        with _bound_parameter_counts(engine) as counts:
            row_ids = _matching_ids(db, _Row, _Row.reference_id, set(range(1, 1201)))

        assert row_ids == set(range(1, 1201))
        assert counts
        assert max(counts) <= 500
    finally:
        db.close()
        engine.dispose()


def test_null_references_batches_matches_and_updates() -> None:
    db, engine = _session_with_rows()
    owned_ids = set(range(1, 101))
    try:
        with _bound_parameter_counts(engine) as counts:
            updated = _null_references(
                db,
                _Row,
                _Row.reference_id,
                set(range(1, 1201)),
                owned_ids,
            )

        assert updated == 1100
        assert db.query(_Row).filter(_Row.id.in_(owned_ids), _Row.reference_id.is_(None)).count() == 0
        assert db.query(_Row).filter(~_Row.id.in_(owned_ids), _Row.reference_id.is_not(None)).count() == 0
        assert counts
        assert max(counts) <= 500
    finally:
        db.close()
        engine.dispose()


def test_delete_ids_batches_large_id_sets() -> None:
    db, engine = _session_with_rows()
    try:
        with _bound_parameter_counts(engine) as counts:
            deleted = _delete_ids(db, _Row, set(range(1, 1201)))

        assert deleted == 1200
        assert db.query(_Row).count() == 0
        assert counts
        assert max(counts) <= 500
    finally:
        db.close()
        engine.dispose()
