<template>
  <section class="page ldap-page">
    <div class="page-head">
      <div><h1>LDAP 集成</h1><p>连接 AD 域，选择员工同步到 SDLC 用户目录。</p></div>
      <div class="page-actions">
        <div class="page-action-column"><el-button @click="router.push('/admin')">返回后台管理</el-button></div>
        <div class="page-action-column page-action-right">
          <el-button :icon="Clock" @click="openHistory">同步历史</el-button>
          <el-button :icon="Refresh" :loading="syncingBound" @click="syncBoundUsers">同步已导入用户</el-button>
        </div>
      </div>
    </div>

    <div class="ldap-workbench">
      <section class="config-panel" v-loading="loading">
        <div class="panel-heading"><div><h2>目录配置</h2><span :class="['readiness', directoryReady ? 'is-ready' : '']">{{ directoryReady ? '连接已验证' : '尚未验证' }}</span></div></div>
        <el-form ref="formRef" :model="form" :rules="rules" label-position="top" size="default">
          <div class="config-section"><h3>连接设置</h3><div class="form-grid">
            <el-form-item label="启用 LDAP"><el-switch v-model="form.enabled" /></el-form-item>
            <el-form-item label="协议"><el-segmented v-model="form.protocol" :options="protocolOptions" @change="handleProtocolChange" /></el-form-item>
            <el-form-item label="服务器地址" prop="host"><el-input v-model="form.host" placeholder="dc01.company.com" /></el-form-item>
            <el-form-item label="端口" prop="port"><el-input-number v-model="form.port" :min="1" :max="65535" controls-position="right" /></el-form-item>
            <el-form-item class="span-2" label="Base DN" prop="base_dn"><el-input v-model="form.base_dn" placeholder="DC=company,DC=com" /></el-form-item>
            <el-form-item label="连接超时（秒）"><el-input-number v-model="form.connect_timeout" :min="1" :max="30" controls-position="right" /></el-form-item>
          </div></div>

          <div class="config-section"><h3>查询账号</h3><div class="form-grid">
            <el-form-item label="绑定账号" prop="bind_username"><el-input v-model="form.bind_username" placeholder="svc_sdlc@company.com" /></el-form-item>
            <el-form-item label="绑定密码" :required="!form.has_bind_password"><el-input v-model="form.bind_password" type="password" show-password autocomplete="new-password" placeholder="留空保留已保存密码" /></el-form-item>
            <div v-if="connectionIdentityChanged" class="identity-warning span-2">修改连接身份后需重新输入绑定密码</div>
          </div></div>

          <div class="config-section"><h3>字段映射</h3><div class="mapping-grid">
            <el-form-item label="用户名"><el-input v-model="form.username_attribute" placeholder="sAMAccountName" /></el-form-item>
            <el-form-item label="工号"><el-input v-model="form.employee_no_attribute" placeholder="employeeID" /></el-form-item>
            <el-form-item label="姓名"><el-input v-model="form.full_name_attribute" placeholder="displayName" /></el-form-item>
            <el-form-item label="邮箱"><el-input v-model="form.email_attribute" placeholder="mail" /></el-form-item>
            <el-form-item label="手机号"><el-input v-model="form.mobile_attribute" placeholder="mobile" /></el-form-item>
            <el-form-item label="部门"><el-input v-model="form.department_attribute" placeholder="department" /></el-form-item>
            <el-form-item class="span-2" label="唯一标识"><el-input v-model="form.external_id_attribute" placeholder="objectGUID" /></el-form-item>
          </div></div>
        </el-form>
        <div class="config-actions"><el-button :loading="testing" :disabled="saving" @click="testConnection">测试连接</el-button><el-button type="primary" :loading="saving" :disabled="testing" @click="saveConfig">保存配置</el-button></div>
      </section>

      <section class="directory-panel">
        <div class="panel-heading directory-heading"><div><h2>AD 域用户</h2><span>从目录选择需要进入 SDLC 的员工</span></div><el-button type="primary" :icon="Upload" :disabled="!selectedRows.length" :loading="syncing" @click="syncSelected">同步所选</el-button></div>
        <div class="directory-query-controls">
          <label class="directory-query-field directory-query-base"><span>用户 Base DN</span><el-input v-model="directoryQuery.user_base_dn" :disabled="!directoryReady || directoryLoading" placeholder="留空查询整个域" /></label>
          <label class="directory-query-field"><span>排除禁用账号</span><el-switch v-model="directoryQuery.exclude_disabled" :disabled="!directoryReady || directoryLoading" /></label>
          <label class="directory-query-field"><span>每页数量</span><el-input-number v-model="directoryQuery.page_size" :disabled="!directoryReady || directoryLoading" :min="10" :max="200" :step="10" controls-position="right" /></label>
        </div>
        <template v-if="!directoryReady"><el-empty description="保存并测试配置后可查询目录用户" :image-size="72" /></template>
        <template v-else>
          <div class="directory-toolbar"><el-input v-model="keyword" clearable :disabled="directoryLoading" :prefix-icon="Search" placeholder="搜索姓名、账号或工号" @keyup.enter="searchDirectory" @clear="searchDirectory" /><el-button :icon="Search" :disabled="directoryLoading" @click="searchDirectory">查询</el-button><el-button :icon="Refresh" :loading="directoryLoading" @click="loadDirectory({ reset: true })">刷新</el-button></div>
          <el-table ref="directoryTableRef" v-loading="directoryLoading" :data="directoryUsers" row-key="external_id" height="100%" @selection-change="selectedRows = $event">
            <el-table-column type="selection" width="44" :selectable="selectableDirectoryUser" />
            <el-table-column prop="full_name" label="姓名" min-width="100" show-overflow-tooltip />
            <el-table-column prop="username" label="账号" min-width="120" show-overflow-tooltip />
            <el-table-column prop="employee_no" label="工号" min-width="92" show-overflow-tooltip />
            <el-table-column prop="department" label="部门" min-width="110" show-overflow-tooltip />
            <el-table-column prop="email" label="邮箱" min-width="150" show-overflow-tooltip />
            <el-table-column label="同步状态" min-width="220"><template #default="{ row }"><div class="sync-status-cell"><el-tooltip :content="statusTooltip(row)" :disabled="!statusTooltip(row)"><el-tag :type="statusMap[row.sync_status].type" effect="plain">{{ statusMap[row.sync_status].label }}</el-tag></el-tooltip><span v-if="row.sync_status === 'match_suggested' && row.matched_user" class="matched-user">{{ row.matched_user.full_name }} / {{ row.matched_user.username }}</span><el-button v-if="['unlinked', 'match_suggested'].includes(row.sync_status)" link type="primary" size="small" @click="openBindDialog(row)">绑定 SDLC 用户</el-button></div></template></el-table-column>
          </el-table>
          <div class="cursor-pagination"><el-button :icon="ArrowLeft" :disabled="directoryLoading || !cursorStack.length" @click="previousPage">上一页</el-button><span>第 {{ cursorStack.length + 1 }} 页</span><el-button :disabled="directoryLoading || !nextCursor" @click="nextPage">下一页<el-icon class="el-icon--right"><ArrowRight /></el-icon></el-button></div>
        </template>
      </section>
    </div>

    <el-dialog v-model="bindDialogVisible" title="绑定 SDLC 用户" width="min(560px, 92vw)" @closed="resetBindDialog">
      <div class="bind-directory-user">AD 用户：{{ bindSource?.full_name || '-' }} / {{ bindSource?.username || '-' }}</div>
      <el-input v-model="bindUserKeyword" clearable placeholder="搜索姓名、账号或工号" />
      <el-radio-group v-model="bindTargetId" class="bind-user-list" v-loading="bindLoading">
        <el-radio v-for="user in filteredBindUsers" :key="user.id" :label="user.id"><span>{{ user.full_name }} / {{ user.username }}</span><small>{{ user.employee_no || '无工号' }} · {{ user.auth_source === 'ldap' ? 'AD 用户' : '本地用户' }}</small></el-radio>
      </el-radio-group>
      <template #footer><el-button @click="bindDialogVisible = false">取消</el-button><el-button type="primary" :loading="binding" :disabled="!bindTargetId" @click="confirmBind">确认绑定</el-button></template>
    </el-dialog>

    <el-drawer v-model="historyVisible" title="同步历史" size="min(620px, 92vw)"><el-table v-loading="historyLoading" :data="syncRuns"><el-table-column prop="started_at" label="执行时间" min-width="168" /><el-table-column prop="status" label="状态" width="110" /><el-table-column prop="total_count" label="总数" width="72" /><el-table-column prop="failed_count" label="失败" width="72" /><el-table-column prop="error_summary" label="错误摘要" min-width="180" show-overflow-tooltip /></el-table><el-pagination v-model:current-page="historyPage" :page-size="historyPageSize" :total="historyTotal" layout="prev, pager, next" @current-change="loadHistory" /></el-drawer>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, ArrowRight, Clock, Refresh, Search, Upload } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { fetchLdapBindUsers, fetchLdapConfig, fetchLdapDirectoryUsers, fetchLdapSyncRuns, saveLdapConfig, syncBoundLdapUsers, syncLdapUsers, testLdapConnection } from '../api/ldap'
