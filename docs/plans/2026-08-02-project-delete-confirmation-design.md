# Project Delete Confirmation Design

## Goal

Make project deletion use the same centered confirmation dialog as project-set
deletion, while keeping the existing project deletion warning text unchanged.

## Design

Replace the row-local `el-popconfirm` in `ProjectsView` with a delete button
that calls `confirmRemoveProject`. The new function will await
`ElMessageBox.confirm('确认删除该项目？子项目将一并删除。', '提示', { type: 'warning' })`
before delegating to the existing `removeProject` function. Cancellation keeps
the existing row and performs no request.

## Testing

Add a source-contract test requiring the button handler, the exact confirmation
message, warning style, and delegation to `removeProject`.
