from pathlib import Path
import re


REPOSITORY_ROOT = Path(__file__).parents[2]
PRD_PATH = REPOSITORY_ROOT / "docs/prd/2026-07-21-workbench-active-iteration-scope-prd.md"
DICTIONARY_PATH = (
    REPOSITORY_ROOT / "docs/database/2026-06-09-intellective-bio-sdlc-data-dictionary-mysql.md"
)
BOOTSTRAP_SQL_PATH = REPOSITORY_ROOT / "docs/database/init_mysql.sql"


def _table_definition(sql: str, table_name: str) -> str:
    match = re.search(
        rf"CREATE TABLE IF NOT EXISTS {table_name} \((.*?)\) ENGINE=InnoDB",
        sql,
        flags=re.DOTALL,
    )
    assert match, f"{table_name} bootstrap definition is missing"
    return match.group(1)


def test_prd_distinguishes_pool_requirements_from_uniterated_tasks_and_bugs():
    prd = PRD_PATH.read_text(encoding="utf-8")

    assert "需求必须始终关联项目需求池或交付迭代" in prd
    assert "需求池中的需求，以及未关联迭代的任务和 Bug 不进入工作台任何正常入口" in prd
    assert "需求池本身不属于异常" in prd
    assert "未关联迭代的任务和 Bug" in prd
    assert "未关联迭代的正常需求、任务和 Bug" not in prd


def test_requirement_pool_schema_contract_is_documented_and_bootstrapped():
    dictionary = DICTIONARY_PATH.read_text(encoding="utf-8")
    sql = BOOTSTRAP_SQL_PATH.read_text(encoding="utf-8")

    assert (
        "| requirement_pool_iteration_id | BIGINT UNSIGNED | NULL, UNIQUE, "
        "FK -> iterations.id (RESTRICT) | 项目唯一需求池迭代 ID |"
    ) in dictionary
    assert (
        "| is_requirement_pool | TINYINT(1) | NOT NULL DEFAULT 0 | "
        "是否为项目系统需求池：1 是，0 否 |"
    ) in dictionary
    assert (
        "| iteration_id | BIGINT UNSIGNED | NOT NULL, FK -> iterations.id (RESTRICT) "
        "| 所属迭代 ID；必须为项目需求池或交付迭代 |"
    ) in dictionary

    projects = _table_definition(sql, "projects")
    iterations = _table_definition(sql, "iterations")
    requirements = _table_definition(sql, "requirements")

    assert "requirement_pool_iteration_id BIGINT UNSIGNED NULL" in projects
    assert "UNIQUE KEY uk_projects_requirement_pool_iteration (requirement_pool_iteration_id)" in projects
    assert "is_requirement_pool TINYINT(1) NOT NULL DEFAULT 0" in iterations
    assert "KEY idx_iterations_requirement_pool (is_requirement_pool)" in iterations
    assert "iteration_id BIGINT UNSIGNED NOT NULL" in requirements
    assert (
        "CONSTRAINT fk_requirements_iteration FOREIGN KEY (iteration_id) "
        "REFERENCES iterations (id) ON DELETE RESTRICT"
    ) in requirements
    assert re.search(
        r"CONSTRAINT fk_projects_requirement_pool_iteration\s+"
        r"FOREIGN KEY \(requirement_pool_iteration_id\) REFERENCES iterations \(id\)\s+"
        r"ON DELETE RESTRICT",
        sql,
    )
