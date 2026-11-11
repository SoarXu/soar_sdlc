from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
from io import BytesIO

from fastapi import HTTPException, status
from jose import jwt, JWTError
from openpyxl import Workbook, load_workbook
from openpyxl.worksheet.datavalidation import DataValidation
from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.iteration import Iteration
from app.models.requirement import Requirement
from app.models.task import Task
from app.models.user import User
from app.core.config import settings
from app.services.lifecycle_service import project_lifecycle_phase
from app.services.workflow_state_service import initial_workflow_values
from app.services.project_permission_service import ensure_work_item_create_permission, ensure_work_item_action_permission
from app.services.iteration_service import ensure_iteration_mutable, lock_iterations_for_mutation
from app.services.work_item_iteration_history_service import move_work_item_to_iteration
from app.services.iteration_assignment_service import validate_requirement_iteration


REQUIREMENT_IMPORT_COLUMNS = [
    "项目名称",
    "迭代名称",
    "需求标题",
    "类型",
    "优先级",
    "提出人",
    "需求描述",
    "验收标准",
]
REQUIRED_COLUMNS = ["项目名称", "迭代名称", "需求标题"]
REQUIREMENT_TYPE_VALUES = ["功能", "接口", "性能", "安全", "体验", "改进", "其他"]
PRIORITY_VALUES = {"1", "2", "3", "4", "5"}


@dataclass
class ParsedRequirementRow:
    row_number: int
    project_id: int
    project_name: str
    iteration_id: int
    title: str
    requirement_type: str | None
    priority: str
    owner_id: int | None
    proposer: str | None
    review_status: str
    description: str | None
    acceptance_criteria: str | None
    requirement_id: int | None = None


def build_requirement_import_template(db: Session, project_id: int | None = None) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "需求导入"
    sheet.append(REQUIREMENT_IMPORT_COLUMNS)
    project_name = _template_project_name(db, project_id)
    sheet.append([project_name, "请填写迭代名称", "示例需求", "功能", "3", "", "需求描述", "验收标准"])
    _add_list_validation(sheet, "D", REQUIREMENT_TYPE_VALUES)
    _add_list_validation(sheet, "E", sorted(PRIORITY_VALUES))
    for column in sheet.columns:
        sheet.column_dimensions[column[0].column_letter].width = 18
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def ensure_excel_filename(filename: str) -> None:
    if not filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="仅支持 .xlsx 文件")


def preview_requirement_import(
    db: Session,
    file_bytes: bytes,
    project_id: int | None = None,
    actor: User | None = None,
    duplicate_strategy: str = "update_existing",
    decisions: list | None = None,
) -> dict:
    prepared = _prepare_import(db, file_bytes, project_id, actor, duplicate_strategy, decisions)
    return _preview_result(db, prepared, file_bytes, project_id, actor, duplicate_strategy, decisions)


