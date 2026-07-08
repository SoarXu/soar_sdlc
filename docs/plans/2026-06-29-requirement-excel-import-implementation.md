# Requirement Excel Import Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add fixed-template Excel import for requirements with preview, duplicate confirmation, and commit strategies.

**Architecture:** Backend owns template generation, Excel parsing, validation, duplicate detection, and commit behavior. Frontend requirements page downloads the backend template, uploads `.xlsx` files for preview, displays validation and duplicate results, then calls commit with the selected duplicate strategy.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, MySQL, pytest, Vue 3, Element Plus, Axios. Use `openpyxl` for `.xlsx` generation and parsing.

---

### Task 1: Add Excel Dependency

**Files:**
- Modify: `backend/requirements.txt`

**Step 1: Add dependency**

Add:

```text
openpyxl==3.1.5
```

**Step 2: Install dependencies**

Run:

```bash
python -m pip install -r backend/requirements.txt -r backend/requirements-dev.txt
```

Expected: install succeeds.

**Step 3: Commit**

```bash
git add backend/requirements.txt
git commit -m "chore: add excel parsing dependency"
```

---

### Task 2: Backend Template Endpoint

**Files:**
- Modify: `backend/app/controllers/requirement_controller.py`
- Create: `backend/app/services/requirement_import_service.py`
- Test: `backend/tests/test_requirement_import_api.py`

**Step 1: Write failing test**

Create `backend/tests/test_requirement_import_api.py` with:

```python
from io import BytesIO

from fastapi.testclient import TestClient
from openpyxl import load_workbook


def test_requirement_import_template_downloads_excel(client: TestClient):
    response = client.get("/api/v1/requirements/import/template")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    workbook = load_workbook(BytesIO(response.content))
    sheet = workbook.active
    assert [cell.value for cell in sheet[1]] == [
        "项目名称",
        "来源项目名称",
        "迭代名称",
        "需求标题",
        "类型",
        "优先级",
        "负责人",
        "提出人",
        "评审状态",
        "需求描述",
        "验收标准",
    ]
```

**Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest backend/tests/test_requirement_import_api.py::test_requirement_import_template_downloads_excel -q
```

Expected: FAIL with 404.

**Step 3: Implement service**

Create `backend/app/services/requirement_import_service.py`:

```python
from io import BytesIO

from openpyxl import Workbook


REQUIREMENT_IMPORT_COLUMNS = [
    "项目名称",
    "来源项目名称",
    "迭代名称",
    "需求标题",
    "类型",
    "优先级",
    "负责人",
    "提出人",
    "评审状态",
    "需求描述",
    "验收标准",
]


def build_requirement_import_template() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "需求导入"
    sheet.append(REQUIREMENT_IMPORT_COLUMNS)
    sheet.append(["示例项目", "", "", "示例需求", "功能", "3", "", "", "无需评审", "需求描述", "验收标准"])
    for column in sheet.columns:
        sheet.column_dimensions[column[0].column_letter].width = 18
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
```

**Step 4: Add endpoint**

In `backend/app/controllers/requirement_controller.py`, import:

```python
from fastapi.responses import Response
from app.services.requirement_import_service import build_requirement_import_template
```

Add route before `/{requirement_id}` routes:

```python
@router.get("/import/template")
def download_requirement_import_template():
    content = build_requirement_import_template()
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=requirement-import-template.xlsx"},
    )
```

If `Response` is already imported from `fastapi`, avoid duplicate imports and use that existing import.

**Step 5: Run test to verify it passes**

Run:

```bash
python -m pytest backend/tests/test_requirement_import_api.py::test_requirement_import_template_downloads_excel -q
```

Expected: PASS.

**Step 6: Commit**

```bash
git add backend/app/controllers/requirement_controller.py backend/app/services/requirement_import_service.py backend/tests/test_requirement_import_api.py
git commit -m "feat: add requirement import template"
```

---

### Task 3: Backend Preview Validation

**Files:**
- Modify: `backend/app/services/requirement_import_service.py`
- Modify: `backend/app/controllers/requirement_controller.py`
- Modify: `backend/app/views/requirement_view.py`
- Test: `backend/tests/test_requirement_import_api.py`

**Step 1: Add failing preview tests**

Append tests:

```python
from io import BytesIO
from uuid import uuid4

