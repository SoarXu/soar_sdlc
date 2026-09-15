export function releaseStatus(frontend, backend) {
  if (!backend) return '后端不可用'
  if (frontend.version !== backend.app_version) return '版本不一致'
  if (Boolean(frontend.commit) !== Boolean(backend.git_commit)) return '构建未确认'
  if (frontend.commit && backend.git_commit && frontend.commit !== backend.git_commit) return '构建不一致'
  return '一致'
}