def commit_requirement_import(
    db: Session,
    file_bytes: bytes,
    duplicate_strategy: str,
    project_id: int | None = None,
    actor: User | None = None,
    decisions: list | None = None,
    preview_token: str | None = None,
) -> dict:
    prepared = _prepare_import(db, file_bytes, project_id, actor, duplicate_strategy, decisions)
    parsed_rows, errors, existing_requirements, records = prepared
    if errors:
        return {"created_count": 0, "updated_count": 0, "error_count": len(errors), "errors": errors}
    if any(record['proposer_status'] in UNRESOLVED_STATUSES and record['action'] != 'skip' for record in records):
        raise HTTPException(status_code=422, detail="存在提出人待确认的需求，请选择 AD 人员或跳过后重新预检")
    new_rows = [row for row, target, record in zip(parsed_rows, existing_requirements, records)
                if target is None and record['action'] != 'skip' and duplicate_strategy == 'update_existing']
    # Serialize new-title imports even when their destination iterations differ.
    for new_project_id in sorted({row.project_id for row in new_rows}):
        db.query(Project).filter(Project.id == new_project_id).with_for_update().populate_existing().one()
    iteration_ids = {
        requirement.iteration_id
        for requirement, record in zip(existing_requirements, records)
        if record['action'] != 'skip' and requirement is not None and requirement.iteration_id is not None
    }
    iteration_ids.update(row.iteration_id for row, record in zip(parsed_rows, records) if record['action'] != 'skip')
    prelocked_iterations = lock_iterations_for_mutation(db, iteration_ids) if iteration_ids else {}
    for row in new_rows:
        # Use a current read: a repeatable-read snapshot predates the lock wait.
        appeared = db.query(Requirement.id).filter(
            Requirement.project_id == row.project_id, Requirement.title == row.title,
            Requirement.deleted == 0).with_for_update().first()
        if appeared:
            raise HTTPException(status_code=409, detail='同名需求已被其他操作新增，请重新预检')
    for index, existing in sorted(enumerate(existing_requirements), key=lambda pair: pair[1].id if pair[1] else 0):
        if existing and records[index]['action'] != 'skip':
            existing_requirements[index] = _lock_requirement_for_import_update(db, existing.id, prelocked_iterations)
    if preview_token:
        current = _preview_result(db, (parsed_rows, errors, existing_requirements, records), file_bytes,
                                  project_id, actor, duplicate_strategy, decisions)
        try:
            payload = jwt.decode(preview_token, settings.secret_key, algorithms=['HS256'])
            fresh = jwt.decode(current['preview_token'], settings.secret_key, algorithms=['HS256'])
            if payload.get('purpose') != 'requirement-import' or payload.get('digest') != fresh['digest']:
                raise ValueError('changed')
        except (JWTError, ValueError):
            raise HTTPException(status_code=409, detail="文件、选择或平台需求已变化，或预检已过期，请重新预检")
    created_count = 0
    updated_count = 0
    skipped_count = 0
    for row, existing, record in zip(parsed_rows, existing_requirements, records):
        if record['action'] in {'skip', 'unchanged'}:
            skipped_count += 1
            continue
        if existing and duplicate_strategy == "update_existing":
            _apply_row_to_requirement(
                db,
                existing,
                row,
                actor_id=actor.id if actor else None,
                prelocked_iterations=prelocked_iterations,
            )
            updated_count += 1
            continue
        workflow_values = initial_workflow_values(db, "requirement", row.project_id)
        iteration_id = row.iteration_id
        ensure_iteration_mutable(prelocked_iterations[iteration_id])
        requirement = Requirement(
            project_id=row.project_id,
            source_project_id=None,
            iteration_id=iteration_id,
            title=row.title,
            requirement_type=row.requirement_type,
            priority=row.priority,
            owner_id=row.owner_id,
            proposer=row.proposer,
            **workflow_values,
            review_status=row.review_status,
            lifecycle_phase=project_lifecycle_phase(db, row.project_id),
            description=row.description,
            acceptance_criteria=row.acceptance_criteria,
            creator_id=actor.id if actor else None,
        )
        db.add(requirement)
        db.flush()
        move_work_item_to_iteration(
            db,
            requirement,
            iteration_id,
            actor_id=actor.id if actor else None,
            reason="created",
        )
        created_count += 1
    db.commit()
    return {"created_count": created_count, "updated_count": updated_count, "skipped_count": skipped_count, "error_count": 0, "errors": []}


def _parse_requirement_rows(
    db: Session,
    file_bytes: bytes,
    project_id: int | None = None,
) -> tuple[list[ParsedRequirementRow], list[dict]]:
    try:
        workbook = load_workbook(BytesIO(file_bytes), data_only=True)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Excel 文件无法解析") from exc
    sheet = workbook.active
    headers = {str(cell.value).strip(): index for index, cell in enumerate(sheet[1]) if cell.value}
    required_columns = REQUIRED_COLUMNS if project_id is None else REQUIRED_COLUMNS[1:]
    missing_columns = [column for column in required_columns if column not in headers]
    if missing_columns:
        return [], [{"row_number": 1, "messages": [f"缺少列：{column}" for column in missing_columns]}]

    scoped_project = _resolve_project_id(db, project_id) if project_id is not None else None
    rows = []
    errors = []
    for row_number, row in enumerate(sheet.iter_rows(min_row=2), start=2):
        values = {header: (str(row[index].value) if row[index].value is not None else '')
                  if header in {'需求描述', '验收标准'} else _cell_text(row[index].value)
                  for header, index in headers.items()}
        parsed, messages = _parse_requirement_row(db, row_number, values, scoped_project)
        if messages:
            errors.append({"row_number": row_number, "messages": messages})
        else:
            rows.append(parsed)
    return rows, errors


