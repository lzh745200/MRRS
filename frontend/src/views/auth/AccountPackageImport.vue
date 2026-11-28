<template>
  <div class="account-import-page">
    <el-card class="import-card" shadow="always">
      <template #header>
        <div class="import-header">
          <h2>导入账号开通包</h2>
          <p>仅全新机器（尚无账号）可在登录前导入；已初始化机器请登录管理员后在系统管理中导入。</p>
        </div>
      </template>

      <el-alert
        type="warning"
        :closable="false"
        show-icon
        title="账号包与包口令必须来自不同渠道。首次登录必须修改初始密码。"
      />

      <template v-if="!result">
        <el-upload
          drag
          action="#"
          accept=".apkg"
          :auto-upload="false"
          :limit="1"
          :on-change="onFileChange"
          :on-remove="onFileRemove"
        >
          <div class="upload-tip">拖拽账号包（.apkg）到此处，或点击选择</div>
        </el-upload>
        <el-input
          v-model="password"
          type="password"
          show-password
          autocomplete="off"
          placeholder="包口令"
          class="password-input"
        />
        <el-button type="primary" :loading="previewing" @click="preview">校验并预览</el-button>

        <div class="takeover-block">
          <p class="takeover-hint">
            全新机器导入时，必须同时为本机的出厂管理员设置新密码；导入成功后出厂密码立即失效。
          </p>
          <el-input
            v-model="factoryPassword"
            type="password"
            show-password
            autocomplete="new-password"
            placeholder="本机超级管理员新密码"
            class="password-input"
            data-testid="factory-password"
          />
          <el-input
            v-model="factoryPasswordConfirm"
            type="password"
            show-password
            autocomplete="new-password"
            placeholder="再次输入新密码"
            class="password-input"
            data-testid="factory-password-confirm"
          />
        </div>

        <div v-if="previewData" class="preview" data-testid="account-import-preview">
          <h3>包内容预览</h3>
          <p>组织：{{ previewData.organization_name }}（{{ previewData.organization_code }}）</p>
          <p>过期时间：{{ formatDateTimeLocale(previewData.expires_at) }}</p>
          <div
            v-if="previewData.signer_fingerprint"
            class="signer-trust"
            data-testid="signer-trust"
          >
            <el-alert
              v-if="previewData.signer_trusted"
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
              <p>
                签发机指纹：<code data-testid="import-signer-fingerprint">{{
                  previewData.signer_fingerprint
                }}</code>
              </p>
              <el-checkbox v-model="trustAcknowledged" data-testid="ack-signer-fingerprint">
                我已通过独立渠道核对上述指纹
              </el-checkbox>
            </template>
          </div>
          <p v-if="previewData.authorization" data-testid="account-import-authorization">
            授权范围：页面 {{ previewData.authorization.page_count }} 个（可操作
            {{ previewData.authorization.edit_page_count }} / 只读
            {{ previewData.authorization.view_page_count }}），接口模块
            {{ previewData.authorization.module_count }} 个
          </p>
          <ul>
            <li v-for="account in previewData.accounts || []" :key="account.username">
              {{ account.full_name || account.username }}（{{ account.username }} /
              {{ account.role || '-' }} / {{ account.data_scope || '-' }}）
            </li>
          </ul>
          <el-button type="danger" :loading="confirming" @click="confirm">
            确认导入并创建账号
          </el-button>
        </div>
      </template>

      <div v-else class="result" data-testid="account-import-result">
        <el-result icon="success" title="账号包导入成功" />
        <p>组织编码：{{ result.organization_code }}</p>
        <el-alert
          type="warning"
          :closable="false"
          show-icon
          title="本机的出厂管理员仍是出厂密码，请现在登录修改。"
        />
        <p v-for="user in result.users" :key="user.user_id">
          {{ user.username }}（首次登录须修改密码）
        </p>
        <el-button type="primary" @click="goLogin">前往登录</el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage, type UploadFile } from 'element-plus'
