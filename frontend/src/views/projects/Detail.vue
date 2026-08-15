<template>
  <div class="project-detail">
    <!-- Loading -->
    <template v-if="loading">
      <el-skeleton :rows="3" animated style="margin-bottom: 20px" />
      <el-skeleton :rows="8" animated />
    </template>

    <!-- Error -->
    <el-result v-else-if="error" icon="error" title="加载失败" :sub-title="error">
      <template #extra>
        <el-button type="primary" @click="loadProject">重新加载</el-button>
        <el-button @click="pushSafe('/projects')">返回列表</el-button>
      </template>
    </el-result>

    <!-- Content -->
    <template v-else-if="project">
      <!-- Header -->
      <div class="detail-header">
        <div class="header-left">
          <h2 class="project-name">{{ project.name }}</h2>
          <el-tag :type="statusType" size="large">{{ statusText }}</el-tag>
        </div>
        <div class="header-actions">
          <el-button type="primary" @click="pushSafe(`/projects/${projectId}/edit`)">
            <el-icon><Edit /></el-icon> 编辑
          </el-button>
          <el-button @click="pushSafe('/projects')">
            <el-icon><Back /></el-icon> 返回
          </el-button>
        </div>
      </div>

      <el-progress
        :percentage="project.progress ?? 0"
        :color="progressColor"
        :stroke-width="10"
        style="margin-bottom: 20px"
      />

      <!-- Tabs -->
      <el-tabs v-model="activeTab" type="border-card">
        <!-- 概览 -->
        <el-tab-pane label="概览" name="overview">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="项目名称">{{ project.name }}</el-descriptions-item>
            <el-descriptions-item label="项目编号">{{ project.code ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="项目类型">{{ project.type ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="当前状态">
              <el-tag :type="statusType">{{ statusText }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="预算金额">
              {{ project.budget != null ? `${project.budget} 万元` : '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="负责单位">{{
              project.responsible_unit ?? '-'
            }}</el-descriptions-item>
            <el-descriptions-item label="所属村庄">{{
              project.village ?? project.village_id ?? '-'
            }}</el-descriptions-item>
            <el-descriptions-item label="开始日期">{{
              project.start_date ?? '-'
            }}</el-descriptions-item>
            <el-descriptions-item label="结束日期">{{
              project.end_date ?? '-'
            }}</el-descriptions-item>
            <el-descriptions-item label="创建时间">{{
              project.created_at ?? '-'
            }}</el-descriptions-item>
            <el-descriptions-item label="项目描述" :span="2">{{
              project.description ?? '-'
            }}</el-descriptions-item>
          </el-descriptions>
        </el-tab-pane>

        <!-- 任务 -->
        <el-tab-pane label="任务" name="tasks">
          <!-- 任务完成进度与状态分布 -->
          <div class="task-progress-summary">
            <div class="task-progress-bar">
              <div class="task-progress-label">
                <span>任务完成进度</span>
                <span class="task-progress-num">{{ taskCompleted }} / {{ taskTotal }}</span>
              </div>
              <el-progress
                :percentage="taskProgressPercent"
                :color="taskProgressColor"
                :stroke-width="10"
              />
            </div>
            <div class="task-status-dist">
              <el-tag type="info" size="small" effect="plain"
                >待处理 {{ taskStatusCounts.pending }}</el-tag
              >
              <el-tag type="warning" size="small" effect="plain"
                >进行中 {{ taskStatusCounts.in_progress }}</el-tag
              >
              <el-tag type="success" size="small" effect="plain"
                >已完成 {{ taskStatusCounts.completed }}</el-tag
              >
            </div>
          </div>
          <div class="tab-toolbar">
            <el-button type="primary" size="small" @click="openTaskDialog()">新建任务</el-button>
          </div>
          <el-table v-loading="tasksLoading" :data="tasks" stripe>
            <el-table-column prop="title" label="任务名称" min-width="180" />
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="taskStatusType(row.status)" size="small">{{ row.status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="priority" label="优先级" width="90">
              <template #default="{ row }">
                <el-tag :type="priorityType(row.priority)" size="small" effect="plain">{{
                  row.priority ?? '普通'
                }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="assignee" label="负责人" width="120" />
            <el-table-column prop="due_date" label="截止日期" width="120" />
            <el-table-column label="操作" width="140" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click="openTaskDialog(row)"
                  >编辑</el-button
                >
                <el-popconfirm title="确定删除该任务？" @confirm="handleDeleteTask(row.id)">
                  <template #reference>
                    <el-button link type="danger" size="small">删除</el-button>
                  </template>
                </el-popconfirm>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- 经费 -->
        <el-tab-pane label="经费" name="funds">
          <el-table v-loading="fundsLoading" :data="funds" stripe>
            <el-table-column prop="name" label="经费名称" min-width="200" />
            <el-table-column prop="amount" label="金额（万元）" width="130">
              <template #default="{ row }">{{ row.amount ?? '-' }}</template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag size="small">{{ row.status ?? '-' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="type" label="类型" width="120" />
          </el-table>
        </el-tab-pane>

        <!-- 附件 -->
        <el-tab-pane label="附件" name="files">
          <div class="tab-toolbar">
            <el-upload
              :show-file-list="false"
              :before-upload="() => true"
              :http-request="handleFileUpload"
              multiple
            >
              <el-button type="primary" size="small">上传附件</el-button>
            </el-upload>
          </div>
          <el-table v-loading="filesLoading" :data="files" stripe>
            <el-table-column prop="filename" label="文件名" min-width="220">
              <template #default="{ row }">{{ row.filename ?? row.name ?? '-' }}</template>
            </el-table-column>
            <el-table-column prop="category" label="分类" width="100" />
            <el-table-column prop="file_size" label="大小" width="100">
              <template #default="{ row }">{{ formatSize(row.file_size ?? row.size) }}</template>
            </el-table-column>
            <el-table-column prop="created_at" label="上传时间" width="170" />
            <el-table-column label="操作" width="200" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click="handlePreviewFile(row)"
                  >预览</el-button
                >
                <el-button link type="primary" size="small" @click="handleDownload(row)"
                  >下载</el-button
                >
                <el-popconfirm title="确定删除该附件？" @confirm="handleDeleteFile(row.id)">
                  <template #reference>
                    <el-button link type="danger" size="small">删除</el-button>
                  </template>
                </el-popconfirm>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- 变更历史 -->
        <el-tab-pane label="变更历史" name="history">
          <div v-loading="historyLoading">
            <el-empty v-if="!history.length" description="暂无变更记录" />
            <el-timeline v-else>
              <el-timeline-item
                v-for="(item, idx) in history"
                :key="idx"
                :timestamp="item.changed_at"
                placement="top"
              >
                <el-card shadow="never" class="history-card">
                  <p><strong>变更字段：</strong>{{ item.field }}</p>
                  <p><strong>变更前：</strong>{{ item.old_value ?? '（空）' }}</p>
                  <p><strong>变更后：</strong>{{ item.new_value ?? '（空）' }}</p>
                  <p v-if="item.changed_by" class="history-by">操作人：{{ item.changed_by }}</p>
                </el-card>
              </el-timeline-item>
            </el-timeline>
          </div>
        </el-tab-pane>
      </el-tabs>
    </template>

    <!-- Task Dialog -->
    <el-dialog
      v-model="taskDialogVisible"
      :title="editingTask ? '编辑任务' : '新建任务'"
      width="500px"
      destroy-on-close
    >
      <el-form :model="taskForm" label-width="80px">
        <el-form-item label="任务名称" required>
          <el-input v-model="taskForm.title" placeholder="请输入任务名称" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="taskForm.status" placeholder="请选择状态" style="width: 100%">
            <el-option label="待处理" value="pending" />
            <el-option label="进行中" value="in_progress" />
            <el-option label="已完成" value="completed" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="taskForm.priority" placeholder="请选择优先级" style="width: 100%">
            <el-option label="低" value="low" />
            <el-option label="普通" value="normal" />
            <el-option label="高" value="high" />
            <el-option label="紧急" value="urgent" />
          </el-select>
        </el-form-item>
        <el-form-item label="负责人">
          <el-input v-model="taskForm.assignee" placeholder="请输入负责人" />
        </el-form-item>
        <el-form-item label="截止日期">
          <el-date-picker
            v-model="taskForm.due_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="请选择日期"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="taskDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="taskSaving" @click="handleSaveTask">保存</el-button>
      </template>
    </el-dialog>

    <!-- 附件预览（通用组件，复用政策/经费预览策略） -->
    <FilePreview
      v-model="previewVisible"
      :fetch-blob="previewFetchBlob"
      :file-name="previewFileName"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Edit, Back } from '@element-plus/icons-vue'
import { logger } from '@/utils/logger'
import { projectsApi } from '@/api/projects'
import { safeRouteParam, useRouterSafe } from '@/composables/useRouterSafe'
import { AuthStorage } from '@/utils/authStorage'
import { chartColor } from '@/utils/chartColors'
import FilePreview from '@/components/FilePreview.vue'

const route = useRoute()
const { pushSafe } = useRouterSafe()

const projectId = safeRouteParam(route.params.id)

// --- State ---
const loading = ref(true)
const error = ref('')
const project = ref<any>(null)
const activeTab = ref('overview')

const tasks = ref<any[]>([])
const tasksLoading = ref(false)
const funds = ref<any[]>([])
const fundsLoading = ref(false)
const files = ref<any[]>([])
const filesLoading = ref(false)
// 附件预览（FilePreview 通用组件）
const previewVisible = ref(false)
const previewFileName = ref('')
const previewFetchBlob = ref<() => Promise<Blob>>(() => Promise.resolve(new Blob()))
const history = ref<any[]>([])
const historyLoading = ref(false)

// Task dialog
const taskDialogVisible = ref(false)
const taskSaving = ref(false)
const editingTask = ref<any>(null)
const taskForm = ref({
  title: '',
  status: 'pending',
  priority: 'normal',
  assignee: '',
  due_date: '',
})

// --- Computed ---
type ElTagType = 'primary' | 'success' | 'warning' | 'info' | 'danger'
const statusMap: Record<string, { type: ElTagType; text: string }> = {
  draft: { type: 'info', text: '草稿' },
  pending: { type: 'info', text: '待审批' },
  approved: { type: 'primary', text: '已审批' },
  planning: { type: 'info', text: '规划中' },
  in_progress: { type: 'warning', text: '进行中' },
  completed: { type: 'success', text: '已完成' },
  cancelled: { type: 'danger', text: '已取消' },
  suspended: { type: 'danger', text: '已暂停' },
}
const statusType = computed((): ElTagType => statusMap[project.value?.status]?.type ?? 'info')
const statusText = computed(
  () => statusMap[project.value?.status]?.text ?? project.value?.status ?? '-'
)
const progressColor = computed(() => {
  const p = project.value?.progress ?? 0
  if (p >= 80) return '#40916c'
  if (p >= 50) return chartColor('warning')
  return chartColor('danger')
})

// 任务完成进度与状态分布
const taskTotal = computed(() => tasks.value.length)
const taskCompleted = computed(
  () => tasks.value.filter((t: any) => t.status === 'completed').length
)
const taskProgressPercent = computed(() =>
  taskTotal.value === 0 ? 0 : Math.round((taskCompleted.value / taskTotal.value) * 100)
)
const taskProgressColor = computed(() => {
  const p = taskProgressPercent.value
  if (p >= 80) return '#40916c'
  if (p >= 50) return chartColor('warning')
  return chartColor('danger')
})
const taskStatusCounts = computed(() => {
  const counts = { pending: 0, in_progress: 0, completed: 0 }
  tasks.value.forEach((t: any) => {
    const s = t.status as keyof typeof counts
    if (s in counts) counts[s] += 1
  })
  return counts
})

// --- Helpers ---
const taskStatusType = (s: string): ElTagType =>
  ((({ pending: 'info', in_progress: 'warning', completed: 'success' }) as Record<string, string>)[
    s
  ] ?? 'info') as ElTagType
const priorityType = (p: string): ElTagType =>
  ((({ low: 'info', normal: '', high: 'warning', urgent: 'danger' }) as Record<string, string>)[
    p
  ] ?? 'info') as ElTagType
const formatSize = (bytes?: number) => {
  if (bytes == null) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1048576).toFixed(1) + ' MB'
}

// --- Data loading ---
async function loadProject() {
  loading.value = true
  error.value = ''
  try {
    project.value = await projectsApi.get(projectId)
  } catch (e: any) {
    logger.error('加载项目详情失败', e)
    error.value = e?.message || '项目详情加载失败，请重试'
  } finally {
    loading.value = false
  }
}

async function loadTasks() {
  tasksLoading.value = true
  try {
    const res = await projectsApi.getTasks(projectId)
    tasks.value = Array.isArray(res) ? res : (res?.items ?? [])
  } catch (e) {
    logger.error('加载任务失败', e)
  } finally {
    tasksLoading.value = false
  }
}

async function loadFunds() {
  fundsLoading.value = true
  try {
    const res = await projectsApi.getFunds(projectId)
    funds.value = Array.isArray(res) ? res : (res?.items ?? [])
  } catch (e) {
    logger.error('加载经费失败', e)
  } finally {
    fundsLoading.value = false
  }
}

async function loadFiles() {
  filesLoading.value = true
  try {
    const res = await projectsApi.listFiles(projectId)
    // 后端返回 {files: [...], grouped: {...}}（非 items）——兼容两种结构，防止对象被当数组
    files.value = Array.isArray(res) ? res : (res?.files ?? res?.items ?? [])
  } catch (e) {
    logger.error('加载附件失败', e)
  } finally {
    filesLoading.value = false
  }
}

async function loadHistory() {
  historyLoading.value = true
  try {
    const res = await projectsApi.getChangeHistory(projectId)
    history.value = Array.isArray(res) ? res : (res?.items ?? [])
  } catch (e) {
    logger.error('加载变更历史失败', e)
  } finally {
    historyLoading.value = false
  }
}

// --- Task CRUD ---
const PRIORITY_MAP: Record<string, number> = { low: 2, normal: 5, high: 8, urgent: 10 }

function openTaskDialog(task?: any) {
  editingTask.value = task ?? null
  taskForm.value = task
    ? {
        // 后端返回 name 字段；priority 为数字 0-10
        title: task.name ?? task.title ?? '',
        status: task.status ?? 'pending',
        priority: task.priority ?? 'normal',
        assignee: task.assignee ?? '',
        due_date: task.due_date ?? '',
      }
    : { title: '', status: 'pending', priority: 'normal', assignee: '', due_date: '' }
  taskDialogVisible.value = true
}

async function handleSaveTask() {
  if (!taskForm.value.title?.trim()) {
    ElMessage.warning('请输入任务名称')
    return
  }
  taskSaving.value = true
  try {
    // 契约对齐：后端字段 name（必填）、priority 为数字 0-10
    const payload = {
      name: taskForm.value.title.trim(),
      status: taskForm.value.status,
      priority: PRIORITY_MAP[taskForm.value.priority] ?? 5,
      assignee: taskForm.value.assignee || undefined,
      due_date: taskForm.value.due_date || undefined,
    }
    if (editingTask.value) {
      await projectsApi.updateTask(projectId, editingTask.value.id, payload)
      ElMessage.success('任务已更新')
    } else {
      await projectsApi.createTask(projectId, payload)
      ElMessage.success('任务已创建')
    }
    taskDialogVisible.value = false
    await loadTasks()
  } catch (e: any) {
    logger.error('保存任务失败', e)
    ElMessage.error(e?.response?.data?.detail || e?.message || '保存任务失败')
  } finally {
    taskSaving.value = false
  }
}

async function handleDeleteTask(taskId: number) {
  try {
    await projectsApi.deleteTask(projectId, taskId)
    ElMessage.success('任务已删除')
    await loadTasks()
  } catch (e: any) {
    logger.error('删除任务失败', e)
    ElMessage.error(e?.message || '删除任务失败')
  }
}

// --- Files ---
async function handleFileUpload(options: any) {
  try {
    // 分类须在后端白名单（research/approval/implementation/acceptance/photo）内，否则 400
    await projectsApi.uploadFiles(projectId, 'implementation', [options.file])
    await loadFiles()
  } catch (e: any) {
    logger.error('上传附件失败', e)
    ElMessage.error(e?.message || '上传失败')
  }
}

function handlePreviewFile(file: any) {
  previewFileName.value = file.filename || file.name || '附件'
  previewFetchBlob.value = () => projectsApi.previewFile(projectId, file.id)
  previewVisible.value = true
}

async function handleDownload(file: any) {
  try {
    const url = projectsApi.getFileDownloadUrl(projectId, file.id)
    const token = AuthStorage.getToken()
    const response = await fetch(url, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!response.ok) throw new Error('Download failed')
    const blob = await response.blob()
    const blobUrl = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = blobUrl
    link.download = file.filename || file.name || 'download'
    link.click()
    setTimeout(() => URL.revokeObjectURL(blobUrl), 1000)
  } catch (e: any) {
    logger.error('下载文件失败', e)
    ElMessage.error(e?.message || '下载失败')
  }
}

async function handleDeleteFile(fileId: number) {
  try {
    await projectsApi.deleteFile(projectId, fileId)
    ElMessage.success('附件已删除')
    await loadFiles()
  } catch (e: any) {
    logger.error('删除附件失败', e)
    ElMessage.error(e?.message || '删除附件失败')
  }
}

// --- Init ---
onMounted(() => {
  loadProject()
  loadTasks()
  loadFunds()
  loadFiles()
  loadHistory()
})
</script>

<style scoped lang="scss">
.project-detail {
  padding: 20px;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;

  .header-left {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .project-name {
    margin: 0;
    font-size: 22px;
    color: #303133;
  }
}

.tab-toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 12px;
}

.task-progress-summary {
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 14px 16px;
  margin-bottom: 14px;
  background: #f8faf9;
  border: 1px solid #e6ebe8;
  border-radius: 8px;

  .task-progress-bar {
    flex: 1;
    min-width: 0;
  }

  .task-progress-label {
    display: flex;
    justify-content: space-between;
    margin-bottom: 6px;
    font-size: 13px;
    color: #606266;

    .task-progress-num {
      font-weight: 600;
      color: #303133;
    }
  }

  .task-status-dist {
    display: flex;
    gap: 8px;
    flex-shrink: 0;
  }
}

.history-card {
  p {
    margin: 4px 0;
    font-size: 13px;
    color: #606266;
  }

  .history-by {
    color: var(--color-info);
    font-size: 12px;
  }
}
</style>
