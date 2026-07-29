# Project Close Blocker Message Design

## Goal

When a project cannot close because it has an unfinished iteration, show a short Chinese warning message that disappears automatically instead of opening a second modal over the close-project form.

## Chosen Interaction

- Keep the close-project dialog open after the failed request.
- Detect the existing project-close API blocker response that includes `unfinished iteration`.
- Display Element Plus `ElMessage.warning` at its normal top-center position.
- Use the short Chinese copy: `项目存在未结束迭代，无法关闭。`
- Let Element Plus use its normal automatic-dismiss behavior; no acknowledgement is required.
- Preserve the existing error-dialog feedback for unrelated project-status failures.

## Verification

- Add a focused frontend source-contract test that requires the iteration blocker to use `ElMessage.warning` with the Chinese copy.
- The same test must ensure that this blocker branch does not call the modal-based `showActionError` helper.
- Run the focused test, the complete frontend test suite, and a production frontend build.
