<template>
  <div class="approval-history">
    <!-- 页面标题 -->
    <el-card class="header-card">
      <template #header>
        <div class="card-header">
          <span class="title">审批历史</span>
          <el-button :loading="loading" @click="loadHistory">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>
      </template>

      <!-- 筛选条件 -->
      <el-form :model="filterForm" inline>
        <el-form-item label="实体类型">
          <el-select v-model="filterForm.entity_type" placeholder="全部" clearable>
            <el-option label="帮扶村" value="supported_village" />
            <el-option label="项目" value="project" />
            <el-option label="经费" value="fund" />
            <el-option label="学校" value="school" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filterForm.status" placeholder="全部" clearable style="width: 140px">
            <el-option label="待审批" value="pending" />
            <el-option label="已通过" value="approved" />
            <el-option label="已拒绝" value="rejected" />
            <el-option label="已撤回" value="withdrawn" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">
            <el-icon><Search /></el-icon>
            搜索
          </el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 历史列表 -->
    <el-card class="list-card">
      <el-table v-loading="loading" :data="historyList" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="title" label="审批标题" min-width="200">
          <template #default="{ row }">
            {{ row.title || `${formatEntityType(row.entity_type)} #${row.entity_id}` }}
          </template>
        </el-table-column>
        <el-table-column label="类型" width="100">
          <template #default="{ row }">
            {{ formatEntityType(row.entity_type) }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="formatApprovalStatus(row.status).type" size="small">
              {{ formatApprovalStatus(row.status).text }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="审批级别" width="100" align="center">
          <template #default="{ row }"> 第 {{ row.current_level }} 级 </template>
        </el-table-column>
        <el-table-column label="提交时间" width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="完成时间" width="180">
          <template #default="{ row }">
            {{ row.completed_at ? formatDateTime(row.completed_at) : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="handleViewDetail(row)">
              <el-icon><View /></el-icon>
              详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <el-pagination
        v-if="total > 0"
        v-model:current-page="page"
        v-model:page-size="pageSize"
        class="pagination"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="loadHistory"
        @current-change="loadHistory"
      />
    </el-card>

    <!-- 详情对话框 -->
    <el-dialog v-model="detailDialogVisible" title="审批详情" width="800px">
      <div v-if="currentTask" class="task-detail">
        <!-- 基本信息 -->
        <el-descriptions :column="2" border>
          <el-descriptions-item label="审批标题">
            {{ currentTask.title || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="实体类型">
            {{ formatEntityType(currentTask.entity_type) }}
          </el-descriptions-item>
          <el-descriptions-item label="实体ID">
            {{ currentTask.entity_id }}
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="formatApprovalStatus(currentTask.status).type">
              {{ formatApprovalStatus(currentTask.status).text }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="提交时间">
            {{ formatDateTime(currentTask.created_at) }}
          </el-descriptions-item>
          <el-descriptions-item label="完成时间">
            {{ currentTask.completed_at ? formatDateTime(currentTask.completed_at) : '-' }}
          </el-descriptions-item>
        </el-descriptions>

        <!-- 变更对比 -->
        <el-divider content-position="left">变更内容</el-divider>
        <div v-if="taskDiff" class="diff-view">
          <el-table :data="diffTableData" border size="small">
            <el-table-column prop="field" label="字段" width="150" />
            <el-table-column prop="original" label="原值">
              <template #default="{ row }">
                <span :class="{ 'diff-changed': row.changed }">{{ row.original ?? '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="new" label="新值">
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
        <el-empty v-else description="加载中..." :image-size="60" />
      </div>
      <template #footer>
        <el-button @click="detailDialogVisible = false">关闭</el-button>
        <el-button
          v-if="navigableEntity(currentTask)"
          type="primary"
          @click="handleViewEntity(currentTask!)"
        >
          查看{{ formatEntityType(currentTask!.entity_type) }}详情
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouterSafe } from '@/composables/useRouterSafe'
import { ElMessage } from 'element-plus'
import { Refresh, Search, View } from '@element-plus/icons-vue'
import {
  getTasksHistory,
  getTaskDiff,
  formatApprovalStatus,
  formatEntityType,
  type ApprovalTask,
  type TaskDiff,
} from '@/api/approval'

// ==================== 状态 ====================

const { pushSafe } = useRouterSafe()
const loading = ref(false)
const historyList = ref<ApprovalTask[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

const filterForm = ref({
  entity_type: undefined as string | undefined,
  status: undefined as string | undefined,
})

// 详情对话框
const detailDialogVisible = ref(false)
const currentTask = ref<ApprovalTask | null>(null)
const taskDiff = ref<TaskDiff | null>(null)

// ==================== 计算属性 ====================

/** 可跳转的业务实体类型 */
function navigableEntity(task: any): boolean {
  return ['rural_work', 'fund', 'project', 'school', 'supported_village'].includes(
    task?.entity_type
  )
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

// ==================== 方法 ====================

/**
 * 加载审批历史（任务维度：管理员看全部，普通用户仅看自己提交的）
 */
async function loadHistory() {
  loading.value = true
  try {
    const skip = (page.value - 1) * pageSize.value
    const result = await getTasksHistory({
      entity_type: filterForm.value.entity_type,
      status: filterForm.value.status,
      skip,
      limit: pageSize.value,
    })
    historyList.value = result.items
    total.value = result.total
  } catch (error) {
    ElMessage.error('加载审批历史失败')
  } finally {
    loading.value = false
  }
}

/**
 * 搜索
 */
function handleSearch() {
  page.value = 1
  loadHistory()
}

/**
 * 重置
 */
function handleReset() {
  filterForm.value = {
    entity_type: undefined,
    status: undefined,
  }
  page.value = 1
  loadHistory()
}

/**
 * 查看详情
 */
async function handleViewDetail(task: any) {
  currentTask.value = task
  taskDiff.value = null
  detailDialogVisible.value = true

  try {
    taskDiff.value = await getTaskDiff(task.id)
  } catch (error) {
    // 可能没有变更数据
  }
}

/**
 * 跳转到实体详情
 */
function handleViewEntity(task: any) {
  const detailRoutes: Record<string, string> = {
    fund: `/funds/${task.entity_id}`,
    project: `/projects/${task.entity_id}`,
    school: `/schools/${task.entity_id}`,
    supported_village: `/supported-villages/${task.entity_id}`,
  }
  if (task.entity_type === 'rural_work') {
    detailDialogVisible.value = false
    pushSafe({
      path: '/rural-works',
      query: { id: task.entity_id, action: 'view' },
    })
  } else if (detailRoutes[task.entity_type]) {
    detailDialogVisible.value = false
    pushSafe(detailRoutes[task.entity_type])
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
  loadHistory()
})
</script>

<style scoped lang="scss">
.approval-history {
  padding: 20px;
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
  }
}

.list-card {
  .pagination {
    margin-top: 20px;
    justify-content: flex-end;
  }
}

.task-detail {
  .diff-view {
    margin-top: 16px;

    .diff-changed {
      font-weight: 600;
    }

    .diff-new {
      color: #67c23a;
    }
  }
}
</style>
