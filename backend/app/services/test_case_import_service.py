import json
import re
from html import escape
from io import BytesIO
from zipfile import ZipFile

from fastapi import HTTPException
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.worksheet.datavalidation import DataValidation
from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.iteration import Iteration
from app.models.requirement import Requirement
from app.models.test_case import TestCase
from app.models.user import User
from app.services.lifecycle_service import project_lifecycle_phase, requirement_lifecycle_phase
from app.services.project_permission_service import ensure_test_case_manage_permission
from app.services.project_team_service import default_tester_id


IMPORT_COLUMNS = ['用例标题', '关联需求', '用例类型', '适用范围', '测试人账号', '前置条件', '用例步骤', '预期结果']
CASE_TYPES = {'接口测试': 'api', '功能测试': 'functional', '安装部署': 'deploy', '配置相关': 'config', '性能测试': 'performance', '安全相关': 'security', '其他': 'other'}
SCOPES = {'单元测试环节': 'unit_test', '功能测试环节': 'functional_test', '集成测试环节': 'integration_test', '系统测试环节': 'system_test', '冒烟测试环节': 'smoke_test', '版本验证环节': 'release_validation'}
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_ROWS = 1000


def _project(db, project_id, actor, *, lock=False):
    ensure_test_case_manage_permission(db, project_id, actor)
    query = db.query(Project).filter(Project.id == project_id, Project.deleted == 0)
    if lock:
        query = query.with_for_update()
    project = query.first()
    if project is None:
        raise HTTPException(404, '项目不存在')
    return project


def _requirements(db, project_id, *, lock=False):
    query = db.query(Requirement).filter(Requirement.project_id == project_id, Requirement.deleted == 0).order_by(Requirement.id)
    return (query.with_for_update() if lock else query).all()


def requirement_option(requirement):
    return f'{requirement.title}【需求#{requirement.id}】'


def build_test_case_import_template(db: Session, project_id: int, actor) -> bytes:
    project = _project(db, project_id, actor)
    requirements = _requirements(db, project_id)
    iteration_ids = {item.iteration_id for item in requirements if item.iteration_id}
    iterations = {item.id: item.name for item in db.query(Iteration).filter(Iteration.id.in_(iteration_ids)).all()} if iteration_ids else {}
    users = db.query(User).filter(User.deleted == 0, User.is_active.is_(True)).order_by(User.username).all()
    book = Workbook()
    sheet = book.active
    sheet.title = '测试用例导入'
    sheet.append(IMPORT_COLUMNS)
    sheet.freeze_panes = 'A2'
    sheet.auto_filter.ref = 'A1:H1001'
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for index, width in enumerate([32, 48, 18, 35, 24, 40, 55, 40], 1):
        sheet.column_dimensions[sheet.cell(1, index).column_letter].width = width
    for row in sheet.iter_rows(min_row=2, max_row=1001, max_col=8):
        for cell in row:
            cell.number_format = '@'
            cell.alignment = Alignment(wrap_text=True, vertical='top')
    refs = book.create_sheet('需求清单')
    refs.append(['关联需求选项', '需求 ID', '需求标题', '迭代', '状态'])
    for item in requirements:
        refs.append([requirement_option(item), str(item.id), item.title, iterations.get(item.iteration_id, ''), item.status_name or ''])
    people = book.create_sheet('测试人清单')
    people.append(['账号', '姓名'])
    for user in users:
        people.append([user.username, user.full_name])
    options = book.create_sheet('选项')
    options.append(['用例类型', '适用范围'])
    for index in range(max(len(CASE_TYPES), len(SCOPES))):
        options.append([list(CASE_TYPES)[index] if index < len(CASE_TYPES) else '', list(SCOPES)[index] if index < len(SCOPES) else ''])
    for name, formula, column in [
        ('RequirementOptions', f"'需求清单'!$A$2:$A${max(2, len(requirements) + 1)}", 'B'),
        ('TesterOptions', f"'测试人清单'!$A$2:$A${max(2, len(users) + 1)}", 'E'),
        ('CaseTypeOptions', f"'选项'!$A$2:$A${len(CASE_TYPES) + 1}", 'C'),
        ('ScopeOptions', f"'选项'!$B$2:$B${len(SCOPES) + 1}", 'D'),
    ]:
        book.defined_names.add(DefinedName(name, attr_text=formula))
        rule = DataValidation(type='list', formula1=f'={name}', allow_blank=True)
        # 手填标题、多范围也是有效输入，交由预检判断。
        rule.showErrorMessage = False
        sheet.add_data_validation(rule)
        rule.add(f'{column}2:{column}1001')
    instructions = book.create_sheet('填写说明')
    for text in [
        f'目标项目：{project.name}；一次仅导入当前所选项目。',
        '每行一条用例，用例标题必填；其他字段可选。数据填写在“测试用例导入”工作表。',
        '关联需求可下拉选择“标题【需求#ID】”，自动按 ID 关联，无需手填 ID。也可输入需求标题，重名/找不到时在预检中分组确认。',
        '留空关联需求使用弹窗中选择的默认需求；不选默认需求则不关联。',
        '适用范围可下拉选一个，多个范围用中文分号分隔；空值默认为功能测试环节。用例类型默认功能测试。',
        '测试人填账号而非姓名，留空使用项目默认测试人。账号见测试人清单。',
        '前置条件、用例步骤、预期结果支持单元格内换行；内容按纯文字导入，导入后可在平台补充图片。',
        '不支持公式或嵌入图片；最多1000条、10MB；重复可跳过或继续新增，不覆盖已有用例。',
    ]:
        instructions.append([text])
    for tab in [refs, people, options, instructions]:
        for cells in tab.columns:
            tab.column_dimensions[cells[0].column_letter].width = 45 if tab != instructions else 120
        # 项目名称、需求标题可能以 = 开头，引用表仅写文字，不生成公式。
        for row in tab:
            for cell in row:
                if isinstance(cell.value, str):
                    cell.data_type = 's'
    stream = BytesIO()
    book.save(stream)
    return stream.getvalue()


