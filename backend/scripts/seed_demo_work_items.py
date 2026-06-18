from __future__ import annotations

import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import delete  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.models.bug import Bug  # noqa: E402
from app.models.iteration import Iteration, IterationProject  # noqa: E402
from app.models.program import Program  # noqa: E402
from app.models.project import Project  # noqa: E402
from app.models.requirement import Requirement  # noqa: E402
from app.models.task import Task  # noqa: E402
from app.models.test_case import TestCase  # noqa: E402
from app.models.test_case_execution import TestCaseExecutionLog  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.user_service import seed_default_users  # noqa: E402


BATCH_PREFIX = "演示验证-"
ASCII_MARKERS = [
    "QA档案",
    "BD看板",
    "BD线索",
    "InnovateX运维响应中心",
    "灵犀平台年度建设",
    "实验室数字化能力",
    "档案检索MVP",
    "线索看板联调",
]


def main() -> None:
    db = SessionLocal()
    try:
        seed_default_users(db)
        users = {user.username: user for user in db.query(User).filter(User.deleted == 0).all()}
        owner_po = users.get("po_li") or users.get("admin")
        owner_dev = users.get("rd_lin") or users.get("admin")
        owner_qa = users.get("qa_wang") or users.get("admin")
        owner_pm = users.get("pm_chen") or users.get("admin")

        cleanup_existing_batch(db)

        program_lingxi = Program(
            name=f"{BATCH_PREFIX}灵犀平台年度建设",
            owner_id=owner_pm.id,
            planned_start_date=date(2026, 6, 1),
            planned_end_date=date(2026, 12, 31),
            status="active",
            description="用于验证项目集、项目、迭代和工作台联动的演示项目集。",
        )
        program_lab = Program(
            name=f"{BATCH_PREFIX}实验室数字化能力",
            owner_id=owner_pm.id,
            planned_start_date=date(2026, 7, 1),
            is_long_term=True,
            status="planning",
            description="用于验证长期项目集和跨项目筛选。",
        )
        db.add_all([program_lingxi, program_lab])
        db.flush()

        project_archive = Project(
            program_id=program_lingxi.id,
            name=f"{BATCH_PREFIX}QA档案智能检索",
            owner_id=owner_po.id,
            start_date=date(2026, 6, 10),
            end_date=date(2026, 9, 30),
            actual_start_date=date(2026, 6, 12),
            status="active",
            lifecycle_phase="development",
            description="验证 QA 档案归档、检索和权限相关需求。",
        )
        project_bd = Project(
            program_id=program_lingxi.id,
            name=f"{BATCH_PREFIX}BD线索转化看板",
            owner_id=owner_dev.id,
            start_date=date(2026, 6, 20),
            end_date=date(2026, 10, 15),
            status="active",
            lifecycle_phase="development",
            description="验证 BD 线索看板和商机流转场景。",
        )
        project_ops = Project(
            program_id=program_lingxi.id,
            name=f"{BATCH_PREFIX}InnovateX运维响应中心",
            owner_id=owner_qa.id,
            start_date=date(2026, 7, 1),
            is_long_term=True,
            status="active",
            lifecycle_phase="maintenance",
            description="验证长期运维项目和缺陷响应场景。",
        )
        db.add_all([project_archive, project_bd, project_ops])
        db.flush()

        iteration_archive = Iteration(
            name=f"{BATCH_PREFIX}档案检索MVP迭代",
            owner_id=owner_pm.id,
            start_date=date(2026, 6, 15),
            end_date=date(2026, 7, 15),
            actual_start_date=date(2026, 6, 15),
            status="active",
            lifecycle_phase="development",
            goal="完成档案检索、权限校验和审计追踪主链路。",
        )
        iteration_bd = Iteration(
            name=f"{BATCH_PREFIX}线索看板联调迭代",
            owner_id=owner_pm.id,
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 31),
            status="planning",
            lifecycle_phase="development",
            goal="验证 BD 看板字段、转化状态和提醒。",
        )
        db.add_all([iteration_archive, iteration_bd])
        db.flush()
        db.add_all([
            IterationProject(iteration_id=iteration_archive.id, project_id=project_archive.id),
            IterationProject(iteration_id=iteration_archive.id, project_id=project_ops.id),
            IterationProject(iteration_id=iteration_bd.id, project_id=project_bd.id),
        ])
        db.flush()

        req_archive_search = Requirement(
            project_id=project_archive.id,
            iteration_id=iteration_archive.id,
            title=f"{BATCH_PREFIX}QA档案检索-按批号快速定位报告",
            requirement_type="功能",
            priority="1",
            owner_id=owner_po.id,
            proposer_id=owner_pm.id,
            status="active",
            review_status="approved",
            lifecycle_phase="development",
            description="质控人员输入样本批号后，应快速定位原始记录、复核报告和签批记录。",
            acceptance_criteria="输入有效批号时 3 秒内返回档案列表；无权限用户不可查看敏感报告。",
        )
        req_archive_acl = Requirement(
            project_id=project_archive.id,
            iteration_id=iteration_archive.id,
            title=f"{BATCH_PREFIX}QA档案检索-敏感报告下载留痕",
            requirement_type="安全",
            priority="2",
            owner_id=owner_qa.id,
            proposer_id=owner_po.id,
            status="draft",
            review_status="pending",
            lifecycle_phase="development",
            description="下载稳定性报告时记录下载人、时间、IP 和下载原因。",
            acceptance_criteria="下载记录可在审计日志中查询，且不可被普通用户删除。",
        )
        req_bd_funnel = Requirement(
            project_id=project_bd.id,
            iteration_id=iteration_bd.id,
            title=f"{BATCH_PREFIX}BD看板-高价值线索自动标记",
            requirement_type="功能",
            priority="3",
            owner_id=owner_dev.id,
            proposer_id=owner_pm.id,
            status="active",
            review_status="approved",
            lifecycle_phase="development",
            description="当线索来自重点客户且预计金额超过阈值时自动标记为高价值。",
            acceptance_criteria="高价值标记可在列表和详情页展示，并触发负责人提醒。",
        )
        db.add_all([req_archive_search, req_archive_acl, req_bd_funnel])
        db.flush()

        task_archive_index = Task(
            project_id=project_archive.id,
            iteration_id=iteration_archive.id,
            requirement_id=req_archive_search.id,
            title=f"{BATCH_PREFIX}任务-QA档案检索-批号索引接口",
            task_type="后端开发",
            priority="1",
            owner_id=owner_dev.id,
            estimated_hours=Decimal("16.0"),
            due_date=date(2026, 6, 28),
            status="doing",
            lifecycle_phase="development",
            description="实现批号、项目编号和报告类型的组合索引查询接口。",
        )
        task_archive_audit = Task(
            project_id=project_archive.id,
            iteration_id=iteration_archive.id,
            requirement_id=req_archive_acl.id,
            title=f"{BATCH_PREFIX}任务-QA档案留痕-下载审计记录",
            task_type="后端开发",
            priority="2",
            owner_id=owner_dev.id,
            estimated_hours=Decimal("10.0"),
            due_date=date(2026, 7, 5),
            status="todo",
            lifecycle_phase="development",
            description="在报告下载接口写入审计日志并暴露查询条件。",
        )
        task_bd_badge = Task(
            project_id=project_bd.id,
            iteration_id=iteration_bd.id,
            requirement_id=req_bd_funnel.id,
            title=f"{BATCH_PREFIX}任务-BD高价值线索-红色角标展示",
            task_type="前端开发",
            priority="3",
            owner_id=owner_dev.id,
            estimated_hours=Decimal("8.0"),
            due_date=date(2026, 7, 12),
            status="todo",
            lifecycle_phase="development",
            description="在 BD 看板列表中展示高价值线索角标和筛选入口。",
        )
        db.add_all([task_archive_index, task_archive_audit, task_bd_badge])
        db.flush()

        case_archive_hit = TestCase(
            project_id=project_archive.id,
            requirement_id=req_archive_search.id,
            iteration_id=iteration_archive.id,
            title=f"{BATCH_PREFIX}用例-QA档案检索-批号命中报告列表",
            case_type="功能测试",
            test_scope="项目用例",
            default_tester_id=owner_qa.id,
            precondition="已存在批号 BATCH-2026-A17 的稳定性报告和复核报告。",
            steps_json=[
                {"step": "登录质控账号并进入 QA 档案检索", "expected": "进入检索页面"},
                {"step": "输入批号 BATCH-2026-A17 并点击查询", "expected": "返回稳定性报告和复核报告"},
                {"step": "打开任一报告详情", "expected": "展示报告基础信息和权限标识"},
            ],
            expected_result="报告列表完整，详情页可正常打开。",
            last_execute_time=datetime(2026, 6, 17, 15, 30),
            last_execute_result="failed",
            lifecycle_phase="development",
        )
        case_archive_acl = TestCase(
            project_id=project_archive.id,
            requirement_id=req_archive_acl.id,
            iteration_id=iteration_archive.id,
            title=f"{BATCH_PREFIX}用例-QA档案留痕-下载生成审计记录",
            case_type="安全测试",
            test_scope="项目用例",
            default_tester_id=owner_qa.id,
            precondition="测试账号具备敏感报告下载权限。",
            steps_json=[
                {"step": "打开敏感报告详情并填写下载原因", "expected": "允许提交下载申请"},
                {"step": "点击下载报告", "expected": "文件开始下载"},
                {"step": "进入审计日志查询该报告编号", "expected": "能看到下载人和下载原因"},
            ],
            expected_result="下载行为完整留痕。",
            last_execute_time=datetime(2026, 6, 17, 16, 10),
            last_execute_result="blocked",
            lifecycle_phase="development",
        )
        case_bd_marker = TestCase(
            project_id=project_bd.id,
            requirement_id=req_bd_funnel.id,
            iteration_id=iteration_bd.id,
            title=f"{BATCH_PREFIX}用例-BD看板-高价值线索自动角标",
            case_type="功能测试",
            test_scope="项目用例",
            default_tester_id=owner_qa.id,
            precondition="已导入重点客户线索 ACME-GLP-2026，预计金额 180 万。",
            steps_json=[
                {"step": "打开 BD 线索看板", "expected": "线索列表加载完成"},
                {"step": "查看 ACME-GLP-2026 线索", "expected": "展示高价值角标"},
            ],
            expected_result="高价值线索展示角标并可筛选。",
            lifecycle_phase="development",
        )
        db.add_all([case_archive_hit, case_archive_acl, case_bd_marker])
        db.flush()

        db.add_all([
            TestCaseExecutionLog(
                test_case_id=case_archive_hit.id,
                executor_id=owner_qa.id,
                execute_time=datetime(2026, 6, 17, 15, 30),
                result="failed",
                steps_result_json=[
                    {"step": "登录质控账号并进入 QA 档案检索", "result": "passed", "actual": "页面打开正常"},
                    {"step": "输入批号 BATCH-2026-A17 并点击查询", "result": "failed", "actual": "只返回稳定性报告，缺少复核报告"},
                    {"step": "打开任一报告详情", "result": "blocked", "actual": "列表缺失导致未继续"},
                ],
            ),
            TestCaseExecutionLog(
                test_case_id=case_archive_acl.id,
                executor_id=owner_qa.id,
                execute_time=datetime(2026, 6, 17, 16, 10),
                result="blocked",
                steps_result_json=[
                    {"step": "打开敏感报告详情并填写下载原因", "result": "passed", "actual": "下载原因可填写"},
                    {"step": "点击下载报告", "result": "blocked", "actual": "下载按钮灰显，无法继续"},
                ],
            ),
        ])

        bug_missing_review = Bug(
            project_id=project_archive.id,
            iteration_id=iteration_archive.id,
            requirement_id=req_archive_search.id,
            task_id=task_archive_index.id,
            test_case_id=case_archive_hit.id,
            title=f"{BATCH_PREFIX}Bug-QA档案检索-批号查询遗漏复核报告",
            bug_type="代码错误",
            severity="2",
            priority="2",
            owner_id=owner_dev.id,
            reporter_id=owner_qa.id,
            reproduce_steps="1. 登录质控账号\n2. 输入批号 BATCH-2026-A17 查询\n3. 观察报告列表\n实际只返回稳定性报告，缺少复核报告。",
            expected_result="稳定性报告和复核报告都应出现在结果列表。",
            actual_result="复核报告未返回，导致质控人员无法完成复核链路检查。",
            status="fixing",
            lifecycle_phase="development",
        )
        bug_download_blocked = Bug(
            project_id=project_archive.id,
            iteration_id=iteration_archive.id,
            requirement_id=req_archive_acl.id,
            task_id=task_archive_audit.id,
            test_case_id=case_archive_acl.id,
            title=f"{BATCH_PREFIX}Bug-QA档案留痕-敏感报告下载按钮灰显",
            bug_type="配置相关",
            severity="3",
            priority="3",
            owner_id=owner_dev.id,
            reporter_id=owner_qa.id,
            reproduce_steps="1. 使用具备下载权限的账号打开敏感报告\n2. 填写下载原因\n3. 查看下载按钮状态\n按钮仍为灰显。",
            expected_result="具备权限且填写原因后允许下载，并生成审计记录。",
            actual_result="下载按钮不可点击，阻塞审计留痕验证。",
            status="open",
            lifecycle_phase="development",
        )
        db.add_all([bug_missing_review, bug_download_blocked])
        db.commit()

        print("Demo work items seeded:")
        print(f"- programs: {program_lingxi.name}, {program_lab.name}")
        print(f"- projects: {project_archive.name}, {project_bd.name}, {project_ops.name}")
        print(f"- iterations: {iteration_archive.name}, {iteration_bd.name}")
        print("- requirements: 3, tasks: 3, test cases: 3, bugs: 2")
    finally:
        db.close()


