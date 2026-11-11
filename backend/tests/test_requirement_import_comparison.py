from io import BytesIO
import json
from uuid import uuid4

import pytest
from openpyxl import Workbook, load_workbook

from app.db.session import SessionLocal
from app.models.requirement import Requirement
from app.models.user import User
from app.core.security import create_access_token
from app.services import requirement_import_service as service
from app.services.iteration_assignment_service import fallback_iteration_for_project


@pytest.fixture
def project_data(client):
    client.enable_real_iteration_defaults()
    p = client.post('/api/v1/projects', json={'name': '往返导入-' + uuid4().hex[:8]}).json()
    r = client.post('/api/v1/requirements', json={
        'project_id': p['id'], 'title': '原需求', 'priority': '3',
        'description': '<p>原描述</p>', 'proposer': '原提出人',
    }).json()
    with SessionLocal() as db:
        iteration = fallback_iteration_for_project(db, p['id'])
        iteration_name = iteration.name
    return p, r, iteration_name


def excel(p, r, iteration, **values):
    fields = {'项目名称': p['name'], '迭代名称': iteration, '需求标题': r['title'],
              '类型': '', '优先级': '3', '提出人': '', '需求描述': '<p>原描述</p>',
              '验收标准': '', '需求ID': str(r['id'])}
    fields.update(values)
    w = Workbook(); w.active.append(list(fields)); w.active.append(list(fields.values()))
    b = BytesIO(); w.save(b)
    return ('requirements.xlsx', b.getvalue(), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


def preview(client, p, file, decisions=None, strategy='update_existing'):
    return client.post('/api/v1/requirements/import/preview',
                       data={'project_id': p['id'], 'duplicate_strategy': strategy,
                             'decisions': json.dumps(decisions or [])}, files={'file': file})


def commit(client, p, file, result, decisions=None):
    return client.post('/api/v1/requirements/import/commit',
                       data={'project_id': p['id'], 'duplicate_strategy': 'update_existing',
                             'decisions': json.dumps(decisions or []), 'preview_token': result['preview_token']},
                       files={'file': file})


def test_preview_differences_by_id_and_preserves_blank_proposer(client, project_data):
    p, r, iteration = project_data
    file = excel(p, r, iteration, **{'需求标题': '改名需求', '优先级': '2'})
    result = preview(client, p, file)
    assert result.status_code == 200, result.text
    row = result.json()['rows'][0]
    changes = {c['field']: c for c in row['changes']}
    assert row['existing_requirement_id'] == r['id']
    assert changes['title']['old_value'] == '原需求'
    assert changes['title']['new_value'] == '改名需求'
    assert changes['priority']['new_value'] == '2'
    assert 'proposer' not in changes
    assert row['proposer_status'] == 'preserved'
    with SessionLocal() as db:
        item = db.get(Requirement, r['id']); item.review_status = 'approved'; db.commit()
    # Refresh preview after a concurrent state change, then preserve that state.
    fresh = preview(client, p, file).json()
    response = commit(client, p, file, fresh)
    assert response.status_code == 200, response.text
    assert response.json()['updated_count'] == 1
    item = client.get(f"/api/v1/requirements/{r['id']}").json()
    assert item['title'] == '改名需求' and item['proposer'] == '原提出人'
    assert item['review_status'] == 'approved'
    assert item['current_state_id'] == r['current_state_id']
    assert item['owner_id'] == r['owner_id']


def test_export_round_trip_is_unchanged_and_formula_safe(client, project_data, monkeypatch):
    p, r, _ = project_data
    with SessionLocal() as db:
        item = db.get(Requirement, r['id']); item.proposer = None; item.title = '=1+1'; db.commit()
    response = client.get('/api/v1/requirements/export', params={'project_id': p['id']})
    assert response.status_code == 200, response.text
    sheet = load_workbook(BytesIO(response.content)).active
    assert [c.value for c in sheet[1]] == service.REQUIREMENT_IMPORT_COLUMNS + ['需求ID']
    assert sheet.cell(2, 3).value == '=1+1' and sheet.cell(2, 3).data_type == 's'
    assert str(sheet.cell(2, 9).value) == str(r['id'])
    file = ('export.xlsx', response.content, response.headers['content-type'])
    result = preview(client, p, file).json()
    assert result['rows'][0]['action'] == 'unchanged'
    done = commit(client, p, file, result)
    assert done.status_code == 200, done.text
    assert done.json()['updated_count'] == 0 and done.json()['skipped_count'] == 1


def test_ad_ambiguity_can_be_resolved_in_preview(client, project_data, monkeypatch):
    p, r, iteration = project_data
    people = [dict(external_id='ad-a', username='alice', employee_no='100', full_name='同名人员', department='研发', enabled=True),
              dict(external_id='ad-b', username='bob', employee_no='101', full_name='同名人员', department='测试', enabled=True)]
    monkeypatch.setattr(service, '_directory_candidates', lambda db, query: people, raising=False)
    file = excel(p, r, iteration, **{'提出人': '同名人员'})
    result = preview(client, p, file).json()
    assert result['rows'][0]['proposer_status'] == 'ambiguous'
    assert result['unresolved_count'] == 1
    bad = commit(client, p, file, result)
    assert bad.status_code == 422
    decisions = [{'row_number': 2, 'proposer_external_id': 'ad-b'}]
    fresh = preview(client, p, file, decisions).json()
    assert fresh['rows'][0]['proposer']['username'] == 'bob'
    assert fresh['unresolved_count'] == 0
    done = commit(client, p, file, fresh, decisions)
    assert done.status_code == 200, done.text
    assert client.get(f"/api/v1/requirements/{r['id']}").json()['proposer'] == '同名人员'


def test_commit_rejects_stale_preview_without_overwriting(client, project_data):
    p, r, iteration = project_data
    file = excel(p, r, iteration, **{'优先级': '1'})
    result = preview(client, p, file).json()
    with SessionLocal() as db:
        item = db.get(Requirement, r['id']); item.description = '他人修改'; db.commit()
    response = commit(client, p, file, result)
    assert response.status_code == 409, response.text
    with SessionLocal() as db:
        assert db.get(Requirement, r['id']).description == '他人修改'
        assert db.get(Requirement, r['id']).priority == '3'


def test_export_requires_project_access(client, project_data):
    p, _, _ = project_data
    response = client.get('/api/v1/requirements/export', params={'project_id': p['id']}, headers={'X-Test-No-Auth': '1'})
    assert response.status_code == 401


def test_unmatched_proposer_can_be_skipped_without_affecting_other_rows(client, project_data, monkeypatch):
    p, r, iteration = project_data
    monkeypatch.setattr(service, '_directory_candidates', lambda db, query: [])
    file = excel(p, r, iteration, **{'提出人': '找不到的人员', '优先级': '1'})
    result = preview(client, p, file).json()
    assert result['rows'][0]['proposer_status'] == 'unmatched'
    assert commit(client, p, file, result).status_code == 422
    decisions = [{'row_number': 2, 'skip': True}]
    result = preview(client, p, file, decisions).json()
    response = commit(client, p, file, result, decisions)
    assert response.status_code == 200, response.text
    assert response.json()['skipped_count'] == 1
    assert client.get(f"/api/v1/requirements/{r['id']}").json()['priority'] == '3'


def test_ad_account_precedes_duplicate_names(client, project_data, monkeypatch):
    p, r, iteration = project_data
    people = [dict(external_id='1', username='alice', employee_no='100', full_name='李四'),
              dict(external_id='2', username='bob', employee_no='101', full_name='李四')]
    monkeypatch.setattr(service, '_directory_candidates', lambda db, query: people)
    file = excel(p, r, iteration, **{'提出人': 'ALICE'})
    result = preview(client, p, file).json()
    assert result['unresolved_count'] == 0
    assert result['rows'][0]['proposer']['external_id'] == '1'
    done = commit(client, p, file, result)
    assert done.status_code == 200, done.text
    assert client.get(f"/api/v1/requirements/{r['id']}").json()['proposer'] == '李四'


def test_directory_outage_is_a_visible_blocker(client, project_data, monkeypatch):
    from fastapi import HTTPException
    p, r, iteration = project_data
    def unavailable(*args):
        raise HTTPException(502, 'offline')
    monkeypatch.setattr(service, '_directory_candidates', unavailable)
    result = preview(client, p, excel(p, r, iteration, **{'提出人': '李四'})).json()
    assert result['rows'][0]['proposer_status'] == 'unavailable'
    assert result['unresolved_count'] == 1


def test_cross_project_ids_and_duplicate_target_rows_are_rejected(client, project_data):
    p, r, iteration = project_data
    other = client.post('/api/v1/projects', json={'name': '其他-' + uuid4().hex[:8]}).json()
    other_req = client.post('/api/v1/requirements', json={'project_id': other['id'], 'title': '其他需求'}).json()
    result = preview(client, p, excel(p, r, iteration, **{'需求ID': str(other_req['id'])})).json()
    assert result['error_count'] == 1
    file = excel(p, r, iteration)
    w = load_workbook(BytesIO(file[1])); w.active.append([c.value for c in w.active[2]])
    b = BytesIO(); w.save(b)
    result = preview(client, p, ('twice.xlsx', b.getvalue(), file[2])).json()
    assert result['error_count'] == 1


def test_selected_identity_is_revalidated_before_commit(client, project_data, monkeypatch):
    from app.services.ldap_client import ldap_client
    from app.services import ldap_config_service
    from types import SimpleNamespace
    p, r, iteration = project_data
    people = [dict(external_id='ad-a', username='alice', employee_no='100', full_name='李四')]
    monkeypatch.setattr(service, '_directory_candidates', lambda db, query: people)
    file = excel(p, r, iteration, **{'提出人': '李四'})
    decisions = [{'row_number': 2, 'proposer_external_id': 'ad-a'}]
    result = preview(client, p, file, decisions).json()
    people.clear()
    monkeypatch.setattr(ldap_config_service, 'require_ready_config', lambda db: SimpleNamespace())
    monkeypatch.setattr(ldap_config_service, '_password', lambda config: 'test')
    monkeypatch.setattr(ldap_client, 'search_user_by_external_id', lambda *args: None)
    response = commit(client, p, file, result, decisions)
    assert response.status_code == 422
    assert client.get(f"/api/v1/requirements/{r['id']}").json()['proposer'] == '原提出人'


def test_commit_requires_snapshot_and_rejects_file_changes(client, project_data):
    p, r, iteration = project_data
    file = excel(p, r, iteration, **{'优先级': '1'})
    response = client.post('/api/v1/requirements/import/commit',
                           data={'project_id': p['id'], 'duplicate_strategy': 'update_existing'}, files={'file': file})
    assert response.status_code == 422
    result = preview(client, p, file).json()
    changed = excel(p, r, iteration, **{'优先级': '2'})
    assert commit(client, p, changed, result).status_code == 409


def test_export_project_isolation_and_all_rows(client, project_data):
    p, r, _ = project_data
    for i in range(12):
        client.post('/api/v1/requirements', json={'project_id': p['id'], 'title': f'导出需求{i}'}).raise_for_status()
    other = client.post('/api/v1/projects', json={'name': '隔离-' + uuid4().hex[:8]}).json()
    client.post('/api/v1/requirements', json={'project_id': other['id'], 'title': '不能导出'}).raise_for_status()
    response = client.get('/api/v1/requirements/export', params={'project_id': p['id']})
    sheet = load_workbook(BytesIO(response.content)).active
    assert sheet.max_row == 14
    assert {sheet.cell(row, 1).value for row in range(2, 15)} == {p['name']}
    with SessionLocal() as db:
        outsider = db.query(User).filter(User.username == 'bob').one()
        token = create_access_token(outsider.username)
    response = client.get('/api/v1/requirements/export', params={'project_id': p['id']}, headers={'Authorization': f'Bearer {token}'})
    assert response.status_code == 403


def test_directory_matching_searches_all_pages(monkeypatch):
    from app.services import ldap_config_service
    from app.services.ldap_client import ldap_client, LdapSearchResult
    monkeypatch.setattr(ldap_config_service, 'require_ready_config', lambda db: object())
    monkeypatch.setattr(ldap_config_service, '_password', lambda config: 'test')
    calls = []
    def search(*args, **kwargs):
        calls.append(kwargs['cursor'])
        if not kwargs['cursor']:
            return LdapSearchResult([{'external_id': 'first', 'username': 'alice', 'full_name': '李四'}], 'next')
        return LdapSearchResult([{'external_id': 'second', 'username': 'bob', 'full_name': '李四'}], None)
    monkeypatch.setattr(ldap_client, 'search_users', search)
    state, person, candidates, _ = service._resolve_import_proposer(object(), '李四', None, {})
    assert state == 'ambiguous' and person is None and len(candidates) == 2
    assert calls == [None, 'next']


def test_new_title_created_after_preparation_requires_new_preview(client, project_data, monkeypatch):
    p, r, iteration = project_data
    file = excel(p, r, iteration, **{'需求ID': '', '需求标题': '并发新增'})
    result = preview(client, p, file).json()
    original = service._prepare_import
    def prepare(*args, **kwargs):
        prepared = original(*args, **kwargs)
        # Another transaction commits after this request has resolved its target.
        with SessionLocal() as db:
            db.add(Requirement(project_id=p['id'], iteration_id=r['iteration_id'], title='并发新增', priority='3',
                               workflow_definition_id=r['workflow_definition_id'], current_state_id=r['current_state_id']))
            db.commit()
        return prepared
    monkeypatch.setattr(service, '_prepare_import', prepare)
    response = commit(client, p, file, result)
    assert response.status_code == 409, response.text
    with SessionLocal() as db:
        assert db.query(Requirement).filter_by(project_id=p['id'], title='并发新增', deleted=0).count() == 1


def test_export_rejects_long_text_instead_of_silent_truncation(client, project_data):
    p, r, _ = project_data
    with SessionLocal() as db:
        db.get(Requirement, r['id']).description = '<p>' + 'x' * 40000 + '</p>'
        db.commit()
    response = client.get('/api/v1/requirements/export', params={'project_id': p['id']})
    assert response.status_code == 422
    assert str(r['id']) in response.json()['detail']['message']
    assert '需求描述' in response.json()['detail']['message']


def test_manual_selection_can_recover_from_invalid_original_search(monkeypatch):
    from app.services import ldap_config_service
    from app.services.ldap_client import ldap_client, LdapQueryError
    def invalid(*args):
        raise LdapQueryError('invalid query')
    monkeypatch.setattr(service, '_directory_candidates', invalid)
    monkeypatch.setattr(ldap_config_service, 'require_ready_config', lambda db: object())
    monkeypatch.setattr(ldap_config_service, '_password', lambda config: 'test')
    monkeypatch.setattr(ldap_client, 'search_user_by_external_id', lambda *args: {'external_id': 'a', 'username': 'alice', 'full_name': '李四'})
    state, person, _, _ = service._resolve_import_proposer(object(), '*invalid', 'a', {})
    assert state == 'selected' and person['username'] == 'alice'


def test_export_round_trip_preserves_description_whitespace(client, project_data):
    p, r, _ = project_data
    with SessionLocal() as db:
        item = db.get(Requirement, r['id'])
        item.proposer = None
        item.description = '  原描述\n\n'
        item.acceptance_criteria = '\n 验收标准  '
        db.commit()
    response = client.get('/api/v1/requirements/export', params={'project_id': p['id']})
    result = preview(client, p, ('roundtrip.xlsx', response.content, response.headers['content-type'])).json()
    assert result['rows'][0]['action'] == 'unchanged'


def test_duplicate_new_title_in_file_is_rejected(client, project_data):
    p, r, iteration = project_data
    file = excel(p, r, iteration, **{'需求ID': '', '需求标题': '重复新增'})
    w = load_workbook(BytesIO(file[1])); w.active.append([c.value for c in w.active[2]])
    b = BytesIO(); w.save(b)
    result = preview(client, p, ('twice.xlsx', b.getvalue(), file[2])).json()
    assert result['error_count'] == 1
