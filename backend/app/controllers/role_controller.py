from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services import role_service
from app.views.role_view import RoleCreate, RoleRead, RoleUpdate


router = APIRouter()


@router.get("", response_model=list[RoleRead])
def get_roles(db: Session = Depends(get_db)):
    return role_service.list_roles(db)


@router.post("", response_model=RoleRead, status_code=status.HTTP_201_CREATED)
def create_role(payload: RoleCreate, db: Session = Depends(get_db)):
    return role_service.create_role(db, payload)


@router.put("/{role_id}", response_model=RoleRead)
def update_role(role_id: int, payload: RoleUpdate, db: Session = Depends(get_db)):
    return role_service.update_role(db, role_id, payload)


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(role_id: int, db: Session = Depends(get_db)):
    role_service.delete_role(db, role_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