import { actionErrorMessage } from '../utils/permissions'

const router = useRouter()
const formRef = ref(); const directoryTableRef = ref()
const loading = ref(false); const saving = ref(false); const testing = ref(false); const directoryLoading = ref(false); const syncing = ref(false); const syncingBound = ref(false)
const configBusy = ref(false)
const keyword = ref(''); const directoryUsers = ref([]); const selectedRows = ref([])
const appliedKeyword = ref('')
const directoryQuery = reactive(defaultDirectoryQuery())
const appliedDirectoryQuery = reactive(defaultDirectoryQuery())
const currentCursor = ref(null); const nextCursor = ref(null); const cursorStack = ref([])
const historyVisible = ref(false); const historyLoading = ref(false); const syncRuns = ref([]); const historyPage = ref(1); const historyPageSize = 20; const historyTotal = ref(0)
const bindDialogVisible = ref(false); const bindLoading = ref(false); const binding = ref(false); const bindUsers = ref([]); const bindUserKeyword = ref(''); const bindTargetId = ref(null); const bindSource = ref(null)
const savedIdentity = ref(null)
const savedConfiguration = ref(null)
const persistedEnabled = ref(false)
let directoryRequestId = 0
const form = reactive(defaultForm())
const protocolOptions = [{ label: 'LDAP + StartTLS', value: 'ldap' }, { label: 'LDAPS', value: 'ldaps' }]
const rules = { host: [{ required: true, message: '请输入服务器地址', trigger: 'blur' }], port: [{ required: true, message: '请输入端口', trigger: 'change' }], base_dn: [{ required: true, message: '请输入 Base DN', trigger: 'blur' }], bind_username: [{ required: true, message: '请输入绑定账号', trigger: 'blur' }] }
const statusMap = { unlinked: { label: '未同步', type: 'info' }, match_suggested: { label: '可绑定', type: 'warning' }, linked: { label: '已同步', type: 'success' }, conflict: { label: '冲突', type: 'danger' }, ad_disabled: { label: 'AD 已禁用', type: 'info' } }
const directoryReady = computed(() => Boolean(persistedEnabled.value && form.configuration_tested))
const connectionIdentityChanged = computed(() => Boolean(savedIdentity.value && savedIdentity.value !== identityKey() && !form.bind_password))
const configurationChanged = computed(() => savedConfiguration.value !== configurationKey())
const filteredBindUsers = computed(() => { const keywordValue = bindUserKeyword.value.trim().toLowerCase(); if (!keywordValue) return bindUsers.value; return bindUsers.value.filter(user => [user.full_name, user.username, user.employee_no].some(value => String(value || '').toLowerCase().includes(keywordValue))) })

