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
            <el-button
              type="primary"
              data-testid="open-export"
              :disabled="issueStatus !== null && !issueStatus.can_issue"
              :title="issueStatus && !issueStatus.can_issue ? issueStatus.reason : ''"
              @click="openExportDialog"
            >
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
      <el-alert
        v-if="issueStatus && !issueStatus.can_issue"
        class="issue-blocked"
        type="info"
        :closable="false"
        show-icon
        :title="`当前不可签发：${issueStatus.reason}`"
      />

      <div class="signing-key-panel" data-testid="signing-key-panel">
        <div class="signing-key-head">
          <div>
            <strong>本机签发密钥</strong>
            <p class="signing-key-hint">
              首次签发时自动生成，私钥只保存在本机。目标机导入时会显示此指纹，请通过独立渠道核对。
            </p>
          </div>
          <el-tag :type="signingKeys?.ready ? 'success' : 'info'" size="small">
            {{ signingKeys?.ready ? '已就绪' : '未生成' }}
          </el-tag>
        </div>
        <template v-if="signingKeys?.ready">
          <div class="signing-key-row">
            <span class="signing-key-label">签名指纹</span>
            <code data-testid="signing-fingerprint">{{ signingKeys.fingerprint }}</code>
            <el-button link type="primary" @click="copyText(signingKeys.fingerprint, '指纹')">
              复制
            </el-button>
            <el-tag v-if="signingKeys.source === 'environment'" size="small" type="warning">
              使用环境变量私钥
            </el-tag>
          </div>
          <div class="signing-key-row">
            <span class="signing-key-label">签发公钥</span>
            <el-input
              :model-value="signingKeys.public_key"
              readonly
              data-testid="signing-public-key"
            />
            <el-button link type="primary" @click="copyText(signingKeys.public_key, '公钥')">
              复制
            </el-button>
          </div>
        </template>
        <el-alert
          v-else
          type="info"
          :closable="false"
          title="尚未生成签发密钥；超级管理员首次打开本页或签发时会自动生成。"
        />

        <div class="trusted-keys">
          <div class="trusted-keys-title">
            信任的签发机
            <span class="signing-key-hint">
              导入账号包并核对指纹后自动加入；也可手动添加对方公钥。
            </span>
          </div>
          <div v-if="(signingKeys?.trusted_keys || []).length === 0" class="signing-key-hint">
            暂无外部信任的签发机（本机签发的包默认信任）。
          </div>
          <div
            v-for="key in signingKeys?.trusted_keys || []"
            :key="key.fingerprint"
            class="signing-key-row"
          >
            <code>{{ key.fingerprint }}</code>
            <el-button
              v-if="issueStatus?.is_superuser"
              link
              type="danger"
              @click="untrustSigningKey(key.fingerprint)"
            >
              移除
            </el-button>
          </div>
          <div v-if="issueStatus?.is_superuser" class="trust-key-form">
            <el-input
              v-model.trim="trustKeyPublicKey"
              placeholder="粘贴对方签发机公钥（64 位十六进制）"
              data-testid="trust-public-key"
            />
            <el-button type="primary" plain :loading="trusting" @click="trustSigningKey">
              信任此签发机
            </el-button>
          </div>
        </div>
      </div>

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
        <el-form-item label="页面授权">
          <div class="grant-block">
            <div class="grant-hint">
              按页面勾选只读/可操作；“可操作”会自动包含该页面对应的接口模块。未勾选的页面不开放。
            </div>
            <el-scrollbar max-height="320px" class="grant-scroll">
              <div
                v-for="section in authzCatalog?.sections || []"
                :key="section.key"
                class="grant-section"
              >
                <div class="grant-section-title">{{ section.label }}</div>
                <template v-for="item in section.items" :key="item.key">
                  <div v-if="item.kind === 'group'" class="grant-group">
                    <div class="grant-group-title">{{ item.label }}</div>
                    <div v-for="page in groupChildren(item)" :key="page.key" class="grant-row">
                      <span class="grant-label">{{ page.label }}</span>
                      <el-select
                        :model-value="grantValue(page)"
                        clearable
                        placeholder="不开放"
                        @update:model-value="selectGrant(page, $event)"
                      >
                        <el-option label="只读" value="view" />
                        <el-option label="可操作" value="edit" :disabled="!canEditPage(page)" />
                      </el-select>
                    </div>
                  </div>
                  <div v-else class="grant-row">
                    <span class="grant-label">{{ pageItem(item).label }}</span>
                    <el-select
                      :model-value="grantValue(pageItem(item))"
                      clearable
                      placeholder="不开放"
                      @update:model-value="selectGrant(pageItem(item), $event)"
                    >
                      <el-option label="只读" value="view" />
                      <el-option
                        label="可操作"
                        value="edit"
                        :disabled="!canEditPage(pageItem(item))"
                      />
                    </el-select>
                  </div>
                </template>
              </div>
            </el-scrollbar>
            <div class="grant-summary">
              已选择 {{ selectedGrantCount }} 个页面
              <span v-if="issueStatus && !issueStatus.can_issue" class="grant-blocked">
                · {{ issueStatus.reason }}
              </span>
            </div>
          </div>
        </el-form-item>
        <div class="accounts-heading">
          <span>开通账号</span>
          <el-button link type="primary" data-testid="add-account" @click="addAccount"
            >添加账号</el-button
          >
        </div>
        <div v-for="(account, index) in exportForm.accounts" :key="index" class="account-block">
          <div class="account-row">
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
          <div class="account-row account-row--secondary">
            <el-input
              v-model="account.initial_password"
              type="password"
              show-password
              autocomplete="new-password"
              placeholder="初始登录密码（留空自动生成，至少 12 位字母+数字）"
            />
            <el-select
              v-model="account.allowed_menus"
              multiple
              filterable
              collapse-tags
              clearable
              placeholder="可见菜单（留空=角色默认）"
            >
              <el-option
                v-for="option in menuOptions"
                :key="option.key"
                :label="`${option.group} / ${option.label}`"
                :value="option.key"
              />
            </el-select>
          </div>
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
        <p v-if="exportResult.signer_fingerprint">
          签发机指纹：<code>{{ exportResult.signer_fingerprint }}</code>
          （目标机导入时会显示，请通过独立渠道核对）
        </p>
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
        <el-button data-testid="download-credential-sheet" @click="downloadCredentialSheet"
          >下载初始化清单（与账号包分渠道传递）</el-button
        >
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
            <dt>授权范围</dt>
            <dd>
              <template v-if="importPreview.authorization">
                页面 {{ importPreview.authorization.page_count }} 个（可操作
                {{ importPreview.authorization.edit_page_count }} / 只读
                {{ importPreview.authorization.view_page_count }}），接口模块
                {{ importPreview.authorization.module_count }} 个
              </template>
              <span v-else>未携带页面授权</span>
            </dd>
            <dt>开通账号</dt>
            <dd>
              <span
                v-for="account in importPreview.accounts || []"
                :key="account.username"
                class="imported-user"
              >
                {{ account.full_name }}（{{ account.username }} / {{ account.role || '-' }} /
                {{ account.data_scope || '-' }}）
              </span>
            </dd>
          </dl>
          <div
            v-if="importPreview.signer_fingerprint"
            class="signer-trust"
            data-testid="signer-trust"
          >
            <el-alert
              v-if="importPreview.signer_trusted"
              type="success"
              :closable="false"
              show-icon
              title="签发机已在本机信任列表中"
            />
            <template v-else>
              <el-alert
                type="warning"
                :closable="false"
                show-icon
                title="首次来自该签发机：请通过独立渠道核对指纹后再确认导入。"
              />
              <div class="signing-key-row">
                <span class="signing-key-label">签发机指纹</span>
                <code data-testid="import-signer-fingerprint">
                  {{ importPreview.signer_fingerprint }}
                </code>
              </div>
              <el-checkbox v-model="importTrustAcknowledged" data-testid="ack-signer-fingerprint">
                我已通过独立渠道核对上述指纹
              </el-checkbox>
            </template>
          </div>
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
        <el-alert
          type="warning"
          :closable="false"
          show-icon
          title="请使用本机管理员账号登录后立即修改出厂管理员密码；跨机账号首次登录也须修改一次性口令。"
        />
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
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type UploadFile } from 'element-plus'
import request, { del, downloadBlob, get, parseContentDisposition, post } from '@/api/request'
import { getErrorMessage } from '@/utils/getErrorMessage'
import { formatDateTimeLocale } from '@/utils/datetime'
import { useMenuStore } from '@/stores/menu'

