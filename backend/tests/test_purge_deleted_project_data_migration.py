import importlib.util
from pathlib import Path

import sqlalchemy as sa


MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "20260810_001_purge_deleted_project_data.py"
)

DELETED_PROJECT_ID = 1
ACTIVE_PROJECT_ID = 2

P1_POOL_ITERATION_ID = 101
P1_ITERATION_ID = 102
SHARED_ITERATION_ID = 103
P1_WORK_ITEM_ONLY_ITERATION_ID = 104
P2_POOL_ITERATION_ID = 201
UNRELATED_ITERATION_ID = 999

P1_REQUIREMENT_ID = 1001
P1_TASK_ID = 1101
P1_BUG_ID = 1201
P1_TEST_CASE_ID = 1301
P1_TEST_RUN_ID = 1401

P2_REQUIREMENT_ID = 2001
P2_SOURCE_REQUIREMENT_ID = 2002
P2_TASK_ID = 2101
P2_BUG_ID = 2201
P2_TEST_CASE_ID = 2301
P2_TEST_RUN_ID = 2401

P1_COMPONENT_ID = 3001
P2_COMPONENT_ID = 3002
P1_SOURCE_COMPONENT_ID = 3003

PROJECT_ITERATION_OBJECT_TABLES = (
    "audit_log",
    "status_operation_log",
    "work_item_comments",
    "object_watch",
    "object_tags",
    "attachments",
    "custom_field_value",
    "external_integration_mapping",
    "devops_commit_links",
)
SIMPLE_OBJECT_TABLES = ("workflow_migration_logs", *PROJECT_ITERATION_OBJECT_TABLES)