def _parse_requirement_row(
    db: Session,
    row_number: int,
    values: dict[str, str],
    scoped_project: Project | None = None,
) -> tuple[ParsedRequirementRow | None, list[str]]:
    messages = []
    requirement_id = None
    raw_id = values.get('需求ID')
    if raw_id:
        try:
            requirement_id = int(raw_id)
            if requirement_id < 1:
                raise ValueError()
        except ValueError:
            messages.append('需求ID必须是正整数')
    project_name = values.get("项目名称", "")
    title = values.get("需求标题", "")
    iteration_name = values.get("迭代名称", "")
    if scoped_project is None and not project_name:
        messages.append("项目名称不能为空")
    if not title:
        messages.append("需求标题不能为空")
    if not iteration_name:
        messages.append("迭代名称不能为空")

    project = scoped_project or (_resolve_project(db, project_name, "项目名称", messages) if project_name else None)
    if requirement_id and project:
        target = db.query(Requirement).filter(Requirement.id == requirement_id, Requirement.deleted == 0).first()
        if target is None or target.project_id != project.id:
            messages.append('需求ID不存在或不属于当前项目')
    iteration = _resolve_iteration(db, project, iteration_name, messages) if project and iteration_name else None
    proposer = values.get("提出人") or None
    requirement_type = values.get("类型") or None
    if requirement_type and requirement_type not in REQUIREMENT_TYPE_VALUES:
        messages.append(f"类型必须是 {'、'.join(REQUIREMENT_TYPE_VALUES)}")
    priority = values.get("优先级") or "3"
    if priority not in PRIORITY_VALUES:
        messages.append("优先级必须是 1、2、3、4、5")
    if messages:
        return None, messages
    return (
        ParsedRequirementRow(
            row_number=row_number,
            project_id=project.id,
            project_name=project.name,
            iteration_id=iteration.id,
            title=title,
            requirement_type=requirement_type,
            priority=priority,
            owner_id=None,
            proposer=proposer,
            review_status="not_required",
            description=values.get("需求描述") or None,
            acceptance_criteria=values.get("验收标准") or None,
            requirement_id=requirement_id,
        ),
        [],
    )


def _resolve_project(db: Session, name: str, field: str, messages: list[str]) -> Project | None:
    if not name:
        return None
    matches = db.query(Project).filter(Project.name == name, Project.deleted == 0).all()
    if not matches:
        messages.append(f"{field}不存在：{name}")
        return None
    if len(matches) > 1:
        messages.append(f"{field}不唯一：{name}")
        return None
    return matches[0]


def _resolve_iteration(
    db: Session,
    project: Project,
    name: str,
    messages: list[str],
) -> Iteration | None:
    matches = db.query(Iteration).filter(Iteration.name == name, Iteration.deleted == 0).all()
    eligible = []
    for iteration in matches:
        try:
            validate_requirement_iteration(db, project.id, iteration.id)
            eligible.append(iteration)
        except HTTPException:
            continue
    if not eligible:
        messages.append(f"迭代不存在、已关闭或不属于项目：{name}")
        return None
    if len(eligible) > 1:
        messages.append(f"迭代名称不唯一：{name}")
        return None
    return eligible[0]


def _resolve_project_id(db: Session, project_id: int) -> Project:
    project = db.query(Project).filter(Project.id == project_id, Project.deleted == 0).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
    return project


def _duplicate_rows(db: Session, rows: list[ParsedRequirementRow]) -> list[dict]:
    duplicates = []
    for row in rows:
        existing = _find_existing_requirement(db, row.project_id, row.title)
        if existing:
            duplicates.append(
                {
                    "row_number": row.row_number,
                    "project_id": row.project_id,
                    "project_name": row.project_name,
                    "title": row.title,
                    "existing_requirement_id": existing.id,
                    "existing_requirement_title": existing.title,
                }
            )
    return duplicates


def _find_existing_requirement(db: Session, project_id: int, title: str) -> Requirement | None:
    matches = (
        db.query(Requirement)
        .filter(Requirement.project_id == project_id, Requirement.title == title, Requirement.deleted == 0)
        .all()
    )
    if len(matches) > 1:
        raise HTTPException(status_code=422, detail=f'同项目存在多个同名需求：{title}，请使用导出文件中的需求ID定位')
    return matches[0] if matches else None


