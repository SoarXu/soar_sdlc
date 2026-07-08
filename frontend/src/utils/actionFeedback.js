import { ElMessageBox } from 'element-plus'

import { actionErrorMessage } from './permissions'

export function showActionError(error, fallback = '操作失败') {
  return ElMessageBox.alert(actionErrorMessage(error, fallback), '提示', { type: 'warning' })
}