function defaultForm() { return { enabled: false, protocol: 'ldaps', host: '', port: 636, connect_timeout: 5, base_dn: '', bind_username: '', bind_password: '', has_bind_password: false, user_base_dn: '', user_filter: '(&(objectCategory=person)(objectClass=user))', exclude_disabled: true, page_size: 50, username_attribute: 'sAMAccountName', employee_no_attribute: 'employeeID', full_name_attribute: 'displayName', email_attribute: 'mail', mobile_attribute: 'mobile', department_attribute: 'department', external_id_attribute: 'objectGUID', configuration_tested: false } }
function defaultDirectoryQuery() { return { user_base_dn: '', exclude_disabled: true, page_size: 50 } }
function identityKey() { return [form.protocol, form.host.trim(), form.port, form.bind_username.trim()].join('|') }
function payload() { const value = { ...form }; delete value.has_bind_password; delete value.configuration_tested; delete value.tested_at; if (!value.bind_password) delete value.bind_password; value.user_base_dn = value.user_base_dn?.trim() || null; value.user_filter = '(&(objectCategory=person)(objectClass=user))'; return value }
function configurationKey() { const value = payload(); delete value.enabled; delete value.bind_password; return JSON.stringify(value) }
function handleProtocolChange(value) { if (value === 'ldaps' && form.port === 389) form.port = 636; else if (value === 'ldap' && form.port === 636) form.port = 389 }
function selectableDirectoryUser(row) { return Boolean(row.external_id) && !['conflict', 'ad_disabled'].includes(row.sync_status) }
function statusTooltip(row) { if (row.conflict_reason) return row.conflict_reason; if (row.sync_status === 'linked' && row.matched_user) return `已关联：${row.matched_user.full_name} / ${row.matched_user.username}`; return '' }
async function openBindDialog(row) { bindSource.value = row; bindTargetId.value = row.matched_user?.id || null; bindUserKeyword.value = ''; bindDialogVisible.value = true; bindLoading.value = true; try { bindUsers.value = (await fetchLdapBindUsers()).data || [] } catch (error) { bindDialogVisible.value = false; ElMessage.error(actionErrorMessage(error)) } finally { bindLoading.value = false } }
function resetBindDialog() { bindSource.value = null; bindTargetId.value = null; bindUserKeyword.value = ''; bindUsers.value = [] }
async function confirmBind() { if (!bindSource.value || !bindTargetId.value || binding.value) return; binding.value = true; try { const { data } = await syncLdapUsers([{ external_id: bindSource.value.external_id, decision: 'bind', user_id: bindTargetId.value }]); const item = data.items?.[0]; if (item?.status === 'failed') throw new Error(item.message || '绑定失败'); ElMessage.success('LDAP 用户绑定成功'); bindDialogVisible.value = false; await loadDirectory({ reset: true }) } catch (error) { ElMessage.error(error?.message || actionErrorMessage(error)) } finally { binding.value = false } }

