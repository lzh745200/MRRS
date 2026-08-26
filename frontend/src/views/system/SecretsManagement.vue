<template>
  <div class="secrets-management">
    <!-- 页面标题 -->
    <div class="page-header">
      <h3>密钥生命周期管理</h3>
      <el-button :icon="Refresh" :loading="loadingStatus" @click="refreshAll"> 刷新 </el-button>
    </div>

    <!-- 状态概览卡片 -->
    <el-row :gutter="16" class="status-row">
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="总版本数" :value="status.total_versions" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="活跃版本数" :value="status.active_versions" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="最新版本">
            <template #default>
              {{ status.latest_version?.version_id ?? '-' }}
            </template>
          </el-statistic>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="rotation-status">
            <span class="rotation-label">需要轮换</span>
            <el-tag :type="status.requires_rotation ? 'warning' : 'success'" size="large">
              {{ status.requires_rotation ? '是' : '否' }}
            </el-tag>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 操作栏 -->
    <el-card class="actions-card">
      <div class="actions-bar">
        <el-button type="warning" :icon="Warning" :loading="loadingRotate" @click="handleRotate">
          轮换密钥
        </el-button>
        <el-button type="primary" :icon="Key" :loading="loadingCreate" @click="openCreateDialog">
          创建密钥
        </el-button>
        <el-button
          type="danger"
          plain
          :icon="Delete"
          :loading="loadingCleanup"
          @click="handleCleanup"
        >
          清理过期密钥
        </el-button>
      </div>
    </el-card>

    <!-- 密钥版本表格 -->
    <el-card class="table-card">
      <template #header>
        <span>密钥版本列表</span>
      </template>

      <el-table
        v-loading="loadingVersions"
        :data="versions"
        stripe
        border
        empty-text="暂无密钥版本"
      >
        <el-table-column prop="version_id" label="版本 ID" min-width="200" show-overflow-tooltip />
        <el-table-column label="创建时间" width="200" align="center">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="120" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row)">
              {{ getStatusText(row) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="key_type" label="密钥类型" width="120" align="center" />
        <el-table-column label="操作" width="120" align="center" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.is_active"
              type="danger"
              size="small"
              :loading="revokingId === row.version_id"
              @click="handleRevoke(row)"
            >
              撤销
            </el-button>
            <span v-else class="text-gray">-</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 创建密钥对话框 -->
    <el-dialog v-model="createDialogVisible" title="创建新密钥" :width="DIALOG_SM" destroy-on-close>
      <el-form ref="createFormRef" :model="createForm" label-width="100px">
        <el-form-item label="密钥类型">
          <el-select v-model="createForm.key_type" style="width: 100%">
            <el-option label="Fernet (推荐)" value="fernet" />
            <el-option label="AES" value="aes" />
            <el-option label="ChaCha20" value="chacha20" />
          </el-select>
        </el-form-item>
        <el-form-item label="过期天数">
          <el-input-number
            v-model="createForm.expires_days"
            :min="1"
            :max="3650"
            placeholder="留空表示永不过期"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="loadingCreate" @click="handleCreate"> 创建 </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { DIALOG_SM } from '@/config/dialog'
import { ref, reactive, onMounted } from 'vue'
import { Refresh, Key, Warning, Delete } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { secretsApi, type KeyVersion, type SecretsStatus } from '@/api/secrets'

// ==================== 响应式状态 ====================

const loadingStatus = ref(false)
const loadingVersions = ref(false)
const loadingRotate = ref(false)
const loadingCreate = ref(false)
const loadingCleanup = ref(false)
const revokingId = ref<string | null>(null)

const status = reactive<SecretsStatus>({
  total_versions: 0,
  active_versions: 0,
  latest_version: undefined,
  requires_rotation: false,
})

const versions = ref<KeyVersion[]>([])

const createDialogVisible = ref(false)
const createForm = reactive({
  key_type: 'fernet',
  expires_days: undefined as number | undefined,
})

// ==================== 数据加载 ====================

async function loadStatus() {
  loadingStatus.value = true
  try {
    const res = await secretsApi.getStatus()
    status.total_versions = res.total_versions
    status.active_versions = res.active_versions
    status.latest_version = res.latest_version
    status.requires_rotation = res.requires_rotation
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : '获取密钥状态失败'
    ElMessage.error(msg)
  } finally {
    loadingStatus.value = false
  }
}

async function loadVersions() {
  loadingVersions.value = true
  try {
    const res = await secretsApi.getVersions()
    versions.value = res.versions
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : '获取密钥版本失败'
    ElMessage.error(msg)
  } finally {
    loadingVersions.value = false
  }
}

async function refreshAll() {
  await Promise.all([loadStatus(), loadVersions()])
}

// ==================== 操作处理 ====================

async function handleRotate() {
  try {
    await ElMessageBox.confirm('这将使所有现有令牌失效，确定继续吗？', '确认轮换', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    // 用户取消
    return
  }

  loadingRotate.value = true
  try {
    const res = await secretsApi.rotateSecrets()
    ElMessage.success(res.message ?? '密钥轮换成功')
    await refreshAll()
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : '密钥轮换失败'
    ElMessage.error(msg)
  } finally {
    loadingRotate.value = false
  }
}

async function handleCreate() {
  loadingCreate.value = true
  try {
    const params: { key_type?: string; expires_days?: number } = {
      key_type: createForm.key_type,
    }
    if (createForm.expires_days !== undefined && createForm.expires_days !== null) {
      params.expires_days = createForm.expires_days
    }
    const res = await secretsApi.createSecret(params)
    ElMessage.success(res.message ?? '密钥创建成功')
    createDialogVisible.value = false
    createForm.key_type = 'fernet'
    createForm.expires_days = undefined
    await refreshAll()
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : '创建密钥失败'
    ElMessage.error(msg)
  } finally {
    loadingCreate.value = false
  }
}

function openCreateDialog() {
  createForm.key_type = 'fernet'
  createForm.expires_days = undefined
  createDialogVisible.value = true
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
async function handleRevoke(row: any) {
  try {
    await ElMessageBox.confirm(
      `确定撤销密钥版本 ${row.version_id} 吗？撤销后该密钥将无法使用。`,
      '确认撤销',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
  } catch {
    return
  }

  revokingId.value = row.version_id
  try {
    const res = await secretsApi.revokeSecret(row.version_id)
    ElMessage.success(res.message ?? '密钥已撤销')
    await refreshAll()
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : '撤销密钥失败'
    ElMessage.error(msg)
  } finally {
    revokingId.value = null
  }
}

async function handleCleanup() {
  try {
    await ElMessageBox.confirm('将清理超过保留期的过期和已撤销密钥，确定继续吗？', '确认清理', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }

  loadingCleanup.value = true
  try {
    const res = await secretsApi.cleanup()
    ElMessage.success(res.message ?? `清理了 ${res.deleted_count} 个过期密钥`)
    await refreshAll()
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : '清理失败'
    ElMessage.error(msg)
  } finally {
    loadingCleanup.value = false
  }
}

// ==================== 工具函数 ====================

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function formatTime(ts?: any): string {
  if (!ts) return '-'
  return new Date(Number(ts) * 1000).toLocaleString('zh-CN')
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function getStatusType(row: any): 'success' | 'warning' | 'danger' | 'info' {
  if (row.is_active) return 'success'
  if (row.revoked_at) return 'danger'
  return 'warning'
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function getStatusText(row: any): string {
  if (row.is_active) return '活跃'
  if (row.revoked_at) return '已撤销'
  return '已过期'
}

// ==================== 生命周期 ====================

onMounted(() => {
  refreshAll()
})
</script>

<style scoped>
.secrets-management {
  padding: 16px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.page-header h3 {
  margin: 0;
  font-size: 18px;
}

.status-row {
  margin-bottom: 16px;
}

.status-row .el-card {
  text-align: center;
}

.rotation-status {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.rotation-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.actions-card {
  margin-bottom: 16px;
}

.actions-bar {
  display: flex;
  gap: 12px;
}

.table-card {
  margin-bottom: 16px;
}

.text-gray {
  color: var(--el-text-color-placeholder);
}
</style>
