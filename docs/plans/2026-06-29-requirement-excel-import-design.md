# Requirement Excel Import Design

## Goal

Add a fixed-template Excel import flow for requirements. Users can download the template from the requirements page, fill it offline, upload it, preview validation results, and import rows into the system.

## Template

The backend generates the Excel template so the downloadable file stays aligned with backend parsing rules.

Columns:

- 项目名称
- 来源项目名称
- 迭代名称
- 需求标题
- 类型
- 优先级
- 负责人
- 提出人
- 评审状态
- 需求描述
- 验收标准

Required fields:

- 项目名称
- 需求标题

Optional fields use the same defaults as normal requirement creation. Imported requirements start as `draft`.

## Import Flow

The import is a two-stage flow.

1. User uploads an Excel file from the requirements page.
2. Backend parses and validates the file without writing data.
3. Backend returns row-level validation results and duplicate matches.
4. If there are validation errors, the frontend shows them and blocks import.
5. If there are no duplicate requirements, the frontend can run import immediately.
6. If duplicate requirements exist, the frontend opens a confirmation dialog listing duplicate rows. A duplicate is defined as the same project and same requirement title.
7. User chooses one duplicate strategy:
   - `update_existing`: update the matched existing requirement for duplicate rows, and create new requirements for non-duplicate rows.
   - `create_duplicate`: create all valid rows as new requirements, including duplicate titles.
   - cancel: do not write anything.

## Backend API

Add endpoints under `/api/v1/requirements/import`.

- `GET /template`
  - Returns the Excel template as an `.xlsx` file.

- `POST /preview`
  - Accepts multipart Excel upload.
  - Parses and validates rows.
  - Does not write to the database.
  - Returns valid rows, row errors, and duplicate matches.

- `POST /commit`
  - Accepts the same Excel upload plus duplicate strategy.
  - Re-runs parsing and validation server-side.
  - Writes valid rows according to strategy.
  - Returns created count, updated count, failed rows, and duplicate decisions.

Preview and commit both parse the uploaded file independently. The server does not trust frontend preview state.

## Validation

Validation rules:

- File must be `.xlsx`.
- Required columns must exist.
- Required cells must not be blank.
- Project name must resolve to exactly one active project.
- Source project name, if present, must resolve to exactly one active project.
- Iteration name, if present, must resolve to exactly one active iteration and must include the target project in scope.
- Owner and proposer names, if present, must resolve to exactly one active user by full name or username.
- Priority must be one of `1`, `2`, `3`, `4`, `5`.
- Review status must be one of the supported values or display labels.

Rows with validation errors are not imported. Duplicate rows are valid rows that require a strategy decision.

## Frontend

On the requirements page:

- Add `下载模板` button.
- Add `导入需求` button.
- Upload dialog accepts only `.xlsx`.
- Preview result dialog shows:
  - valid row count
  - failed row count with row-level messages
  - duplicate row list with row number, project name, requirement title, and existing requirement ID/title
- If duplicates exist, require the user to choose `更新已有需求` or `重复创建`.

After import succeeds, refresh the requirements list and show created/updated counts.

## Tests

Backend tests cover:

- Template endpoint returns an Excel file.
- Preview rejects invalid file type.
- Preview reports missing required cells.
- Preview resolves project, iteration, and users.
- Preview detects same-project same-title duplicates.
- Commit creates rows when no duplicates exist.
- Commit updates existing rows with `update_existing`.
- Commit creates duplicate rows with `create_duplicate`.

Frontend verification covers:

- Build succeeds.
- Requirements page exposes template download and import controls.
- Duplicate confirmation dialog displays duplicate rows and strategy choices.
