export function releaseStatus(frontendVersion, backend) {
  if (!backend) return '版本信息无法获取'
  if (frontendVersion !== backend.app_version) return '版本不一致'
  return '一致'
}