interface AccountDraft {
  username: string
  full_name: string
  role: string
  data_scope: string
  initial_password: string
  allowed_menus: string[]
}

interface AuthzPage {
  key: string
  label: string
  section: string
  section_label: string
  kind: string
  modules: string[]
  can_edit: boolean
  tabs?: Array<{ key: string; label: string }>
}

interface AuthzGroup {
  key: string
  label: string
  kind: 'group'
  children: AuthzPage[]
}

interface AuthzSection {
  key: string
  label: string
  items: Array<AuthzPage | AuthzGroup>
}

interface AuthzCatalog {
  catalog_version: string
  sections: AuthzSection[]
  pages: AuthzPage[]
  modules: string[]
}

interface IssueStatus {
  can_issue: boolean
  enabled: boolean
  signing_key_configured: boolean
  is_superuser: boolean
  reason: string
  reason_code?: string | null
  signing_public_key?: string
  signing_fingerprint?: string
  signing_key_source?: string
}

interface TrustedSigningKey {
  public_key: string
  fingerprint: string
}

interface SigningKeyInfo {
  public_key: string
  fingerprint: string
  source: string
  ready: boolean
  trusted_keys: TrustedSigningKey[]
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
  organization_code?: string
  organization_name?: string
  signer_public_key?: string
  signer_fingerprint?: string
  accounts: Array<{
    username: string
    one_time_password: string
    generated_password?: boolean
    role?: string
    data_scope?: string
  }>
}