async function loadConfig() { loading.value = true; try { const data = (await fetchLdapConfig()).data; Object.assign(form, defaultForm(), data || {}, { bind_password: '' }); const queryDefaults = { user_base_dn: form.user_base_dn || '', exclude_disabled: form.exclude_disabled, page_size: form.page_size }; Object.assign(directoryQuery, queryDefaults); Object.assign(appliedDirectoryQuery, queryDefaults); savedIdentity.value = data ? identityKey() : null; savedConfiguration.value = data ? configurationKey() : null; persistedEnabled.value = Boolean(data?.enabled) } catch (error) { ElMessage.error(actionErrorMessage(error)) } finally { loading.value = false } }
async function persistConfig(enabled = form.enabled) { const request = { ...payload(), enabled }; const { data } = await saveLdapConfig(request); Object.assign(form, data, { bind_password: '' }); savedIdentity.value = identityKey(); savedConfiguration.value = configurationKey(); persistedEnabled.value = Boolean(data.enabled); return data }
async function saveConfig() { if (configBusy.value) return; configBusy.value = true; saving.value = true; try { await formRef.value.validate(); if (connectionIdentityChanged.value) return ElMessage.warning('修改连接身份后需重新输入绑定密码'); await persistConfig(); ElMessage.success('LDAP 配置已保存') } catch (error) { if (error !== false) ElMessage.error(actionErrorMessage(error)) } finally { saving.value = false; configBusy.value = false } }
async function testConnection() { if (configBusy.value) return; configBusy.value = true; testing.value = true; try { await formRef.value.validate(); if (connectionIdentityChanged.value) return ElMessage.warning('修改连接身份后需重新输入绑定密码'); const requestedEnabled = form.enabled; const enablementChanged = form.enabled !== persistedEnabled.value; const needsStaging = configurationChanged.value || !form.configuration_tested || Boolean(form.bind_password) || enablementChanged; if (needsStaging) await persistConfig(false); const { data } = await testLdapConnection(); form.configuration_tested = true; if (needsStaging && requestedEnabled) { form.enabled = true; await persistConfig(true) } ElMessage.success(data.message || 'LDAP 连接测试成功') } catch (error) { if (error !== false) ElMessage.error(actionErrorMessage(error)) } finally { testing.value = false; configBusy.value = false } }
async function loadDirectory({ reset = false, cursor = reset ? null : currentCursor.value } = {}) { const requestId = ++directoryRequestId; directoryLoading.value = true; try { const { data } = await fetchLdapDirectoryUsers({ q: appliedKeyword.value || undefined, cursor: cursor || undefined, page_size: appliedDirectoryQuery.page_size, user_base_dn: appliedDirectoryQuery.user_base_dn, exclude_disabled: appliedDirectoryQuery.exclude_disabled }); if (requestId !== directoryRequestId) return false; directoryUsers.value = data.items || []; nextCursor.value = data.next_cursor || null; if (reset) { currentCursor.value = null; cursorStack.value = [] } return true } catch (error) { if (requestId === directoryRequestId) ElMessage.error(actionErrorMessage(error)); return false } finally { if (requestId === directoryRequestId) directoryLoading.value = false } }
function searchDirectory() { appliedKeyword.value = keyword.value.trim(); Object.assign(appliedDirectoryQuery, { user_base_dn: directoryQuery.user_base_dn.trim(), exclude_disabled: directoryQuery.exclude_disabled, page_size: directoryQuery.page_size }); return loadDirectory({ reset: true }) }
async function nextPage() { if (directoryLoading.value || !nextCursor.value) return; const targetCursor = nextCursor.value; const loaded = await loadDirectory({ cursor: targetCursor }); if (loaded) { cursorStack.value.push(currentCursor.value); currentCursor.value = targetCursor } }
async function previousPage() { if (directoryLoading.value || !cursorStack.value.length) return; const targetCursor = cursorStack.value.at(-1) ?? null; const loaded = await loadDirectory({ cursor: targetCursor }); if (loaded) { cursorStack.value.pop(); currentCursor.value = targetCursor } }

