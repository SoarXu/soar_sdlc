from app.db.session import SessionLocal
from app.services.iteration_service import auto_start_due_iterations


def run_auto_start_due_iterations() -> int:
    db = SessionLocal()
    try:
        return auto_start_due_iterations(db)
    finally:
        db.close()
