<template>
  <div class="school-mgmt-list-page">
    <!-- 页面头部 -->
    <!-- 页面头部区（PageHeader 标准件 · T1 契约） -->
    <PageHeader title="帮扶学校管理" subtitle="管理帮扶学校信息，跟踪教育帮扶进展">
      <template #extra>
        <el-button type="primary" @click="handleCreate">
          <el-icon><Plus /></el-icon>新增学校
        </el-button>
        <el-button type="success" plain @click="handleDownloadTemplate">
          <el-icon><Download /></el-icon>下载模板
        </el-button>
        <el-button type="warning" plain @click="showImportDialog = true">
          <el-icon><Upload /></el-icon>导入
        </el-button>
        <el-button type="info" plain @click="handleExport">
          <el-icon><Download /></el-icon>导出
        </el-button>
      </template>
    </PageHeader>

    <!-- 统计卡片 -->
    <div class="stats-row">
      <div
        class="stat-item clickable"
        role="button"
        tabindex="0"
        @click="filterByStatus('')"
        @keydown.enter.prevent="filterByStatus('')"
        @keydown.space.prevent="filterByStatus('')"
      >
        <div class="stat-value">{{ stats.total }}</div>
        <div class="stat-label">学校总数</div>
      </div>
      <div
        class="stat-item clickable"
        role="button"
        tabindex="0"
        @click="filterByStatus('active')"
        @keydown.enter.prevent="filterByStatus('active')"
        @keydown.space.prevent="filterByStatus('active')"
      >
        <div class="stat-value text-success">{{ stats.active }}</div>
        <div class="stat-label">帮扶中</div>
      </div>
      <div
        class="stat-item clickable"
        role="button"
        tabindex="0"
        @click="filterByStatus('completed')"
        @keydown.enter.prevent="filterByStatus('completed')"
        @keydown.space.prevent="filterByStatus('completed')"
      >
        <div class="stat-value text-primary">{{ stats.completed }}</div>
        <div class="stat-label">已完成</div>
      </div>
      <div class="stat-item">
        <div class="stat-value text-warning">{{ stats.totalStudents }}</div>
        <div class="stat-label">学生总数</div>
      </div>
      <div class="stat-item">
        <div class="stat-value text-info">{{ stats.totalTeachers }}</div>
        <div class="stat-label">教师总数</div>
      </div>
      <div class="stat-item">
        <div class="stat-value text-project">{{ apiStats.project_count }}</div>
        <div class="stat-label">助学兴教项目</div>
      </div>
      <div class="stat-item">
        <div class="stat-value text-scholarship">
          {{ apiStats.scholarship_count }}
        </div>
        <div class="stat-label">资助学生数</div>
      </div>
    </div>

    <!-- 统计图表 -->
    <el-row :gutter="16" class="charts-row">
      <el-col :xs="24" :sm="12">
        <div class="chart-card">
          <h3 class="chart-title">学生分布（按学校 Top 10）</h3>
          <div ref="studentBarRef" class="chart-body" />
        </div>
      </el-col>
      <el-col :xs="24" :sm="12">
        <div class="chart-card">
          <h3 class="chart-title">学校类型分布</h3>
          <div ref="typePieRef" class="chart-body" />
        </div>
      </el-col>
    </el-row>

    <!-- 搜索筛选 -->
    <div class="filter-card">
      <el-form :model="filterForm" inline @submit.prevent>
        <el-form-item label="学校名称">
          <el-input
            v-model="filterForm.keyword"
            placeholder="名称/编码/帮扶单位"
            clearable
            style="width: 200px"
            @keyup.enter="handleSearch"
          />
        </el-form-item>
        <el-form-item label="学校类型">
          <el-select
            v-model="filterForm.type"
            placeholder="全部类型"
            clearable
            style="width: 130px"
          >
            <el-option label="小学" value="primary" />
            <el-option label="初中" value="middle" />
            <el-option label="高中" value="high" />
            <el-option label="职业学校" value="vocational" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="帮扶状态">
          <el-select
            v-model="filterForm.status"
            placeholder="全部状态"
            clearable
            style="width: 130px"
          >
            <el-option label="帮扶中" value="active" />
            <el-option label="未帮扶" value="inactive" />
            <el-option label="已完成" value="completed" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">
            <el-icon><Search /></el-icon>搜索
          </el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
        <el-form-item>
          <el-tooltip
            v-if="canViewDeleted"
            content="切换显示已软删的学校（管理员可见）"
            placement="top"
          >
            <el-switch
              v-model="showDeletedOnly"
              inline-prompt
              active-text="回收站"
              inactive-text="正常"
              @change="handleToggleDeleted"
            />
          </el-tooltip>
        </el-form-item>
      </el-form>
    </div>

    <!-- 数据表格 -->
    <div class="table-card">
      <el-result
        v-if="loadError && !tableData.length"
        icon="error"
        title="数据加载失败"
        :sub-title="loadErrorMsg || '请稍后重试'"
      >
        <template #extra>
          <el-button type="primary" @click="fetchData">重试</el-button>
        </template>
      </el-result>
      <template v-else>
        <el-table v-loading="loading" :data="tableData" stripe>
          <template #empty>
            <EmptyState text="暂无数据" />
          </template>
          <el-table-column type="index" label="序号" width="60" align="center" />
          <el-table-column prop="name" label="学校名称" min-width="180">
            <template #default="scope">
              <el-link type="primary" @click="handleView(scope.row)">{{ scope.row.name }}</el-link>
            </template>
          </el-table-column>
          <el-table-column prop="type" label="类型" width="100" align="center">
            <template #default="scope">
              <el-tag size="small">{{ typeMap[scope.row.type] || scope.row.type || '-' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="support_unit" label="帮扶单位" width="140" show-overflow-tooltip />
          <el-table-column prop="student_count" label="学生数" width="90" align="right">
            <template #default="scope">
              {{ scope.row.student_count || scope.row.students || 0 }}
            </template>
          </el-table-column>
          <el-table-column prop="teacher_count" label="教师数" width="90" align="right">
            <template #default="scope">
              {{ scope.row.teacher_count || scope.row.teachers || 0 }}
            </template>
          </el-table-column>
          <el-table-column prop="support_status" label="帮扶状态" width="100" align="center">
            <template #default="scope">
              <el-tag :type="getStatusTagType(scope.row.support_status)" size="small">
                {{ statusMap[scope.row.support_status] || '未帮扶' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="address" label="地址" min-width="160" show-overflow-tooltip>
            <template #default="scope">
              {{ ds(scope.row.address, 'address') }}
            </template>
          </el-table-column>
          <el-table-column prop="created_at" label="创建时间" width="110" align="center">
            <template #default="scope">
              {{ scope.row.created_at ? String(scope.row.created_at).split('T')[0] : '-' }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="200" fixed="right">
            <template #default="scope">
              <el-button type="primary" link size="small" @click="handleView(scope.row)"
                >查看</el-button
              >
              <el-button type="primary" link size="small" @click="handleEdit(scope.row)"
                >编辑</el-button
              >
              <template v-if="showDeletedOnly">
                <el-button type="success" link size="small" @click="handleRestore(scope.row)"
                  >恢复</el-button
                >
                <el-button type="danger" link size="small" @click="handlePurge(scope.row)"
                  >彻底删除</el-button
                >
              </template>
              <el-popconfirm v-else title="确定删除该学校吗？" @confirm="handleDelete(scope.row)">
                <template #reference>
                  <el-button type="danger" link size="small">删除</el-button>
                </template>
              </el-popconfirm>
            </template>
          </el-table-column>
        </el-table>

        <div class="pagination-wrapper">
          <el-pagination
            v-model:current-page="currentPage"
            v-model:page-size="pageSize"
            :page-sizes="[10, 20, 50, 100]"
            :total="total"
            layout="total, sizes, prev, pager, next, jumper"
            @size-change="handleSizeChange"
            @current-change="handlePageChange"
          />
        </div>
      </template>
    </div>

    <!-- 导入对话框 -->
    <el-dialog
      v-model="showImportDialog"
      title="导入帮扶学校数据"
      :width="DIALOG_SM"
      destroy-on-close
    >
      <div class="import-dialog-body">
        <el-alert
          title="请先下载模板，按模板格式填写学校数据后上传"
          type="info"
          show-icon
          :closable="false"
          style="margin-bottom: 16px"
        />
        <el-upload
          ref="importUploadRef"
          :action="importUrl"
          :headers="uploadHeaders"
          :before-upload="beforeImportUpload"
          :on-success="onImportSuccess"
          :on-error="onImportError"
          :limit="1"
          accept=".xlsx,.xls"
          drag
        >
          <el-icon class="el-icon--upload"><Upload /></el-icon>
          <div class="el-upload__text">将 Excel 文件拖到此处，或 <em>点击上传</em></div>
          <template #tip>
            <div class="el-upload__tip">只支持 .xlsx / .xls 格式</div>
          </template>
        </el-upload>
      </div>
      <template #footer>
        <el-button @click="showImportDialog = false">关闭</el-button>
        <el-button type="success" plain @click="handleDownloadTemplate">下载模板</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import PageHeader from '@/components/common/PageHeader.vue'
import { DIALOG_SM } from '@/config/dialog'
import EmptyState from '@/components/business/EmptyState/EmptyState.vue'
import { logger } from '@/utils/logger'
import { getErrorMessage } from '@/utils/getErrorMessage'
import { AuthStorage } from '@/utils/authStorage'
import { useUploadHeaders } from '@/composables/useUploadHeaders'

import { ref, reactive, computed, onMounted, onActivated, onUnmounted, watch, nextTick } from 'vue'
import { useRouterSafe } from '@/composables/useRouterSafe'
import { useDesensitize } from '@/composables/useDesensitize'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Download, Upload, Search } from '@element-plus/icons-vue'
import { del, apiRequest } from '@/api/request'
import { schoolApi } from '@/api/schools'
import { restoreSchool, previewPurgeSchool, purgeSchool } from '@/api/schoolsRecycle'
import { useAuthStore } from '@/stores/auth'
import { downloadImportTemplateAndSave } from '@/api/import'
import echarts from '@/utils/echarts'

const { pushSafe } = useRouterSafe()
const { ds } = useDesensitize()
const tableData = ref<any[]>([])
const loading = ref(false)
const loadError = ref(false)
const loadErrorMsg = ref('')
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)

const showImportDialog = ref(false)
const importUploadRef = ref()
defineExpose({ importUploadRef })

const filterForm = reactive({
  keyword: '',
  type: '',
  status: '',
})

// 上传相关
const baseUrl = import.meta.env.VITE_API_BASE_URL || '/api/v1'
const importUrl = `${baseUrl}/schools/import/excel`
const { uploadHeaders } = useUploadHeaders()

const typeMap: Record<string, string> = {
  primary: '小学',
  middle: '初中',
  high: '高中',
  vocational: '职业学校',
  other: '其他',
}
const statusMap: Record<string, string> = {
  active: '帮扶中',
  inactive: '未帮扶',
  completed: '已完成',
}

// 统计数据（优先使用服务端全量统计，回退到当前页数据）
const serverSchoolStats = ref<any>(null)
const stats = computed(() => {
  const s = serverSchoolStats.value
  if (s) {
    return {
      total: s.total_schools ?? (total.value || tableData.value.length),
      active: s.active ?? 0,
      completed: s.completed ?? 0,
      totalStudents:
        s.total_students ??
        tableData.value.reduce(
          (sum: number, sc: any) => sum + (sc.student_count || sc.students || 0),
          0
        ),
      totalTeachers:
        s.total_teachers ??
        tableData.value.reduce(
          (sum: number, sc: any) => sum + (sc.teacher_count || sc.teachers || 0),
          0
        ),
    }
  }
  const list = tableData.value
  return {
    total: total.value || list.length,
    active: list.filter((s) => s.support_status === 'active').length,
    completed: list.filter((s) => s.support_status === 'completed').length,
    totalStudents: list.reduce((sum, s) => sum + (s.student_count || s.students || 0), 0),
    totalTeachers: list.reduce((sum, s) => sum + (s.teacher_count || s.teachers || 0), 0),
  }
})

// API 统计数据（助学兴教）
const apiStats = ref({
  project_count: 0,
  project_total_budget: 0,
  scholarship_count: 0,
  scholarship_total_amount: 0,
})
async function loadApiStats() {
  try {
    const data = await schoolApi.getStatistics()
    // 服务端返回的 total_schools/active/completed 是全量准确数据
    if (data) {
      apiStats.value = data
      serverSchoolStats.value = data
    }
  } catch (error) {
    logger.error('Failed to load API stats:', error)
    ElMessage.error('统计数据加载失败')
  }
}

function getStatusTagType(status: string) {
  if (status === 'active') return 'success'
  if (status === 'completed') return 'primary'
  return 'info'
}

// ========== 统计图表 ==========
const studentBarRef = ref<HTMLElement>()
const typePieRef = ref<HTMLElement>()
let studentBarChart: echarts.ECharts | null = null
let typePieChart: echarts.ECharts | null = null

function buildStudentBarOption(): echarts.EChartsCoreOption {
  const rows = tableData.value
    .map((s: any) => ({
      name: String(s.name || '-'),
      value: Number(s.student_count || s.students || 0),
    }))
    .sort((a: any, b: any) => b.value - a.value)
    .slice(0, 10)
  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: 'rgba(255,255,255,.96)',
      borderColor: '#e2e8f0',
      borderRadius: 8,
      textStyle: { color: '#1e293b', fontSize: 13 },
    },
    grid: { left: 8, right: 32, top: 8, bottom: 8, containLabel: true },
    xAxis: {
      type: 'value',
      axisLabel: { color: '#94a3b8', fontSize: 11 },
      splitLine: { lineStyle: { color: '#f1f5f9', type: 'dashed' } },
    },
    yAxis: {
      type: 'category',
      data: rows.map((r: any) => (r.name.length > 8 ? r.name.slice(0, 8) + '…' : r.name)).reverse(),
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#475569', fontSize: 12 },
    },
    series: [
      {
        name: '学生数',
        type: 'bar',
        data: rows.map((r: any) => r.value).reverse(),
        barWidth: 16,
        itemStyle: {
          borderRadius: [0, 6, 6, 0],
          color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
            { offset: 0, color: '#2d6a4f' },
            { offset: 1, color: '#52b788' },
          ]),
        },
        label: { show: true, position: 'right', color: '#64748b', fontSize: 11 },
      },
    ],
  }
}

