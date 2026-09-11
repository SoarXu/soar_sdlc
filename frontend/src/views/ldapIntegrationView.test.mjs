import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const view = await readFile(new URL('./LdapIntegrationView.vue', import.meta.url), 'utf8')
const api = await readFile(new URL('../api/ldap.js', import.meta.url), 'utf8')

test('LDAP API follows the saved-config directory and sync contracts', () => {
  assert.match(api, /testLdapConnection\(\) \{ return http\.post\('\/admin\/ldap\/test'\) \}/)
  assert.match(api, /fetchLdapDirectoryUsers\(params\).*http\.get\('\/admin\/ldap\/directory-users', \{ params \}\)/)
  assert.match(api, /syncLdapUsers\(items\).*http\.post\('\/admin\/ldap\/sync', \{ items \}, \{ timeout: 900000 \}\)/)
  assert.match(api, /syncBoundLdapUsers\(\).*http\.post\('\/admin\/ldap\/sync-bound-users', null, \{ timeout: 900000 \}\)/)
  assert.match(api, /fetchLdapSyncRuns\(params\).*http\.get\('\/admin\/ldap\/sync-runs', \{ params \}\)/)
})

test('page exposes three connection configuration groups and all AD default mappings', () => {
  for (const title of ['连接设置', '查询账号', '字段映射']) assert.match(view, new RegExp(title))
  for (const value of ['sAMAccountName', 'employeeID', 'displayName', 'mail', 'mobile', 'department', 'objectGUID']) {
    assert.match(view, new RegExp(value))
  }
  assert.match(view, /autocomplete="new-password"/)
  assert.match(view, /留空保留已保存密码/)
  assert.match(view, /connectionIdentityChanged/)
  assert.match(view, /修改连接身份后需重新输入绑定密码/)
})

test('AD user filter stays internal instead of being administrator-configurable', () => {
  assert.doesNotMatch(view, /label="用户筛选器"/)
  assert.doesNotMatch(view, /user_filter:\s*\[\{ required:/)
  assert.match(view, /user_filter: '\(&\(objectCategory=person\)\(objectClass=user\)\)'/)
})

test('directory query controls live above the AD list and apply without saving config', () => {
  assert.doesNotMatch(view, /<h3>用户查询<\/h3>/)
  const controls = view.indexOf('class="directory-query-controls"')
  const table = view.indexOf('<el-table ref="directoryTableRef"')
  assert.ok(controls > view.indexOf('class="directory-heading"'))
  assert.ok(table > controls)
  for (const label of ['用户 Base DN', '排除禁用账号', '每页数量']) assert.match(view, new RegExp(label))
  assert.match(view, /const directoryQuery = reactive/)
  assert.match(view, /user_base_dn: appliedDirectoryQuery\.user_base_dn/)
  assert.match(view, /exclude_disabled: appliedDirectoryQuery\.exclude_disabled/)
})

test('page uses stable responsive workbench layout and ready empty state', () => {
  assert.match(view, /class="ldap-workbench"/)
  assert.match(view, /grid-template-columns:\s*minmax\(0,\s*44fr\) minmax\(0,\s*56fr\)/)
  assert.match(view, /class="page-action-column page-action-right"/)
  assert.match(view, /\.ldap-page \.page-actions \{[^}]*grid-template-columns:\s*minmax\(0,\s*44fr\) minmax\(0,\s*56fr\)/)
  assert.match(view, /\.page-action-right \{[^}]*justify-content:\s*space-between/)
  assert.match(view, /@media \(max-width: 900px\)/)
  assert.match(view, /v-if="!directoryReady"/)
  assert.match(view, /保存并测试配置后可查询目录用户/)
})

test('desktop keeps LDAP scrolling inside each panel and restores page flow on narrow screens', () => {
  assert.match(view, /\.ldap-page \{[^}]*height:\s*100%[^}]*overflow:\s*hidden/)
  assert.match(view, /\.ldap-workbench \{[^}]*height:\s*100%[^}]*min-height:\s*0/)
  assert.match(view, /\.config-panel \{[^}]*overflow-y:\s*auto/)
  assert.match(view, /<el-table[^>]*height="100%"/)
  assert.match(view, /@media \(max-width: 900px\)[\s\S]*?\.ldap-page \{[^}]*height:\s*auto[^}]*overflow:\s*visible/)
})

test('directory table covers selection identity matching and all statuses', () => {
  assert.match(view, /type="selection"/)
  for (const label of ['姓名', '账号', '工号', '部门', '邮箱', '同步状态']) {
    assert.match(view, new RegExp(`label="${label}"`))
  }
  assert.doesNotMatch(view, /label="SDLC 匹配"/)
  for (const pair of [
    ['unlinked', '未同步'], ['match_suggested', '可绑定'], ['linked', '已同步'],
    ['conflict', '冲突'], ['ad_disabled', 'AD 已禁用'],
  ]) {
    assert.match(view, new RegExp(`${pair[0]}[\\s\\S]*?${pair[1]}`))
  }
  assert.match(view, /selectableDirectoryUser/)
  assert.match(view, /!\['conflict', 'ad_disabled'\]\.includes\(row\.sync_status\)/)
})

