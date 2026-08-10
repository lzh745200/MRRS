<template>
  <div class="projects-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-info">
        <h2 class="page-title">帮扶项目管理</h2>
        <p class="page-desc">管理所有乡村振兴帮扶项目，涵盖16个帮扶数据板块</p>
      </div>
      <div class="header-actions">
        <el-button type="primary" @click="handleCreate">
          <el-icon><Plus /></el-icon>新建项目
        </el-button>
        <el-button @click="pushSafe('/data-import/batch')">
          <el-icon><Upload /></el-icon>批量导入
        </el-button>
        <el-button @click="handleExport">
          <el-icon><Download /></el-icon>导出
        </el-button>
        <el-button type="success" @click="pushSafe('/data-analysis')">
          <el-icon><TrendCharts /></el-icon>数据统计
        </el-button>
      </div>
    </div>

    <!-- 搜索筛选 -->
    <div class="filter-card">
      <el-form :model="filterForm" inline @submit.prevent>
        <el-form-item label="项目名称">
          <el-input
            v-model="filterForm.name"
            placeholder="帮扶村/单位/项目编号"
            clearable
            style="width: 200px"
          />
        </el-form-item>
        <el-form-item label="项目状态">
          <el-select
            v-model="filterForm.status"
            placeholder="全部状态"
            clearable
            style="width: 140px"
          >
            <el-option label="草稿" value="draft" />
            <el-option label="待审批" value="pending" />
            <el-option label="已审批" value="approved" />
            <el-option label="进行中" value="in_progress" />
            <el-option label="已完成" value="completed" />
            <el-option label="已取消" value="cancelled" />
          </el-select>
        </el-form-item>
        <el-form-item label="帮扶类型">
          <el-select
            v-model="filterForm.type"
            placeholder="全部类型"
            clearable
            style="width: 140px"
          >
            <el-option label="基础设施" value="infrastructure" />
            <el-option label="教育帮扶" value="education" />
            <el-option label="产业发展" value="industry" />
            <el-option label="医疗卫生" value="medical" />
            <el-option label="党建帮扶" value="party_building" />
            <el-option label="消费帮扶" value="consumption" />
            <el-option label="就业帮扶" value="employment" />
          </el-select>
        </el-form-item>
        <el-form-item label="地区">
          <el-select
            v-model="filterForm.region"
            placeholder="全部地区"
            clearable
            style="width: 140px"
          >
            <el-option label="都匀市" value="都匀市" />
            <el-option label="长顺县" value="长顺县" />
            <el-option label="独山县" value="独山县" />
            <el-option label="平塘县" value="平塘县" />
            <el-option label="罗甸县" value="罗甸县" />
            <el-option label="惠水县" value="惠水县" />
            <el-option label="贵定县" value="贵定县" />
            <el-option label="福泉市" value="福泉市" />
            <el-option label="瓮安县" value="瓮安县" />
            <el-option label="三都县" value="三都县" />
            <el-option label="荔波县" value="荔波县" />
            <el-option label="龙里县" value="龙里县" />
          </el-select>
        </el-form-item>
        <el-form-item label="年份">
          <el-input-number
            v-model="filterForm.year"
            :min="2000"
            :max="2099"
            :step="1"
            controls-position="right"
            placeholder="全部年份"
            clearable
            style="width: 140px"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">
            <el-icon><Search /></el-icon>搜索
          </el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-row">
      <div class="stat-item stat-clickable" @click="handleStatClick('')">
        <div class="stat-value">{{ stats.total }}</div>
        <div class="stat-label">项目总数</div>
      </div>
      <div class="stat-item stat-clickable" @click="handleStatClick('in_progress')">
        <div class="stat-value text-primary">{{ stats.inProgress }}</div>
        <div class="stat-label">进行中</div>
      </div>
      <div class="stat-item stat-clickable" @click="handleStatClick('completed')">
        <div class="stat-value text-success">{{ stats.completed }}</div>
        <div class="stat-label">已完成</div>
      </div>
      <div class="stat-item">
        <div class="stat-value text-warning">{{ stats.totalBudget }}万</div>
        <div class="stat-label">总预算</div>
      </div>
    </div>

    <!-- 数据表格 -->
    <div class="table-card">
      <!-- 批量操作工具栏 -->
      <div v-if="selectedRows.length > 0" class="batch-toolbar">
        <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>
        <el-button
          type="danger"
          size="small"
          :loading="batchDeleting"
          :disabled="batchDeleting"
          @click="handleBatchDelete"
        >
          批量删除 ({{ selectedRows.length }})
        </el-button>
        <el-button size="small" @click="handleBatchExport">
          批量导出 ({{ selectedRows.length }})
        </el-button>
        <el-button size="small" text @click="clearSelection">取消选择</el-button>
      </div>
      <el-table
        ref="tableRef"
        v-loading="loading"
        :data="projectList"
        stripe
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="45" />
        <el-table-column prop="code" label="项目编号" width="120" />
        <el-table-column prop="name" label="项目名称" min-width="200">
          <template #default="{ row }">
            <el-link type="primary" @click="handleView(row)">{{ row.name }}</el-link>
          </template>
        </el-table-column>
        <el-table-column prop="type" label="项目类型" width="120">
          <template #default="{ row }">
            <el-tag>{{ getTypeText(row.type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ getStatusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="progress" label="进度" width="150">
          <template #default="{ row }">
            <el-progress
              :percentage="row.progress"
              :color="getProgressColor(row.progress)"
              :stroke-width="6"
            />
          </template>
        </el-table-column>
        <el-table-column prop="budget" label="预算(万元)" width="120" align="right">
          <template #default="{ row }">
            {{ row.budget?.toLocaleString() || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="responsible_person" label="负责人" width="100">
          <template #default="{ row }">
            {{ ds(row.responsible_person, 'name') }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="handleView(row)">查看</el-button>
            <el-button type="primary" link @click="handleEdit(row)">编辑</el-button>
            <el-popconfirm title="确定删除该项目吗？" @confirm="handleDelete(row)">
              <template #reference>
                <el-button type="danger" link>删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="pagination.total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSizeChange"
          @current-change="handlePageChange"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { logger } from '@/utils/logger'

import { ref, reactive, computed, onMounted } from 'vue'
import { useRouterSafe } from '@/composables/useRouterSafe'
import { useDesensitize } from '@/composables/useDesensitize'
import { ElMessage, ElMessageBox, ElTable } from 'element-plus'
import { Plus, Download, Search, Upload, TrendCharts } from '@element-plus/icons-vue'
import { projectApi, type Project } from '@/api/projects'

const { pushSafe } = useRouterSafe()
const { ds } = useDesensitize()
const loading = ref(false)
const batchDeleting = ref(false)
const selectedRows = ref<Project[]>([])
const selectedIds = computed(() => selectedRows.value.map((r) => r.id))
const tableRef = ref<any>(null)

// 筛选表单
const filterForm = reactive({
  name: '',
  status: '',
  type: '',
  region: '',
  year: null as number | null,
})

// 统计数据
const stats = reactive({
  total: 0,
  inProgress: 0,
  completed: 0,
  totalBudget: 0,
})

// 分页
const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0,
})

// 项目列表数据
const projectList = ref<Project[]>([])

// 辅助函数
const getTypeText = (type: string) => {
  const texts: Record<string, string> = {
    infrastructure: '基础设施',
    education: '教育帮扶',
    industry: '产业发展',
    medical: '医疗卫生',
    healthcare: '医疗卫生',
    agriculture: '农业发展',
    other: '其他',
  }
  return texts[type] || type
}

const getStatusType = (status: string): 'success' | 'info' | 'warning' | 'danger' | 'primary' => {
  const types: Record<string, 'success' | 'info' | 'warning' | 'danger' | 'primary'> = {
    draft: 'info',
    pending: 'info',
    approved: 'primary',
    planning: 'info',
    in_progress: 'warning',
    completed: 'success',
    cancelled: 'danger',
    suspended: 'danger',
  }
  return types[status] || 'info'
}

const getStatusText = (status: string) => {
  const texts: Record<string, string> = {
    draft: '草稿',
    pending: '待审批',
    approved: '已审批',
    planning: '规划中',
    in_progress: '进行中',
    completed: '已完成',
    cancelled: '已取消',
    suspended: '已暂停',
  }
  return texts[status] || status
}

const getProgressColor = (progress: number) => {
  if (progress >= 80) return '#40916c'
  if (progress >= 50) return '#e6a23c'
  return '#f56c6c'
}

// 加载统计数据（一次调用获取所有统计）
const loadStats = async () => {
  try {
    const data = await projectApi.getStats()
    const s = data?.data || data
    stats.total = s?.total ?? 0
    stats.inProgress = s?.in_progress ?? 0
    stats.completed = s?.completed ?? 0
    stats.totalBudget = Math.round(s?.total_budget ?? 0)
  } catch {
    // 统计加载失败不阻塞主流程
  }
}

// 加载项目列表
const loadData = async () => {
  loading.value = true
  try {
    const params: Record<string, any> = {
      page: pagination.page,
      page_size: pagination.pageSize,
      keyword: filterForm.name || undefined,
      project_type: filterForm.type || undefined,
      status: filterForm.status || undefined,
      region: filterForm.region || undefined,
      year: filterForm.year || undefined,
    }
    if (filterForm.status === 'cancelled') {
      params.include_cancelled = true
    }
    const res = await projectApi.list(params)
    projectList.value = (res as any)?.data?.items || (res as any)?.items || []
    pagination.total = (res as any)?.data?.total || (res as any)?.total || 0
  } catch (e) {
    logger.error('[Projects] loadData failed:', e)
    ElMessage.error('加载项目列表失败')
    projectList.value = []
    pagination.total = 0
  } finally {
    loading.value = false
  }
}

// 事件处理
const handleSearch = () => {
  pagination.page = 1
  loadData()
}

const handleReset = () => {
  filterForm.name = ''
  filterForm.status = ''
  filterForm.type = ''
  filterForm.region = ''
  filterForm.year = null
  handleSearch()
}

const handleCreate = () => {
  pushSafe('/projects/create')
}

const handleView = (row: any) => {
  const id = row?.id
  if (!id) {
    ElMessage.error('无法查看：项目 ID 无效')
    return
  }
  pushSafe(`/projects/${id}`)
}

const handleEdit = (row: any) => {
  const id = row?.id
  if (!id) {
    ElMessage.error('无法编辑：项目 ID 无效')
    return
  }
  pushSafe(`/projects/${id}/edit`)
}

const handleDelete = async (row: any) => {
  const id = row?.id
  if (!id) {
    ElMessage.error('无法删除：项目 ID 无效')
    return
  }
  try {
    await projectApi.delete(id)
    ElMessage.success('删除成功')
    pagination.page = 1 // 重置到第1页，确保新建/编辑后的数据可见
    await loadData()
    loadStats()
  } catch {
    ElMessage.error('删除失败')
  }
}

/** 点击统计卡片 - 按状态筛选 */
const handleStatClick = (status: string) => {
  filterForm.status = status
  filterForm.name = ''
  filterForm.type = ''
  pagination.page = 1
  loadData()
}

const handleExport = async () => {
  try {
    await projectApi.exportList({
      keyword: filterForm.name || undefined,
      project_type: filterForm.type || undefined,
      status: filterForm.status || undefined,
    })
    ElMessage.success('导出成功')
  } catch {
    ElMessage.error('导出失败，请稍后重试')
  }
}

const handleSizeChange = () => {
  pagination.page = 1
  loadData()
}

const handlePageChange = () => {
  loadData()
}

// 批量操作
const handleSelectionChange = (rows: any[]) => {
  selectedRows.value = rows
}

const clearSelection = () => {
  tableRef.value?.clearSelection()
  selectedRows.value = []
}

const handleBatchDelete = async () => {
  if (!selectedIds.value.length || batchDeleting.value) return
  const count = selectedIds.value.length
  try {
    await ElMessageBox.confirm(
      `确定删除选中的 ${count} 个项目吗？此操作不可撤销。`,
      '批量删除确认',
      { type: 'warning' }
    )
  } catch {
    return
  }
  batchDeleting.value = true
  try {
    const results = await Promise.allSettled(selectedIds.value.map((id) => projectApi.delete(id)))
    const deleted = results.filter((r) => r.status === 'fulfilled').length
    const failed = results.length - deleted
    if (deleted > 0) ElMessage.success(`成功删除 ${deleted} 个项目`)
    if (failed > 0) ElMessage.warning(`${failed} 个项目删除失败`)
    clearSelection()
    pagination.page = 1 // 重置到第1页，确保新建/编辑后的数据可见
    await loadData()
    loadStats()
  } finally {
    batchDeleting.value = false
  }
}

const handleBatchExport = async () => {
  if (!selectedIds.value.length) return
  try {
    await projectApi.exportList({ ids: selectedIds.value })
    ElMessage.success(`已导出 ${selectedIds.value.length} 条项目记录`)
  } catch {
    ElMessage.error('导出失败')
  }
}

onMounted(() => {
  loadData()
  loadStats()
})
</script>

<style scoped>
.projects-page {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.page-title {
  font-size: 20px;
  font-weight: 600;
  color: #1b4332;
  margin: 0 0 4px 0;
}

.page-desc {
  font-size: 14px;
  color: #666;
  margin: 0;
}

.header-actions {
  display: flex;
  gap: 12px;
}

.filter-card {
  background: white;
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.stat-item {
  background: white;
  padding: 20px;
  border-radius: 8px;
  text-align: center;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  transition: all 0.3s;
}

.stat-clickable {
  cursor: pointer;
}

.stat-clickable:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: #1b4332;
}

.stat-value.text-primary {
  color: var(--color-primary);
}
.stat-value.text-success {
  color: #67c23a;
}
.stat-value.text-warning {
  color: #e6a23c;
}

.stat-label {
  font-size: 14px;
  color: #666;
  margin-top: 4px;
}

.table-card {
  flex: 1;
  background: white;
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  display: flex;
  flex-direction: column;
}

.batch-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  background: var(--color-primary-light-8);
  border: 1px solid var(--color-primary-light-5);
  border-radius: 6px;
  margin-bottom: 12px;
}

.batch-info {
  font-size: 13px;
  color: var(--color-primary);
  font-weight: 500;
}

.pagination-wrapper {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid #f0f0f0;
}

@media (max-width: 768px) {
  .stats-row {
    grid-template-columns: repeat(2, 1fr);
  }

  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }
}
</style>
