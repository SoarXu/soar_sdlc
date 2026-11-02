from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth_dependencies import get_current_user
from app.db.session import get_db
from app.services.ldap_config_service import proposer_options
from app.views.ldap_view import LdapProposerOption


router = APIRouter()


@router.get("/proposers", response_model=list[LdapProposerOption])
def get_proposers(
    q: str | None = Query(default=None, max_length=100),
    db: Session = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    return proposer_options(db, q)
