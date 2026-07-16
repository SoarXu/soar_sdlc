export const adminModules = [
  {
    key: 'roles',
    title: '\u89d2\u8272\u7ba1\u7406',
    description: '\u7ef4\u62a4\u4e1a\u52a1\u89d2\u8272\uff0c\u5e76\u7ed9\u7528\u6237\u5206\u914d\u89d2\u8272\u3002',
    navGroupPath: '/admin',
    path: '/roles'
  },
  {
    key: 'workflow',
    title: '\u5de5\u4f5c\u6d41\u914d\u7f6e',
    description: '\u7ef4\u62a4\u5de5\u4f5c\u6d41\u65b9\u6848\u548c\u9879\u76ee\u7ed1\u5b9a\u5173\u7cfb\u3002',
    navGroupPath: '/admin',
    path: '/workflow'
  },
  {
    key: 'exception_rules',
    title: '异常规则',
    description: '配置工作台异常识别阈值与适用范围。',
    navGroupPath: '/admin',
    path: '/exception-rules'
  }
]

const ADMIN_PATHS = new Set(['/admin', ...adminModules.map((item) => item.path)])

export function isAdminPath(path) {
  return ADMIN_PATHS.has(path)
}

export function activeAdminMenuIndex(path) {
  return isAdminPath(path) ? '/admin' : null
}
