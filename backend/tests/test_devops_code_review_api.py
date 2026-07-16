from app.db.session import SessionLocal
from app.models.bug import Bug
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.requirement import Requirement
from app.models.role import Role, UserRole
from app.models.task import Task
from app.models.user import User
from app.services.workflow_state_service import initial_workflow_values
from app.core.security import get_password_hash


def test_commit_ingest_links_objects_and_creates_review_task(client):
    db = SessionLocal()
    try:
        project = Project(name="DevOps 链接验证项目", status="active")
        db.add(project)
        db.flush()
        requirement = Requirement(
            project_id=project.id,
            title="REQ DevOps 需求",
            owner_id=None,
            **initial_workflow_values(db, "requirement", project.id),
        )
        db.add(requirement)
        db.flush()
        task = Task(
            project_id=project.id,
            title="TASK DevOps 任务",
            requirement_id=requirement.id,
            **initial_workflow_values(db, "task", project.id),
        )
        db.add(task)
        bug = Bug(
            project_id=project.id,
            title="BUG DevOps 缺陷",
            requirement_id=requirement.id,
            **initial_workflow_values(db, "bug", project.id),
        )
        db.add(bug)
        db.commit()

        response = client.post(
            "/api/v1/devops/commits",
            json={
                "commit_sha": "abc1234567890def",
                "branch_name": "feature/devops-review",
                "message": f"REQ-{requirement.id} TASK-{task.id} BUG-{bug.id} add review hook",
                "diff_text": "diff --git a/app.py b/app.py\n+print('review')",
            },
        )
        assert response.status_code == 201
        commit_id = response.json()["id"]

        req_commits = client.get(f"/api/v1/devops/commits?object_type=requirement&object_id={requirement.id}")
        assert req_commits.status_code == 200
        assert [item["id"] for item in req_commits.json()] == [commit_id]

        detail = client.get(f"/api/v1/devops/commits/{commit_id}")
        assert detail.status_code == 200
        links = {(item["object_type"], item["object_id"]) for item in detail.json()["links"]}
        assert ("requirement", requirement.id) in links
        assert ("task", task.id) in links
        assert ("bug", bug.id) in links
        assert "diff --git" in detail.json()["diff_text"]

        reviews = client.get("/api/v1/devops/review-tasks")
        assert reviews.status_code == 200
        assert any(item["commit_id"] == commit_id and item["status"] == "pending" for item in reviews.json())
    finally:
        db.close()


def test_jenkins_webhook_records_build_and_links_commit(client):
    commit_response = client.post(
        "/api/v1/devops/commits",
        json={
            "commit_sha": "def1234567890abc",
            "message": "prepare jenkins integration",
        },
    )
    assert commit_response.status_code == 201
    commit_id = commit_response.json()["id"]

    job_response = client.post(
        "/api/v1/devops/jenkins-jobs",
        json={
            "job_name": "soar-sdlc-backend",
            "jenkins_url": "http://jenkins.example/job/soar-sdlc-backend",
        },
    )
    assert job_response.status_code == 201
    job_id = job_response.json()["id"]

    build_response = client.post(
        "/api/v1/devops/jenkins/webhook",
        json={
            "job_name": "soar-sdlc-backend",
            "build_number": "42",
            "build_url": "http://jenkins.example/job/soar-sdlc-backend/42",
            "branch_name": "main",
            "commit_sha": "def1234567890abc",
            "status": "success",
            "duration_seconds": 35,
        },
    )
    assert build_response.status_code == 200
    build = build_response.json()
    assert build["job_id"] == job_id
    assert build["commit_id"] == commit_id
    assert build["status"] == "success"

    list_response = client.get(f"/api/v1/devops/jenkins-builds?job_id={job_id}")
    assert list_response.status_code == 200
    assert [item["build_number"] for item in list_response.json()] == ["42"]


def test_commit_review_task_assigns_development_lead(client):
    db = SessionLocal()
    try:
        role = db.query(Role).filter(Role.role_key == "development_lead").first()
        if not role:
            role = Role(role_key="development_lead", role_name="Development Lead", enabled=True, is_system=True)
            db.add(role)
            db.flush()
        user = User(
            username="review_lead",
            full_name="Review Lead",
            password_hash=get_password_hash("User123456"),
            is_active=True,
        )
        db.add(user)
        db.flush()
        db.add(UserRole(user_id=user.id, role_id=role.id))
        db.commit()

        response = client.post(
            "/api/v1/devops/commits",
            json={"commit_sha": "lead1234567890abc", "message": "TASK-999 no object still review"},
        )

        assert response.status_code == 201
        reviews = client.get("/api/v1/devops/review-tasks")
        task = next(item for item in reviews.json() if item["commit_id"] == response.json()["id"])
        lead_ids = {
            row.user_id
            for row in db.query(UserRole.user_id)
            .join(Role, Role.id == UserRole.role_id)
            .filter(Role.role_key == "development_lead")
            .all()
        }
        assert task["owner_id"] in lead_ids
    finally:
        db.close()


def test_development_lead_commit_is_assigned_to_another_reviewer(client):
    db = SessionLocal()
    try:
        role = db.query(Role).filter(Role.role_key == "development_lead").first()
        if not role:
            role = Role(role_key="development_lead", role_name="Development Lead", enabled=True, is_system=True)
            db.add(role)
            db.flush()
        author = User(
            username="lead_author",
            full_name="Lead Author",
            email="lead.author@example.com",
            password_hash=get_password_hash("User123456"),
            is_active=True,
        )
        reviewer = User(
            username="lead_reviewer",
            full_name="Lead Reviewer",
            email="lead.reviewer@example.com",
            password_hash=get_password_hash("User123456"),
            is_active=True,
        )
        db.add_all([author, reviewer])
        db.flush()
        db.add_all([UserRole(user_id=author.id, role_id=role.id), UserRole(user_id=reviewer.id, role_id=role.id)])
        project = Project(name="Lead Self Review Project", status="active")
        db.add(project)
        db.flush()
        task = Task(
            project_id=project.id,
            title="Lead authored task",
            owner_id=author.id,
            **initial_workflow_values(db, "task", project.id),
        )
        db.add(task)
        db.flush()
        db.add(ProjectMember(project_id=project.id, user_id=reviewer.id, project_role="tech_lead", is_default_assignee=True))
        db.commit()

        response = client.post(
            "/api/v1/devops/commits",
            json={
                "commit_sha": "selfreview1234567890abc",
                "message": f"TASK-{task.id} development lead change",
                "author_name": "Lead Author",
                "author_email": "lead.author@example.com",
            },
        )

        assert response.status_code == 201
        reviews = client.get("/api/v1/devops/review-tasks")
        task = next(item for item in reviews.json() if item["commit_id"] == response.json()["id"])
        assert task["owner_id"] == reviewer.id
        assert task["owner_id"] != author.id
    finally:
        db.close()
