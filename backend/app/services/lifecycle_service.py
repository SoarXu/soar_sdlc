from sqlalchemy.orm import Session

from app.models.iteration import Iteration
from app.models.project import Project
from app.models.requirement import Requirement
from app.models.test_case import TestCase

DEVELOPMENT_PHASE = "development"
MAINTENANCE_PHASE = "maintenance"


def normalize_lifecycle_phase(value: str | None) -> str:
    return value if value in {DEVELOPMENT_PHASE, MAINTENANCE_PHASE} else DEVELOPMENT_PHASE


def project_lifecycle_phase(db: Session, project_id: int | None) -> str:
    if not project_id:
        return DEVELOPMENT_PHASE
    project = db.query(Project).filter(Project.id == project_id, Project.deleted == 0).first()
    return normalize_lifecycle_phase(project.lifecycle_phase if project else None)


def requirement_lifecycle_phase(db: Session, requirement_id: int | None) -> str | None:
    if not requirement_id:
        return None
    requirement = db.query(Requirement).filter(Requirement.id == requirement_id, Requirement.deleted == 0).first()
    return normalize_lifecycle_phase(requirement.lifecycle_phase) if requirement else None


def test_case_lifecycle_phase(db: Session, test_case_id: int | None) -> str | None:
    if not test_case_id:
        return None
    test_case = db.query(TestCase).filter(TestCase.id == test_case_id, TestCase.deleted == 0).first()
    return normalize_lifecycle_phase(test_case.lifecycle_phase) if test_case else None


def iteration_lifecycle_phase(db: Session, iteration_id: int | None) -> str | None:
    if not iteration_id:
        return None
    iteration = db.query(Iteration).filter(Iteration.id == iteration_id, Iteration.deleted == 0).first()
    return normalize_lifecycle_phase(iteration.lifecycle_phase) if iteration else None
