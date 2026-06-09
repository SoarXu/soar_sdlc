from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.test_case_service import create_test_case, delete_test_case, list_test_cases, update_test_case
from app.views.test_case_view import TestCaseCreate, TestCaseRead, TestCaseUpdate


router = APIRouter()


@router.get("", response_model=list[TestCaseRead])
def get_test_cases(db: Session = Depends(get_db)):
    return list_test_cases(db)


@router.post("", response_model=TestCaseRead)
def post_test_case(payload: TestCaseCreate, db: Session = Depends(get_db)):
    return create_test_case(db, payload)


@router.patch("/{test_case_id}", response_model=TestCaseRead)
def patch_test_case(test_case_id: int, payload: TestCaseUpdate, db: Session = Depends(get_db)):
    return update_test_case(db, test_case_id, payload)


@router.delete("/{test_case_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_test_case(test_case_id: int, db: Session = Depends(get_db)):
    delete_test_case(db, test_case_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
