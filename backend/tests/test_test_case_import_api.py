from io import BytesIO
from uuid import uuid4

import pytest
from openpyxl import Workbook, load_workbook


COLUMNS = ['用例标题', '关联需求', '用例类型', '适用范围', '测试人账号', '前置条件', '用例步骤', '预期结果']
BASE = '/api/v1/test-cases/import'


def excel(rows):
    book = Workbook()
    for row in [COLUMNS, *rows]:
        book.active.append(row)
    content = BytesIO()
    book.save(content)
    return ('cases.xlsx', content.getvalue(), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@pytest.fixture
def context(client):
    client.enable_real_iteration_defaults()
    project = client.post('/api/v1/projects', json={'name': f'import-{uuid4().hex[:8]}'}).json()
    requirement = client.post('/api/v1/requirements', json={'project_id': project['id'], 'title': '登录需求'}).json()
    assert 'id' in requirement, requirement
    return project['id'], requirement


def upload(client, context, rows, action='preview', **options):
    project_id, _ = context
    return client.post(f'{BASE}/{action}', data={'project_id': str(project_id), **options}, files={'file': excel(rows)})


def test_template_contains_requirement_dropdown(client, context):
    project_id, requirement = context
    response = client.get(f'{BASE}/template', params={'project_id': project_id})
    assert response.status_code == 200, response.text
    book = load_workbook(BytesIO(response.content))
    assert [cell.value for cell in book.active[1]] == COLUMNS
    assert f"登录需求【需求#{requirement['id']}】" in [row[0] for row in book['需求清单'].iter_rows(min_row=2, values_only=True)]
    assert any('B2:B1001' in str(rule.sqref) for rule in book.active.data_validations.dataValidation)


def test_downloaded_template_can_be_filled_and_imported(client, context):
    project_id, requirement = context
    response = client.get(f'{BASE}/template', params={'project_id': project_id})
    book = load_workbook(BytesIO(response.content))
    book.active.cell(2, 1, '模板往返验证')
    book.active.cell(2, 2, f"登录需求【需求#{requirement['id']}】")
    book.active.cell(2, 7, '第一步\n第二步')
    stream = BytesIO()
    book.save(stream)
    result = client.post(f'{BASE}/commit', data={'project_id': project_id}, files={'file': ('filled.xlsx', stream.getvalue())})
    assert result.status_code == 200, result.text
    assert result.json()['created_count'] == 1


def test_selected_requirement_and_plain_title_resolve(client, context):
    _, requirement = context
    response = upload(client, context, [['选择下拉', f"登录需求【需求#{requirement['id']}】"], ['手填标题', '登录需求']])
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['error_count'] == 0
    assert [row['requirement_id'] for row in data['rows']] == [requirement['id']] * 2


def test_commit_preserves_text_and_scope_and_skips_duplicates(client, context):
    rows = [['批量用例', '登录需求', '功能测试', '功能测试环节；冒烟测试环节', '', 'a < b', '1. 输入\n2. 提交', '成功']]
    response = upload(client, context, rows, 'commit')
    assert response.status_code == 200, response.text
    assert response.json()['created_count'] == 1
    project_id, requirement = context
    cases = client.get('/api/v1/test-cases').json()
    item = next(item for item in cases if item['project_id'] == project_id and item['title'] == '批量用例')
    assert item['requirement_id'] == requirement['id']
    assert item['steps_content'] == '1. 输入<br>2. 提交'
    assert item['precondition'] == 'a &lt; b'
    assert item['steps_json'] is None
    assert item['test_scopes'] == ['functional_test', 'smoke_test']
    second = upload(client, context, rows, 'commit').json()
    assert second['created_count'] == 0 and second['skipped_count'] == 1
    third = upload(client, context, rows, 'commit', duplicate_strategy='create_duplicate').json()
    assert third['created_count'] == 1


def test_ambiguous_titles_can_be_resolved_once_for_all_rows(client, context):
    project_id, requirement = context
    other = client.post('/api/v1/requirements', json={'project_id': project_id, 'title': '登录需求'}).json()
    rows = [['第一条', '登录需求'], ['第二条', '登录需求']]
    preview = upload(client, context, rows).json()
    assert preview['error_count'] == 2
    assert len(preview['requirement_groups']) == 1
    assert preview['requirement_groups'][0]['count'] == 2
    resolved = upload(client, context, rows, requirement_overrides=f'{{"登录需求": {other["id"]}}}').json()
    assert resolved['error_count'] == 0
    assert all(row['requirement_id'] == other['id'] for row in resolved['rows'])


def test_default_requirement_and_explicit_unlinked(client, context):
    _, requirement = context
    data = upload(client, context, [['默认需求']], default_requirement_id=str(requirement['id'])).json()
    assert data['rows'][0]['requirement_id'] == requirement['id']
    unlinked = upload(client, context, [['不关联', '不存在']], requirement_overrides='{"不存在": null}').json()
    assert unlinked['error_count'] == 0 and unlinked['rows'][0]['requirement_id'] is None


def test_cross_project_requirement_and_invalid_row_block_entire_import(client, context):
    foreign_project = client.post('/api/v1/projects', json={'name': f'foreign-{uuid4().hex[:8]}'}).json()
    foreign = client.post('/api/v1/requirements', json={'project_id': foreign_project['id'], 'title': '外部需求'}).json()
    response = upload(client, context, [['有效用例'], ['错误关联', f"外部需求【需求#{foreign['id']}】"]], 'commit')
    assert response.status_code == 422
    project_id, _ = context
    assert not any(item['project_id'] == project_id for item in client.get('/api/v1/test-cases').json())


def test_invalid_enums_accounts_and_formula_report_row_errors(client, context):
    response = upload(client, context, [['错误', '', '未知类型', '未知范围', 'nonexistent-account'], ['=1+1']])
    assert response.status_code == 200
    data = response.json()
    assert data['error_count'] == 2
    assert len(data['errors'][0]['messages']) >= 3


def test_import_requires_authentication(client, context):
    response = client.get(f'{BASE}/template', params={'project_id': context[0]}, headers={'X-Test-No-Auth': '1'})
    assert response.status_code == 401


def test_file_duplicates_and_default_requirement_validation(client, context):
    response = upload(client, context, [['同名'], ['同名']], 'commit')
    assert response.json() == {'created_count': 1, 'skipped_count': 1}
    response = upload(client, context, [['无效默认需求']], default_requirement_id='999999999')
    assert response.status_code == 422
    response = upload(client, context, [['非法关联']], requirement_overrides='{"x": true}')
    assert response.status_code == 422


def test_revalidate_deleted_requirement_before_commit(client, context):
    _, requirement = context
    rows = [['需重检', f"登录需求【需求#{requirement['id']}】"]]
    assert upload(client, context, rows).json()['error_count'] == 0
    assert client.delete(f"/api/v1/requirements/{requirement['id']}").status_code == 204
    assert upload(client, context, rows, 'commit').status_code == 422


def test_file_constraints_and_missing_title(client, context):
    assert upload(client, context, [['']]).status_code == 422
    assert upload(client, context, [['', '登录需求']]).json()['error_count'] == 1
    response = upload(client, context, [[str(index)] for index in range(1001)])
    assert response.status_code == 422
    response = client.post(f'{BASE}/preview', data={'project_id': context[0]}, files={'file': ('cases.csv', b'a,b', 'text/csv')})
    assert response.status_code == 422
    response = client.post(f'{BASE}/preview', data={'project_id': context[0]}, files={'file': ('cases.xlsx', b'invalid', 'application/octet-stream')})
    assert response.status_code == 422


def test_import_transaction_rolls_back_on_second_insert(client, context):
    from sqlalchemy import event
    from app.models.test_case import TestCase

    count = 0

    def fail_second(mapper, connection, target):
        nonlocal count
        count += 1
        if count == 2:
            raise RuntimeError('simulated insert failure')

    event.listen(TestCase, 'before_insert', fail_second)
    try:
        with pytest.raises(RuntimeError, match='simulated insert failure'):
            upload(client, context, [['第一条'], ['第二条']], 'commit')
    finally:
        event.remove(TestCase, 'before_insert', fail_second)
    assert not any(item['project_id'] == context[0] for item in client.get('/api/v1/test-cases').json())


def test_user_without_test_permission_cannot_import(client, context):
    from app.core.security import create_access_token
    from app.db.session import SessionLocal
    from app.models.user import User

    with SessionLocal() as db:
        outsider = db.query(User).filter(User.username == 'bob').one()
        token = create_access_token(outsider.username)
    headers = {'Authorization': f'Bearer {token}'}
    for action in ['preview', 'commit']:
        response = client.post(f'{BASE}/{action}', data={'project_id': context[0]}, files={'file': excel([['无权用例']])}, headers=headers)
        assert response.status_code == 403
    assert client.get(f'{BASE}/template', params={'project_id': context[0]}, headers=headers).status_code == 403


def test_rejects_embedded_images_and_oversize_file(client, context):
    from zipfile import ZipFile
    name, data, mime = excel([['含图片']])
    content = BytesIO(data)
    with ZipFile(content, 'a') as archive:
        archive.writestr('xl/media/image1.png', b'image')
    response = client.post(f'{BASE}/preview', data={'project_id': context[0]}, files={'file': (name, content.getvalue(), mime)})
    assert response.status_code == 422 and '图片' in response.json()['detail']['message']
    response = client.post(f'{BASE}/preview', data={'project_id': context[0]}, files={'file': (name, b'x' * (10 * 1024 * 1024 + 1), mime)})
    assert response.status_code == 422


def test_concurrent_skip_uses_current_read_after_project_lock(client, context, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from app.services import test_case_import_service

    original = test_case_import_service.ensure_test_case_manage_permission
    both_authorized = Barrier(2)

    def synchronized_permission(*args):
        original(*args)
        both_authorized.wait(timeout=10)

    monkeypatch.setattr(test_case_import_service, 'ensure_test_case_manage_permission', synchronized_permission)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(upload, client, context, [['并发同名用例', '登录需求']], 'commit') for _ in range(2)]
        results = [future.result(timeout=30) for future in futures]
    assert all(result.status_code == 200 for result in results), [result.text for result in results]
    assert sorted(result.json()['created_count'] for result in results) == [0, 1]
    assert sorted(result.json()['skipped_count'] for result in results) == [0, 1]