def _apply_row_to_requirement(
    db: Session,
    requirement: Requirement,
    row: ParsedRequirementRow,
    actor_id: int | None = None,
    prelocked_iterations: dict | None = None,
) -> None:
    requirement = _lock_requirement_for_import_update(db, requirement.id, prelocked_iterations or {})
    if requirement.iteration_id is not None:
        ensure_iteration_mutable(prelocked_iterations[requirement.iteration_id])
    ensure_iteration_mutable(prelocked_iterations[row.iteration_id])
    if requirement.iteration_id != row.iteration_id:
        move_work_item_to_iteration(
            db,
            requirement,
            row.iteration_id,
            actor_id=actor_id,
            reason="import_updated",
        )
        for task in db.query(Task).filter(
            Task.requirement_id == requirement.id,
            Task.deleted == 0,
        ):
            move_work_item_to_iteration(
                db,
                task,
                row.iteration_id,
                actor_id=actor_id,
                reason="requirement_import_updated",
            )
    requirement.title = row.title
    requirement.requirement_type = row.requirement_type
    requirement.priority = row.priority
    if row.owner_id is not None:
        requirement.owner_id = row.owner_id
    if row.proposer is not None:
        requirement.proposer = row.proposer
    requirement.updater_id = actor_id
    requirement.description = row.description
    requirement.acceptance_criteria = row.acceptance_criteria


def _lock_requirement_for_import_update(
    db: Session,
    requirement_id: int,
    prelocked_iterations: dict,
) -> Requirement:
    requirement = _get_requirement_for_import_update(db, requirement_id, for_update=True)
    if requirement.iteration_id in prelocked_iterations:
        return requirement
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "ITERATION_STATE_CONFLICT",
            "message": "Iteration membership changed during import; refresh and retry",
        },
    )


def _get_requirement_for_import_update(db: Session, requirement_id: int, *, for_update: bool) -> Requirement:
    query = db.query(Requirement).filter(Requirement.id == requirement_id, Requirement.deleted == 0)
    if for_update:
        query = query.with_for_update().populate_existing()
    requirement = query.first()
    if not requirement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requirement not found")
    return requirement


def _ensure_rows_create_permission(db: Session, rows: list[ParsedRequirementRow], actor: User | None) -> None:
    checked_project_ids: set[int] = set()
    for row in rows:
        if row.project_id in checked_project_ids:
            continue
        ensure_work_item_create_permission(db, row.project_id, actor)
        checked_project_ids.add(row.project_id)


def _cell_text(value) -> str:
    return str(value).strip() if value is not None else ""


def _template_project_name(db: Session, project_id: int | None) -> str:
    if not project_id:
        return "示例项目"
    project = db.query(Project).filter(Project.id == project_id, Project.deleted == 0).first()
    return project.name if project else "示例项目"


def _add_list_validation(sheet, column_letter: str, values: list[str]) -> None:
    validation = DataValidation(type="list", formula1=f'"{",".join(values)}"', allow_blank=True)
    sheet.add_data_validation(validation)
    validation.add(f"{column_letter}2:{column_letter}500")


UNRESOLVED_STATUSES = {'unmatched', 'ambiguous', 'unavailable'}
IMPORT_FIELDS = {
    'title': '需求标题', 'iteration_id': '迭代', 'requirement_type': '类型',
    'priority': '优先级', 'proposer': '提出人', 'description': '需求描述',
    'acceptance_criteria': '验收标准',
}


def build_requirement_export(db: Session, project_id: int) -> bytes:
    project = _resolve_project_id(db, project_id)
    workbook = load_workbook(BytesIO(build_requirement_import_template(db, project_id)))
    sheet = workbook.active
    sheet.delete_rows(2, sheet.max_row)
    sheet.cell(1, len(REQUIREMENT_IMPORT_COLUMNS) + 1, '需求ID')
    sheet.column_dimensions['I'].width = 20
    rows = db.query(Requirement).filter(Requirement.project_id == project_id, Requirement.deleted == 0).order_by(Requirement.id).all()
    iteration_names = dict(db.query(Iteration.id, Iteration.name).all())
    for item in rows:
        values = [project.name, iteration_names.get(item.iteration_id, ''), item.title,
                  item.requirement_type, item.priority, item.proposer, item.description,
                  item.acceptance_criteria, str(item.id)]
        for label, value in zip(REQUIREMENT_IMPORT_COLUMNS + ['需求ID'], values):
            if isinstance(value, str) and len(value) > 32767:
                raise HTTPException(status_code=422, detail=f'需求 {item.id} 的{label}超过 Excel 单元格 32767 字符上限，无法完整导出，请缩短后重试')
        sheet.append(values)
        # Preserve literal Excel values, including text beginning with '='.
        for cell in sheet[sheet.max_row]:
            if isinstance(cell.value, str):
                cell.data_type = 's'
    for validation in sheet.data_validations.dataValidation:
        column = 'D' if '功能' in validation.formula1 else 'E'
        validation.sqref = f'{column}2:{column}{max(500, sheet.max_row)}'
    sheet.freeze_panes = 'A2'
    buffer = BytesIO(); workbook.save(buffer)
    return buffer.getvalue()


