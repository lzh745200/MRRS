<template>
  <div class="task-manager">
    <!-- ── Header ── -->
    <div class="page-header">
      <div class="header-left">
        <h2 class="page-title">后台任务管理</h2>
        <el-badge
          v-if="runningCount.running > 0"
          :value="runningCount.running"
          class="running-badge"
        >
          <el-tag type="warning" size="small" class="pulse-tag"> 运行中 </el-tag>
        </el-badge>
      </div>
      <div class="header-right">
        <span v-if="lastUpdated" class="last-updated"> 更新于 {{ lastUpdated }} </span>
        <el-switch
          v-model="autoRefresh"
          active-text="自动刷新"
          size="small"
          @change="toggleAutoRefresh"
        />
        <el-button
          :icon="Refresh"
          :loading="loading"
          size="small"
          type="primary"
          @click="refreshAll"
        >
          刷新
        </el-button>
        <el-button :icon="Plus" size="small" type="success" @click="showCreateDialog = true">
          创建任务
        </el-button>
      </div>
    </div>

    <!-- ── 任务统计行 ── -->
    <el-row :gutter="16" class="stats-row">
      <el-col :span="4">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">总任务数</div>
          <div class="stat-value">{{ stats.total }}</div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover" class="stat-card active-card">
          <div class="stat-label">活跃任务</div>
          <div class="stat-value highlight">{{ stats.active_count }}</div>
          <div class="stat-sub">
            运行 {{ runningCount.running }} / 等待 {{ runningCount.pending }}
          </div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">已完成</div>
          <div class="stat-value completed">
            {{ stats.by_status?.completed || 0 }}
          </div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">失败</div>
          <div class="stat-value failed">
            {{ stats.by_status?.failed || 0 }}
          </div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">已取消</div>
          <div class="stat-value cancelled">
            {{ stats.by_status?.cancelled || 0 }}
          </div>
        </el-card>
      </el-col>
      <el-col :span="4">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-label">任务类型</div>
          <div class="stat-tags">
            <el-tag
              v-for="(count, type) in stats.by_type || {}"
              :key="type"
              size="small"
              class="type-tag"
            >
              {{ type }}: {{ count }}
            </el-tag>
            <span v-if="!Object.keys(stats.by_type || {}).length" class="stat-empty">--</span>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- ── 任务列表表格 ── -->
    <el-card shadow="hover" class="table-card">
      <template #header>
        <div class="card-header-bar">
          <span class="card-title">任务列表</span>
          <div class="filter-bar">
            <el-select
              v-model="filterStatus"
              placeholder="状态筛选"
              clearable
              size="small"
              style="width: 140px"
              @change="handleSearch"
            >
              <el-option label="全部" value="" />
              <el-option label="等待中" value="pending" />
              <el-option label="运行中" value="running" />
              <el-option label="已完成" value="completed" />
              <el-option label="失败" value="failed" />
              <el-option label="已取消" value="cancelled" />
            </el-select>
            <el-input
              v-model="filterType"
              placeholder="任务类型"
              clearable
              size="small"
              style="width: 180px"
              @clear="handleSearch"
              @keyup.enter="handleSearch"
            />
            <el-button size="small" :icon="Search" @click="handleSearch">查询</el-button>
            <el-button size="small" @click="resetFilters">重置</el-button>
          </div>
        </div>
      </template>

      <el-table v-loading="loading" :data="taskList" stripe style="width: 100%">
        <el-table-column prop="task_id" label="任务ID" width="140">
          <template #default="{ row }">
            <el-tooltip :content="row.task_id" placement="top">
              <span class="text-truncate">{{ row.task_id?.substring(0, 14) }}...</span>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column prop="task_name" label="任务名称" width="160">
          <template #default="{ row }">
            <span class="text-truncate">{{ row.task_name }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="task_type" label="类型" width="120">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ row.task_type || '--' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="progress" label="进度" width="160">
          <template #default="{ row }">
            <template v-if="row.status === 'running'">
              <el-progress
                :percentage="row.progress"
                :stroke-width="16"
                :text-inside="true"
                :status="row.progress === 100 ? 'success' : undefined"
              />
            </template>
            <template v-else-if="row.status === 'completed'">
              <el-progress
                :percentage="100"
                :stroke-width="16"
                :text-inside="true"
                status="success"
              />
            </template>
            <template v-else>
              <span class="text-muted">--</span>
            </template>
          </template>
        </el-table-column>
        <el-table-column prop="message" label="消息" min-width="160">
          <template #default="{ row }">
            <el-tooltip v-if="row.message" :content="row.message" placement="top">
              <span class="text-truncate"
                >{{ row.message?.substring(0, 30)
                }}{{ row.message?.length > 30 ? '...' : '' }}</span
              >
            </el-tooltip>
            <span v-else class="text-muted">--</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="170">
          <template #default="{ row }">
            {{ formatDateTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column prop="created_by" label="创建人" width="100">
          <template #default="{ row }">
            {{ row.created_by || '--' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'pending' || row.status === 'running'"
              type="warning"
              size="small"
              :icon="VideoPause"
              link
              @click="handleCancel(row as TaskInfo)"
            >
              取消
            </el-button>
            <el-button
              v-if="
                row.status === 'completed' || row.status === 'failed' || row.status === 'cancelled'
              "
              type="danger"
              size="small"
              :icon="Delete"
              link
              @click="handleDelete(row as TaskInfo)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handlePageChange"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>

    <!-- ── 创建任务对话框 ── -->
    <el-dialog
      v-model="showCreateDialog"
      title="创建后台任务"
      width="520px"
      :close-on-click-modal="false"
      @closed="resetCreateForm"
    >
      <el-form ref="createFormRef" :model="createForm" :rules="createFormRules" label-width="100px">
        <el-form-item label="任务名称" prop="task_name">
          <el-input
            v-model="createForm.task_name"
            placeholder="请输入任务名称"
            maxlength="100"
            show-word-limit
          />
        </el-form-item>
        <el-form-item label="任务类型" prop="task_type">
          <el-input
            v-model="createForm.task_type"
            placeholder="请输入任务类型（可选）"
            maxlength="50"
          />
        </el-form-item>
        <el-form-item label="任务参数" prop="params">
          <el-input
            v-model="createForm.params"
            type="textarea"
            :rows="4"
            placeholder='JSON格式参数（可选），例如: {"key": "value"}'
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" :loading="createLoading" @click="handleCreateTask">
          创建
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, VideoPause, Delete, Plus, Search } from '@element-plus/icons-vue'
import { tasksApi, type TaskInfo, type TaskStats, type RunningTaskCount } from '@/api/tasks'

// ==================== 响应式状态 ====================

const loading = ref(false)
const taskList = ref<TaskInfo[]>([])
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

const filterStatus = ref('')
const filterType = ref('')

const autoRefresh = ref(false)
const showCreateDialog = ref(false)
const createLoading = ref(false)
const lastUpdated = ref('')

const stats = ref<TaskStats>({
  total: 0,
  by_status: {},
  by_type: {},
  active_count: 0,
})

const runningCount = ref<RunningTaskCount>({
  running: 0,
  pending: 0,
  total_active: 0,
})

const createForm = reactive({
  task_name: '',
  task_type: '',
  params: '',
})

const createFormRef = ref()

const createFormRules = {
  task_name: [{ required: true, message: '请输入任务名称', trigger: 'blur' }],
}

// ==================== 自动刷新 ====================

let refreshInterval: ReturnType<typeof setInterval> | null = null

function toggleAutoRefresh(value: string | number | boolean) {
  if (value) {
    startAutoRefresh()
  } else {
    stopAutoRefresh()
  }
}

function startAutoRefresh() {
  stopAutoRefresh()
  refreshInterval = setInterval(async () => {
    try {
      const countRes = await tasksApi.getRunningCount()
      if (countRes.success && countRes.data.total_active > 0) {
        await fetchTaskList(false)
        updateLastUpdated()
      }
    } catch {
      // auto-refresh silently fails
    }
  }, 5000)
}

function stopAutoRefresh() {
  if (refreshInterval !== null) {
    clearInterval(refreshInterval)
    refreshInterval = null
  }
}

// ==================== 数据获取 ====================

async function fetchStats() {
  try {
    const res = await tasksApi.getStats()
    if (res.success) {
      stats.value = res.data
    }
  } catch {
    // stats failure is non-blocking
  }
}

async function fetchRunningCount() {
  try {
    const res = await tasksApi.getRunningCount()
    if (res.success) {
      runningCount.value = res.data
    }
  } catch {
    // non-blocking
  }
}

async function fetchTaskList(showLoading = true) {
  if (showLoading) loading.value = true
  try {
    const params: Record<string, any> = {
      page: page.value,
      page_size: pageSize.value,
    }
    if (filterStatus.value) {
      params.status = filterStatus.value
    }
    if (filterType.value) {
      params.task_type = filterType.value
    }
    const res = await tasksApi.listTasks(params)
    if (res?.success) {
      taskList.value = res.data?.items || []
      total.value = res.data?.total || 0
    }
  } catch {
    ElMessage.error('获取任务列表失败')
  } finally {
    if (showLoading) loading.value = false
  }
}

async function refreshAll() {
  loading.value = true
  try {
    await Promise.all([fetchStats(), fetchRunningCount(), fetchTaskList(false)])
    updateLastUpdated()
  } finally {
    loading.value = false
  }
}

function updateLastUpdated() {
  const now = new Date()
  lastUpdated.value = now.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

// ==================== 事件处理 ====================

function handleSearch() {
  page.value = 1
  fetchTaskList()
}

function resetFilters() {
  filterStatus.value = ''
  filterType.value = ''
  page.value = 1
  fetchTaskList()
}

function handlePageChange() {
  fetchTaskList()
}

async function handleCancel(row: TaskInfo) {
  try {
    await ElMessageBox.confirm(`确定要取消任务「${row.task_name}」吗？`, '确认取消', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
    const res = await tasksApi.cancelTask(row.task_id)
    if (res.success) {
      ElMessage.success('已取消')
      page.value = 1 // 重置到第1页，确保新建/编辑后的数据可见
      await refreshAll()
    } else {
      ElMessage.error(res.message || '取消失败')
    }
  } catch (err: any) {
    if (err !== 'cancel' && err?.message !== 'cancel') {
      ElMessage.error(err?.message || '取消操作失败')
    }
  }
}

async function handleDelete(row: TaskInfo) {
  try {
    await ElMessageBox.confirm(
      `确定要删除任务「${row.task_name}」吗？此操作不可恢复。`,
      '确认删除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
    const res = await tasksApi.deleteTask(row.task_id)
    if (res.success) {
      ElMessage.success('已删除')
      page.value = 1 // 重置到第1页，确保新建/编辑后的数据可见
      await refreshAll()
    } else {
      ElMessage.error(res.message || '删除失败')
    }
  } catch (err: any) {
    if (err !== 'cancel' && err?.message !== 'cancel') {
      ElMessage.error(err?.message || '删除操作失败')
    }
  }
}

async function handleCreateTask() {
  const valid = await createFormRef.value?.validate().catch(() => false)
  if (!valid) return

  createLoading.value = true
  try {
    let params: Record<string, any> | undefined
    if (createForm.params.trim()) {
      try {
        params = JSON.parse(createForm.params)
      } catch {
        ElMessage.error('参数格式错误，请输入有效的JSON')
        createLoading.value = false
        return
      }
    }
    const res = await tasksApi.createTask({
      task_name: createForm.task_name,
      task_type: createForm.task_type || undefined,
      params,
    })
    if (res.success) {
      ElMessage.success(res.message || '任务创建成功')
      showCreateDialog.value = false
      page.value = 1 // 重置到第1页，确保新建/编辑后的数据可见
      await refreshAll()
    } else {
      ElMessage.error(res.message || '创建失败')
    }
  } catch {
    ElMessage.error('创建任务失败')
  } finally {
    createLoading.value = false
  }
}

function resetCreateForm() {
  createForm.task_name = ''
  createForm.task_type = ''
  createForm.params = ''
  createFormRef.value?.resetFields()
}

// ==================== 工具函数 ====================

function statusTagType(
  status: string
): 'primary' | 'success' | 'warning' | 'info' | 'danger' | undefined {
  const map: Record<string, 'primary' | 'success' | 'warning' | 'info' | 'danger' | undefined> = {
    pending: 'info',
    running: undefined,
    completed: 'success',
    failed: 'danger',
    cancelled: 'warning',
  }
  return map[status] || 'info'
}

function statusLabel(status: string) {
  const map: Record<string, string> = {
    pending: '等待中',
    running: '运行中',
    completed: '已完成',
    failed: '失败',
    cancelled: '已取消',
  }
  return map[status] || status
}

function formatDateTime(dateStr: string) {
  if (!dateStr) return '--'
  try {
    const date = new Date(dateStr)
    if (isNaN(date.getTime())) return dateStr
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  } catch {
    return dateStr
  }
}

// ==================== 生命周期 ====================

onMounted(() => {
  refreshAll()
})

onUnmounted(() => {
  stopAutoRefresh()
})
</script>

<style scoped>
.task-manager {
  padding: 16px;
}

/* ── Header ── */
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.page-title {
  font-size: 20px;
  font-weight: 600;
  color: #303133;
  margin: 0;
}

.running-badge {
  line-height: 1;
}

.pulse-tag {
  animation: pulse-blink 1.5s ease-in-out infinite;
}

@keyframes pulse-blink {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

.header-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.last-updated {
  font-size: 12px;
  color: #909399;
}

/* ── Stats Row ── */
.stats-row {
  margin-bottom: 16px;
}

.stat-card {
  text-align: center;
}

.stat-card :deep(.el-card__body) {
  padding: 14px 8px;
}

.stat-label {
  font-size: 13px;
  color: #909399;
  margin-bottom: 6px;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: #303133;
}

.stat-value.highlight {
  color: var(--color-warning);
}

.stat-value.completed {
  color: var(--color-success);
}

.stat-value.failed {
  color: var(--color-danger);
}

.stat-value.cancelled {
  color: var(--color-warning);
}

.stat-sub {
  font-size: 11px;
  color: #909399;
  margin-top: 4px;
}

.stat-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  justify-content: center;
  margin-top: 4px;
}

.type-tag {
  margin: 0;
}

.stat-empty {
  color: #c0c4cc;
  font-size: 14px;
}

.active-card {
  border-left: 3px solid var(--color-warning);
}

/* ── Table Card ── */
.table-card {
  margin-bottom: 16px;
}

.card-header-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-title {
  font-size: 15px;
  font-weight: 600;
}

.filter-bar {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* ── Table ── */
.text-truncate {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.text-muted {
  color: #c0c4cc;
}

/* ── Pagination ── */
.pagination-wrapper {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