def cleanup_existing_batch(db) -> None:
    bug_ids = _matching_ids(db, Bug, Bug.title)
    case_ids = _matching_ids(db, TestCase, TestCase.title)
    task_ids = _matching_ids(db, Task, Task.title)
    req_ids = _matching_ids(db, Requirement, Requirement.title)
    iteration_ids = _matching_ids(db, Iteration, Iteration.name)
    project_ids = _matching_ids(db, Project, Project.name)
    program_ids = _matching_ids(db, Program, Program.name)

    if case_ids:
        db.execute(delete(TestCaseExecutionLog).where(TestCaseExecutionLog.test_case_id.in_(case_ids)))
    if bug_ids:
        db.execute(delete(Bug).where(Bug.id.in_(bug_ids)))
    if case_ids:
        db.execute(delete(TestCase).where(TestCase.id.in_(case_ids)))
    if task_ids:
        db.execute(delete(Task).where(Task.id.in_(task_ids)))
    if req_ids:
        db.execute(delete(Requirement).where(Requirement.id.in_(req_ids)))
    if iteration_ids:
        db.execute(delete(IterationProject).where(IterationProject.iteration_id.in_(iteration_ids)))
        db.execute(delete(Iteration).where(Iteration.id.in_(iteration_ids)))
    if project_ids:
        db.execute(delete(Project).where(Project.id.in_(project_ids)))
    if program_ids:
        db.execute(delete(Program).where(Program.id.in_(program_ids)))
    db.commit()


def _matching_ids(db, model, field) -> list[int]:
    conditions = [field.like(f"{BATCH_PREFIX}%")]
    conditions.extend(field.like(f"%{marker}%") for marker in ASCII_MARKERS)
    rows = []
    for condition in conditions:
        rows.extend(db.query(model.id).filter(condition).all())
    return sorted({row.id for row in rows})


if __name__ == "__main__":
    main()