def _directory_candidates(db: Session, query: str) -> list[dict]:
    from app.services.ldap_config_service import require_ready_config, _password
    from app.services.ldap_client import ldap_client
    config = require_ready_config(db)
    password = _password(config)
    users, cursor, seen = {}, None, set()
    while True:
        page = ldap_client.search_users(config, password, query=query or None, cursor=cursor,
                                        page_size=50, exclude_disabled=True)
        for person in page.items:
            if person.get('enabled', True) and person.get('external_id') and person.get('username'):
                users[person['external_id']] = {key: person.get(key) for key in
                    ('external_id', 'username', 'employee_no', 'full_name', 'department')}
        cursor = page.next_cursor
        if not cursor or not query:
            break
        if cursor in seen:
            raise HTTPException(status_code=502, detail='AD 人员查询分页异常，请重试')
        seen.add(cursor)
    return sorted(users.values(), key=lambda person: person['external_id'])


def import_proposer_options(db: Session, query: str = '') -> list[dict]:
    from app.services.ldap_client import LdapConnectionError, LdapQueryError
    try:
        return _directory_candidates(db, query.strip())
    except (LdapConnectionError, LdapQueryError) as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


def _resolve_import_proposer(db, value, external_id, cache):
    from app.services.ldap_client import ldap_client, LdapConnectionError, LdapQueryError
    from app.services.ldap_config_service import require_ready_config, _password
    key = (value or '').strip().casefold()
    try:
        if key not in cache:
            try:
                cache[key] = _directory_candidates(db, value or '')
            except (HTTPException, LdapConnectionError, LdapQueryError) as error:
                cache[key] = error
        if isinstance(cache[key], Exception) and not external_id:
            raise cache[key]
        candidates = [] if isinstance(cache[key], Exception) else cache[key]
        if external_id:
            person = next((p for p in candidates if p['external_id'] == external_id), None)
            if person is None:
                config = require_ready_config(db)
                person = ldap_client.search_user_by_external_id(config, _password(config), external_id)
            if not person or not person.get('enabled', True) or not person.get('username'):
                return 'unmatched', None, candidates, '所选 AD 人员不存在或已停用'
            return 'selected', person, candidates, None
        exact = [p for p in candidates if key in {str(p.get('username') or '').casefold(), str(p.get('employee_no') or '').casefold()}]
        if not exact:
            exact = [p for p in candidates if str(p.get('full_name') or '').casefold() == key]
        if len(exact) == 1:
            return 'matched', exact[0], candidates, None
        return ('ambiguous' if len(exact) > 1 else 'unmatched'), None, candidates, ('AD 存在重名，请选择具体人员' if len(exact) > 1 else '未匹配到 AD 人员')
    except (HTTPException, LdapConnectionError, LdapQueryError):
        return 'unavailable', None, [], 'AD 配置未就绪或查询失败，请重试或跳过该行'


