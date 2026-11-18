<template>
  <div class="account-package-page">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <div>
            <strong>账号开通包</strong>
            <p class="page-description">离线签发、下载和导入账号，支持签发记录与导入回执审计。</p>
          </div>
          <div class="header-actions">
            <el-button data-testid="refresh-packages" :loading="loading" @click="refresh">
              刷新
            </el-button>
            <el-button data-testid="open-import" @click="openImportDialog">导入账号包</el-button>
            <el-button type="primary" data-testid="open-export" @click="openExportDialog">
              签发账号包
            </el-button>
          </div>
        </div>
      </template>

      <el-alert
        type="warning"
        :closable="false"
        show-icon
        title="账号包与包口令必须分渠道传递；一次性口令仅在签发成功时展示一次，关闭后无法找回。"
      />

      <h3>签发记录</h3>
      <el-table v-loading="loading" :data="packages" empty-text="暂无签发记录">
        <el-table-column prop="target_org_code" label="目标组织" min-width="110" />
        <el-table-column prop="package_id" label="包 ID" min-width="220" show-overflow-tooltip />
        <el-table-column prop="issued_at" label="签发时间" min-width="170">
          <template #default="{ row }">{{ formatDateTimeLocale(row.issued_at) }}</template>
        </el-table-column>
        <el-table-column prop="expires_at" label="过期时间" min-width="170">
          <template #default="{ row }">{{ formatDateTimeLocale(row.expires_at) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.state === 'active' ? 'success' : 'info'">
              {{ stateLabel(row.state) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="170" fixed="right">
          <template #default="{ row }">
            <el-button
              link
              type="primary"
              :loading="downloadingId === row.package_id"
              @click="downloadPackage(row)"
            >
              下载
            </el-button>
            <el-button
              link
              type="danger"
              :disabled="row.state !== 'active'"
              @click="revokePackage(row)"
            >
              撤销
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <h3>导入回执</h3>
      <el-table :data="receipts" empty-text="暂无导入回执">
        <el-table-column prop="package_id" label="包 ID" min-width="220" show-overflow-tooltip />
        <el-table-column prop="target_org_code" label="目标组织" min-width="110" />
        <el-table-column prop="confirmed_at" label="导入时间" min-width="170">
          <template #default="{ row }">{{ formatDateTimeLocale(row.confirmed_at) }}</template>
        </el-table-column>
        <el-table-column prop="state" label="状态" width="100" />
      </el-table>
    </el-card>

    <el-dialog
      v-model="exportVisible"
      title="签发账号开通包"
      width="760px"
      :close-on-click-modal="false"
    >
      <el-form label-width="110px">
        <div class="form-grid">
          <el-form-item label="组织编码" required>
            <el-input
              v-model.trim="exportForm.organization_code"
              maxlength="6"
              placeholder="6 位组织编码"
            />
          </el-form-item>
          <el-form-item label="组织名称">
            <el-input v-model.trim="exportForm.organization_name" maxlength="100" />
          </el-form-item>
          <el-form-item label="上级组织编码">
            <el-input v-model.trim="exportForm.parent_code" maxlength="6" placeholder="选填" />
          </el-form-item>
          <el-form-item label="目标机器码" required>
            <el-input
              v-model.trim="exportForm.target_machine_code"
              placeholder="目标机器的机器码"
            />
          </el-form-item>
          <el-form-item label="包口令" required>
            <el-input
              v-model="exportForm.package_password"
              type="password"
              show-password
              autocomplete="new-password"
              placeholder="至少 12 位，包含字母和数字"
            />
          </el-form-item>
          <el-form-item label="有效期（天）" required>
            <el-input-number v-model="exportForm.valid_days" :min="1" :max="30" />
          </el-form-item>
        </div>
        <el-form-item label="授权配置">
          <el-input
            v-model="exportForm.grantsText"
            type="textarea"
            :rows="3"
            placeholder='JSON 对象，例如 {"villages":"edit","projects":"view"}'
          />
        </el-form-item>
        <div class="accounts-heading">
          <span>开通账号</span>
          <el-button link type="primary" data-testid="add-account" @click="addAccount"
            >添加账号</el-button
          >
        </div>
        <div v-for="(account, index) in exportForm.accounts" :key="index" class="account-row">
          <el-input v-model.trim="account.username" placeholder="用户名" maxlength="20" />
          <el-input v-model.trim="account.full_name" placeholder="姓名" maxlength="50" />
          <el-select v-model="account.role" aria-label="角色">
            <el-option label="管理员" value="admin" />
            <el-option label="普通用户" value="user" />
            <el-option label="只读用户" value="viewer" />
          </el-select>
          <el-select v-model="account.data_scope" aria-label="数据范围">
            <el-option label="本组织" value="org" />
            <el-option label="本组织及下级" value="org_children" />
            <el-option label="仅本人" value="self" />
          </el-select>
          <el-button
            link
            type="danger"
            :disabled="exportForm.accounts.length === 1"
            @click="removeAccount(index)"
          >
            删除
          </el-button>
        </div>
      </el-form>
      <el-alert
        type="info"
        :closable="false"
        title="请通过另一安全渠道告知接收方包口令；本页不会再次显示该口令。"
      />
      <template #footer>
        <el-button @click="exportVisible = false">取消</el-button>
        <el-button
          type="primary"
          data-testid="export-package"
          :loading="exporting"
          @click="exportPackage"
        >
          签发并生成
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      :model-value="exportResult !== null"
      title="签发成功：立即保存一次性口令"
      width="620px"
      :close-on-click-modal="false"
      @close="closeOtpDialog"
    >
      <template v-if="exportResult">
        <el-alert
          type="warning"
          :closable="false"
          show-icon
          title="以下一次性口令仅显示这一次。关闭窗口后无法再次查看，请立即安全抄录并分别交付对应用户。"
        />
        <p>文件：{{ exportResult.file_name }}</p>
        <div
          v-for="account in exportResult.accounts"
          :key="account.username"
          class="credential-row"
        >
          <span>{{ account.username }}</span>
          <code :data-testid="`otp-${account.username}`">{{ account.one_time_password }}</code>
        </div>
      </template>
      <template #footer>
        <el-button v-if="exportResult" @click="downloadPackage(exportResult)">下载账号包</el-button>
        <el-button type="primary" data-testid="close-otp" @click="closeOtpDialog"
          >我已妥善保存</el-button
        >
      </template>
    </el-dialog>

    <el-dialog
      v-model="importVisible"
      title="导入账号开通包"
      width="620px"
      :close-on-click-modal="false"
      @close="resetImport"
    >
      <template v-if="!importResult">
        <el-alert
          type="info"
          :closable="false"
          show-icon
          title="请选择 .apkg 文件并输入签发方通过另一渠道提供的包口令。确认导入可能要求再次验证当前管理员密码。"
        />
        <el-upload
          drag
          action="#"
          accept=".apkg"
          :auto-upload="false"
          :limit="1"
          :on-change="onImportFileChange"
          :on-remove="onImportFileRemove"
        >
          <div class="upload-tip">拖拽账号包到此处，或点击选择</div>
        </el-upload>
        <el-input
          v-model="importPassword"
          type="password"
          show-password
          autocomplete="off"
          placeholder="包口令"
          data-testid="import-password"
        />
        <el-button
          type="primary"
          data-testid="preview-import"
          :loading="previewing"
          @click="previewImport"
        >
          校验并预览
        </el-button>

        <div v-if="importPreview" class="import-preview" data-testid="import-preview">
          <h4>包内容预览</h4>
          <dl>
            <dt>目标组织</dt>
            <dd>{{ importPreview.organization_name }}（{{ importPreview.organization_code }}）</dd>
            <dt>包 ID</dt>
            <dd>{{ importPreview.package_id }}</dd>
            <dt>过期时间</dt>
            <dd>{{ formatDateTimeLocale(importPreview.expires_at) }}</dd>
            <dt>首个账号</dt>
            <dd>{{ importPreview.admin?.full_name }}（{{ importPreview.admin?.username }}）</dd>
          </dl>
          <el-button
            type="danger"
            data-testid="confirm-import"
            :loading="confirming"
            @click="confirmImport"
          >
            确认导入并开通账号
          </el-button>
        </div>
      </template>
      <div v-else class="import-result" data-testid="import-result">
        <el-result icon="success" title="账号包导入成功" />
        <p>组织编码：{{ importResult.organization_code }}</p>
        <div v-for="user in importResult.users" :key="user.user_id" class="imported-user">
          {{ user.username }}<span v-if="user.must_change_password">（首次登录须修改密码）</span>
        </div>
      </div>
      <template #footer>
        <el-button data-testid="close-import" @click="importVisible = false">
          {{ importResult ? '完成' : '取消' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type UploadFile } from 'element-plus'
import request, { downloadBlob, get, parseContentDisposition, post } from '@/api/request'
import { getErrorMessage } from '@/utils/getErrorMessage'
import { formatDateTimeLocale } from '@/utils/datetime'

interface AccountDraft {
  username: string
  full_name: string
  role: string
  data_scope: string
}

interface PackageRow {
  package_id: string
  target_org_code?: string
  issued_at?: string
  expires_at?: string
  state?: string
  file_name?: string
}

interface ReceiptRow {
  package_id: string
  target_org_code?: string
  confirmed_at?: string
  state?: string
}

interface ExportResult extends PackageRow {
  file_name: string
  accounts: Array<{ username: string; one_time_password: string }>
}

interface ImportPreview {
  package_id: string
  organization_code: string
  organization_name: string
  expires_at: string
  admin?: { username?: string; full_name?: string }
}

interface ImportResult {
  organization_code: string
  users: Array<{ user_id: number; username: string; must_change_password: boolean }>
}

const packages = ref<PackageRow[]>([])
const receipts = ref<ReceiptRow[]>([])
const loading = ref(false)
const downloadingId = ref('')
const exportVisible = ref(false)
const exporting = ref(false)
const exportResult = ref<ExportResult | null>(null)
const importVisible = ref(false)
const importFile = ref<File | null>(null)
const importPassword = ref('')
const importPreview = ref<ImportPreview | null>(null)
const importResult = ref<ImportResult | null>(null)
const previewing = ref(false)
const confirming = ref(false)

function newAccount(): AccountDraft {
  return { username: '', full_name: '', role: 'admin', data_scope: 'org' }
}

const exportForm = reactive({
  organization_code: '',
  organization_name: '',
  parent_code: '',
  target_machine_code: '',
  package_password: '',
  valid_days: 7,
  grantsText: '',
  accounts: [newAccount()],
})

function errorText(error: unknown, fallback: string): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (detail && typeof detail === 'object' && 'message' in detail) {
    const message = (detail as { message?: unknown }).message
    if (typeof message === 'string' && message) return message
  }
  return getErrorMessage(error, fallback)
}

function stateLabel(state?: string): string {
  return state === 'active' ? '有效' : state === 'revoked' ? '已撤销' : state || '未知'
}

async function loadPackages(): Promise<void> {
  loading.value = true
  try {
    const result = await get<{ items: PackageRow[] }>('/account-packages', { limit: 100 })
    packages.value = Array.isArray(result.items) ? result.items : []
  } catch (error) {
    ElMessage.error(errorText(error, '加载账号包列表失败'))
  } finally {
    loading.value = false
  }
}

async function loadReceipts(): Promise<void> {
  try {
    const result = await get<{ items: ReceiptRow[] }>('/account-packages/receipts')
    receipts.value = Array.isArray(result.items) ? result.items : []
  } catch (error) {
    ElMessage.error(errorText(error, '加载导入回执失败'))
  }
}

async function refresh(): Promise<void> {
  await Promise.all([loadPackages(), loadReceipts()])
}

function resetExportForm(): void {
  Object.assign(exportForm, {
    organization_code: '',
    organization_name: '',
    parent_code: '',
    target_machine_code: '',
    package_password: '',
    valid_days: 7,
    grantsText: '',
    accounts: [newAccount()],
  })
}

function openExportDialog(): void {
  resetExportForm()
  exportVisible.value = true
}

function addAccount(): void {
  exportForm.accounts.push(newAccount())
}

function removeAccount(index: number): void {
  if (exportForm.accounts.length > 1) exportForm.accounts.splice(index, 1)
}

function parseGrants(): Record<string, string> {
  const text = exportForm.grantsText.trim()
  if (!text) return {}
  const parsed: unknown = JSON.parse(text)
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('授权配置必须是 JSON 对象')
  }
  return parsed as Record<string, string>
}

async function exportPackage(): Promise<void> {
  const first = exportForm.accounts[0]
  if (
    exportForm.organization_code.length !== 6 ||
    exportForm.target_machine_code.length < 8 ||
    exportForm.package_password.length < 12 ||
    exportForm.accounts.some((account) => !account.username)
  ) {
    ElMessage.warning('请填写 6 位组织编码、目标机器码、至少 12 位包口令及所有账号用户名')
    return
  }
  exporting.value = true
  try {
    const result = await post<ExportResult>('/account-packages/export', {
      organization_code: exportForm.organization_code,
      organization_name: exportForm.organization_name,
      parent_code: exportForm.parent_code,
      admin_username: first.username,
      admin_full_name: first.full_name,
      target_machine_code: exportForm.target_machine_code,
      package_password: exportForm.package_password,
      grants: parseGrants(),
      valid_days: exportForm.valid_days,
      accounts: exportForm.accounts.map((account) => ({ ...account })),
    })
    exportResult.value = result
    exportVisible.value = false
    exportForm.package_password = ''
    ElMessage.success('账号包签发成功，一次性口令仅此一次展示')
    await loadPackages()
  } catch (error) {
    ElMessage.error(errorText(error, '签发账号包失败'))
  } finally {
    exporting.value = false
  }
}

function closeOtpDialog(): void {
  exportResult.value = null
}

async function downloadPackage(row: any): Promise<void> {
  downloadingId.value = row.package_id
  try {
    const response = await request.get(`/account-packages/${row.package_id}/download`, {
      responseType: 'blob',
    })
    const filename = parseContentDisposition(
      response.headers as unknown as Record<string, string>,
      row.file_name || `account-package-${row.package_id}.apkg`
    )
    downloadBlob(response.data, filename)
    ElMessage.success('账号包下载已开始')
  } catch (error) {
    ElMessage.error(errorText(error, '下载账号包失败'))
  } finally {
    downloadingId.value = ''
  }
}

async function revokePackage(row: any): Promise<void> {
  let reason = ''
  try {
    const result = await ElMessageBox.prompt('请输入撤销原因（选填）：', '撤销账号包', {
      inputPlaceholder: '撤销后该包将无法导入',
      inputType: 'textarea',
      confirmButtonText: '确认撤销',
      cancelButtonText: '取消',
    })
    reason = result.value || ''
  } catch {
    return
  }
  try {
    await post(`/account-packages/${row.package_id}/revoke`, { reason })
    ElMessage.success('账号包已撤销')
    await loadPackages()
  } catch (error) {
    ElMessage.error(errorText(error, '撤销账号包失败'))
  }
}

function openImportDialog(): void {
  resetImport()
  importVisible.value = true
}

function resetImport(): void {
  importFile.value = null
  importPassword.value = ''
  importPreview.value = null
  importResult.value = null
}

function onImportFileChange(file: UploadFile): void {
  importFile.value = file.raw || null
  importPreview.value = null
  importResult.value = null
}

function onImportFileRemove(): void {
  importFile.value = null
  importPreview.value = null
}

function importFormData(): FormData {
  const form = new FormData()
  form.append('file', importFile.value as File)
  form.append('password', importPassword.value)
  return form
}

async function previewImport(): Promise<void> {
  if (!importFile.value || !importPassword.value) {
    ElMessage.warning('请先选择账号包并输入包口令')
    return
  }
  previewing.value = true
  try {
    importPreview.value = await post<ImportPreview>('/account-packages/preview', importFormData())
    importResult.value = null
  } catch (error) {
    importPreview.value = null
    ElMessage.error(errorText(error, '账号包预览失败'))
  } finally {
    previewing.value = false
  }
}

async function confirmImport(): Promise<void> {
  if (!importFile.value || !importPassword.value || !importPreview.value) {
    ElMessage.warning('请先完成账号包预览')
    return
  }
  confirming.value = true
  try {
    // 已初始化系统由 request 拦截器处理 428，并通过 X-Confirm-Password 安全重放。
    importResult.value = await post<ImportResult>('/account-packages/confirm', importFormData())
    importPreview.value = null
    ElMessage.success('账号包导入成功，用户首次登录须修改一次性口令')
    await loadReceipts()
  } catch (error) {
    ElMessage.error(errorText(error, '确认导入失败'))
  } finally {
    confirming.value = false
  }
}

onMounted(() => {
  void refresh()
})

defineExpose({
  packages,
  receipts,
  exportForm,
  exportResult,
  importFile,
  importPassword,
  importPreview,
  importResult,
  openExportDialog,
  addAccount,
  removeAccount,
  exportPackage,
  closeOtpDialog,
  downloadPackage,
  revokePackage,
  openImportDialog,
  onImportFileChange,
  onImportFileRemove,
  previewImport,
  confirmImport,
  refresh,
  stateLabel,
})
</script>

<style scoped>
.account-package-page {
  padding: 16px;
}
.card-header,
.header-actions,
.accounts-heading,
.account-row,
.credential-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.card-header,
.accounts-heading,
.credential-row {
  justify-content: space-between;
}
.page-description {
  margin: 6px 0 0;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  column-gap: 16px;
}
.accounts-heading {
  margin: 8px 0 12px;
  font-weight: 600;
}
.account-row {
  margin-bottom: 10px;
}
.account-row .el-input {
  width: 150px;
}
.account-row .el-select {
  width: 135px;
}
.credential-row {
  margin-top: 14px;
  padding: 12px;
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
}
.credential-row code {
  user-select: all;
  font-size: 16px;
}
.upload-tip {
  padding: 28px 0;
  color: var(--el-text-color-secondary);
}
.import-preview,
.import-result {
  margin-top: 16px;
}
.import-preview dl {
  display: grid;
  grid-template-columns: 100px 1fr;
  gap: 8px;
}
.import-preview dd {
  margin: 0;
  word-break: break-all;
}
.imported-user {
  padding: 6px 0;
}
@media (max-width: 800px) {
  .form-grid {
    grid-template-columns: 1fr;
  }
  .card-header,
  .account-row {
    align-items: flex-start;
    flex-wrap: wrap;
  }
}
</style>