import { post } from '@/api/request'
import { getErrorMessage } from '@/utils/getErrorMessage'
import { formatDateTimeLocale } from '@/utils/datetime'
import { useRouterSafe } from '@/composables/useRouterSafe'

interface PreviewAccount {
  username?: string
  full_name?: string
  role?: string
  data_scope?: string
}

interface PreviewData {
  organization_code: string
  organization_name: string
  expires_at: string
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
  }
  factory_admin_rotation_required?: boolean
}

interface ImportResult {
  organization_code: string
  users: Array<{ user_id: number; username: string }>
}

const { pushSafe } = useRouterSafe()
const file = ref<File | null>(null)
const password = ref('')
const factoryPassword = ref('')
const factoryPasswordConfirm = ref('')
const previewing = ref(false)
const confirming = ref(false)
const previewData = ref<PreviewData | null>(null)
const result = ref<ImportResult | null>(null)
const trustAcknowledged = ref(false)

function errorText(error: unknown, fallback: string): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (detail && typeof detail === 'object' && 'message' in detail) {
    const message = (detail as { message?: unknown }).message
    if (typeof message === 'string' && message) return message
  }
  return getErrorMessage(error, fallback)
}

function onFileChange(uploadFile: UploadFile): void {
  file.value = uploadFile.raw || null
  previewData.value = null
  trustAcknowledged.value = false
}

function onFileRemove(): void {
  file.value = null
  previewData.value = null
  trustAcknowledged.value = false
}

function formData(): FormData {
  const form = new FormData()
  form.append('file', file.value as File)
  form.append('password', password.value)
  // 登录前导入专用：本机出厂管理员的新密码；服务端只在确有未改密的出厂超管时使用
  form.append('factory_admin_password', factoryPassword.value)
  if (trustAcknowledged.value && previewData.value?.signer_fingerprint) {
    form.append('confirmed_fingerprint', previewData.value.signer_fingerprint)
  }
  return form
}

async function preview(): Promise<void> {
  if (!file.value || !password.value) {
    ElMessage.warning('请选择账号包并输入包口令')
    return
  }
  previewing.value = true
  try {
    previewData.value = await post<PreviewData>('/account-packages/preview', formData())
    trustAcknowledged.value = false
  } catch (error) {
    previewData.value = null
    ElMessage.error(errorText(error, '账号包预览失败'))
  } finally {
    previewing.value = false
  }
}

async function confirm(): Promise<void> {
  if (!file.value || !password.value || !previewData.value) {
    ElMessage.warning('请先完成账号包预览')
    return
  }
  if (previewData.value.trust_required && !trustAcknowledged.value) {
    ElMessage.warning('请先通过独立渠道核对签发机指纹并勾选确认')
    return
  }
  if (factoryPassword.value !== factoryPasswordConfirm.value) {
    ElMessage.warning('两次输入的超级管理员新密码不一致')
    return
  }
  confirming.value = true
  try {
    result.value = await post<ImportResult>('/account-packages/confirm', formData())
    ElMessage.success('账号包导入成功')
  } catch (error) {
    ElMessage.error(errorText(error, '确认导入失败'))
  } finally {
    confirming.value = false
  }
}

function goLogin(): void {
  pushSafe('/login')
}
</script>

<style scoped>
.account-import-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: var(--el-bg-color-page);
}
.import-card {
  width: 680px;
}
.import-header h2 {
  margin: 0 0 8px;
}
.import-header p {
  margin: 0;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.upload-tip {
  padding: 28px 0;
  color: var(--el-text-color-secondary);
}
.password-input {
  margin: 16px 0;
}
.takeover-hint {
  margin: 12px 0 0;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.preview {
  margin-top: 20px;
}
.signer-trust {
  margin: 12px 0;
  padding: 10px 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
}
.signer-trust code {
  word-break: break-all;
}
.result {
  margin-top: 16px;
}
</style>
