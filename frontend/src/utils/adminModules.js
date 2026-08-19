export const adminModules = [
  {
    key: 'roles',
    title: '\u7528\u6237\u7ba1\u7406',
    description: '\u7ef4\u62a4\u7cfb\u7edf\u7528\u6237\u4e0e\u7cfb\u7edf\u7ba1\u7406\u5458\u6743\u9650\u3002',
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
