<template>
  <div class="error-reports-page">
    <!-- 页面标题 -->
    <div class="page-header">
      <h2 class="page-title">错误报告监控</h2>
      <el-button
        type="primary"
        :icon="Refresh"
        :loading="statsLoading && tableLoading"
        @click="refreshAll"
      >
        刷新
      </el-button>
    </div>

    <!-- 错误统计概览 -->
    <el-row :gutter="16" class="stats-row">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card stat-card--default">
          <div class="stat-label">错误总数</div>
          <div class="stat-value">{{ stats.total }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card stat-card--warning">
          <div class="stat-label">未处理</div>
          <div class="stat-value">{{ stats.open }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card stat-card--danger">
          <div class="stat-label">
            <el-icon><Warning /></el-icon>
            严重错误
          </div>
          <div class="stat-value">{{ stats.critical }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card stat-card--success">
          <div class="stat-label">已解决</div>
          <div class="stat-value">{{ stats.total - stats.open }}</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 分类统计 -->
    <el-row :gutter="16" class="breakdown-row">
      <el-col :span="12">
        <el-card shadow="hover" class="breakdown-card">
          <template #header>
            <span class="breakdown-title">按来源分类</span>
          </template>
          <div class="tag-list">
            <el-tag
              v-for="(count, source) in stats.by_source"
              :key="source"
              type="info"
              class="breakdown-tag"
            >
              {{ source }}：{{ count }}
            </el-tag>
            <span v-if="!Object.keys(stats.by_source || {}).length" class="empty-hint"
              >暂无数据</span
            >
          </div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="hover" class="breakdown-card">
          <template #header>
            <span class="breakdown-title">按严重程度分类</span>
          </template>
          <div class="tag-list">
            <el-tag
              v-for="(count, sev) in stats.by_severity"
              :key="sev"
              :type="severityTagType(sev)"
              class="breakdown-tag"
            >
              {{ severityLabel(sev) }}：{{ count }}
            </el-tag>
            <span v-if="!Object.keys(stats.by_severity || {}).length" class="empty-hint"
              >暂无数据</span
            >
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 错误报告列表 -->
    <el-card class="table-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">错误报告列表</span>
          <el-tag type="info">共 {{ tableTotal }} 条</el-tag>
        </div>
      </template>

      <!-- 筛选栏 -->
      <el-form :inline="true" :model="filters" class="filter-form">
        <el-form-item label="严重程度">
          <el-select
            v-model="filters.severity"
            placeholder="全部"
            clearable
            style="width: 130px"
            @change="handleSearch"
          >
            <el-option label="严重" value="critical" />
            <el-option label="错误" value="error" />
            <el-option label="警告" value="warning" />
            <el-option label="信息" value="info" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select
            v-model="filters.status"
            placeholder="全部"
            clearable
            style="width: 130px"
            @change="handleSearch"
          >
            <el-option label="待处理" value="open" />
            <el-option label="处理中" value="in_progress" />
            <el-option label="已解决" value="resolved" />
            <el-option label="已忽略" value="ignored" />
          </el-select>
        </el-form-item>
        <el-form-item label="来源">
          <el-input
            v-model="filters.source"
            placeholder="输入来源关键词"
            clearable
            style="width: 180px"
            @clear="handleSearch"
            @keyup.enter="handleSearch"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">查询</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>

      <!-- 表格 -->
      <el-table v-loading="tableLoading" :data="tableData" stripe border>
        <el-table-column prop="id" label="ID" width="70" align="center" />
        <el-table-column prop="createdAt" label="时间" width="170">
          <template #default="{ row }">
            {{ formatTime(row.createdAt) }}
          </template>
        </el-table-column>
        <el-table-column prop="source" label="来源" width="140" show-overflow-tooltip />
        <el-table-column prop="errorType" label="错误类型" width="140" show-overflow-tooltip />
        <el-table-column prop="message" label="错误信息" min-width="220" show-overflow-tooltip />
        <el-table-column prop="severity" label="严重程度" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="severityTagType(row.severity)" size="small">
              {{ severityLabel(row.severity) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" align="center" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link :icon="View" @click="showDetail(row.id)">
              详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="tableTotal"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        class="pagination"
        @current-change="loadTableData"
        @size-change="handlePageSizeChange"
      />
    </el-card>

    <!-- 错误详情弹窗 -->
    <el-dialog v-model="detailVisible" title="错误详情" :width="DIALOG_MD" :close-on-click-modal="false">
      <template v-if="detailLoading">
        <el-skeleton :rows="10" animated />
      </template>
      <template v-else-if="detail">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="ID">{{ detail.id }}</el-descriptions-item>
          <el-descriptions-item label="来源">{{ detail.source }}</el-descriptions-item>
          <el-descriptions-item label="错误类型">{{ detail.errorType }}</el-descriptions-item>
          <el-descriptions-item label="严重程度">
            <el-tag :type="severityTagType(detail.severity)" size="small">
              {{ severityLabel(detail.severity) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="statusTagType(detail.status)" size="small">
              {{ statusLabel(detail.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="上报人">{{
            detail.reporter || '系统'
          }}</el-descriptions-item>
          <el-descriptions-item label="上报时间">{{
            formatTime(detail.createdAt)
          }}</el-descriptions-item>
          <el-descriptions-item label="解决时间">{{
            formatTime(detail.resolvedAt) || '--'
          }}</el-descriptions-item>
          <el-descriptions-item label="错误信息" :span="2">
            <div class="detail-message">{{ detail.message }}</div>
          </el-descriptions-item>
          <el-descriptions-item v-if="detail.stackTrace" label="堆栈跟踪" :span="2">
            <el-input
              type="textarea"
              :rows="6"
              :model-value="detail.stackTrace"
              readonly
              class="stack-trace-input"
            />
          </el-descriptions-item>
          <el-descriptions-item v-if="detail.context" label="上下文数据" :span="2">
            <pre class="context-json">{{ JSON.stringify(detail.context, null, 2) }}</pre>
          </el-descriptions-item>
          <el-descriptions-item v-if="detail.resolutionNote" label="解决备注" :span="2">
            {{ detail.resolutionNote }}
          </el-descriptions-item>
        </el-descriptions>

        <!-- 状态更新 -->
        <el-divider content-position="left">状态更新</el-divider>
        <el-form :model="updateForm" label-width="80px" class="update-form">
          <el-form-item label="状态">
            <el-select v-model="updateForm.status" placeholder="请选择状态" style="width: 200px">
              <el-option label="处理中" value="in_progress" />
              <el-option label="已解决" value="resolved" />
              <el-option label="已忽略" value="ignored" />
            </el-select>
          </el-form-item>
          <el-form-item label="解决备注">
            <el-input
              v-model="updateForm.resolution_note"
              type="textarea"
              :rows="3"
              placeholder="请输入解决备注（可选）"
            />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="updateLoading" @click="handleUpdateStatus">
              更新状态
            </el-button>
          </el-form-item>
        </el-form>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { DIALOG_MD } from '@/config/dialog'
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, View, Warning } from '@element-plus/icons-vue'
import { errorReportApi, type ErrorReport, type ErrorStats } from '@/api/errorReport'

// ==================== 统计数据 ====================
const statsLoading = ref(false)
const stats = ref<ErrorStats>({
  total: 0,
  open: 0,
  critical: 0,
  by_source: {},
  by_severity: {},
})

async function loadStats() {
  statsLoading.value = true
  try {
    const res = await errorReportApi.getStats()
    if (res.success && res.data) {
      stats.value = res.data
    }
  } catch (e: any) {
    ElMessage.error('加载错误统计失败')
  } finally {
    statsLoading.value = false
  }
}

// ==================== 筛选 ====================
const filters = reactive({
  severity: undefined as string | undefined,
  status: undefined as string | undefined,
  source: undefined as string | undefined,
})

// ==================== 分页 ====================
const pagination = reactive({
  page: 1,
  pageSize: 20,
})

// ==================== 表格 ====================
const tableLoading = ref(false)
const tableData = ref<ErrorReport[]>([])
const tableTotal = ref(0)

async function loadTableData() {
  tableLoading.value = true
  try {
    const params: Record<string, any> = {
      page: pagination.page,
      page_size: pagination.pageSize,
    }
    if (filters.severity) params.severity = filters.severity
    if (filters.status) params.status = filters.status
    if (filters.source) params.source = filters.source

    const res = await errorReportApi.listReports(params)
    if (res.success && res.data) {
      tableData.value = res.data.items || []
      tableTotal.value = res.data.total || 0
    }
  } catch (e: any) {
    tableData.value = []
    tableTotal.value = 0
    ElMessage.error('加载错误报告列表失败')
  } finally {
    tableLoading.value = false
  }
}

function handleSearch() {
  pagination.page = 1
  loadTableData()
}

function handleReset() {
  filters.severity = undefined
  filters.status = undefined
  filters.source = undefined
  pagination.page = 1
  loadTableData()
}

function handlePageSizeChange() {
  pagination.page = 1
  loadTableData()
}

// ==================== 详情弹窗 ====================
const detailVisible = ref(false)
const detailLoading = ref(false)
const detail = ref<ErrorReport | null>(null)

async function showDetail(reportId: number) {
  detailVisible.value = true
  detailLoading.value = true
  detail.value = null
  try {
    const res = await errorReportApi.getReport(reportId)
    if (res.success && res.data) {
      detail.value = res.data
      // 初始化更新表单（后端 to_dict 为 camelCase 键名；兼容旧 snake_case 响应）
      updateForm.status = res.data.status
      updateForm.resolution_note =
        res.data.resolutionNote || (res.data as any).resolution_note || ''
    }
  } catch (e: any) {
    ElMessage.error('加载错误详情失败')
    detailVisible.value = false
  } finally {
    detailLoading.value = false
  }
}

// ==================== 状态更新 ====================
const updateLoading = ref(false)
const updateForm = reactive({
  status: 'resolved',
  resolution_note: '',
})

async function handleUpdateStatus() {
  if (!detail.value) return
  updateLoading.value = true
  try {
    const res = await errorReportApi.updateReport(detail.value.id, {
      status: updateForm.status,
      resolution_note: updateForm.resolution_note || undefined,
    })
    if (res.success) {
      ElMessage.success(res.message || '状态更新成功')
      detailVisible.value = false
      pagination.page = 1
      loadTableData()
      loadStats()
    } else {
      ElMessage.error(res.message || '状态更新失败')
    }
  } catch (e: any) {
    ElMessage.error('状态更新失败')
  } finally {
    updateLoading.value = false
  }
}

// ==================== 全局刷新 ====================
async function refreshAll() {
  await Promise.all([loadStats(), loadTableData()])
}

// ==================== 工具函数 ====================
function severityLabel(severity: string): string {
  const map: Record<string, string> = {
    critical: '严重',
    error: '错误',
    warning: '警告',
    info: '信息',
  }
  return map[severity] || severity
}

type TagType = 'primary' | 'success' | 'warning' | 'info' | 'danger'

function severityTagType(severity: string): TagType {
  const map: Record<string, TagType> = {
    critical: 'danger',
    error: 'danger',
    warning: 'warning',
    info: 'info',
  }
  return map[severity] || 'info'
}

function statusLabel(status: string): string {
  const map: Record<string, string> = {
    open: '待处理',
    in_progress: '处理中',
    resolved: '已解决',
    ignored: '已忽略',
  }
  return map[status] || status
}

function statusTagType(status: string): TagType {
  const map: Record<string, TagType> = {
    open: 'warning',
    in_progress: 'primary',
    resolved: 'success',
    ignored: 'info',
  }
  return map[status] || 'info'
}

function formatTime(isoStr?: string): string {
  if (!isoStr) return ''
  try {
    const d = new Date(isoStr)
    if (isNaN(d.getTime())) return isoStr
    const pad = (n: number) => String(n).padStart(2, '0')
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
    /* c8 ignore start */
  } catch {
    return isoStr
  }
  /* c8 ignore stop */
}

// ==================== 生命周期 ====================
onMounted(() => {
  refreshAll()
})
</script>

<style scoped>
.error-reports-page {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: var(--color-text-primary);
}

/* 统计卡片 */
.stats-row {
  margin-bottom: 16px;
}

.stat-card {
  text-align: center;
  cursor: pointer;
  transition: transform 0.2s;
}

.stat-card:hover {
  transform: translateY(-2px);
}

.stat-card--default {
  border-top: 3px solid var(--color-info);
}

.stat-card--warning {
  border-top: 3px solid var(--color-warning);
}

.stat-card--danger {
  border-top: 3px solid var(--color-danger);
}

.stat-card--success {
  border-top: 3px solid var(--color-success);
}

.stat-label {
  font-size: 14px;
  color: var(--color-info);
  margin-bottom: 8px;
}

.stat-value {
  font-size: 32px;
  font-weight: 700;
  color: var(--color-text-primary);
}

.stat-card--warning .stat-value {
  color: var(--color-warning);
}

.stat-card--danger .stat-value {
  color: var(--color-danger);
}

.stat-card--success .stat-value {
  color: var(--color-success);
}

/* 分类统计 */
.breakdown-row {
  margin-bottom: 16px;
}

.breakdown-title {
  font-weight: 600;
  font-size: 15px;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  min-height: 32px;
  align-items: center;
}

.breakdown-tag {
  font-size: 13px;
}

.empty-hint {
  color: #c0c4cc;
  font-size: 13px;
}

/* 表格卡片 */
.table-card {
  margin-bottom: 16px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
}

.filter-form {
  margin-bottom: 16px;
}

.pagination {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

/* 详情弹窗 */
.detail-message {
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 120px;
  overflow-y: auto;
}

.stack-trace-input :deep(.el-textarea__inner) {
  font-family: 'Courier New', Courier, monospace;
  font-size: 12px;
  line-height: 1.5;
  background-color: var(--color-bg-hover);
}

.context-json {
  margin: 0;
  padding: 12px;
  background-color: var(--color-bg-hover);
  border: 1px solid var(--color-border-light);
  border-radius: 4px;
  font-family: 'Courier New', Courier, monospace;
  font-size: 12px;
  line-height: 1.6;
  max-height: 200px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

.update-form {
  margin-top: 16px;
}
</style>