def parse_import_options(overrides: str) -> dict:
    try:
        value = json.loads(overrides)
        if not isinstance(value, dict) or len(value) > MAX_ROWS:
            raise ValueError()
        for key, item in value.items():
            if not isinstance(key, str) or (item is not None and (type(item) is not int or item <= 0)):
                raise ValueError()
        return value
    except (ValueError, TypeError):
        raise HTTPException(422, '需求关联设置格式不正确')


def _read_rows(content, filename):
    if not filename.lower().endswith('.xlsx'):
        raise HTTPException(422, '仅支持 .xlsx 文件')
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(422, '文件不能超过10MB')
    try:
        with ZipFile(BytesIO(content)) as archive:
            if sum(info.file_size for info in archive.infolist()) > 50 * 1024 * 1024:
                raise HTTPException(422, 'Excel解压后内容过大，请拆分文件')
            if any(name.startswith('xl/media/') for name in archive.namelist()):
                raise HTTPException(422, '暂不支持导入嵌入图片，请移除图片后重试，导入后可在平台补充')
        book = load_workbook(BytesIO(content), data_only=False, read_only=True, keep_links=False)
        try:
            sheet = book['测试用例导入'] if '测试用例导入' in book.sheetnames else book.active
            if sheet.max_column > 50 or sheet.max_row > 10001:
                raise HTTPException(422, '工作表范围过大，请使用模板并移除多余空行列')
            iterator = sheet.iter_rows()
            headers = [str(cell.value or '').strip() for cell in next(iterator, [])]
            if '用例标题' not in headers or len(headers) != len(set(headers)):
                raise HTTPException(422, '模板必须包含用例标题，且列名不能重复')
            rows = []
            for number, cells in enumerate(iterator, 2):
                if not any(cell.value is not None and str(cell.value).strip() for cell in cells):
                    continue
                if len(rows) >= MAX_ROWS:
                    raise HTTPException(422, '单次最多导入1000条用例')
                values = {headers[i]: str(cell.value).strip() if cell.value is not None else '' for i, cell in enumerate(cells) if i < len(headers)}
                formulas = any(cell.data_type == 'f' for cell in cells)
                rows.append((number, values, formulas))
            if not rows:
                raise HTTPException(422, '文件没有可导入的用例')
            return rows
        finally:
            book.close()
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(422, '无法读取Excel文件，请使用有效的.xlsx模板') from error


def _rich_text(value):
    return escape(value, quote=True).replace('\r\n', '\n').replace('\r', '\n').replace('\n', '<br>') or None