function buildTypePieOption(): echarts.EChartsCoreOption {
  const counts: Record<string, number> = {}
  tableData.value.forEach((s: any) => {
    const key = String(s.type || 'other')
    counts[key] = (counts[key] || 0) + 1
  })
  const data = Object.entries(counts)
    .map(([key, value]) => ({ value, name: typeMap[key] || key }))
    .sort((a, b) => b.value - a.value)
  return {
    color: ['#2d6a4f', '#1e4d8c', '#f59e0b', '#52b788', '#94a3b8'],
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(255,255,255,.96)',
      borderColor: '#e2e8f0',
      borderRadius: 8,
      textStyle: { color: '#1e293b', fontSize: 13 },
      formatter: (p: any) => `${p.marker} ${p.name}: <b>${p.value}所</b> (${p.percent}%)`,
    },
    legend: { bottom: 0, textStyle: { color: '#64748b', fontSize: 11 } },
    series: [
      {
        name: '学校类型',
        type: 'pie',
        radius: ['45%', '70%'],
        center: ['50%', '46%'],
        itemStyle: { borderRadius: 4, borderColor: '#fff', borderWidth: 3 },
        label: { show: false },
        emphasis: { itemStyle: { shadowBlur: 16, shadowColor: 'rgba(0,0,0,.12)' } },
        data,
      },
    ],
  }
}