async function syncSelected() { try { const items = []; for (const row of selectedRows.value) { if (row.sync_status === 'unlinked') items.push({ external_id: row.external_id, decision: 'create' }); else if (row.sync_status === 'linked') items.push({ external_id: row.external_id, decision: 'update' }); else if (row.sync_status === 'match_suggested') { await ElMessageBox.confirm(`将 ${row.full_name || row.username} 绑定到现有用户 ${row.matched_user.full_name} / ${row.matched_user.username}？`, '确认绑定', { type: 'warning' }); items.push({ external_id: row.external_id, decision: 'bind', user_id: row.matched_user.id }) } } if (!items.length) return; syncing.value = true; const { data } = await syncLdapUsers(items); ElMessage.success(`同步完成：成功 ${data.summary.total - data.summary.failed}，失败 ${data.summary.failed}`); directoryTableRef.value?.clearSelection(); await loadDirectory({ reset: true }) } catch (error) { if (error !== 'cancel' && error !== 'close') ElMessage.error(actionErrorMessage(error)) } finally { syncing.value = false } }
async function syncBoundUsers() { syncingBound.value = true; try { const { data } = await syncBoundLdapUsers(); ElMessage.success(`已同步 ${data.summary.updated} 位用户，失败 ${data.summary.failed}`); if (directoryReady.value) await loadDirectory({ reset: true }) } catch (error) { ElMessage.error(actionErrorMessage(error)) } finally { syncingBound.value = false } }
async function openHistory() { historyVisible.value = true; historyPage.value = 1; await loadHistory() }
async function loadHistory() { historyLoading.value = true; try { const { data } = await fetchLdapSyncRuns({ page: historyPage.value, page_size: historyPageSize }); syncRuns.value = data.items || []; historyTotal.value = data.total || 0 } catch (error) { ElMessage.error(actionErrorMessage(error)) } finally { historyLoading.value = false } }
async function initializePage() { await loadConfig(); if (directoryReady.value) await loadDirectory({ reset: true }) }
onMounted(initializePage)
</script>