interface PreviewAccount {
  username?: string
  full_name?: string
  role?: string
  data_scope?: string
}

interface ImportPreview {
  package_id: string
  organization_code: string
  organization_name: string
  expires_at: string
  admin?: PreviewAccount
  accounts?: PreviewAccount[]
  signer_public_key?: string
  signer_fingerprint?: string
  signer_trusted?: boolean
  trust_required?: boolean
  authorization?: {
    page_count: number
    edit_page_count: number
    view_page_count: number
    module_count: number
    digest: string
  }
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
const menuStore = useMenuStore()
const authzCatalog = ref<AuthzCatalog | null>(null)
const issueStatus = ref<IssueStatus | null>(null)
const signingKeys = ref<SigningKeyInfo | null>(null)
const trustKeyPublicKey = ref('')
const trusting = ref(false)
const importTrustAcknowledged = ref(false)
const grantSelections = reactive<Record<string, string>>({})

const menuOptions = computed(() =>
  menuStore.flatEntries.map((entry: any) => ({
    key: entry.key,
    label: entry.label,
    group: entry.sectionLabel || '菜单',
  }))
)

const selectedGrantCount = computed(
  () =>
    Object.values(grantSelections).filter((level) => level === 'view' || level === 'edit').length
)

function canEditPage(page: AuthzPage): boolean {
  return page.can_edit && Array.isArray(page.modules) && page.modules.length > 0
}

function groupChildren(item: AuthzPage | AuthzGroup): AuthzPage[] {
  return item.kind === 'group' ? (item as AuthzGroup).children : []
}

function pageItem(item: AuthzPage | AuthzGroup): AuthzPage {
  return item as AuthzPage
}

function selectGrant(page: AuthzPage, value: string): void {
  if (!value) {
    delete grantSelections[page.key]
    return
  }
  grantSelections[page.key] = value
}

function grantValue(page: AuthzPage): string {
  return grantSelections[page.key] || ''
}

function buildGrants(): Record<string, string> {
  const result: Record<string, string> = {}
  for (const [key, level] of Object.entries(grantSelections)) {
    if (level === 'view' || level === 'edit') result[key] = level
  }
  return result
}

function resetGrantSelections(): void {
  for (const key of Object.keys(grantSelections)) delete grantSelections[key]
}

function newAccount(role: 'admin' | 'user' | 'viewer' = 'admin'): AccountDraft {
  return {
    username: '',
    full_name: '',
    role,
    data_scope: 'org',
    initial_password: '',
    allowed_menus: [],
  }
}

const exportForm = reactive({
  organization_code: '',
  organization_name: '',
  parent_code: '',
  target_machine_code: '',
  package_password: '',
  valid_days: 7,
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
    accounts: [newAccount()],
  })
  resetGrantSelections()
}

function openExportDialog(): void {
  resetExportForm()
  exportVisible.value = true
}