function renderCharts() {
  studentBarChart?.dispose()
  studentBarChart = null
  typePieChart?.dispose()
  typePieChart = null
  if (studentBarRef.value) {
    studentBarChart = echarts.init(studentBarRef.value)
    studentBarChart.setOption(buildStudentBarOption())
  }
  if (typePieRef.value) {
    typePieChart = echarts.init(typePieRef.value)
    typePieChart.setOption(buildTypePieOption())
  }
}

function handleChartResize() {
  studentBarChart?.resize()
  typePieChart?.resize()
}

// 表格数据变化（加载/筛选/翻页）时重绘图表
watch(tableData, () => {
  nextTick(renderCharts)
})

async function fetchData() {
  loading.value = true
  loadError.value = false
  loadErrorMsg.value = ''
  try {
    const response = await apiRequest({
      method: 'GET',
      url: '/schools',
      params: {
        page: currentPage.value,
        page_size: pageSize.value,
        keyword: filterForm.keyword || undefined,
        type: filterForm.type || undefined,
        support_status: filterForm.status || undefined,
      },
    })
    const res: any = response
    // 防御：信封保留 data 键，裸分页对象直接使用
    const inner = res?.data ?? res
    tableData.value = inner?.items ?? (Array.isArray(inner) ? inner : [])
    total.value = inner?.total ?? tableData.value.length
  } catch (e) {
    logger.error('加载数据失败:', e)
    tableData.value = [] // 防御：确保表格数据始终为数组，避免 Element Plus TypeError: e is not iterable
    total.value = 0
    loadError.value = true
    // 内联错误态展示真实原因（不再弹全局提示）
    loadErrorMsg.value = getErrorMessage(e, '数据加载失败，请稍后重试')
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  currentPage.value = 1
  fetchData()
}
function handleReset() {
  filterForm.keyword = ''
  filterForm.type = ''
  filterForm.status = ''
  currentPage.value = 1
  fetchData()
}
function filterByStatus(status: string) {
  filterForm.status = status
  currentPage.value = 1
  fetchData()
}
function handleSizeChange() {
  currentPage.value = 1
  fetchData()
}
function handlePageChange() {
  fetchData()
}
function handleCreate() {
  pushSafe('/schools/create')
}
function handleView(row: any) {
  if (!row?.id) return
  pushSafe(`/schools/${row.id}`)
}
function handleEdit(row: any) {
  if (!row?.id) return
  pushSafe(`/schools/${row.id}/edit`)
}
async function handleDelete(row: any) {
  if (!row?.id) return
  try {
    await del(`/schools/${row.id}`)
    // 成功静默：删除成功仅刷新列表
    currentPage.value = 1 // 重置到第1页，确保新建/编辑后的数据可见
    fetchData()
  } catch (error) {
    logger.error('Failed to delete school:', error)
  }
}
// 下载模板（自动解析后端 Content-Disposition 文件名，避免浏览器误用 "UTF-8"）
async function handleDownloadTemplate() {
  try {
    await downloadImportTemplateAndSave('school', '学校')
    // 模板下载成功 — 浏览器已确认
  } catch {
    ElMessage.error('模板下载失败，请重试')
  }
}

// 导入相关
function beforeImportUpload(file: any) {
  const isExcel = file.name.endsWith('.xlsx') || file.name.endsWith('.xls')
  if (!isExcel) {
    ElMessage.error('只能上传 Excel 文件')
    return false
  }
  if (file.size > 10 * 1024 * 1024) {
    ElMessage.error('文件大小不能超过 10MB')
    return false
  }
  return true
}

function onImportSuccess(response: any) {
  // 信封兼容：{code,data,message} 或裸数据
  const body = response?.data ?? response ?? {}
  const payload = body?.data ?? body
  const msg = payload?.message || body?.message || `成功导入 ${payload?.imported || 0} 所学校`
  ElMessage.success(msg)
  const importErrors = payload?.errors ?? body?.errors ?? []
  if (importErrors.length) {
    const detail = importErrors
      .slice(0, 10)
      .map((e: any, i: number) => {
        const row = e?.row ?? e?.row_index ?? i + 1
        const m = e?.error ?? e?.message ?? JSON.stringify(e)
        return `${i + 1}. 第 ${row} 行：${m}`
      })
      .join('<br/>')
    const more = importErrors.length > 10 ? `<br/>… 共 ${importErrors.length} 条失败` : ''
    ElMessageBox.alert(detail + more, '导入失败明细', {
      dangerouslyUseHTMLString: true,
      type: 'warning',
      confirmButtonText: '知道了',
    })
  }
  showImportDialog.value = false
  currentPage.value = 1 // 重置到第1页，确保新建/编辑后的数据可见
  fetchData()
}

function onImportError() {
  ElMessage.error('导入失败，请检查文件格式')
}

// 导出
async function handleExport() {
  ElMessage.success('正在导出学校数据...')
  try {
    const token = AuthStorage.getToken() || ''
    const resp = await fetch(`${baseUrl}/schools/export/excel`, {
      headers: { Authorization: token ? `Bearer ${token}` : '' },
    })
    if (!resp.ok) throw new Error('export failed')
    const blob = await resp.blob()
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'schools.xlsx'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
    // 导出成功 — 浏览器已确认
  } catch {
    ElMessage.error('导出失败')
  }
}

onMounted(() => {
  fetchData()
  loadApiStats()
  window.addEventListener('resize', handleChartResize)
})

// 页面激活时刷新数据（解决keep-alive缓存问题）
onActivated(() => {
  fetchData()
  loadApiStats()
  // keep-alive 恢复后容器尺寸可能变化，重绘图表
  nextTick(handleChartResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleChartResize)
  studentBarChart?.dispose()
  studentBarChart = null
  typePieChart?.dispose()
  typePieChart = null
})

// ── 回收站（Phase C 推广）──
const authStore = useAuthStore()
const canViewDeleted = computed(() => authStore.canViewDeleted)
const showDeletedOnly = ref(false)

async function handleToggleDeleted() {
  currentPage.value = 1
  await fetchData()
}

async function handleRestore(row: any) {
  try {
    await ElMessageBox.confirm(`确定恢复学校【${row.name}】吗？`, '恢复确认', {
      confirmButtonText: '确认恢复',
      cancelButtonText: '取消',
      type: 'info',
    })
  } catch {
    return
  }
  try {
    await restoreSchool(row.id)
    ElMessage.success('恢复成功')
    fetchData()
  } catch {
    ElMessage.error('恢复失败')
  }
}

async function handlePurge(row: any) {
  let totalRefs = 0
  try {
    const pv: any = await previewPurgeSchool(row.id)
    totalRefs = Number((pv?.data || pv)?.total_references || 0)
  } catch {
    // 预览失败不阻断流程
  }
  try {
    await ElMessageBox.confirm(
      `彻底删除后【${row.name}】及其关联的 ${totalRefs} 条数据将无法恢复！不可撤销。`,
      '彻底删除警告',
      { confirmButtonText: '继续', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }
  let confirmPassword = ''
  try {
    const r = await ElMessageBox.prompt(
      `彻底删除【${row.name}】需二次确认，请输入登录密码：`,
      '二次确认',
      {
        confirmButtonText: '确认彻底删除',
        inputType: 'password',
        inputValidator: (v: string) => (v ? true : '密码不能为空'),
      }
    )
    confirmPassword = r.value || ''
  } catch {
    return
  }
  loading.value = true
  try {
    const res: any = await purgeSchool(row.id, confirmPassword)
    ElMessage.success(res?.data?.message || `已清理 ${res?.data?.deleted_records ?? 0} 条关联数据`)
    fetchData()
  } catch {
    ElMessage.error('彻底删除失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.school-mgmt-list-page {
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
  color: var(--color-primary-dark-1);
}

.page-desc {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--color-text-secondary);
}

.header-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.import-dialog-body {
  padding: 0 10px;
}

/* 统计卡片 */
.stats-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-md);
  margin-bottom: 20px;
}

.stat-item {
  flex: 1 1 140px;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-lighter);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  padding: var(--spacing-md) var(--spacing-lg);
  text-align: center;
  transition: all 0.3s;
}

.stat-item.clickable {
  cursor: pointer;
}

.stat-item.clickable:hover {
  border-color: var(--color-primary);
  box-shadow: var(--shadow-md);
}

.stat-item.clickable:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--color-text-primary);
  line-height: 1.2;
}

.stat-label {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin-top: 4px;
}

.text-success {
  color: var(--color-success);
}
.text-primary {
  color: var(--color-primary);
}
.text-warning {
  color: var(--color-warning);
}
.text-info {
  color: var(--color-info);
}
.text-project {
  color: var(--color-primary);
}
.text-scholarship {
  color: var(--color-accent-gold);
}

/* 统计图表 */
.charts-row {
  margin-bottom: 20px;
}

.chart-card {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-lighter);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  padding: var(--spacing-md) var(--spacing-lg);
  margin-bottom: var(--spacing-md);
}

.chart-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 0 0 12px 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.chart-title::before {
  content: '';
  display: inline-block;
  width: 4px;
  height: 16px;
  border-radius: 2px;
  background: var(--color-primary);
}

.chart-body {
  width: 100%;
  height: 260px;
}

/* 筛选区 */
.filter-card {
  background: white;
  border-radius: 8px;
  padding: 16px 20px 4px;
  margin-bottom: 20px;
  border: 1px solid var(--color-border-light);
}

/* 表格区 */
.table-card {
  background: white;
  border-radius: 8px;
  padding: 20px;
  border: 1px solid var(--color-border-light);
}

.pagination-wrapper {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