<style scoped>
.ldap-page { min-width: 0; }.ldap-page .page-actions { display: grid; grid-template-columns: minmax(0, 44fr) minmax(0, 56fr); gap: 16px; }.page-action-column { display: flex; align-items: center; }.page-action-right { justify-content: space-between; }.ldap-workbench { display: grid; grid-template-columns: minmax(0, 44fr) minmax(0, 56fr); gap: 16px; align-items: start; }.config-panel,.directory-panel { min-width: 0; border: 1px solid var(--el-border-color-light); border-radius: 6px; background: var(--el-bg-color); }.config-panel { padding: 0 20px 18px; }.directory-panel { overflow: hidden; }.panel-heading { min-height: 64px; display: flex; align-items: center; justify-content: space-between; gap: 12px; border-bottom: 1px solid var(--el-border-color-lighter); }.panel-heading h2 { margin: 0; font-size: 17px; }.panel-heading span { color: var(--el-text-color-secondary); font-size: 12px; }.directory-heading { padding: 0 16px; }.readiness { display: inline-block; margin-top: 4px; }.readiness.is-ready { color: var(--el-color-success); }.config-section { padding-top: 20px; }.config-section + .config-section { margin-top: 4px; border-top: 1px solid var(--el-border-color-lighter); }.config-section h3 { margin: 0 0 15px; font-size: 15px; }.form-grid,.mapping-grid { display: grid; grid-template-columns: minmax(0,1fr) minmax(0,1fr); gap: 0 16px; }.span-2 { grid-column: 1 / -1; }.form-grid :deep(.el-input-number),.form-grid :deep(.el-segmented) { width: 100%; }.identity-warning { margin: -8px 0 16px; color: var(--el-color-warning); font-size: 12px; }.config-actions { position: sticky; bottom: 0; display: flex; justify-content: flex-end; gap: 8px; padding-top: 14px; border-top: 1px solid var(--el-border-color-lighter); background: var(--el-bg-color); }.directory-query-controls { display: grid; grid-template-columns: minmax(220px,1fr) minmax(120px,150px) minmax(120px,150px); gap: 12px; align-items: end; padding: 12px 16px 4px; }.directory-query-field { display: grid; gap: 6px; color: var(--el-text-color-regular); font-size: 13px; }.directory-query-field :deep(.el-input-number) { width: 100%; }.directory-query-field :deep(.el-switch) { height: 32px; }.directory-toolbar { display: grid; grid-template-columns: minmax(180px,1fr) auto auto; gap: 8px; padding: 12px 16px; }.cursor-pagination { height: 54px; display: flex; align-items: center; justify-content: flex-end; gap: 14px; padding: 0 16px; border-top: 1px solid var(--el-border-color-lighter); }.cursor-pagination span,.muted { color: var(--el-text-color-secondary); font-size: 13px; }.directory-panel :deep(.el-empty) { height: 570px; }.directory-panel :deep(.el-tag) { width: 82px; justify-content: center; }.ldap-page :deep(.el-drawer__body) { padding-top: 0; }.ldap-page :deep(.el-pagination) { margin-top: 16px; justify-content: flex-end; }
.ldap-page { display: grid; grid-template-rows: auto minmax(0,1fr); height: 100%; overflow: hidden; }
.ldap-workbench { height: 100%; min-height: 0; align-items: stretch; }
.config-panel { box-sizing: border-box; height: 100%; overflow-y: auto; }
.directory-panel { display: flex; flex-direction: column; height: 100%; min-height: 0; }
.directory-panel :deep(.el-table) { flex: 1; min-height: 0; }
.directory-panel :deep(.el-empty) { flex: 1; min-height: 0; height: auto; }
@media (max-width: 1200px) { .ldap-page .page-actions,.ldap-workbench { grid-template-columns: minmax(380px, 48fr) minmax(0, 52fr); } }
@media (max-width: 900px) { .ldap-page .page-actions { grid-template-columns: auto minmax(0,1fr); }.ldap-workbench { grid-template-columns: 1fr; }.directory-panel :deep(.el-empty) { height: 320px; } }
@media (max-width: 900px) { .ldap-page { display: block; height: auto; overflow: visible; }.ldap-workbench,.config-panel,.directory-panel { height: auto; }.config-panel { overflow-y: visible; }.directory-panel :deep(.el-table) { flex: none; height: 590px !important; }.directory-panel :deep(.el-empty) { flex: none; } }
@media (max-width: 600px) { .ldap-page .page-actions { grid-template-columns: 1fr; }.page-action-right { flex-wrap: wrap; gap: 8px; }.form-grid,.mapping-grid { grid-template-columns: 1fr; }.span-2 { grid-column: auto; }.directory-query-controls { grid-template-columns: 1fr 1fr; }.directory-query-base { grid-column: 1 / -1; }.directory-toolbar { grid-template-columns: 1fr auto; }.directory-toolbar .el-button:last-child { display: none; }.page-head { align-items: flex-start; flex-direction: column; } }
@media (max-width: 600px) { .directory-panel :deep(.el-table) { height: 440px !important; } }
.sync-status-cell { display: flex; align-items: center; gap: 8px; min-width: 0; }.matched-user { min-width: 0; overflow: hidden; color: var(--el-text-color-secondary); font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }.bind-directory-user { margin-bottom: 14px; color: var(--el-text-color-regular); }.bind-user-list { display: grid; max-height: 300px; margin-top: 14px; overflow-y: auto; }.bind-user-list :deep(.el-radio) { display: flex; align-items: flex-start; min-height: 42px; margin-right: 0; }.bind-user-list small { display: block; margin-top: 3px; color: var(--el-text-color-secondary); font-size: 12px; }
</style>
