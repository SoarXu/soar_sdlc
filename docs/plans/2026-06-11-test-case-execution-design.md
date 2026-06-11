# Test Case Execution Design

## Goal

Remove test case priority from business screens and add direct test case execution with per-step results and execution history.

## Confirmed Rules

- Test cases do not need priority.
- Priority is removed from frontend lists, dialogs, PRD, and backend API exposure.
- Existing physical `test_cases.priority` can remain for compatibility, but the application no longer uses it.
- Test cases support an Execute action.
- Executing a test case records:
  - execution time
  - overall result
  - per-step result
  - per-step actual situation
  - executor
- Result options are `ignored`, `passed`, `failed`, and `blocked`.
- Overall result is automatically calculated:
  - any failed step -> failed
  - otherwise any blocked step -> blocked
  - otherwise all ignored -> ignored
  - otherwise passed
- Each execution creates a history record.
- Saving an execution updates the test case list's latest execution time and latest execution result.

## Data Model

Add to `test_cases`:

- `last_execute_time DATETIME NULL`
- `last_execute_result VARCHAR(32) NULL`

Create `test_case_execution_log`:

- `id BIGINT UNSIGNED PK`
- `test_case_id BIGINT UNSIGNED NOT NULL`
- `executor_id BIGINT UNSIGNED NULL`
- `execute_time DATETIME NOT NULL`
- `result VARCHAR(32) NOT NULL`
- `steps_result_json JSON NULL`
- `create_time DATETIME NOT NULL`

## API Shape

- `POST /api/v1/test-cases/{id}/executions`
  - Body: `{ executor_id, execute_time, steps_result_json }`
  - Calculates overall result and updates the test case latest execution fields.
- `GET /api/v1/test-cases/{id}/executions`
  - Returns execution history ordered by latest first.

## Frontend

The execution dialog opens from test case lists in:

- project detail test cases
- global test management
- iteration detail test cases

The dialog shows:

- test case title
- step table with step, expected, result, actual
- save button
- execution history with expandable step details

## Verification

- Backend tests cover execution result calculation and latest execution field updates.
- Frontend build verifies page wiring.
