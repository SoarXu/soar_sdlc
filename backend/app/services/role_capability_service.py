from sqlalchemy.orm import Session

from app.models.role import RoleCapability


def role_ids_for_capabilities(db: Session, capabilities: set[str] | tuple[str, ...] | list[str]) -> set[int]:
    if not capabilities:
        return set()
    return {
        role_id
        for (role_id,) in db.query(RoleCapability.role_id)
        .filter(RoleCapability.capability.in_(set(capabilities)))
        .all()
    }


def role_id_for_capability(db: Session, capability: str) -> int | None:
    return (
        db.query(RoleCapability.role_id)
        .filter(RoleCapability.capability == capability)
        .scalar()
    )
