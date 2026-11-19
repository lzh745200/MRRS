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

        <div v-if="previewData" class="preview" data-testid="account-import-preview">
          <h3>包内容预览</h3>
          <p>组织：{{ previewData.organization_name }}（{{ previewData.organization_code }}）</p>
          <p>过期时间：{{ formatDateTimeLocale(previewData.expires_at) }}</p>
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
}

interface ImportResult {
  organization_code: string
  users: Array<{ user_id: number; username: string }>
}

const { pushSafe } = useRouterSafe()
const file = ref<File | null>(null)
const password = ref('')
const previewing = ref(false)
const confirming = ref(false)
const previewData = ref<PreviewData | null>(null)
const result = ref<ImportResult | null>(null)

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
}

function onFileRemove(): void {
  file.value = null
  previewData.value = null
}

function formData(): FormData {
  const form = new FormData()
  form.append('file', file.value as File)
  form.append('password', password.value)
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
.preview {
  margin-top: 20px;
}
.result {
  margin-top: 16px;
}
</style>
