<template>
  <div class="backup-management">
    <!-- W12-T045: 磁盘空间不足警告 -->
    <el-alert
      v-if="diskSpaceWarning"
      type="warning"
      :closable="false"
      show-icon
      :title="diskSpaceWarning"
      style="margin-bottom: 16px"
    />
    <!-- 自动备份设置 -->
    <el-card class="auto-backup-card">
      <template #header>
        <div class="card-header">
          <span class="title">自动备份设置</span>
        </div>
      </template>
      <el-form :model="autoBackupConfig" label-width="140px" class="auto-backup-form">
        <el-form-item label="启用自动备份">
          <el-switch v-model="autoBackupConfig.enabled" active-text="开启" inactive-text="关闭" />
        </el-form-item>
        <el-form-item label="备份频率">
          <el-radio-group
            v-model="autoBackupConfig.frequency"
            :disabled="!autoBackupConfig.enabled"
          >
            <el-radio value="daily">每日</el-radio>
            <el-radio value="weekly">每周</el-radio>
            <el-radio value="monthly">每月</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="保留备份份数">
          <el-input-number
            v-model="autoBackupConfig.retentionCount"
            :min="1"
            :max="30"
            :disabled="!autoBackupConfig.enabled"
          />
          <span class="retention-hint">保留最近 N 份备份</span>
        </el-form-item>
        <el-form-item label="下次备份时间">
          <span>{{ nextBackupTime }}</span>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="saveAutoBackupConfig">保存设置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 备份目标（U盘/移动硬盘） -->
    <el-card class="backup-target-card">
      <template #header>
        <div class="card-header">
          <span class="title">备份目标目录</span>
          <el-button :loading="targetLoading" @click="loadBackupDirs">刷新磁盘</el-button>
        </div>
      </template>
      <el-alert
        type="info"
        show-icon
        :closable="false"
        title="建议把备份写到 U 盘或移动硬盘：即使本机硬盘损坏，数据仍可恢复。"
        class="target-tip"
      />
      <el-form label-width="120px" class="target-form">
        <el-form-item label="当前目标">
          <el-input
            v-model="backupTarget"
            placeholder="留空=应用数据目录；可填 U 盘/共享盘路径，如 E:\backup"
          >
            <template #append>
              <el-button @click="saveBackupTarget">保存目标</el-button>
            </template>
          </el-input>
        </el-form-item>
        <el-form-item label="检测到的磁盘">
          <div v-if="backupDirs.length" class="dir-list">
            <el-tag
              v-for="d in backupDirs"
              :key="d.path"
              :type="d.available ? (d.type === 'removable' ? 'success' : 'info') : 'danger'"
              class="dir-tag"
              @click="backupTarget = d.path"
            >
              {{ d.path }} ({{ dirTypeLabel(d.type) }}{{ d.available ? '' : '·不可写' }})
            </el-tag>
          </div>
          <span v-else class="dir-empty">未检测到磁盘信息</span>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card>
      <template #header>
        <div class="card-header">
          <span class="title">系统备份管理</span>
          <div class="header-actions">
            <el-button :loading="loading" @click="refreshAll">刷新</el-button>
            <template v-if="canOperateBackup">
              <el-button type="success" @click="importDialogVisible = true"> 导入备份包 </el-button>
              <el-button type="primary" @click="handleCreateBackup"> 创建备份 </el-button>
            </template>
            <el-tag v-else type="info" size="small">只读模式（普通用户）</el-tag>
          </div>
        </div>
      </template>

      <!-- 备份统计 -->
      <el-descriptions :column="3" border class="backup-status">
        <el-descriptions-item label="备份数量">
          {{ backupStats.totalBackups ?? 0 }}
        </el-descriptions-item>
        <el-descriptions-item label="总大小">
          {{ formatSize(backupStats.totalSize ?? 0) }}
        </el-descriptions-item>
        <el-descriptions-item label="最近备份">
          {{ formatTime(backupStats.lastBackup) }}
        </el-descriptions-item>
        <el-descriptions-item label="完整备份">
          {{ backupStats.fullBackups ?? 0 }}
        </el-descriptions-item>
        <el-descriptions-item label="增量备份">
          {{ backupStats.incrementalBackups ?? 0 }}
        </el-descriptions-item>
        <el-descriptions-item label="自动备份">
          <el-tag :type="backupStats.scheduleEnabled ? 'success' : 'info'">
            {{ backupStats.scheduleEnabled ? '已启用' : '未启用' }}
          </el-tag>
        </el-descriptions-item>
      </el-descriptions>

      <!-- 备份列表 -->
      <el-table v-loading="loading" :data="backupList" style="width: 100%; margin-top: 20px">
        <el-table-column prop="file_name" label="文件名" min-width="200" />
        <el-table-column prop="description" label="描述" min-width="150" />
        <el-table-column prop="backup_type" label="类型" width="80">
          <template #default="{ row }">
            <el-tag size="small" :type="row.backup_type === 'incremental' ? 'warning' : 'primary'">
              {{ row.backup_type === 'incremental' ? '增量' : '完整' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="大小" width="100">
          <template #default="{ row }">
            {{ formatSize(row.file_size) }}
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <template v-if="canOperateBackup">
              <el-button size="small" type="primary" @click="handleDownload(row)"> 下载 </el-button>
              <el-button size="small" type="warning" @click="handleRestore(row)"> 恢复 </el-button>
              <el-button size="small" type="danger" @click="handleDelete(row)"> 删除 </el-button>
            </template>
            <span v-else class="readonly-hint">—</span>
          </template>
        </el-table-column>
      </el-table>

      <EmptyState v-if="!loading && !backupList.length" text="暂无备份记录" />
    </el-card>

    <!-- 备份计划配置 -->
    <el-card class="schedule-card">
      <template #header>
        <div class="card-header">
          <span class="title">备份计划</span>
          <el-tag :type="scheduleConfig.enabled ? 'success' : 'info'" size="small">
            {{ scheduleConfig.enabled ? '已启用' : '未启用' }}
          </el-tag>
        </div>
      </template>
      <el-form :model="scheduleConfig" label-width="120px" class="schedule-form">
        <el-form-item label="启用定时备份">
          <el-switch v-model="scheduleConfig.enabled" active-text="开启" inactive-text="关闭" />
        </el-form-item>
        <el-form-item label="备份频率">
          <el-select
            v-model="scheduleConfig.frequency"
            placeholder="请选择频率"
            style="width: 200px"
          >
            <el-option label="每天" value="daily" />
            <el-option label="每周" value="weekly" />
            <el-option label="每月" value="monthly" />
          </el-select>
        </el-form-item>
        <el-form-item label="备份时间">
          <el-time-picker
            v-model="scheduleConfig.backupTime"
            format="HH:mm"
            value-format="HH:mm"
            placeholder="选择时间"
            style="width: 200px"
          />
        </el-form-item>
        <el-form-item label="保留份数">
          <el-input-number
            v-model="scheduleConfig.retentionCount"
            :min="1"
            :max="99"
            placeholder="保留最近 N 份备份"
          />
        </el-form-item>
        <el-form-item v-if="canOperateBackup">
          <el-button type="primary" :loading="savingSchedule" @click="saveSchedule">
            保存计划
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 创建备份对话框 -->
    <el-dialog v-model="createDialogVisible" append-to-body title="创建备份" :width="DIALOG_SM">
      <el-form :model="backupForm" label-width="120px">
        <el-form-item label="备份描述">
          <el-input v-model="backupForm.description" placeholder="请输入备份描述" />
        </el-form-item>
        <el-form-item label="包含上传文件">
          <el-switch v-model="backupForm.include_uploads" />
        </el-form-item>
        <el-form-item label="加密密码">
          <el-input
            v-model="backupForm.password"
            type="password"
            placeholder="留空则不加密"
            show-password
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="confirmCreateBackup">
          确定
        </el-button>
      </template>
    </el-dialog>

    <!-- 恢复备份确认对话框 -->
    <el-dialog v-model="restoreDialogVisible" append-to-body title="恢复备份" :width="DIALOG_SM">
      <el-alert title="警告：恢复备份将覆盖当前所有数据！" type="error" :closable="false" />
      <div style="margin-top: 16px">
        <p><strong>备份文件：</strong>{{ restoreTarget?.file_name }}</p>
        <p><strong>创建时间：</strong>{{ formatTime(restoreTarget?.created_at) }}</p>
        <p><strong>大小：</strong>{{ formatSize(restoreTarget?.file_size ?? 0) }}</p>
      </div>
      <el-form
        v-if="restoreTarget?.is_encrypted"
        :model="restoreForm"
        label-width="120px"
        style="margin-top: 16px"
      >
        <el-form-item label="解密密码" required>
          <el-input
            v-model="restoreForm.password"
            type="password"
            placeholder="请输入加密密码"
            show-password
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="restoreDialogVisible = false">取消</el-button>
        <el-button type="danger" :loading="restoring" @click="confirmRestore"> 确认恢复 </el-button>
      </template>
    </el-dialog>
    <!-- 导入备份包对话框 -->
    <el-dialog
      v-model="importDialogVisible"
      append-to-body
      title="导入备份包并恢复"
      :width="DIALOG_SM"
      :close-on-click-modal="false"
    >
      <el-alert
        title="警告：恢复将覆盖当前全部数据（含数据库与上传文件），此操作不可撤销！"
        type="error"
        :closable="false"
        class="import-warn"
      />
      <el-form label-width="110px" style="margin-top: 16px">
        <el-form-item label="备份文件" required>
          <el-upload
            :auto-upload="false"
            :limit="1"
            accept=".zip"
            :on-change="onImportFileChange"
            :on-remove="() => (importFile = null)"
            :file-list="importFileList"
          >
            <el-button>选择备份包（.zip）</el-button>
            <template #tip>
              <div class="el-upload__tip">支持本机或其他机器导出的备份包（含加密备份）</div>
            </template>
          </el-upload>
        </el-form-item>
        <el-form-item label="解密密码">
          <el-input
            v-model="importForm.password"
            type="password"
            placeholder="加密备份必填，未加密可留空"
            show-password
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="importDialogVisible = false">取消</el-button>
        <el-button
          type="danger"
          :loading="importing"
          :disabled="!importFile"
          @click="confirmImportRestore"
        >
          确认导入并恢复
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { DIALOG_SM } from '@/config/dialog'
import EmptyState from '@/components/business/EmptyState/EmptyState.vue'
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { get, post, put, del } from '@/api/request'
import { useBackupSchedule } from '@/composables/useBackupSchedule'
import { uploadRestoreBackup } from '@/api/backup'
import { AuthStorage } from '@/utils/authStorage'

// 普通用户只读：仅 admin/super_admin 可执行备份写操作（后端 require_admin 双重把关）。
// 无用户信息时保持按钮可见（后端权限兜底），兼容未注入用户态的旧测试场景。
const canOperateBackup = computed(() => {
  try {
    const user: any = typeof AuthStorage.getUser === 'function' ? AuthStorage.getUser() : null
    if (!user) return true
    const role = user.role || ''
    return ['admin', 'super_admin'].includes(role) || !!user.is_superuser
  } catch {
    return true
  }
})

const loading = ref(false)
const creating = ref(false)
const restoring = ref(false)
const backupList = ref<any[]>([])
const backupStats = ref<Record<string, any>>({
  totalBackups: 0,
  totalSize: 0,
  lastBackup: null,
  fullBackups: 0,
  incrementalBackups: 0,
  scheduleEnabled: false,
})

// W12-T045: 磁盘空间感知（备份目录 / 数据库目录剩余空间）
const diskSpace = ref<Record<string, any> | null>(null)
const diskSpaceWarning = computed(() => {
  const info = diskSpace.value
  if (!info) return null
  const dir = info.backup_dir || info.db_dir
  if (!dir || dir.sufficient === undefined) return null
  if (dir.sufficient === false) {
    return `磁盘剩余空间不足（${dir.free_mb ?? -1}MB < ${info.threshold_mb ?? 500}MB），备份/恢复可能被拒绝`
  }
  return null
})

const createDialogVisible = ref(false)
const restoreDialogVisible = ref(false)
const restoreTarget = ref<any>(null)
const backupForm = ref({
  description: '手动备份',
  include_uploads: true,
  password: '',
})
const restoreForm = ref({ password: '' })

// ── 备份目标目录（U盘/移动硬盘） ──
const targetLoading = ref(false)
const backupTarget = ref('')
const backupDirs = ref<Array<{ path: string; type: string; available: boolean }>>([])

async function loadBackupDirs() {
  targetLoading.value = true
  try {
    const res = await get('/system/backup/dirs')
    backupDirs.value = res?.dirs ?? []
    backupTarget.value = res?.current ?? ''
  } catch {
    ElMessage.error('检测备份目录失败')
  } finally {
    targetLoading.value = false
  }
}

async function saveBackupTarget() {
  try {
    await put('/system/backup/target', { target_dir: backupTarget.value.trim() })
    ElMessage.success('备份目标已保存')
    await loadBackupDirs()
  } catch (e: any) {
    ElMessage.error(e?.detail || '保存备份目标失败')
  }
}

function dirTypeLabel(type: string): string {
  const map: Record<string, string> = {
    removable: '可移动',
    fixed: '固定盘',
    network: '网络盘',
    configured: '已配置',
  }
  return map[type] ?? type
}

// ── Auto backup settings (localStorage-based) ──
const AUTO_BACKUP_STORAGE_KEY = 'auto-backup-config'

interface AutoBackupConfig {
  enabled: boolean
  frequency: 'daily' | 'weekly' | 'monthly'
  retentionCount: number
}

function loadAutoBackupConfig(): AutoBackupConfig {
  try {
    const raw = localStorage.getItem(AUTO_BACKUP_STORAGE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw)
      return {
        enabled: typeof parsed.enabled === 'boolean' ? parsed.enabled : false,
        frequency: ['daily', 'weekly', 'monthly'].includes(parsed.frequency)
          ? parsed.frequency
          : 'daily',
        retentionCount:
          typeof parsed.retentionCount === 'number' &&
          parsed.retentionCount >= 1 &&
          parsed.retentionCount <= 30
            ? parsed.retentionCount
            : 7,
      }
    }
  } catch {
    // Ignore parse errors
  }
  return { enabled: false, frequency: 'daily', retentionCount: 7 }
}

const autoBackupConfig = reactive<AutoBackupConfig>(loadAutoBackupConfig())

watch(
  () => ({ ...autoBackupConfig }),
  (val) => {
    try {
      localStorage.setItem(AUTO_BACKUP_STORAGE_KEY, JSON.stringify(val))
    } catch {
      // Storage full or unavailable
    }
  },
  { deep: true }
)

const nextBackupTime = computed(() => {
  if (!autoBackupConfig.enabled) return '未启用'
  const now = new Date()
  const next = new Date(now)
  next.setHours(2, 0, 0, 0)
  switch (autoBackupConfig.frequency) {
    case 'daily':
      if (next <= now) next.setDate(next.getDate() + 1)
      break
    case 'weekly': {
      const dayOfWeek = next.getDay()
      const daysUntilMonday = dayOfWeek === 0 ? 1 : (8 - dayOfWeek) % 7
      next.setDate(next.getDate() + daysUntilMonday)
      if (next <= now) next.setDate(next.getDate() + 7)
      break
    }
    case 'monthly':
      next.setMonth(next.getMonth() + 1, 1)
      break
  }
  return next.toLocaleString('zh-CN')
})

function saveAutoBackupConfig() {
  try {
    localStorage.setItem(AUTO_BACKUP_STORAGE_KEY, JSON.stringify({ ...autoBackupConfig }))
    ElMessage.success('自动备份设置已保存')
  } catch {
    ElMessage.error('保存自动备份设置失败')
  }
}

// ── Backup schedule configuration ──
const { scheduleConfig, savingSchedule, loadScheduleConfig, saveSchedule } = useBackupSchedule()

async function fetchBackupList() {
  try {
    const res = await get('/system/backup')
    const resData = res.data
    backupList.value = resData?.data?.items ?? resData?.items ?? []
  } catch {
    ElMessage.error('获取备份列表失败')
  }
}

async function fetchBackupStats() {
  try {
    const res = await get('/system/backup/stats')
    const resData = res.data?.data ?? res.data
    backupStats.value = {
      totalBackups: resData?.totalBackups ?? 0,
      totalSize: resData?.totalSize ?? 0,
      lastBackup: resData?.lastBackup ?? null,
      fullBackups: resData?.fullBackups ?? 0,
      incrementalBackups: resData?.incrementalBackups ?? 0,
      scheduleEnabled: resData?.scheduleEnabled ?? false,
    }
    // W12-T045: 磁盘空间感知
    diskSpace.value = resData?.disk_space ?? null
  } catch {
    // 静默处理
  }
}

async function refreshAll() {
  loading.value = true
  try {
    await Promise.all([fetchBackupList(), fetchBackupStats()])
  } finally {
    loading.value = false
  }
}

function handleCreateBackup() {
  backupForm.value = {
    description: '手动备份',
    include_uploads: true,
    password: '',
  }
  createDialogVisible.value = true
}

async function confirmCreateBackup() {
  creating.value = true
  try {
    const res = await post('/system/backup', {
      description: backupForm.value.description,
      include_uploads: backupForm.value.include_uploads,
      password: backupForm.value.password || null,
    })
    if (res?.success !== false) {
      ElMessage.success('已创建')
      createDialogVisible.value = false
      await refreshAll()
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '创建备份失败')
  } finally {
    creating.value = false
  }
}

async function handleDelete(row: any) {
  try {
    await ElMessageBox.confirm(`确定要删除备份 "${row.file_name}" 吗？`, '警告', {
      type: 'warning',
    })
    const res = await del(`/system/backup/${row.file_name}`)
    if (res?.success !== false) {
      ElMessage.success('已删除')
      await refreshAll()
    }
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

function handleRestore(row: any) {
  restoreTarget.value = row
  restoreForm.value.password = ''
  restoreDialogVisible.value = true
}

async function confirmRestore() {
  if (!restoreTarget.value) return
  restoring.value = true
  try {
    const res = await post('/system/backup/restore', {
      filename: restoreTarget.value.file_name,
      password: restoreForm.value.password || null,
    })
    if (res?.success !== false) {
      ElMessage.success('系统恢复成功，请重新登录')
      restoreDialogVisible.value = false
      setTimeout(() => {
        window.location.href = '/login'
      }, 2000)
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '恢复失败')
  } finally {
    restoring.value = false
  }
}

// ── 导入备份包恢复 ──
const importDialogVisible = ref(false)
const importing = ref(false)
const importFile = ref<File | null>(null)
const importFileList = ref<any[]>([])
const importForm = ref({ password: '' })

function onImportFileChange(uploadFile: any) {
  importFile.value = uploadFile?.raw ?? null
}

async function confirmImportRestore() {
  if (!importFile.value) {
    ElMessage.warning('请先选择备份包文件')
    return
  }
  importing.value = true
  try {
    const res = await uploadRestoreBackup(importFile.value, importForm.value.password || undefined)
    if (res?.success !== false) {
      ElMessage.success('导入恢复成功，系统将重新登录')
      importDialogVisible.value = false
      importFile.value = null
      importFileList.value = []
      importForm.value.password = ''
      setTimeout(() => {
        window.location.href = '/login'
      }, 2000)
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '导入恢复失败')
  } finally {
    importing.value = false
  }
}

async function handleDownload(row: any) {
  try {
    const token = AuthStorage.getToken()
    const url = `${import.meta.env.VITE_API_BASE_URL || '/api/v1'}/system/backup/download/${encodeURIComponent(row.file_name)}`
    const response = await fetch(url, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    })
    if (!response.ok) {
      throw new Error(`Download failed: ${response.status}`)
    }
    const blob = await response.blob()
    const blobUrl = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = blobUrl
    link.download = row.file_name
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(blobUrl)
  } catch {
    ElMessage.error('下载备份失败')
  }
}

function formatSize(bytes: number) {
  if (!bytes || bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i]
}

function formatTime(time: string | number | Date | null) {
  if (!time) return '-'
  try {
    return new Date(time).toLocaleString('zh-CN')
  } catch {
    return '-'
  }
}

onMounted(() => {
  refreshAll()
  loadScheduleConfig()
  loadBackupDirs()
})
</script>

<style lang="scss" scoped>
.backup-management {
  padding: 20px;
}
.backup-target-card {
  margin-bottom: 16px;
}
.target-tip {
  margin-bottom: 12px;
}
.target-form {
  max-width: 720px;
}
.dir-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.dir-tag {
  cursor: pointer;
}
.dir-empty {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.title {
  font-size: 16px;
  font-weight: 600;
}
.header-actions {
  display: flex;
  gap: 8px;
}
.backup-status {
  margin-bottom: 20px;
}
.auto-backup-card {
  margin-bottom: 20px;
}
.auto-backup-form {
  max-width: 500px;
}
.retention-hint {
  margin-left: 8px;
  color: var(--color-info);
  font-size: 13px;
}
.schedule-card {
  margin-top: 20px;
}
.schedule-form {
  max-width: 500px;
}
</style>
