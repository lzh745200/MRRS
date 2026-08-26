<template>
  <div v-watermark class="projects-page">
    <!-- 页面头部 -->
    <!-- 页面头部区（PageHeader 标准件 · T1 契约） -->
    <PageHeader title="帮扶项目管理" subtitle="管理所有乡村振兴帮扶项目，涵盖16个帮扶数据板块">
      <template #extra>
        <el-button type="primary" @click="handleCreate">
          <el-icon><Plus /></el-icon>新建项目
        </el-button>
        <el-button @click="pushSafe('/data-package')">
          <el-icon><Upload /></el-icon>批量导入
        </el-button>
        <el-button @click="handleExport">
          <el-icon><Download /></el-icon>导出
        </el-button>
        <el-button type="success" @click="pushSafe('/data-analysis')">
          <el-icon><TrendCharts /></el-icon>数据统计
        </el-button>
      </template>
    </PageHeader>

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
          <!-- 回收站入口（仅管理员）：查看已软删项目 -->
          <el-tooltip
            v-if="canViewDeleted"
            v-permission="['admin', 'super_admin']"
            content="切换显示已软删的项目（管理员可见）"
            placement="top"
          >
            <el-switch
              v-model="showDeletedOnly"
              inline-prompt
              active-text="回收站"
              inactive-text="正常"
              style="margin-left: 12px"
              @change="handleToggleDeleted"
            />
          </el-tooltip>
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
        <div class="stat-value text-warning">{{ format.formatMoney4(stats.totalBudget) }}万</div>
        <div class="stat-label">总预算</div>
      </div>
    </div>

    <!-- 数据表格 -->
    <div class="table-card">
      <!-- 批量操作工具栏 -->
      <div v-if="selectedRows.length > 0" class="batch-toolbar">
        <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>
        <!-- 回收站模式：批量恢复/批量彻底删除 -->
        <template v-if="showDeletedOnly">
          <el-button type="success" size="small" @click="handleBatchRestore">
            批量恢复 ({{ selectedRows.length }})
          </el-button>
          <el-button type="danger" size="small" @click="handleBatchPurge">
            批量彻底删除 ({{ selectedRows.length }})
          </el-button>
        </template>
        <template v-else>
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
        </template>
        <el-button size="small" text @click="clearSelection">取消选择</el-button>
      </div>
      <!-- 加载失败占位 -->
      <el-result
        v-if="loadError"
        icon="error"
        title="加载失败"
        sub-title="项目列表加载失败，请检查网络或稍后重试"
      >
        <template #extra>
          <el-button type="primary" @click="loadData">重试</el-button>
        </template>
      </el-result>
      <el-table
        v-else
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
            <!-- 回收站模式：仅提供 恢复 / 彻底删除 -->
            <template v-if="showDeletedOnly">
              <el-button type="success" link @click="handleRestore(row)">恢复</el-button>
              <el-button type="danger" link @click="handlePurge(row)">彻底删除</el-button>
            </template>
            <template v-else>
              <el-button type="primary" link @click="handleEdit(row)">编辑</el-button>
              <el-popconfirm title="确定删除该项目吗？" @confirm="handleDelete(row)">
                <template #reference>
                  <el-button type="danger" link>删除</el-button>
                </template>
              </el-popconfirm>
            </template>
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
import PageHeader from '@/components/common/PageHeader.vue'
import { logger } from '@/utils/logger'
import { format } from '@/utils'
import { getErrorMessage } from '@/utils/getErrorMessage'

import { ref, reactive, computed, onMounted } from 'vue'
import { useRouterSafe } from '@/composables/useRouterSafe'
import { useDesensitize } from '@/composables/useDesensitize'
import { ElMessage, ElMessageBox, ElTable } from 'element-plus'
import { Plus, Download, Search, Upload, TrendCharts } from '@element-plus/icons-vue'
import {
  projectApi,
  restoreProject,
  previewPurgeProject,
  purgeProject,
  type Project,
} from '@/api/projects'
import { useAuthStore } from '@/stores/auth'
import { chartColor } from '@/utils/chartColors'

const { pushSafe } = useRouterSafe()
const { ds } = useDesensitize()
const authStore = useAuthStore()
const loading = ref(false)
const loadError = ref(false)
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
  if (progress >= 50) return chartColor('warning')
  return chartColor('danger')
}

// 加载统计数据（一次调用获取所有统计）
const loadStats = async () => {
  try {
    const data = await projectApi.getStats()
    const s = data?.data || data
    stats.total = s?.total ?? 0
    stats.inProgress = s?.in_progress ?? 0
    stats.completed = s?.completed ?? 0
    stats.totalBudget = Number(s?.total_budget ?? 0)
  } catch {
    // 统计加载失败不阻塞主流程
  }
}

