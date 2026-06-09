from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.test_case import TestCase
from app.views.test_case_view import TestCaseCreate, TestCaseUpdate


def list_test_cases(db: Session) -> list[TestCase]:
    return db.query(TestCase).filter(TestCase.delete_time.is_(None)).order_by(TestCase.id.desc()).all()


def create_test_case(db: Session, payload: TestCaseCreate) -> TestCase:
    test_case = TestCase(**payload.model_dump())
    db.add(test_case)
    db.commit()
    db.refresh(test_case)
    return test_case


def update_test_case(db: Session, test_case_id: int, payload: TestCaseUpdate) -> TestCase:
    test_case = _get_active_test_case(db, test_case_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(test_case, field, value)
    db.commit()
    db.refresh(test_case)
    return test_case


def delete_test_case(db: Session, test_case_id: int) -> None:
    test_case = _get_active_test_case(db, test_case_id)
    test_case.delete_time = datetime.now()
    db.commit()


def _get_active_test_case(db: Session, test_case_id: int) -> TestCase:
    test_case = db.query(TestCase).filter(TestCase.id == test_case_id, TestCase.delete_time.is_(None)).first()
    if not test_case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test case not found")
    return test_case
