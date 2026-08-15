<template>
  <div class="pending-list">
    <!-- 页面标题 -->
    <el-card class="header-card">
      <template #header>
        <div class="card-header">
          <span class="title">待审批任务</span>
          <div class="actions">
            <el-button :loading="loading" @click="loadTasks">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
            <el-button
              type="success"
              :disabled="tasks.length === 0"
              :loading="autoApproving"
              @click="handleAutoApproveAll"
            >
              <el-icon><Check /></el-icon>
              一键全部通过
            </el-button>
            <el-button
              type="primary"
              :disabled="selectedTasks.length === 0"
              @click="handleBatchApprove"
            >
              <el-icon><Check /></el-icon>
              批量通过 ({{ selectedTasks.length }})
            </el-button>
          </div>
        </div>
      </template>

      <!-- 统计信息 -->
      <el-row :gutter="20">
        <el-col :span="6">
          <el-statistic title="待审批" :value="tasks.length" />
        </el-col>
        <el-col :span="6">
          <el-statistic
            title="高优先级"
            :value="highPriorityCount"
            value-style="color: var(--color-danger)"
          />
        </el-col>
        <el-col :span="6">
          <el-statistic title="今日新增" :value="todayCount" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="已选择" :value="selectedTasks.length" />
        </el-col>
      </el-row>
    </el-card>

    <!-- 筛选条件 -->
    <el-card class="filter-card" shadow="never">
      <el-form inline>
        <el-form-item label="类型">
          <el-select v-model="filterType" placeholder="全部类型" clearable style="width: 140px">
            <el-option
              v-for="t in entityTypeOptions"
              :key="t.value"
              :label="t.label"
              :value="t.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="提交时间">
          <el-date-picker
            v-model="filterDateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            value-format="YYYY-MM-DD"
            style="width: 260px"
          />
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 任务列表 -->
    <el-card class="list-card">
      <el-table
        ref="tableRef"
        v-loading="loading"
        :data="filteredTasks"
        stripe
        row-key="id"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="55" />
        <el-table-column label="优先级" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.priority > 0 ? 'danger' : 'info'" size="small" effect="dark">
              {{ row.priority > 0 ? '高' : '普通' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="审批标题" min-width="200">
          <template #default="{ row }">
            <el-link type="primary" @click="handleViewDetail(row)">
              {{ row.title || `${formatEntityType(row.entity_type)} #${row.entity_id}` }}
            </el-link>
          </template>
        </el-table-column>
        <el-table-column label="业务摘要" min-width="220">
          <template #default="{ row }">
            <span v-if="entitySummary(row)" class="entity-summary">{{ entitySummary(row) }}</span>
            <span v-else class="entity-summary muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="100">
          <template #default="{ row }">
            {{ formatEntityType(row.entity_type) }}
          </template>
        </el-table-column>
        <el-table-column label="提交人" width="110">
          <template #default="{ row }">
            {{ row.submitter_name || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="当前级别" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small">第 {{ row.current_level }} 级</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="提交时间" width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.created_at) }}
            <el-tag
              v-if="isOverdue(row)"
              type="danger"
              size="small"
              effect="dark"
              style="margin-left: 4px"
              >超时</el-tag
            >
          </template>
        </el-table-column>
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <el-button-group>
              <el-button size="small" @click="handleViewDetail(row)">
                <el-icon><View /></el-icon>
                详情
              </el-button>
              <el-button size="small" @click="handleViewDiff(row)">
                <el-icon><Document /></el-icon>
                对比
              </el-button>
              <el-button
                v-if="row.entity_type === 'rural_work'"
                size="small"
                type="primary"
                @click="handleEditWork(row)"
              >
                <el-icon><Edit /></el-icon>
                编辑
              </el-button>
              <el-button size="small" type="success" @click="handleQuickApprove(row)">
                <el-icon><Check /></el-icon>
                快速通过
              </el-button>
              <el-button size="small" @click="handleTransfer(row)">
                <el-icon><Switch /></el-icon>
                转交
              </el-button>
              <el-button size="small" type="danger" @click="handleReject(row)">
                <el-icon><Close /></el-icon>
                拒绝
              </el-button>
            </el-button-group>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <el-pagination
        v-if="total > pageSize"
        v-model:current-page="page"
        v-model:page-size="pageSize"
        class="pagination"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="handleSizeChange"
        @current-change="loadTasks"
      />
    </el-card>

    <!-- 拒绝对话框 -->
    <el-dialog v-model="rejectDialogVisible" title="拒绝确认" width="500px">
      <el-form :model="rejectForm" label-width="80px">
        <el-form-item label="拒绝原因" required>
          <el-input
            v-model="rejectForm.opinion"
            type="textarea"
            :rows="4"
            placeholder="请输入拒绝原因"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="rejectDialogVisible = false">取消</el-button>
        <el-button type="danger" :loading="submitting" @click="confirmReject"> 确认拒绝 </el-button>
      </template>
    </el-dialog>

    <!-- 转交对话框 -->
    <el-dialog v-model="transferDialogVisible" title="转交审批" width="500px">
      <el-form :model="transferForm" label-width="80px">
        <el-form-item label="转交对象" required>
          <el-select
            v-model="transferForm.transferToId"
            filterable
            placeholder="请选择审批人"
            style="width: 100%"
          >
            <el-option
              v-for="u in candidateUsers"
              :key="u.id"
              :label="`${u.username}（${u.role || 'user'}）`"
              :value="u.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="转交原因">
          <el-input
            v-model="transferForm.reason"
            type="textarea"
            :rows="3"
            placeholder="请输入转交原因（可选）"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="transferDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="confirmTransfer">
          确认转交
        </el-button>
      </template>
    </el-dialog>

    <!-- 变更对比对话框 -->
    <el-dialog v-model="diffDialogVisible" title="变更对比" width="800px">
      <div v-if="taskDiff" class="diff-view">
        <el-table :data="diffTableData" border>
          <el-table-column prop="field" label="字段" width="150" />
          <el-table-column prop="original" label="原值">
            <template #default="{ row }">
              <span :class="{ 'diff-changed': row.changed }">{{ row.original ?? '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="changed" label="新值">
            <template #default="{ row }">
              <span
                :class="{
                  'diff-changed': row.changed,
                  'diff-new': row.changed,
                }"
              >
                {{ row.new ?? '-' }}
              </span>
            </template>
          </el-table-column>
        </el-table>
      </div>
      <el-empty v-else description="加载中..." />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Check, Close, View, Edit, Switch, Document } from '@element-plus/icons-vue'
import {
  getPendingTasksWithTotal,
  approveTask,
  rejectTask,
  batchApprove,
  getTaskDiff,
  formatEntityType,
  autoApproveSingleTask,
  autoApproveAll,
  transferTask,
  type ApprovalTask,
  type TaskDiff,
} from '@/api/approval'
import { listUsers } from '@/api/userManagement'

// ==================== 状态 ====================

const loading = ref(false)
const submitting = ref(false)
const autoApproving = ref(false)
const tasks = ref<ApprovalTask[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const selectedTasks = ref<ApprovalTask[]>([])
const currentTask = ref<ApprovalTask | null>(null)

// 对话框
const rejectDialogVisible = ref(false)
const diffDialogVisible = ref(false)
const transferDialogVisible = ref(false)

// 表单
const rejectForm = ref({ opinion: '' })
const transferForm = ref({ transferToId: undefined as number | undefined, reason: '' })
const candidateUsers = ref<Array<{ id: number; username: string; role?: string }>>([])

// 变更对比
const taskDiff = ref<TaskDiff | null>(null)

// 筛选条件（类型/提交时间）
const filterType = ref('')
const filterDateRange = ref<[string, string] | null>(null)
const entityTypeOptions = [
  { value: 'supported_village', label: '帮扶村' },
  { value: 'project', label: '项目' },
  { value: 'fund', label: '经费' },
  { value: 'school', label: '学校' },
  { value: 'rural_work', label: '乡村工作' },
]

const filteredTasks = computed(() => {
  let list = tasks.value
  if (filterType.value) {
    list = list.filter((t) => t.entity_type === filterType.value)
  }
  if (filterDateRange.value && filterDateRange.value.length === 2) {
    const [start, end] = filterDateRange.value
    list = list.filter((t) => {
      const day = (t.created_at || '').slice(0, 10)
      return day >= start && day <= end
    })
  }
  return list
})

// ==================== 计算属性 ====================

const highPriorityCount = computed(() => tasks.value.filter((t) => t.priority > 0).length)

const todayCount = computed(() => {
  const today = new Date().toDateString()
  return tasks.value.filter((t) => new Date(t.created_at).toDateString() === today).length
})

// 超时判断：超过24小时未审批
const OVERDUE_HOURS = 24
function isOverdue(task: any): boolean {
  if (!task.created_at) return false
  const created = new Date(task.created_at).getTime()
  const now = Date.now()
  return (now - created) / (1000 * 60 * 60) > OVERDUE_HOURS
}

const diffTableData = computed(() => {
  if (!taskDiff.value) return []

  const { original_data, change_data, diff_fields } = taskDiff.value
  // 兼容旧接口返回 changed/original 键名
  const original = original_data ?? (taskDiff.value as any).original ?? {}
  const changed = change_data ?? (taskDiff.value as any).changed ?? {}
  const allFields = new Set([...Object.keys(original || {}), ...Object.keys(changed || {})])

  return Array.from(allFields).map((field) => ({
    field,
    original: original?.[field],
    new: changed?.[field],
    changed: diff_fields?.includes(field),
  }))
})

/**
 * 从审批任务变更数据中提取业务摘要（经费名称/金额等）
 */
function entitySummary(task: any): string {
  const cd = task?.change_data
  if (!cd || typeof cd !== 'object') return ''
  if (task?.entity_type === 'fund') {
    const parts: string[] = []
    if (cd.name) parts.push(String(cd.name))
    if (cd.amount != null) parts.push(`¥${Number(cd.amount).toLocaleString('zh-CN')}`)
    if (cd.applicant) parts.push(`申请人: ${cd.applicant}`)
    if (cd.status) parts.push(`状态: ${cd.status}`)
    return parts.join(' · ')
  }
  if (task?.entity_type === 'project') {
    const parts: string[] = []
    if (cd.name || cd.project_name) parts.push(String(cd.name || cd.project_name))
    if (cd.budget != null) parts.push(`预算: ¥${Number(cd.budget).toLocaleString('zh-CN')}`)
    return parts.join(' · ')
  }
  if (cd.name) return String(cd.name)
  return ''
}

// ==================== 方法 ====================

/**
 * 加载待审批任务（分页）
 */
async function loadTasks() {
  loading.value = true
  try {
    const result: any = await getPendingTasksWithTotal({
      skip: (page.value - 1) * pageSize.value,
      limit: pageSize.value,
    })
    // 兼容直接返回数组的旧形态
    const items = Array.isArray(result)
      ? result
      : result?.items || (Array.isArray(result?.data) ? result.data : [])
    const resultTotal = Number(result?.total ?? items.length) || items.length
    tasks.value = Array.isArray(items) ? items : []
    total.value = resultTotal
    // 删除/审批后当前页可能为空，自动回退到最后一页
    if (tasks.value.length === 0 && page.value > 1) {
      page.value = Math.max(1, Math.ceil(resultTotal / pageSize.value) || 1)
      if (page.value > 1) {
        await loadTasks()
        return
      }
    }
  } catch (error) {
    ElMessage.error('加载任务列表失败')
  } finally {
    loading.value = false
  }
}

/**
 * 选择变化
 */
function handleSelectionChange(selection: any[]) {
  selectedTasks.value = selection
}

function handleSizeChange() {
  page.value = 1
  loadTasks()
}

import { useRouterSafe } from '@/composables/useRouterSafe'
const { pushSafe } = useRouterSafe()

// ... existing code ...

/**
 * 查看详情：经费/项目/学校/帮扶村跳转对应业务页面，其余展示变更对比
 */
function handleViewDetail(task: any) {
  const detailRoutes: Record<string, string> = {
    fund: `/funds/${task.entity_id}`,
    project: `/projects/${task.entity_id}`,
    school: `/schools/${task.entity_id}`,
    supported_village: `/supported-villages/${task.entity_id}`,
  }
  if (task.entity_type === 'rural_work') {
    pushSafe({
      path: '/rural-works',
      query: { id: task.entity_id, action: 'view' },
    })
  } else if (detailRoutes[task.entity_type] && Number(task.entity_id) > 0) {
    // 批量操作任务（entity_id=0）无实体详情页 → 展示变更对比
    pushSafe(detailRoutes[task.entity_type])
  } else {
    handleViewDiff(task)
  }
}

function handleEditWork(task: any) {
  if (task.entity_type === 'rural_work') {
    pushSafe({
      path: '/rural-works',
      query: { id: task.entity_id, action: 'edit' },
    })
  } else {
    ElMessage.info('请在对应管理页面进行编辑')
  }
}

/**
 * 查看变更对比
 */
async function handleViewDiff(task: any) {
  currentTask.value = task
  diffDialogVisible.value = true
  taskDiff.value = null

  try {
    taskDiff.value = await getTaskDiff(task.id)
  } catch (error) {
    ElMessage.error('加载变更对比失败')
  }
}

/**
 * 审批拒绝
 */
function handleReject(task: any) {
  currentTask.value = task
  rejectForm.value = { opinion: '' }
  rejectDialogVisible.value = true
}

/**
 * 转交审批：打开转交对话框并加载可转交用户列表
 */
async function handleTransfer(task: any) {
  currentTask.value = task
  transferForm.value = { transferToId: undefined, reason: '' }
  transferDialogVisible.value = true
  try {
    const res: any = await listUsers({ page_size: 200 })
    const users = Array.isArray(res) ? res : res?.items || res?.data?.items || []
    // 排除当前审批人自身
    candidateUsers.value = (users as any[]).filter((u: any) => u.id !== task.current_approver_id)
  } catch {
    candidateUsers.value = []
  }
}

/**
 * 确认转交
 */
async function confirmTransfer() {
  if (!currentTask.value) return
  if (!transferForm.value.transferToId) {
    ElMessage.warning('请选择转交对象')
    return
  }
  submitting.value = true
  try {
    await transferTask(
      currentTask.value.id,
      transferForm.value.transferToId,
      transferForm.value.reason || undefined
    )
    ElMessage.success('已转交')
    transferDialogVisible.value = false
    loadTasks()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '转交失败')
  } finally {
    submitting.value = false
  }
}

/**
 * 确认拒绝
 */
async function confirmReject() {
  if (!currentTask.value) return

  if (!rejectForm.value.opinion) {
    ElMessage.warning('请输入拒绝原因')
    return
  }

  submitting.value = true
  try {
    await rejectTask(currentTask.value.id, rejectForm.value.opinion)
    ElMessage.success('已拒绝')
    rejectDialogVisible.value = false
    loadTasks()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '操作失败')
  } finally {
    submitting.value = false
  }
}

/**
 * 快速通过：优先走标准审批（校验当前审批人），无权限时回退到单机版自动审批
 */
async function handleQuickApprove(task: any) {
  try {
    await ElMessageBox.confirm(
      `确定要快速通过「${task.title || `${formatEntityType(task.entity_type)} #${task.entity_id}`}」吗？`,
      '快速审批',
      { type: 'info', confirmButtonText: '确认通过', cancelButtonText: '取消' }
    )
    try {
      await approveTask(task.id, '快速审批通过')
    } catch {
      await autoApproveSingleTask(task.id, '单机版快速审批通过')
    }
    ElMessage.success('审批通过')
    loadTasks()
  } catch (e: any) {
    // 用户取消（ElMessageBox 拒绝值为 'cancel' 字符串或 Error('cancel')）
    const isCancel =
      e === 'cancel' ||
      e?.message === 'cancel' ||
      e?.toString?.() === 'cancel' ||
      String(e?.message ?? '').includes('cancel')
    if (!isCancel) {
      ElMessage.error(e?.response?.data?.detail || '审批失败')
    }
  }
}

/**
 * 单机版一键审批所有待处理任务
 */
async function handleAutoApproveAll() {
  if (tasks.value.length === 0) return

  try {
    await ElMessageBox.confirm(
      `确定要一键通过所有 ${tasks.value.length} 个待审批任务吗？`,
      '一键全部通过',
      {
        type: 'warning',
        confirmButtonText: '全部通过',
        cancelButtonText: '取消',
      }
    )

    autoApproving.value = true
    const result: any = await autoApproveAll('单机版一键批量审批通过')
    // 兼容两种返回结构：{total_pending, approved, failed} 与 {success, failed}
    const approvedCount =
      result?.approved ?? (Array.isArray(result?.success) ? result.success.length : 0)
    const failedCount = Array.isArray(result?.failed)
      ? result.failed.length
      : typeof result?.failed === 'number'
        ? result.failed
        : 0
    ElMessage.success(
      `批量审批完成：成功 ${approvedCount}${failedCount ? `，失败 ${failedCount}` : ''}`
    )
    loadTasks()
  } catch {
    // 用户取消
  } finally {
    autoApproving.value = false
  }
}

/**
 * 批量通过
 */
async function handleBatchApprove() {
  if (selectedTasks.value.length === 0) return

  try {
    await ElMessageBox.confirm(
      `确定要批量通过选中的 ${selectedTasks.value.length} 个任务吗？`,
      '批量审批确认',
      { type: 'warning' }
    )

    const { value: opinion } = (await ElMessageBox.prompt('请输入审批意见（可选）', '批量审批', {
      inputPlaceholder: '审批意见',
    }).catch(() => ({ value: '' }))) as { value: string }

    loading.value = true
    const taskIds = selectedTasks.value.map((t) => t.id)
    const result = await batchApprove(taskIds, opinion)

    ElMessage.success(`批量审批完成：成功 ${result.success.length}，失败 ${result.failed.length}`)
    loadTasks()
  } catch {
    // 用户取消
  } finally {
    loading.value = false
  }
}

/**
 * 格式化日期时间
 */
function formatDateTime(dateStr: string): string {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

// ==================== 生命周期 ====================

onMounted(() => {
  loadTasks()
})
</script>

<style scoped lang="scss">
.pending-list {
  padding: 20px;
}

.filter-card {
  margin-bottom: 20px;

  :deep(.el-form-item) {
    margin-bottom: 0;
  }
}

.header-card {
  margin-bottom: 20px;

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;

    .title {
      font-size: 18px;
      font-weight: 600;
    }

    .actions {
      display: flex;
      gap: 10px;
    }
  }
}

.list-card {
  :deep(.el-button-group) {
    .el-button {
      padding: 5px 8px;
    }
  }

  .entity-summary {
    color: #1b4332;
    font-size: 13px;

    &.muted {
      color: #c0c4cc;
    }
  }

  .pagination {
    margin-top: 16px;
    justify-content: flex-end;
  }
}

.diff-view {
  .diff-changed {
    font-weight: 600;
  }

  .diff-new {
    color: var(--color-success);
  }
}
</style>