def _prepare_import(db, file_bytes, project_id, actor, strategy, decisions):
    if strategy not in {'update_existing', 'create_duplicate'}:
        raise HTTPException(status_code=422, detail='未知重复处理策略')
    parsed, errors = _parse_requirement_rows(db, file_bytes, project_id)
    _ensure_rows_create_permission(db, parsed, actor)
    choices = {d['row_number']: d for d in decisions or []}
    if len(choices) != len(decisions or []) or set(choices) - {r.row_number for r in parsed}:
        raise HTTPException(status_code=422, detail='导入行选择无效，请重新预检')
    targets, records, cache, seen, new_titles = [], [], {}, set(), set()
    for row in parsed:
        if row.requirement_id:
            existing = db.query(Requirement).filter(Requirement.id == row.requirement_id, Requirement.project_id == row.project_id, Requirement.deleted == 0).first()
        else:
            existing = _find_existing_requirement(db, row.project_id, row.title)
        choice = choices.get(row.row_number, {})
        skip = choice.get('skip', False)
        updating = existing is not None and strategy == 'update_existing'
        if not existing and not skip and strategy == 'update_existing':
            title_key = (row.project_id, row.title.casefold())
            if title_key in new_titles:
                errors.append({'row_number': row.row_number, 'messages': ['同一文件不能重复新增同名需求']})
            new_titles.add(title_key)
        if updating and not skip:
            ensure_work_item_action_permission(db, existing, actor.id if actor else None, '需求')
            if existing.id in seen:
                errors.append({'row_number': row.row_number, 'messages': ['同一文件不能多次更新同一需求']})
            seen.add(existing.id)
        person, candidates, message = None, [], None
        raw_proposer = row.proposer
        if skip:
            proposer_status = 'skipped'
        elif choice.get('proposer_external_id') or row.proposer:
            proposer_status, person, candidates, message = _resolve_import_proposer(db, row.proposer, choice.get('proposer_external_id'), cache)
            if person:
                row.proposer = person.get('full_name') or person['username']
        else:
            proposer_status = 'preserved' if updating and existing.proposer else 'empty'
        record = {'row_number': row.row_number, 'project_id': row.project_id, 'project_name': row.project_name,
                  'title': row.title, 'existing_requirement_id': existing.id if existing else None,
                  'existing_requirement_title': existing.title if existing else None,
                  'action': 'skip' if skip else ('update' if updating else 'create'),
                  'proposer_input': raw_proposer, 'proposer_status': proposer_status,
                  'proposer': {k: person.get(k) for k in ('external_id', 'username', 'employee_no', 'full_name', 'department')} if person else None,
                  'proposer_candidates': candidates, 'proposer_message': message}
        targets.append(existing); records.append(record)
    return parsed, errors, targets, records


def _changes(db, row, existing):
    changes = []
    for field, label in IMPORT_FIELDS.items():
        old = getattr(existing, field) if existing else None
        new = getattr(row, field)
        if field == 'proposer' and new is None and existing:
            new = old
        if (old or '') == (new or ''):
            continue
        if field == 'iteration_id':
            old_iteration = db.get(Iteration, old) if old else None
            new_iteration = db.get(Iteration, new) if new else None
            old = old_iteration.name if old_iteration else None
            new = new_iteration.name if new_iteration else None
        changes.append({'field': field, 'label': label, 'old_value': old, 'new_value': new})
    return changes


def _preview_result(db, prepared, file_bytes, project_id, actor, strategy, decisions):
    parsed, errors, targets, records = prepared
    snapshots = []
    for row, existing, record in zip(parsed, targets, records):
        updating = existing is not None and strategy == 'update_existing'
        record['changes'] = _changes(db, row, existing if updating else None)
        if record['action'] != 'skip':
            record['action'] = ('update' if record['changes'] else 'unchanged') if updating else 'create'
        record['moves_linked_tasks'] = bool(updating and existing.iteration_id != row.iteration_id)
        snapshots.append({k: getattr(existing, k) for k in
            (*IMPORT_FIELDS, 'id', 'source_project_id', 'owner_id', 'current_state_id', 'review_status', 'update_time')} if existing else None)
    digest = hashlib.sha256(json.dumps({'file': hashlib.sha256(file_bytes).hexdigest(), 'project': project_id,
        'actor': actor.id if actor else None, 'strategy': strategy, 'decisions': decisions or [],
        'snapshots': snapshots, 'rows': records}, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()
    token = jwt.encode({'purpose': 'requirement-import', 'digest': digest,
                        'exp': datetime.now(timezone.utc) + timedelta(minutes=30)}, settings.secret_key, algorithm='HS256')
    return {'valid_count': len(parsed), 'error_count': len(errors), 'duplicate_count': sum(t is not None for t in targets),
            'errors': errors, 'duplicates': [r for r in records if r['existing_requirement_id']],
            'rows': records, 'unresolved_count': sum(r['proposer_status'] in UNRESOLVED_STATUSES and r['action'] != 'skip' for r in records),
            'preview_token': token}