// 加载项目列表
const loadData = async () => {
  loading.value = true
  loadError.value = false
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
    if (showDeletedOnly.value) {
      // 回收站模式：仅查看已软删项目（后端 include_deleted 管理员收敛）
      params.include_deleted = true
      params.include_cancelled = true
    }
    const res = await projectApi.list(params)
    // 防御：兼容信封（data.items）与裸分页（items）两种形态
    projectList.value = (res as any)?.data?.items ?? (res as any)?.items ?? []
    pagination.total = (res as any)?.data?.total ?? (res as any)?.total ?? 0
  } catch (e) {
    logger.error('[Projects] loadData failed:', e)
    ElMessage.error('加载项目列表失败')
    loadError.value = true
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
    // 成功静默：仅刷新列表
    pagination.page = 1 // 重置到第1页，确保新建/编辑后的数据可见
    await loadData()
    loadStats()
  } catch {
    ElMessage.error('删除失败')
  }
}

// ── 回收站：恢复 / 彻底删除（与帮扶村回收站同一交互范式） ──
const canViewDeleted = computed(() => authStore.canViewDeleted)
const showDeletedOnly = ref(false)

const handleToggleDeleted = async () => {
  pagination.page = 1
  await loadData()
}

const handleRestore = async (row: any) => {
  try {
    await ElMessageBox.confirm(
      `确定恢复项目【${row.name}】吗？恢复后将重新出现在正常列表中。`,
      '恢复确认',
      { confirmButtonText: '确认恢复', cancelButtonText: '取消', type: 'info' }
    )
  } catch {
    return
  }
  try {
    await restoreProject(row.id)
    ElMessage.success('恢复成功')
    loadData()
  } catch {
    ElMessage.error('恢复失败')
  }
}

const handlePurge = async (row: any) => {
  let cascadeHint = ''
  let totalRefs = 0
  try {
    const preview = (await previewPurgeProject(row.id)) as any
    const data = preview?.data || preview || {}
    totalRefs = Number(data.total_references || 0)
    const top = Object.entries(data.details || {})
      .sort((a: any, b: any) => b[1] - a[1])
      .slice(0, 3)
      .map(([k, v]) => `${k} ${v}条`)
      .join('、')
    cascadeHint = top ? `（含 ${top} 等）` : ''
  } catch {
    // 预览失败不阻断流程
  }
  try {
    await ElMessageBox.confirm(
      `彻底删除后【${row.name}】及其关联的 ${totalRefs} 条数据将无法恢复${cascadeHint}！此操作不可撤销。`,
      '彻底删除警告',
      { confirmButtonText: '继续', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }
  let confirmPassword = ''
  try {
    const { value } = await ElMessageBox.prompt(
      `彻底删除【${row.name}】需二次确认，请输入登录密码：`,
      '二次确认',
      {
        confirmButtonText: '确认彻底删除',
        cancelButtonText: '取消',
        inputType: 'password',
        inputValidator: (v: string) => (v ? true : '密码不能为空'),
      }
    )
    confirmPassword = value || ''
  } catch {
    return
  }
  loading.value = true
  try {
    const result = (await purgeProject(row.id, confirmPassword)) as any
    projectList.value = projectList.value.filter((item) => item.id !== row.id)
    pagination.total = Math.max(0, pagination.total - 1)
    ElMessage.success(`已彻底删除及清理 ${result?.data?.deleted_records ?? 0} 条关联数据`)
    loadData()
  } catch {
    ElMessage.error('彻底删除失败')
  } finally {
    loading.value = false
  }
}

const handleBatchRestore = async () => {
  try {
    await ElMessageBox.confirm(
      `确定批量恢复 ${selectedRows.value.length} 个项目吗？`,
      '批量恢复确认',
      { confirmButtonText: '确认恢复', cancelButtonText: '取消', type: 'info' }
    )
  } catch {
    return
  }
  try {
    for (const row of selectedRows.value) {
      await restoreProject(row.id)
    }
    ElMessage.success(`已恢复 ${selectedRows.value.length} 个项目`)
    clearSelection()
    loadData()
  } catch {
    ElMessage.error('批量恢复失败')
  }
}

const handleBatchPurge = async () => {
  let confirmPassword = ''
  try {
    const r = await ElMessageBox.prompt('批量彻底删除需二次确认，请输入登录密码：', '二次确认', {
      confirmButtonText: '确认',
      inputType: 'password',
      inputValidator: (v: string) => (v ? true : '密码不能为空'),
    })
    confirmPassword = r.value || ''
  } catch {
    return
  }
  loading.value = true
  try {
    for (const row of selectedRows.value) {
      await purgeProject(row.id, confirmPassword)
    }
    ElMessage.success(`已彻底删除 ${selectedRows.value.length} 个项目及关联数据`)
    clearSelection()
    loadData()
  } catch {
    ElMessage.error('批量彻底删除失败')
  } finally {
    loading.value = false
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
  } catch (e) {
    ElMessage.error(getErrorMessage(e, '导出失败，请稍后重试'))
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
  color: var(--color-primary-dark-1);
  margin: 0 0 4px 0;
}

.page-desc {
  font-size: 14px;
  color: var(--color-text-secondary);
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
  color: var(--color-primary-dark-1);
}

.stat-value.text-primary {
  color: var(--color-primary);
}
.stat-value.text-success {
  color: var(--color-success);
}
.stat-value.text-warning {
  color: var(--color-warning);
}

.stat-label {
  font-size: 14px;
  color: var(--color-text-secondary);
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
  border-top: 1px solid var(--color-bg-hover);
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