from openpyxl import Workbook


def _xlsx(rows: list[list[str | None]]) -> tuple[str, bytes, str]:
    workbook = Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    buffer = BytesIO()
    workbook.save(buffer)
    return ("requirements.xlsx", buffer.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def test_requirement_import_preview_rejects_non_excel(client: TestClient):
    response = client.post(
        "/api/v1/requirements/import/preview",
        files={"file": ("requirements.csv", b"title", "text/csv")},
    )

    assert response.status_code == 422


def test_requirement_import_preview_reports_missing_required_cells(client: TestClient):
    response = client.post(
        "/api/v1/requirements/import/preview",
        files={"file": _xlsx([["项目名称", "需求标题"], ["", ""])}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["valid_count"] == 0
    assert data["error_count"] == 1
    assert data["errors"][0]["row_number"] == 2
    assert "项目名称" in data["errors"][0]["messages"]
    assert "需求标题" in data["errors"][0]["messages"]


def test_requirement_import_preview_detects_duplicate_title_in_project(client: TestClient):
    project_name = f"导入项目-{uuid4().hex[:8]}"
    project = client.post("/api/v1/projects", json={"name": project_name}).json()
    existing = client.post(
        "/api/v1/requirements",
        json={"project_id": project["id"], "title": "重复需求"},
    ).json()

    response = client.post(
        "/api/v1/requirements/import/preview",
        files={"file": _xlsx([["项目名称", "需求标题", "优先级"], [project_name, "重复需求", "3"]])},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["valid_count"] == 1
    assert data["duplicate_count"] == 1
    assert data["duplicates"][0]["row_number"] == 2
    assert data["duplicates"][0]["existing_requirement_id"] == existing["id"]
```

**Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest backend/tests/test_requirement_import_api.py -q
```

Expected: template test passes, preview tests fail with 404 or missing implementation.

**Step 3: Add response models**

In `backend/app/views/requirement_view.py`, add:

```python
class RequirementImportError(BaseModel):
    row_number: int
    messages: list[str]


class RequirementImportDuplicate(BaseModel):
    row_number: int
    project_id: int
    project_name: str
    title: str
    existing_requirement_id: int
    existing_requirement_title: str


class RequirementImportPreviewRead(BaseModel):
    valid_count: int
    error_count: int
    duplicate_count: int
    errors: list[RequirementImportError] = []
    duplicates: list[RequirementImportDuplicate] = []
```

**Step 4: Implement parser and preview**

In `requirement_import_service.py`, implement:

- `_load_workbook(file_bytes)`
- `_header_index(sheet)`
- `_cell_text(row, index, header)`
- project lookup by exact name, active and not deleted
- duplicate lookup by `(project_id, title)`
- `preview_requirement_import(db, file_bytes) -> dict`

Keep this minimal for first pass:

```python
from dataclasses import dataclass
from io import BytesIO

from fastapi import HTTPException, status
from openpyxl import load_workbook
from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.requirement import Requirement

REQUIRED_COLUMNS = ["项目名称", "需求标题"]


@dataclass
class ParsedRequirementRow:
    row_number: int
    project_id: int
    project_name: str
    title: str
    priority: str


def ensure_excel_filename(filename: str) -> None:
    if not filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="仅支持 .xlsx 文件")


def preview_requirement_import(db: Session, file_bytes: bytes) -> dict:
    parsed_rows, errors = _parse_requirement_rows(db, file_bytes)
    duplicates = _duplicate_rows(db, parsed_rows)
    return {
        "valid_count": len(parsed_rows),
        "error_count": len(errors),
        "duplicate_count": len(duplicates),
        "errors": errors,
        "duplicates": duplicates,
    }


def _parse_requirement_rows(db: Session, file_bytes: bytes) -> tuple[list[ParsedRequirementRow], list[dict]]:
    workbook = load_workbook(BytesIO(file_bytes), data_only=True)
    sheet = workbook.active
    headers = {str(cell.value).strip(): index for index, cell in enumerate(sheet[1]) if cell.value}
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in headers]
    if missing_columns:
        return [], [{"row_number": 1, "messages": [f"缺少列：{column}" for column in missing_columns]}]

    rows = []
    errors = []
    for row_number, row in enumerate(sheet.iter_rows(min_row=2), start=2):
        values = {header: _cell_text(row[index].value) for header, index in headers.items()}
        if not any(values.values()):
            continue
        messages = []
        project_name = values.get("项目名称", "")
        title = values.get("需求标题", "")
        if not project_name:
            messages.append("项目名称不能为空")
        if not title:
            messages.append("需求标题不能为空")
        project = None
        if project_name:
            project = db.query(Project).filter(Project.name == project_name, Project.deleted == 0).first()
            if not project:
                messages.append(f"项目不存在：{project_name}")
        priority = values.get("优先级") or "3"
        if priority not in {"1", "2", "3", "4", "5"}:
            messages.append("优先级必须是 1、2、3、4、5")
        if messages:
            errors.append({"row_number": row_number, "messages": messages})
            continue
        rows.append(ParsedRequirementRow(row_number, project.id, project.name, title, priority))
    return rows, errors


def _duplicate_rows(db: Session, rows: list[ParsedRequirementRow]) -> list[dict]:
    duplicates = []
    for row in rows:
        existing = (
            db.query(Requirement)
            .filter(Requirement.project_id == row.project_id, Requirement.title == row.title, Requirement.deleted == 0)
            .first()
        )
        if existing:
            duplicates.append({
                "row_number": row.row_number,
                "project_id": row.project_id,
                "project_name": row.project_name,
                "title": row.title,
                "existing_requirement_id": existing.id,
                "existing_requirement_title": existing.title,
            })
    return duplicates


def _cell_text(value) -> str:
    return str(value).strip() if value is not None else ""
```

**Step 5: Add preview endpoint**

In `requirement_controller.py`, import `File`, `UploadFile`, and preview service. Add:

```python
@router.post("/import/preview", response_model=RequirementImportPreviewRead)
async def preview_requirement_import_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    ensure_excel_filename(file.filename or "")
    return preview_requirement_import(db, await file.read())
```

**Step 6: Run tests**

```bash
python -m pytest backend/tests/test_requirement_import_api.py -q
```

Expected: PASS.

**Step 7: Commit**

```bash
git add backend/app/controllers/requirement_controller.py backend/app/services/requirement_import_service.py backend/app/views/requirement_view.py backend/tests/test_requirement_import_api.py
git commit -m "feat: preview requirement excel import"
```

---

### Task 4: Backend Commit Strategies

**Files:**
- Modify: `backend/app/services/requirement_import_service.py`
- Modify: `backend/app/controllers/requirement_controller.py`
- Modify: `backend/app/views/requirement_view.py`
- Test: `backend/tests/test_requirement_import_api.py`

**Step 1: Add failing commit tests**

Append:

```python
def test_requirement_import_commit_creates_new_requirements(client: TestClient):
    project_name = f"导入新增项目-{uuid4().hex[:8]}"
    project = client.post("/api/v1/projects", json={"name": project_name}).json()

    response = client.post(
        "/api/v1/requirements/import/commit",
        data={"duplicate_strategy": "create_duplicate"},
        files={"file": _xlsx([["项目名称", "需求标题", "优先级"], [project_name, "新需求", "2"]])},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["created_count"] == 1
    assert data["updated_count"] == 0
    created = client.get("/api/v1/requirements").json()[0]
    assert created["project_id"] == project["id"]
    assert created["title"] == "新需求"
    assert created["priority"] == "2"


def test_requirement_import_commit_updates_duplicate_requirement(client: TestClient):
    project_name = f"导入更新项目-{uuid4().hex[:8]}"
    project = client.post("/api/v1/projects", json={"name": project_name}).json()
    existing = client.post(
        "/api/v1/requirements",
        json={"project_id": project["id"], "title": "重复需求", "priority": "3"},
    ).json()

    response = client.post(
        "/api/v1/requirements/import/commit",
        data={"duplicate_strategy": "update_existing"},
        files={"file": _xlsx([["项目名称", "需求标题", "优先级"], [project_name, "重复需求", "1"]])},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["created_count"] == 0
    assert data["updated_count"] == 1
    updated = client.get(f"/api/v1/requirements/{existing['id']}").json()
    assert updated["priority"] == "1"
```

**Step 2: Run tests to verify failure**

```bash
python -m pytest backend/tests/test_requirement_import_api.py -q
```

Expected: commit tests fail with 404.

**Step 3: Add models**

In `requirement_view.py`:

```python
class RequirementImportCommitRead(BaseModel):
    created_count: int
    updated_count: int
    error_count: int
    errors: list[RequirementImportError] = []
```

**Step 4: Implement commit service**

In `requirement_import_service.py`, add:

```python
from app.services.lifecycle_service import project_lifecycle_phase


def commit_requirement_import(db: Session, file_bytes: bytes, duplicate_strategy: str) -> dict:
    if duplicate_strategy not in {"update_existing", "create_duplicate"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="未知重复处理策略")
    parsed_rows, errors = _parse_requirement_rows(db, file_bytes)
    if errors:
        return {"created_count": 0, "updated_count": 0, "error_count": len(errors), "errors": errors}
    created_count = 0
    updated_count = 0
    for row in parsed_rows:
        existing = (
            db.query(Requirement)
            .filter(Requirement.project_id == row.project_id, Requirement.title == row.title, Requirement.deleted == 0)
            .first()
        )
        if existing and duplicate_strategy == "update_existing":
            existing.priority = row.priority
            updated_count += 1
            continue
        db.add(Requirement(
            project_id=row.project_id,
            title=row.title,
            priority=row.priority,
            status="draft",
            review_status="not_required",
            lifecycle_phase=project_lifecycle_phase(db, row.project_id),
        ))
        created_count += 1
    db.commit()
    return {"created_count": created_count, "updated_count": updated_count, "error_count": 0, "errors": []}
```

**Step 5: Add endpoint**

```python
@router.post("/import/commit", response_model=RequirementImportCommitRead)
async def commit_requirement_import_file(
    duplicate_strategy: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    ensure_excel_filename(file.filename or "")
    return commit_requirement_import(db, await file.read(), duplicate_strategy)
```

**Step 6: Run tests**

```bash
python -m pytest backend/tests/test_requirement_import_api.py -q
```

Expected: PASS.

**Step 7: Commit**

```bash
git add backend/app/controllers/requirement_controller.py backend/app/services/requirement_import_service.py backend/app/views/requirement_view.py backend/tests/test_requirement_import_api.py
git commit -m "feat: commit requirement excel import"
```

---

### Task 5: Frontend API Client

**Files:**
- Modify: `frontend/src/api/requirements.js`

**Step 1: Add API functions**

Add:

```javascript
export function downloadRequirementImportTemplate() {
  return http.get('/requirements/import/template', { responseType: 'blob' })
}

export function previewRequirementImport(file) {
  const formData = new FormData()
  formData.append('file', file)
  return http.post('/requirements/import/preview', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

export function commitRequirementImport(file, duplicateStrategy) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('duplicate_strategy', duplicateStrategy)
  return http.post('/requirements/import/commit', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}
```

**Step 2: Run frontend build**

```bash
npm run build
```

Expected: PASS.

**Step 3: Commit**

```bash
git add frontend/src/api/requirements.js
git commit -m "feat: add requirement import api client"
```

---

### Task 6: Requirements Page UI

**Files:**
- Modify: `frontend/src/views/RequirementsView.vue`

**Step 1: Add toolbar buttons**

In page header, replace single create button with a compact action group:

```vue
<div class="page-actions">
  <el-button @click="downloadImportTemplate">下载模板</el-button>
  <el-button @click="openImportDialog">导入需求</el-button>
  <el-button type="primary" @click="openCreate">新增需求</el-button>
</div>
```

**Step 2: Add import dialog state**

Import API functions:

```javascript
import {
  activateRequirement,
  closeRequirement,
  commitRequirementImport,
  createRequirement,
  deleteRequirement,
  downloadRequirementImportTemplate,
  fetchRequirements,
  fetchRequirementStatusOperations,
  generateTask,
  previewRequirementImport,
  updateRequirement
} from '../api/requirements'
```

Add refs:

```javascript
const importVisible = ref(false)
const importFile = ref(null)
const importPreview = ref(null)
const duplicateStrategy = ref('')
```

**Step 3: Add methods**

```javascript
async function downloadImportTemplate() {
  const response = await downloadRequirementImportTemplate()
  const url = URL.createObjectURL(response.data)
  const link = document.createElement('a')
  link.href = url
  link.download = '需求导入模板.xlsx'
  link.click()
  URL.revokeObjectURL(url)
}

function openImportDialog() {
  importFile.value = null
  importPreview.value = null
  duplicateStrategy.value = ''
  importVisible.value = true
}

function onImportFileChange(file) {
  importFile.value = file.raw
  importPreview.value = null
}

async function submitImportPreview() {
  if (!importFile.value) return ElMessage.warning('请选择 Excel 文件')
  saving.value = true
  try {
    const { data } = await previewRequirementImport(importFile.value)
    importPreview.value = data
    if (data.error_count) return
    if (!data.duplicate_count) await submitImportCommit('create_duplicate')
  } finally {
    saving.value = false
  }
}

async function submitImportCommit(strategy = duplicateStrategy.value) {
  if (!importFile.value) return ElMessage.warning('请选择 Excel 文件')
  if (importPreview.value?.duplicate_count && !strategy) return ElMessage.warning('请选择重复处理方式')
  saving.value = true
  try {
    const { data } = await commitRequirementImport(importFile.value, strategy || 'create_duplicate')
    importVisible.value = false
    await loadData()
    ElMessage.success(`导入完成，新增 ${data.created_count} 条，更新 ${data.updated_count} 条`)
  } finally {
    saving.value = false
  }
}
```

**Step 4: Add dialog markup**

Add after existing dialogs:

```vue
<el-dialog v-model="importVisible" title="导入需求" width="720px">
  <el-upload
    :auto-upload="false"
    :limit="1"
    accept=".xlsx"
    :on-change="onImportFileChange"
  >
    <el-button>选择 Excel 文件</el-button>
  </el-upload>

  <div v-if="importPreview" class="import-preview">
    <p>有效 {{ importPreview.valid_count }} 行，失败 {{ importPreview.error_count }} 行，重复 {{ importPreview.duplicate_count }} 行</p>
    <el-table v-if="importPreview.errors.length" :data="importPreview.errors" size="small">
      <el-table-column prop="row_number" label="行号" width="80" />
      <el-table-column label="错误">
        <template #default="{ row }">{{ row.messages.join('；') }}</template>
      </el-table-column>
    </el-table>
    <template v-if="importPreview.duplicates.length">
      <el-radio-group v-model="duplicateStrategy">
        <el-radio label="update_existing">更新已有需求</el-radio>
        <el-radio label="create_duplicate">重复创建</el-radio>
      </el-radio-group>
      <el-table :data="importPreview.duplicates" size="small">
        <el-table-column prop="row_number" label="行号" width="80" />
        <el-table-column prop="project_name" label="项目" />
        <el-table-column prop="title" label="需求标题" />
        <el-table-column prop="existing_requirement_id" label="已有ID" width="90" />
      </el-table>
    </template>
  </div>

  <template #footer>
    <el-button @click="importVisible = false">取消</el-button>
    <el-button type="primary" :loading="saving" @click="submitImportPreview">预检</el-button>
    <el-button
      v-if="importPreview && !importPreview.error_count && importPreview.duplicate_count"
      type="success"
      :loading="saving"
      @click="submitImportCommit()"
    >
      确认导入
    </el-button>
  </template>
</el-dialog>
```

**Step 5: Run frontend build**

```bash
npm run build
```

Expected: PASS.

**Step 6: Commit**

```bash
git add frontend/src/views/RequirementsView.vue
git commit -m "feat: add requirement import UI"
```

---

### Task 7: Full Verification

**Files:**
- No code changes expected.

**Step 1: Backend targeted tests**

Run:

```bash
python -m pytest backend/tests/test_requirement_import_api.py backend/tests/test_requirement_task_api.py -q
```

Expected: import tests pass. If an unrelated existing test fails, document it with the exact failure and rerun the import test file alone.

**Step 2: Frontend build**

Run:

```bash
npm run build
```

Expected: PASS.

**Step 3: Optional manual smoke test**

Start backend and frontend if not already running. In requirements page:

1. Download template.
2. Fill a row with an existing project name and new title.
3. Upload and preview.
4. Confirm it imports.
5. Upload a row with the same project and title.
6. Confirm duplicate dialog appears.

**Step 4: Final commit if needed**

```bash
git status --short
```

Commit any verification-only fixes with a focused message.