function addAccount(): void {
  exportForm.accounts.push(newAccount('user'))
}

function removeAccount(index: number): void {
  if (exportForm.accounts.length > 1) exportForm.accounts.splice(index, 1)
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
  if (selectedGrantCount.value === 0) {
    ElMessage.warning('请至少勾选一个页面的授权级别')
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
      grants: buildGrants(),
      valid_days: exportForm.valid_days,
      accounts: exportForm.accounts.map((account) => ({
        username: account.username,
        full_name: account.full_name,
        role: account.role,
        data_scope: account.data_scope,
        initial_password: account.initial_password,
        allowed_menus: account.allowed_menus,
      })),
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

function downloadCredentialSheet(): void {
  if (!exportResult.value) return
  const r = exportResult.value
  const header = [
    '包ID',
    '目标组织编码',
    '目标组织名称',
    '账号',
    '初始登录密码',
    '密码来源',
    '角色',
    '数据范围',
    '过期时间',
    '说明',
  ]
  const rows = r.accounts.map((a) => [
    r.package_id,
    r.organization_code || r.target_org_code || '',
    r.organization_name || '',
    a.username,
    a.one_time_password,
    a.generated_password === false ? '管理员指定' : '系统生成',
    a.role || '',
    a.data_scope || '',
    r.expires_at || '',
    '首次登录必须修改密码；密码与包口令分渠道交付',
  ])
  const csv = [header, ...rows]
    .map((cols) => cols.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(','))
    .join('\r\n')
  downloadBlob(
    new Blob([`\uFEFF${csv}`], { type: 'text/csv;charset=utf-8' }),
    `account-package-${r.package_id}-credentials.csv`
  )
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
  importTrustAcknowledged.value = false
}

function onImportFileChange(file: UploadFile): void {
  importFile.value = file.raw || null
  importPreview.value = null
  importResult.value = null
  importTrustAcknowledged.value = false
}

function onImportFileRemove(): void {
  importFile.value = null
  importPreview.value = null
  importTrustAcknowledged.value = false
}

function importFormData(): FormData {
  const form = new FormData()
  form.append('file', importFile.value as File)
  form.append('password', importPassword.value)
  if (importTrustAcknowledged.value && importPreview.value?.signer_fingerprint) {
    form.append('confirmed_fingerprint', importPreview.value.signer_fingerprint)
  }
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
    importTrustAcknowledged.value = false
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
  if (importPreview.value.trust_required && !importTrustAcknowledged.value) {
    ElMessage.warning('请先通过独立渠道核对签发机指纹并勾选确认')
    return
  }
  confirming.value = true
  try {
    // 已初始化系统由 request 拦截器处理 428，并通过 X-Confirm-Password 安全重放。
    importResult.value = await post<ImportResult>('/account-packages/confirm', importFormData())
    importPreview.value = null
    importTrustAcknowledged.value = false
    ElMessage.success('账号包导入成功，用户首次登录须修改一次性口令')
    await Promise.all([loadReceipts(), loadSigningKeys()])
  } catch (error) {
    ElMessage.error(errorText(error, '确认导入失败'))
  } finally {
    confirming.value = false
  }
}

async function loadSigningKeys(): Promise<void> {
  try {
    signingKeys.value = await get<SigningKeyInfo>('/account-packages/signing-keys')
  } catch (error) {
    signingKeys.value = null
    ElMessage.error(errorText(error, '加载签发密钥失败'))
  }
}

async function copyText(value: string, label: string): Promise<void> {
  if (!value) return
  try {
    await navigator.clipboard.writeText(value)
    ElMessage.success(`${label}已复制`)
  } catch {
    ElMessage.warning('浏览器不允许自动复制，请手动选择文本')
  }
}

async function trustSigningKey(): Promise<void> {
  const publicKey = trustKeyPublicKey.value.trim()
  if (!/^[0-9a-fA-F]{64}$/.test(publicKey)) {
    ElMessage.warning('请粘贴 64 位十六进制的签发机公钥')
    return
  }
  trusting.value = true
  try {
    await post('/account-packages/signing-keys/trusted', { public_key: publicKey })
    trustKeyPublicKey.value = ''
    ElMessage.success('已信任该签发机')
    await loadSigningKeys()
  } catch (error) {
    ElMessage.error(errorText(error, '添加信任失败'))
  } finally {
    trusting.value = false
  }
}

async function untrustSigningKey(fingerprint: string): Promise<void> {
  try {
    await ElMessageBox.confirm(`移除后来自该签发机的包需要重新核对指纹，确定移除？`, '移除信任', {
      type: 'warning',
      confirmButtonText: '移除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await del(`/account-packages/signing-keys/trusted/${encodeURIComponent(fingerprint)}`)
    ElMessage.success('已移除该签发机的信任')
    await loadSigningKeys()
  } catch (error) {
    ElMessage.error(errorText(error, '移除信任失败'))
  }
}

async function loadAuthorization(): Promise<void> {
  try {
    const [catalog, status] = await Promise.all([
      get<AuthzCatalog>('/account-packages/authorization-catalog'),
      get<IssueStatus>('/account-packages/can-issue'),
    ])
    authzCatalog.value = catalog
    issueStatus.value = status
  } catch (error) {
    authzCatalog.value = null
    issueStatus.value = null
    ElMessage.error(errorText(error, '加载授权目录失败'))
  }
}

onMounted(async () => {
  void refresh()
  void loadAuthorization()
  void loadSigningKeys()
  if (!menuStore.loaded) {
    try {
      await menuStore.fetchMenus()
    } catch {
      // 菜单加载失败不阻断签发；未加载时用户只能留空继承角色默认
    }
  }
})

defineExpose({
  packages,
  receipts,
  exportForm,
  exportResult,
  menuOptions,
  authzCatalog,
  issueStatus,
  signingKeys,
  trustKeyPublicKey,
  importTrustAcknowledged,
  grantSelections,
  selectedGrantCount,
  buildGrants,
  loadAuthorization,
  loadSigningKeys,
  trustSigningKey,
  untrustSigningKey,
  copyText,
  importFile,
  importPassword,
  importPreview,
  importResult,
  openExportDialog,
  addAccount,
  removeAccount,
  exportPackage,
  closeOtpDialog,
  downloadCredentialSheet,
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
.grant-block {
  width: 100%;
}
.grant-hint {
  margin-bottom: 8px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
.grant-scroll {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 4px;
  padding: 8px 12px;
}
.grant-section + .grant-section {
  margin-top: 10px;
}
.grant-section-title {
  font-weight: 600;
  margin: 6px 0;
}
.grant-group {
  margin-left: 12px;
  padding-left: 10px;
  border-left: 2px solid var(--el-border-color-lighter);
}
.grant-group-title {
  color: var(--el-text-color-secondary);
  font-size: 12px;
  margin: 6px 0;
}
.grant-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 34px;
}
.grant-label {
  font-size: 13px;
}
.grant-row .el-select {
  width: 150px;
}
.grant-summary {
  margin-top: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.grant-blocked {
  color: var(--el-color-warning);
}
.issue-blocked {
  margin-top: 10px;
}
.accounts-heading {
  margin: 8px 0 12px;
  font-weight: 600;
}
.account-block {
  padding: 8px 0;
  border-bottom: 1px dashed var(--el-border-color-lighter);
}
.account-row {
  margin-bottom: 8px;
}
.account-row--secondary .el-input {
  width: 220px;
}
.account-row--secondary .el-select {
  width: 260px;
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
.signing-key-panel {
  margin: 12px 0 18px;
  padding: 12px 16px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  background: var(--el-fill-color-lighter);
}
.signing-key-head,
.signing-key-row,
.trust-key-form {
  display: flex;
  align-items: center;
  gap: 10px;
}
.signing-key-head {
  justify-content: space-between;
}
.signing-key-hint {
  margin: 4px 0 0;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
.signing-key-row {
  margin-top: 8px;
  flex-wrap: wrap;
}
.signing-key-row code {
  font-size: 13px;
  word-break: break-all;
}
.signing-key-label {
  min-width: 76px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.signing-key-row .el-input {
  max-width: 520px;
}
.trusted-keys {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px dashed var(--el-border-color);
}
.trusted-keys-title {
  font-weight: 600;
  font-size: 13px;
}
.trust-key-form {
  margin-top: 10px;
}
.trust-key-form .el-input {
  max-width: 520px;
}
.signer-trust {
  margin-top: 12px;
  padding: 10px 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
}
.signer-trust .signing-key-row {
  margin: 10px 0;
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