def _migration_module():
    assert MIGRATION_PATH.exists(), "deleted-project purge migration must exist"
    spec = importlib.util.spec_from_file_location("purge_deleted_project_data", MIGRATION_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _object_table(metadata: sa.MetaData, name: str) -> sa.Table:
    return sa.Table(
        name,
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("object_type", sa.String(32), nullable=False),
        sa.Column("object_id", sa.Integer, nullable=False),
    )


def _create_schema(bind) -> dict[str, sa.Table]:
    metadata = sa.MetaData()

    sa.Table(
        "iterations",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("is_requirement_pool", sa.Boolean, nullable=False, default=False),
        sa.Column("deleted", sa.Boolean, nullable=False, default=False),
    )
    sa.Table(
        "projects",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("deleted", sa.Boolean, nullable=False),
        sa.Column(
            "requirement_pool_iteration_id",
            sa.Integer,
            sa.ForeignKey("iterations.id", ondelete="RESTRICT"),
        ),
    )
    sa.Table(
        "iteration_projects",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "iteration_id",
            sa.Integer,
            sa.ForeignKey("iterations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("project_id", sa.Integer, nullable=False),
    )
    sa.Table(
        "requirements",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("project_id", sa.Integer, nullable=False),
        sa.Column("source_project_id", sa.Integer),
        sa.Column(
            "iteration_id",
            sa.Integer,
            sa.ForeignKey("iterations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
    )
    sa.Table(
        "tasks",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("project_id", sa.Integer, nullable=False),
        sa.Column("source_project_id", sa.Integer),
        sa.Column("iteration_id", sa.Integer),
        sa.Column("requirement_id", sa.Integer),
    )
    sa.Table(
        "bugs",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("project_id", sa.Integer, nullable=False),
        sa.Column("iteration_id", sa.Integer),
        sa.Column("requirement_id", sa.Integer),
        sa.Column("task_id", sa.Integer),
        sa.Column("test_case_id", sa.Integer),
        sa.Column("test_run_id", sa.Integer),
    )
    sa.Table(
        "test_cases",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("project_id", sa.Integer, nullable=False),
        sa.Column("requirement_id", sa.Integer),
        sa.Column("iteration_id", sa.Integer),
    )
    sa.Table(
        "test_runs",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("project_id", sa.Integer, nullable=False),
        sa.Column("iteration_id", sa.Integer),
    )
    sa.Table(
        "test_case_execution_log",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("test_case_id", sa.Integer, nullable=False),
    )
    sa.Table(
        "test_run_cases",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("test_run_id", sa.Integer, nullable=False),
        sa.Column("test_case_id", sa.Integer, nullable=False),
    )
    for name in ("project_members", "exception_rules"):
        sa.Table(
            name,
            metadata,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("project_id", sa.Integer, nullable=False),
        )

    sa.Table(
        "business_components",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("project_id", sa.Integer, nullable=False),
        sa.Column("source_project_id", sa.Integer),
    )
    for name in ("business_component_members", "business_component_transition_routes"):
        sa.Table(
            name,
            metadata,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column(
                "component_id",
                sa.Integer,
                sa.ForeignKey("business_components.id", ondelete="CASCADE"),
                nullable=False,
            ),
        )
    sa.Table(
        "work_item_components",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("object_type", sa.String(32), nullable=False),
        sa.Column("object_id", sa.Integer, nullable=False),
        sa.Column(
            "component_id",
            sa.Integer,
            sa.ForeignKey("business_components.id", ondelete="RESTRICT"),
            nullable=False,
        ),
    )

    for name in SIMPLE_OBJECT_TABLES:
        _object_table(metadata, name)
    sa.Table(
        "work_item_iteration_history",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("object_type", sa.String(32), nullable=False),
        sa.Column("object_id", sa.Integer, nullable=False),
        sa.Column("iteration_id", sa.Integer, nullable=False),
    )
    sa.Table(
        "object_relation",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("source_id", sa.Integer, nullable=False),
        sa.Column("target_type", sa.String(32), nullable=False),
        sa.Column("target_id", sa.Integer, nullable=False),
    )
    sa.Table(
        "notifications",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("object_type", sa.String(32), nullable=False),
        sa.Column("object_id", sa.Integer, nullable=False),
        sa.Column("source_type", sa.String(32)),
        sa.Column("source_id", sa.Integer),
    )
    sa.Table(
        "notification_delivery_log",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("notification_id", sa.Integer, nullable=False),
    )
    sa.Table(
        "notification_channel_config",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("scope_type", sa.String(32), nullable=False),
        sa.Column("scope_id", sa.Integer),
    )
    sa.Table(
        "iteration_completion_snapshots",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "iteration_id",
            sa.Integer,
            sa.ForeignKey("iterations.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )

    bind.exec_driver_sql("PRAGMA foreign_keys=ON")
    metadata.create_all(bind)
    assert bind.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
    return dict(metadata.tables)


def _seed_control_graph(bind, tables: dict[str, sa.Table]) -> None:
    bind.execute(
        tables["iterations"].insert(),
        [
            {"id": P1_POOL_ITERATION_ID, "is_requirement_pool": True, "deleted": False},
            {"id": P1_ITERATION_ID, "is_requirement_pool": False, "deleted": False},
            {"id": SHARED_ITERATION_ID, "is_requirement_pool": False, "deleted": False},
            {
                "id": P1_WORK_ITEM_ONLY_ITERATION_ID,
                "is_requirement_pool": False,
                "deleted": False,
            },
            {"id": P2_POOL_ITERATION_ID, "is_requirement_pool": True, "deleted": False},
            {"id": UNRELATED_ITERATION_ID, "is_requirement_pool": False, "deleted": False},
        ],
    )
    bind.execute(
        tables["projects"].insert(),
        [
            {
                "id": DELETED_PROJECT_ID,
                "deleted": True,
                "requirement_pool_iteration_id": P1_POOL_ITERATION_ID,
            },
            {
                "id": ACTIVE_PROJECT_ID,
                "deleted": False,
                "requirement_pool_iteration_id": P2_POOL_ITERATION_ID,
            },
        ],
    )
    bind.execute(
        tables["iteration_projects"].insert(),
        [
            {"id": 2, "iteration_id": P1_ITERATION_ID, "project_id": DELETED_PROJECT_ID},
            {"id": 3, "iteration_id": SHARED_ITERATION_ID, "project_id": DELETED_PROJECT_ID},
            {"id": 4, "iteration_id": SHARED_ITERATION_ID, "project_id": ACTIVE_PROJECT_ID},
            {"id": 5, "iteration_id": P2_POOL_ITERATION_ID, "project_id": ACTIVE_PROJECT_ID},
        ],
    )
    bind.execute(
        tables["requirements"].insert(),
        [
            {
                "id": P1_REQUIREMENT_ID,
                "project_id": DELETED_PROJECT_ID,
                "source_project_id": None,
                "iteration_id": SHARED_ITERATION_ID,
            },
            {
                "id": P2_REQUIREMENT_ID,
                "project_id": ACTIVE_PROJECT_ID,
                "source_project_id": None,
                "iteration_id": P2_POOL_ITERATION_ID,
            },
            {
                "id": P2_SOURCE_REQUIREMENT_ID,
                "project_id": ACTIVE_PROJECT_ID,
                "source_project_id": DELETED_PROJECT_ID,
                "iteration_id": SHARED_ITERATION_ID,
            },
        ],
    )
    bind.execute(
        tables["tasks"].insert(),
        [
            {
                "id": P1_TASK_ID,
                "project_id": DELETED_PROJECT_ID,
                "source_project_id": None,
                "iteration_id": P1_WORK_ITEM_ONLY_ITERATION_ID,
                "requirement_id": P1_REQUIREMENT_ID,
            },
            {
                "id": P2_TASK_ID,
                "project_id": ACTIVE_PROJECT_ID,
                "source_project_id": None,
                "iteration_id": SHARED_ITERATION_ID,
                "requirement_id": P1_REQUIREMENT_ID,
            },
        ],
    )
    bind.execute(
        tables["test_cases"].insert(),
        [
            {
                "id": P1_TEST_CASE_ID,
                "project_id": DELETED_PROJECT_ID,
                "requirement_id": P1_REQUIREMENT_ID,
                "iteration_id": SHARED_ITERATION_ID,
            },
            {
                "id": P2_TEST_CASE_ID,
                "project_id": ACTIVE_PROJECT_ID,
                "requirement_id": P1_REQUIREMENT_ID,
                "iteration_id": SHARED_ITERATION_ID,
            },
        ],
    )
    bind.execute(
        tables["test_runs"].insert(),
        [
            {"id": P1_TEST_RUN_ID, "project_id": DELETED_PROJECT_ID, "iteration_id": SHARED_ITERATION_ID},
            {"id": P2_TEST_RUN_ID, "project_id": ACTIVE_PROJECT_ID, "iteration_id": SHARED_ITERATION_ID},
        ],
    )
    bind.execute(
        tables["bugs"].insert(),
        [
            {
                "id": P1_BUG_ID,
                "project_id": DELETED_PROJECT_ID,
                "iteration_id": SHARED_ITERATION_ID,
                "requirement_id": P1_REQUIREMENT_ID,
                "task_id": P1_TASK_ID,
                "test_case_id": P1_TEST_CASE_ID,
                "test_run_id": P1_TEST_RUN_ID,
            },
            {
                "id": P2_BUG_ID,
                "project_id": ACTIVE_PROJECT_ID,
                "iteration_id": SHARED_ITERATION_ID,
                "requirement_id": P1_REQUIREMENT_ID,
                "task_id": P1_TASK_ID,
                "test_case_id": P1_TEST_CASE_ID,
                "test_run_id": P1_TEST_RUN_ID,
            },
        ],
    )

    bind.execute(
        tables["test_case_execution_log"].insert(),
        [
            {"id": 1, "test_case_id": P1_TEST_CASE_ID},
            {"id": 2, "test_case_id": P2_TEST_CASE_ID},
        ],
    )
    bind.execute(
        tables["test_run_cases"].insert(),
        [
            {"id": 1, "test_run_id": P1_TEST_RUN_ID, "test_case_id": P1_TEST_CASE_ID},
            {"id": 2, "test_run_id": P2_TEST_RUN_ID, "test_case_id": P2_TEST_CASE_ID},
        ],
    )
    for name in ("project_members", "exception_rules"):
        bind.execute(
            tables[name].insert(),
            [
                {"id": 1, "project_id": DELETED_PROJECT_ID},
                {"id": 2, "project_id": ACTIVE_PROJECT_ID},
            ],
        )

    bind.execute(
        tables["business_components"].insert(),
        [
            {"id": P1_COMPONENT_ID, "project_id": DELETED_PROJECT_ID, "source_project_id": None},
            {"id": P2_COMPONENT_ID, "project_id": ACTIVE_PROJECT_ID, "source_project_id": None},
            {
                "id": P1_SOURCE_COMPONENT_ID,
                "project_id": ACTIVE_PROJECT_ID,
                "source_project_id": DELETED_PROJECT_ID,
            },
        ],
    )
    for name in ("business_component_members", "business_component_transition_routes"):
        bind.execute(
            tables[name].insert(),
            [
                {"id": 1, "component_id": P1_COMPONENT_ID},
                {"id": 2, "component_id": P2_COMPONENT_ID},
                {"id": 3, "component_id": P1_SOURCE_COMPONENT_ID},
            ],
        )
    bind.execute(
        tables["work_item_components"].insert(),
        [
            {"id": 1, "object_type": "task", "object_id": P1_TASK_ID, "component_id": P1_COMPONENT_ID},
            {"id": 2, "object_type": "task", "object_id": P2_TASK_ID, "component_id": P2_COMPONENT_ID},
            {
                "id": 3,
                "object_type": "task",
                "object_id": P2_TASK_ID,
                "component_id": P1_SOURCE_COMPONENT_ID,
            },
        ],
    )

    for name in SIMPLE_OBJECT_TABLES:
        rows = [
            {"id": 1, "object_type": "task", "object_id": P1_TASK_ID},
            {"id": 2, "object_type": "task", "object_id": P2_TASK_ID},
        ]
        if name in PROJECT_ITERATION_OBJECT_TABLES:
            rows.extend(
                [
                    {"id": 3, "object_type": "project", "object_id": DELETED_PROJECT_ID},
                    {"id": 4, "object_type": "project", "object_id": ACTIVE_PROJECT_ID},
                    {
                        "id": 5,
                        "object_type": "iteration",
                        "object_id": P1_WORK_ITEM_ONLY_ITERATION_ID,
                    },
                    {"id": 6, "object_type": "iteration", "object_id": SHARED_ITERATION_ID},
                ]
            )
        bind.execute(
            tables[name].insert(),
            rows,
        )
    bind.execute(
        tables["work_item_iteration_history"].insert(),
        [
            {
                "id": 1,
                "object_type": "task",
                "object_id": P1_TASK_ID,
                "iteration_id": P1_WORK_ITEM_ONLY_ITERATION_ID,
            },
            {"id": 2, "object_type": "task", "object_id": P2_TASK_ID, "iteration_id": SHARED_ITERATION_ID},
        ],
    )
    bind.execute(
        tables["object_relation"].insert(),
        [
            {
                "id": 1,
                "source_type": "task",
                "source_id": P1_TASK_ID,
                "target_type": "requirement",
                "target_id": P1_REQUIREMENT_ID,
            },
            {
                "id": 2,
                "source_type": "task",
                "source_id": P2_TASK_ID,
                "target_type": "requirement",
                "target_id": P2_REQUIREMENT_ID,
            },
            {
                "id": 3,
                "source_type": "task",
                "source_id": P2_TASK_ID,
                "target_type": "requirement",
                "target_id": P1_REQUIREMENT_ID,
            },
            {
                "id": 4,
                "source_type": "task",
                "source_id": P1_TASK_ID,
                "target_type": "requirement",
                "target_id": P2_REQUIREMENT_ID,
            },
        ],
    )

    bind.execute(
        tables["notifications"].insert(),
        [
            {
                "id": 1,
                "object_type": "task",
                "object_id": P1_TASK_ID,
                "source_type": "work_item_comment",
                "source_id": 1,
            },
            {
                "id": 2,
                "object_type": "task",
                "object_id": P2_TASK_ID,
                "source_type": "work_item_comment",
                "source_id": 2,
            },
            {
                "id": 3,
                "object_type": "task",
                "object_id": P2_TASK_ID,
                "source_type": "work_item_comment",
                "source_id": 1,
            },
            {
                "id": 4,
                "object_type": "project",
                "object_id": DELETED_PROJECT_ID,
                "source_type": None,
                "source_id": None,
            },
            {
                "id": 5,
                "object_type": "project",
                "object_id": ACTIVE_PROJECT_ID,
                "source_type": None,
                "source_id": None,
            },
            {
                "id": 6,
                "object_type": "iteration",
                "object_id": P1_WORK_ITEM_ONLY_ITERATION_ID,
                "source_type": None,
                "source_id": None,
            },
            {
                "id": 7,
                "object_type": "iteration",
                "object_id": SHARED_ITERATION_ID,
                "source_type": None,
                "source_id": None,
            },
        ],
    )
    bind.execute(
        tables["notification_delivery_log"].insert(),
        [
            {"id": 1, "notification_id": 1},
            {"id": 2, "notification_id": 2},
            {"id": 3, "notification_id": 3},
            {"id": 4, "notification_id": 4},
            {"id": 5, "notification_id": 5},
            {"id": 6, "notification_id": 6},
            {"id": 7, "notification_id": 7},
        ],
    )
    bind.execute(
        tables["notification_channel_config"].insert(),
        [
            {"id": 1, "scope_type": "project", "scope_id": DELETED_PROJECT_ID},
            {"id": 2, "scope_type": "project", "scope_id": ACTIVE_PROJECT_ID},
            {"id": 3, "scope_type": "global", "scope_id": None},
        ],
    )
    bind.execute(
        tables["iteration_completion_snapshots"].insert(),
        [
            {"id": index, "iteration_id": iteration_id}
            for index, iteration_id in enumerate(
                (
                    P1_POOL_ITERATION_ID,
                    P1_ITERATION_ID,
                    SHARED_ITERATION_ID,
                    P1_WORK_ITEM_ONLY_ITERATION_ID,
                    P2_POOL_ITERATION_ID,
                    UNRELATED_ITERATION_ID,
                ),
                start=1,
            )
        ],
    )


def _ids(bind, table: sa.Table) -> list[int]:
    return bind.execute(sa.select(table.c.id).order_by(table.c.id)).scalars().all()


def _assert_purged_state(bind, tables: dict[str, sa.Table]) -> None:
    projects = bind.execute(
        sa.select(
            tables["projects"].c.id,
            tables["projects"].c.deleted,
            tables["projects"].c.requirement_pool_iteration_id,
        ).order_by(tables["projects"].c.id)
    ).all()
    assert projects == [
        (DELETED_PROJECT_ID, True, None),
        (ACTIVE_PROJECT_ID, False, P2_POOL_ITERATION_ID),
    ]

    assert _ids(bind, tables["requirements"]) == [P2_REQUIREMENT_ID, P2_SOURCE_REQUIREMENT_ID]
    assert _ids(bind, tables["tasks"]) == [P2_TASK_ID]
    assert _ids(bind, tables["bugs"]) == [P2_BUG_ID]
    assert _ids(bind, tables["test_cases"]) == [P2_TEST_CASE_ID]
    assert _ids(bind, tables["test_runs"]) == [P2_TEST_RUN_ID]

    source_requirement = bind.execute(
        sa.select(
            tables["requirements"].c.project_id,
            tables["requirements"].c.source_project_id,
        ).where(tables["requirements"].c.id == P2_SOURCE_REQUIREMENT_ID)
    ).one()
    assert source_requirement == (ACTIVE_PROJECT_ID, DELETED_PROJECT_ID)

    assert bind.execute(
        sa.select(tables["tasks"].c.requirement_id).where(tables["tasks"].c.id == P2_TASK_ID)
    ).scalar_one() is None
    assert bind.execute(
        sa.select(tables["test_cases"].c.requirement_id).where(
            tables["test_cases"].c.id == P2_TEST_CASE_ID
        )
    ).scalar_one() is None
    assert bind.execute(
        sa.select(
            tables["bugs"].c.requirement_id,
            tables["bugs"].c.task_id,
            tables["bugs"].c.test_case_id,
            tables["bugs"].c.test_run_id,
        ).where(tables["bugs"].c.id == P2_BUG_ID)
    ).one() == (None, None, None, None)

    assert _ids(bind, tables["iterations"]) == [
        SHARED_ITERATION_ID,
        P2_POOL_ITERATION_ID,
        UNRELATED_ITERATION_ID,
    ]
    scopes = bind.execute(
        sa.select(
            tables["iteration_projects"].c.iteration_id,
            tables["iteration_projects"].c.project_id,
        ).order_by(tables["iteration_projects"].c.id)
    ).all()
    assert scopes == [
        (SHARED_ITERATION_ID, ACTIVE_PROJECT_ID),
        (P2_POOL_ITERATION_ID, ACTIVE_PROJECT_ID),
    ]
    assert bind.execute(
        sa.select(tables["iteration_completion_snapshots"].c.iteration_id).order_by(
            tables["iteration_completion_snapshots"].c.iteration_id
        )
    ).scalars().all() == [SHARED_ITERATION_ID, P2_POOL_ITERATION_ID, UNRELATED_ITERATION_ID]

    assert _ids(bind, tables["test_case_execution_log"]) == [2]
    assert _ids(bind, tables["test_run_cases"]) == [2]
    assert _ids(bind, tables["project_members"]) == [2]
    assert _ids(bind, tables["exception_rules"]) == [2]

    assert _ids(bind, tables["business_components"]) == [P2_COMPONENT_ID]
    assert _ids(bind, tables["business_component_members"]) == [2]
    assert _ids(bind, tables["business_component_transition_routes"]) == [2]
    assert _ids(bind, tables["work_item_components"]) == [2]

    assert _ids(bind, tables["workflow_migration_logs"]) == [2]
    for name in PROJECT_ITERATION_OBJECT_TABLES:
        assert _ids(bind, tables[name]) == [2, 4, 6]
    assert _ids(bind, tables["work_item_iteration_history"]) == [2]
    assert _ids(bind, tables["object_relation"]) == [2]
    assert _ids(bind, tables["notifications"]) == [2, 5, 7]
    assert _ids(bind, tables["notification_delivery_log"]) == [2, 5, 7]
    assert _ids(bind, tables["notification_channel_config"]) == [2, 3]


def test_purge_removes_deleted_project_graph_and_is_idempotent():
    engine = sa.create_engine("sqlite://")
    with engine.begin() as bind:
        tables = _create_schema(bind)
        _seed_control_graph(bind, tables)
        migration = _migration_module()

        first_report = migration._purge_deleted_project_data(bind)
        assert first_report
        _assert_purged_state(bind, tables)

        second_report = migration._purge_deleted_project_data(bind)
        assert second_report
        assert all(isinstance(count, int) and count == 0 for count in second_report.values())
        _assert_purged_state(bind, tables)


def test_migration_revision_follows_project_work_pool_backfill():
    migration = _migration_module()

    assert migration.revision == "20260810_001"
    assert migration.down_revision == "20260806_002"