def inspect_test_case_import(db, project_id, actor, content, filename, default_requirement_id=None, overrides=None, *, lock=False):
    _project(db, project_id, actor, lock=lock)
    requirements = _requirements(db, project_id, lock=lock)
    by_id = {item.id: item for item in requirements}
    by_title = {}
    for item in requirements:
        by_title.setdefault(item.title.strip(), []).append(item)
    if default_requirement_id is not None and default_requirement_id not in by_id:
        raise HTTPException(422, '默认需求不存在或不属于当前项目')
    overrides = overrides or {}
    if any(value is not None and value not in by_id for value in overrides.values()):
        raise HTTPException(422, '指定的关联需求不存在或不属于当前项目')
    users = {user.username: user.id for user in db.query(User).filter(User.deleted == 0, User.is_active.is_(True)).all()}
    existing_query = db.query(TestCase).filter(TestCase.project_id == project_id, TestCase.deleted == 0)
    # 提交使用当前读，避免等待项目锁后仍从 REPEATABLE READ 旧快照读取重复集合。
    existing_cases = (existing_query.with_for_update() if lock else existing_query).all()
    existing = {(item.requirement_id, item.title.strip()) for item in existing_cases}
    seen = set()
    rows, errors, groups = [], [], {}
    for number, values, formulas in _read_rows(content, filename):
        messages = ['不支持公式，请粘贴为文字'] if formulas else []
        title = values.get('用例标题', '')
        if not title or len(title) > 255:
            messages.append('用例标题必填且不能超过255字')
        reference = values.get('关联需求', '')
        requirement_id = None
        association_error = None
        if reference in overrides:
            requirement_id = overrides[reference]
        elif not reference:
            requirement_id = default_requirement_id
        else:
            encoded = re.fullmatch(r'.*【需求#([0-9]+)】', reference)
            if encoded:
                requirement_id = int(encoded.group(1))
                if requirement_id not in by_id:
                    association_error = '关联需求不存在或不属于当前项目'
                    requirement_id = None
            else:
                candidates = by_title.get(reference, [])
                if len(candidates) == 1:
                    requirement_id = candidates[0].id
                else:
                    association_error = '需求标题重名，请选择关联需求' if candidates else '未找到需求，请选择关联需求或明确暂不关联'
        if reference:
            group = groups.setdefault(reference, {'reference': reference, 'count': 0, 'requirement_id': requirement_id, 'message': association_error or ('已指定暂不关联' if requirement_id is None else '已关联')})
            group['count'] += 1
        if association_error:
            messages.append(association_error)
        case_type = values.get('用例类型', '') or '功能测试'
        case_type = CASE_TYPES.get(case_type, case_type)
        if case_type not in CASE_TYPES.values():
            messages.append('用例类型不正确')
        scopes = []
        for scope in re.split('[;；]', values.get('适用范围', '') or '功能测试环节'):
            value = SCOPES.get(scope.strip(), scope.strip())
            if value not in SCOPES.values():
                messages.append(f'适用范围不正确：{scope}')
            elif value not in scopes:
                scopes.append(value)
        username = values.get('测试人账号', '')
        if username and username not in users:
            messages.append('测试人账号不存在或已停用')
        key = (requirement_id, title)
        duplicate = key in existing or key in seen
        if not messages:
            seen.add(key)
        row = {'row_number': number, 'title': title, 'requirement_id': requirement_id, 'duplicate': duplicate, 'messages': messages}
        row['payload'] = {
            'project_id': project_id, 'requirement_id': requirement_id, 'title': title,
            'case_type': case_type, 'test_scope': scopes[0] if scopes else None, 'test_scopes': scopes,
            'default_tester_id': users.get(username), 'precondition': _rich_text(values.get('前置条件', '')),
            'steps_content': _rich_text(values.get('用例步骤', '')), 'steps_json': None,
            'expected_result': _rich_text(values.get('预期结果', '')),
        }
        rows.append(row)
        if messages:
            errors.append({'row_number': number, 'messages': messages})
    return {
        'total_count': len(rows), 'valid_count': len(rows) - len(errors), 'error_count': len(errors),
        'duplicate_count': sum(row['duplicate'] for row in rows if not row['messages']),
        'errors': errors, 'rows': rows, 'requirement_groups': list(groups.values()),
    }


def commit_test_case_import(db, project_id, actor, content, filename, default_requirement_id=None, overrides=None, duplicate_strategy='skip'):
    if duplicate_strategy not in {'skip', 'create_duplicate'}:
        raise HTTPException(422, '未知重复处理策略')
    try:
        preview = inspect_test_case_import(db, project_id, actor, content, filename, default_requirement_id, overrides, lock=True)
        if preview['error_count']:
            raise HTTPException(422, {'message': '预检存在错误，请修正后重试', 'errors': preview['errors']})
        created, skipped = 0, 0
        tester = default_tester_id(db, project_id)
        for row in preview['rows']:
            if row['duplicate'] and duplicate_strategy == 'skip':
                skipped += 1
                continue
            data = row['payload']
            data['default_tester_id'] = data['default_tester_id'] or tester
            data['lifecycle_phase'] = requirement_lifecycle_phase(db, data['requirement_id']) or project_lifecycle_phase(db, project_id)
            data['creator_id'] = actor.id
            db.add(TestCase(**data))
            created += 1
        db.commit()
        return {'created_count': created, 'skipped_count': skipped}
    except Exception:
        db.rollback()
        raise