test('sync status column preserves suggested match and tooltip details', () => {
  assert.match(view, /row\.sync_status === 'match_suggested' && row\.matched_user/)
  assert.match(view, /class="matched-user"/)
  assert.match(view, /statusTooltip\(row\)/)
  assert.match(view, /已关联：/)
})

test('status column accommodates the fixed-width status tag without ellipsis', () => {
  assert.match(view, /<el-table-column label="同步状态" min-width="160">/)
  assert.match(view, /\.directory-panel :deep\(\.el-tag\) \{ width: 82px;/)
})

test('sync decisions confirm suggested binding and refresh after completion', () => {
  assert.match(view, /sync_status === 'unlinked'.*decision: 'create'/s)
  assert.match(view, /sync_status === 'linked'.*decision: 'update'/s)
  assert.match(view, /sync_status === 'match_suggested'.*decision: 'bind'.*user_id: row\.matched_user\.id/s)
  assert.match(view, /ElMessageBox\.confirm/)
  assert.match(view, /row\.matched_user\.username/)
  assert.match(view, /clearSelection\(\)/)
  assert.match(view, /await loadDirectory\(\{ reset: true \}\)/)
})

test('cursor pagination maintains a back stack and resets on search', () => {
  assert.match(view, /const cursorStack = ref\(\[\]\)/)
  assert.match(view, /cursorStack\.value\.push\(currentCursor\.value\)/)
  assert.match(view, /if \(loaded\) \{ cursorStack\.value\.pop\(\); currentCursor\.value = targetCursor \}/)
  assert.match(view, /cursorStack\.value = \[\]/)
  assert.match(view, /nextCursor\.value/)
})

test('directory pagination omits unavailable total counts', () => {
  assert.doesNotMatch(view, /directoryTotal/)
  assert.doesNotMatch(view, /directoryPageCount/)
  assert.doesNotMatch(view, /总数未知/)
  assert.match(view, /第 \{\{ cursorStack\.length \+ 1 \}\} 页/)
})

test('page provides bound-user sync and paged safe history UI', () => {
  assert.match(view, /syncBoundLdapUsers/)
  assert.match(view, /fetchLdapSyncRuns/)
  assert.match(view, /<el-drawer/)
  assert.match(view, /同步历史/)
  assert.match(view, /historyPage/)
  assert.match(view, /historyPageSize/)
})

test('changed config is tested disabled while unchanged ready config stays enabled', () => {
  assert.match(view, /const requestedEnabled = form\.enabled/)
  assert.match(view, /const needsStaging = configurationChanged\.value \|\| !form\.configuration_tested \|\| Boolean\(form\.bind_password\)/)
  assert.match(view, /if \(needsStaging\) await persistConfig\(false\)[\s\S]*await testLdapConnection\(\)[\s\S]*if \(needsStaging && requestedEnabled\)[\s\S]*await persistConfig\(true\)/)
})

test('sync requests use a dedicated long-running timeout', () => {
  assert.match(api, /syncLdapUsers\(items\).*timeout: 900000/)
  assert.match(api, /syncBoundLdapUsers\(\).*timeout: 900000/)
})

test('directory readiness follows persisted enablement instead of the unsaved switch', () => {
  assert.match(view, /const persistedEnabled = ref\(false\)/)
  assert.match(view, /const directoryReady = computed\(\(\) => Boolean\(persistedEnabled\.value && form\.configuration_tested\)\)/)
  assert.match(view, /const enablementChanged = form\.enabled !== persistedEnabled\.value/)
})

test('directory requests discard stale responses and commit cursor state after success', () => {
  assert.match(view, /let directoryRequestId = 0/)
  assert.match(view, /const requestId = \+\+directoryRequestId/)
  assert.match(view, /if \(requestId !== directoryRequestId\) return false/)
  assert.match(view, /const loaded = await loadDirectory\(\{ cursor: targetCursor \}\)[\s\S]*if \(loaded\)[\s\S]*cursorStack\.value\.push/)
})

test('configuration actions are mutually exclusive and binding cancel is handled', () => {
  assert.match(view, /:disabled="testing"[^>]*@click="saveConfig"/)
  assert.match(view, /:disabled="saving"[^>]*@click="testConnection"/)
  assert.match(view, /catch \(error\) \{ if \(error !== 'cancel' && error !== 'close'\)/)
  assert.match(view, /const configBusy = ref\(false\)/)
  assert.match(view, /if \(configBusy\.value\) return; configBusy\.value = true; saving\.value = true; try \{ await formRef\.value\.validate\(\)/)
  assert.match(view, /if \(configBusy\.value\) return; configBusy\.value = true; testing\.value = true; try \{ await formRef\.value\.validate\(\)/)
})
