from app.core.scheduler import scheduled_jobs


def test_scheduler_registers_iteration_auto_start_job_at_3am():
    jobs = scheduled_jobs()

    iteration_job = next(job for job in jobs if job["name"] == "auto_start_due_iterations")
    assert iteration_job["hour"] == 3
    assert iteration_job["minute"] == 0
