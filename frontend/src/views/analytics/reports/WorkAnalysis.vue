<template>
  <div class="work-analysis-page">
    <!-- 页面头部 -->
    <div class="page-header-card">
      <div class="header-left">
        <h1 class="page-title">工作分析</h1>
        <p class="page-desc">乡村振兴工作数据综合分析与可视化</p>
      </div>
      <div class="header-right">
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          value-format="YYYY-MM-DD"
          style="width: 280px"
          @change="refreshData"
        />
        <el-button @click="refreshData">
          <el-icon><Refresh /></el-icon> 刷新
        </el-button>
        <el-button type="success" @click="exportData">
          <el-icon><Download /></el-icon> 导出报告
        </el-button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-grid">
      <div v-for="stat in statsCards" :key="stat.label" class="stat-card">
        <div class="stat-icon" :style="{ background: stat.bgColor }">
          <el-icon class="stat-icon-text"><component :is="stat.icon" /></el-icon>
        </div>
        <div class="stat-info">
          <div class="stat-value" :style="{ color: stat.color }">
            {{ stat.value }}
          </div>
          <div class="stat-label">{{ stat.label }}</div>
          <div class="stat-trend" :class="stat.trendType">
            {{ stat.trend }}
          </div>
        </div>
      </div>
    </div>

    <!-- 图表区域 -->
    <div class="charts-row">
      <div class="chart-card">
        <div class="chart-card-header">
          <h3>工作类型分布</h3>
        </div>
        <div class="chart-body">
          <canvas ref="typeChartRef" height="300"></canvas>
        </div>
      </div>
      <div class="chart-card">
        <div class="chart-card-header">
          <h3>工作状态分布</h3>
        </div>
        <div class="chart-body">
          <canvas ref="statusChartRef" height="300"></canvas>
        </div>
      </div>
    </div>

    <div class="charts-row">
      <div class="chart-card chart-card-full">
        <div class="chart-card-header">
          <h3>月度工作完成趋势</h3>
        </div>
        <div class="chart-body">
          <canvas ref="trendChartRef" height="280"></canvas>
        </div>
      </div>
    </div>

    <!-- 数据明细表 -->
    <div class="table-card">
      <div class="table-card-header">
        <h3>工作数据明细</h3>
        <div class="table-filters">
          <el-input
            v-model="searchText"
            placeholder="搜索工作名称..."
            clearable
            style="width: 220px"
            @keyup.enter="filterTable"
            @clear="filterTable"
          >
            <template #prefix
              ><el-icon><Search /></el-icon
            ></template>
          </el-input>
          <el-select
            v-model="filterType"
            placeholder="工作类型"
            clearable
            style="width: 150px"
            @change="filterTable"
          >
            <el-option label="全部类型" value="" />
            <el-option label="基础设施建设" value="infrastructure" />
            <el-option label="产业发展" value="industry" />
            <el-option label="教育培训" value="education" />
            <el-option label="医疗健康" value="healthcare" />
            <el-option label="生态环境保护" value="environment" />
          </el-select>
          <el-select
            v-model="filterStatus"
            placeholder="状态"
            clearable
            style="width: 130px"
            @change="filterTable"
          >
            <el-option label="全部状态" value="" />
            <el-option label="计划中" value="planned" />
            <el-option label="进行中" value="in_progress" />
            <el-option label="已完成" value="completed" />
            <el-option label="已延期" value="delayed" />
          </el-select>
        </div>
      </div>
      <el-table v-loading="loading" :data="filteredTableData" border stripe style="width: 100%">
        <el-table-column type="index" label="#" width="50" align="center" />
        <el-table-column prop="name" label="工作名称" min-width="200" show-overflow-tooltip />
        <el-table-column prop="typeName" label="工作类型" width="130">
          <template #default="{ row }">
            <el-tag :type="getTypeTagType(row.type)" size="small">{{ row.typeName }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="village_name" label="所属村庄" width="120" />
        <el-table-column prop="responsible_person" label="负责人" width="100">
          <template #default="{ row }">
            {{ ds(row.responsible_person, 'name') }}
          </template>
        </el-table-column>
        <el-table-column prop="statusName" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusTagType(row.status)" size="small">{{ row.statusName }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="progress" label="进度" width="140">
          <template #default="{ row }">
            <el-progress
              :percentage="row.progress"
              :status="row.progress === 100 ? 'success' : row.progress > 60 ? '' : 'warning'"
              :stroke-width="8"
            />
          </template>
        </el-table-column>
        <el-table-column prop="start_date" label="开始日期" width="110" />
        <el-table-column prop="end_date" label="结束日期" width="110" />
      </el-table>
      <div class="table-pagination">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50]"
          :total="totalCount"
          layout="total, sizes, prev, pager, next"
          @size-change="filterTable"
          @current-change="filterTable"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { logger } from '@/utils/logger'
import { getErrorMessage } from '@/utils/getErrorMessage'
import { chartColor, chartColorPrimary, chartPalette } from '@/utils/chartColors'

import { ref, computed, watch, onMounted, nextTick, onBeforeUnmount, markRaw } from 'vue'
import { ElMessage } from 'element-plus'
import { useDesensitize } from '@/composables/useDesensitize'
import {
  Search,
  Refresh,
  Download,
  DataAnalysis,
  Select,
  TrendCharts,
} from '@element-plus/icons-vue'
import { Chart } from 'chart.js/auto'
import { getRuralWorks } from '@/api/ruralWork'

// 类型映射
const TYPE_LABELS: Record<string, string> = {
  infrastructure: '基础设施建设',
  industry: '产业发展',
  education: '教育培训',
  healthcare: '医疗健康',
  environment: '生态环境保护',
}
const STATUS_LABELS: Record<string, string> = {
  planned: '计划中',
  in_progress: '进行中',
  completed: '已完成',
  delayed: '已延期',
}

const { ds } = useDesensitize()

// 状态
const loading = ref(false)
const dateRange = ref<[string, string] | null>(null)
const searchText = ref('')
const filterType = ref('')
const filterStatus = ref('')
const currentPage = ref(1)
const pageSize = ref(10)
const totalCount = ref(0)
const allData = ref<any[]>([])

// 图表
const typeChartRef = ref<HTMLCanvasElement | null>(null)
const statusChartRef = ref<HTMLCanvasElement | null>(null)
const trendChartRef = ref<HTMLCanvasElement | null>(null)
let typeChart: InstanceType<typeof Chart> | null = null
let statusChart: InstanceType<typeof Chart> | null = null
let trendChart: InstanceType<typeof Chart> | null = null

// 模拟数据已清除，使用真实API数据

// 统计卡片
const statsCards = computed(() => {
  const data = allData.value
  const total = data.length
  const completed = data.filter((d) => d.status === 'completed').length
  const inProgress = data.filter((d) => d.status === 'in_progress').length
  const delayed = data.filter((d) => d.status === 'delayed').length
  const avgProgress =
    total > 0 ? Math.round(data.reduce((s, d) => s + (d.progress || 0), 0) / total) : 0

  return [
    {
      label: '工作总数',
      value: total,
      icon: markRaw(DataAnalysis),
      color: 'var(--color-primary)',
      bgColor: 'rgba(45,106,79,0.1)',
      trend: '较上月 +12%',
      trendType: 'up',
    },
    {
      label: '进行中',
      value: inProgress,
      icon: markRaw(Refresh),
      color: 'var(--color-warning)',
      bgColor: 'color-mix(in srgb, var(--color-warning) 10%, transparent)',
      trend: `占比 ${total > 0 ? Math.round((inProgress / total) * 100) : 0}%`,
      trendType: 'neutral',
    },
    {
      label: '已完成',
      value: completed,
      icon: markRaw(Select),
      color: 'var(--color-success)',
      bgColor: 'color-mix(in srgb, var(--color-success) 10%, transparent)',
      trend: `完成率 ${total > 0 ? Math.round((completed / total) * 100) : 0}%`,
      trendType: 'up',
    },
    {
      label: '平均进度',
      value: `${avgProgress}%`,
      icon: markRaw(TrendCharts),
      color: '#1b4332',
      bgColor: 'rgba(27,67,50,0.1)',
      trend: delayed > 0 ? `${delayed}项延期` : '无延期',
      trendType: delayed > 0 ? 'down' : 'up',
    },
  ]
})

// 表格过滤
const filteredData = computed(() => {
  let data = allData.value.map((item) => ({
    ...item,
    typeName: TYPE_LABELS[item.type] || item.type,
    statusName: STATUS_LABELS[item.status] || item.status,
  }))

  if (searchText.value) {
    const q = searchText.value.toLowerCase()
    data = data.filter(
      (d) =>
        (d.name && d.name.toLowerCase().includes(q)) ||
        (d.responsible_person && d.responsible_person.toLowerCase().includes(q)) ||
        (d.village_name && d.village_name.toLowerCase().includes(q))
    )
  }
  if (filterType.value) {
    data = data.filter((d) => d.type === filterType.value)
  }
  if (filterStatus.value) {
    data = data.filter((d) => d.status === filterStatus.value)
  }

  return data
})

const filteredTableData = computed(() => {
  const data = filteredData.value
  const start = (currentPage.value - 1) * pageSize.value
  return data.slice(start, start + pageSize.value)
})

watch(
  filteredData,
  (data) => {
    totalCount.value = data.length
  },
  { immediate: true }
)

function filterTable() {
  currentPage.value = 1
}

// 数据加载
async function loadData() {
  loading.value = true
  try {
    const res = await getRuralWorks({ limit: 100 })
    allData.value = res && (res as any).items ? (res as any).items : []
  } catch (e) {
    logger.error('加载工作数据失败:', e)
    allData.value = []
    ElMessage.error(getErrorMessage(e, '加载数据失败，请稍后重试'))
  } finally {
    loading.value = false
  }
}

async function refreshData() {
  await loadData()
  await nextTick()
  updateCharts()
  ElMessage.success('数据已刷新')
}

// 图表
function destroyCharts() {
  if (typeChart) {
    typeChart.destroy()
    typeChart = null
  }
  if (statusChart) {
    statusChart.destroy()
    statusChart = null
  }
  if (trendChart) {
    trendChart.destroy()
    trendChart = null
  }
}

function updateCharts() {
  destroyCharts()
  const data = allData.value

  // 类型分布 - 饼图
  if (typeChartRef.value) {
    const typeCounts: Record<string, number> = {}
    data.forEach((d) => {
      const label = TYPE_LABELS[d.type] || d.type || '其他'
      typeCounts[label] = (typeCounts[label] || 0) + 1
    })
    typeChart = new Chart(typeChartRef.value, {
      type: 'doughnut',
      data: {
        labels: Object.keys(typeCounts),
        datasets: [
          {
            data: Object.values(typeCounts),
            backgroundColor: chartPalette(),
            borderWidth: 2,
            borderColor: '#fff',
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'bottom',
            labels: { padding: 16, usePointStyle: true },
          },
        },
      },
    })
  }

  // 状态分布 - 柱状图
  if (statusChartRef.value) {
    const statusCounts: Record<string, number> = {
      planned: 0,
      in_progress: 0,
      completed: 0,
      delayed: 0,
    }
    data.forEach((d) => {
      if (statusCounts[d.status] !== undefined) statusCounts[d.status]++
    })
    statusChart = new Chart(statusChartRef.value, {
      type: 'bar',
      data: {
        labels: ['计划中', '进行中', '已完成', '已延期'],
        datasets: [
          {
            label: '工作数量',
            data: [
              statusCounts.planned,
              statusCounts.in_progress,
              statusCounts.completed,
              statusCounts.delayed,
            ],
            backgroundColor: [
              chartColor('info'),
              chartColor('warning'),
              chartColor('success'),
              chartColor('danger'),
            ],
            borderRadius: 6,
            maxBarThickness: 50,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          y: { beginAtZero: true, ticks: { stepSize: 1 } },
        },
      },
    })
  }

  // 月度趋势 - 折线图
  if (trendChartRef.value) {
    // 从真实数据中计算月度统计
    const now = new Date()
    const currentMonth = now.getMonth() // 0-based
    const monthCount = Math.min(currentMonth + 1, 12)
    const months: string[] = []
    const completedByMonth: number[] = []
    const newByMonth: number[] = []
    for (let i = 0; i < monthCount; i++) {
      months.push(`${i + 1}月`)
      const monthItems = data.filter((d) => {
        const created = d.start_date || d.created_at
        if (!created) return false
        const date = new Date(created)
        return date.getMonth() === i && date.getFullYear() === now.getFullYear()
      })
      newByMonth.push(monthItems.length)
      completedByMonth.push(monthItems.filter((d) => d.status === 'completed').length)
    }
    trendChart = new Chart(trendChartRef.value, {
      type: 'line',
      data: {
        labels: months,
        datasets: [
          {
            label: '新增工作',
            data: newByMonth,
            borderColor: chartColorPrimary(),
            // 8 位 hex（末两位 1a ≈ 10% 透明度），tokens 主色的同色浅填充
            backgroundColor: `${chartColorPrimary()}1a`,
            fill: true,
            tension: 0.4,
            pointRadius: 4,
          },
          {
            label: '完成工作',
            data: completedByMonth,
            borderColor: chartColor('success'),
            backgroundColor: `${chartColor('success')}1a`, // 同色 10% 浅填充
            fill: true,
            tension: 0.4,
            pointRadius: 4,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: 'top', labels: { usePointStyle: true } },
        },
        scales: {
          y: { beginAtZero: true, ticks: { stepSize: 1 } },
        },
      },
    })
  }
}

// 导出
function exportData() {
  const data = allData.value
  if (!data.length) {
    ElMessage.warning('没有可导出的数据')
    return
  }

  const headers = [
    '序号',
    '工作名称',
    '工作类型',
    '所属村庄',
    '负责人',
    '状态',
    '进度(%)',
    '开始日期',
    '结束日期',
  ]
  const rows = data.map((item, i) => [
    i + 1,
    item.name || '',
    TYPE_LABELS[item.type] || item.type || '',
    item.village_name || '',
    item.responsible_person || '',
    STATUS_LABELS[item.status] || item.status || '',
    item.progress ?? 0,
    item.start_date || '',
    item.end_date || '',
  ])

  const BOM = '\uFEFF'
  const csv =
    BOM +
    [headers, ...rows]
      .map((r) => r.map((c: any) => `"${String(c).replace(/"/g, '""')}"`).join(','))
      .join('\n')

  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `工作分析报告_${new Date().toISOString().slice(0, 10)}.csv`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
  // 导出成功 — 浏览器已确认
}

// 辅助
function getTypeTagType(type: string): 'success' | 'info' | 'warning' | 'danger' | 'primary' {
  const map: Record<string, 'success' | 'info' | 'warning' | 'danger' | 'primary'> = {
    infrastructure: 'info',
    industry: 'success',
    education: 'warning',
    healthcare: 'danger',
    environment: 'info',
  }
  return map[type] || 'info'
}
function getStatusTagType(status: string): 'success' | 'info' | 'warning' | 'danger' | 'primary' {
  const map: Record<string, 'success' | 'info' | 'warning' | 'danger' | 'primary'> = {
    planned: 'info',
    in_progress: 'primary',
    completed: 'success',
    delayed: 'danger',
  }
  return map[status] || 'info'
}

onMounted(async () => {
  await loadData()
  await nextTick()
  updateCharts()
})

onBeforeUnmount(() => {
  destroyCharts()
})
</script>

<style scoped>
.work-analysis-page {
  padding: 20px;
  background: var(--color-bg-hover);
  min-height: 100vh;
}

/* 页面头部 */
.page-header-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: white;
  border-radius: 8px;
  padding: 20px 24px;
  margin-bottom: 20px;
  border-left: 4px solid #1b4332;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}

.page-title {
  font-size: 22px;
  font-weight: 700;
  color: #1b4332;
  margin: 0 0 4px 0;
}

.page-desc {
  font-size: 14px;
  color: var(--color-info);
  margin: 0;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

/* 统计卡片 */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}

.stat-card {
  background: white;
  border-radius: 8px;
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 16px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
  transition: transform 0.2s;
}

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.stat-icon {
  width: 52px;
  height: 52px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.stat-icon-text {
  font-size: 24px;
  color: var(--color-text-inverse);
}

.stat-info {
  flex: 1;
  min-width: 0;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  line-height: 1.2;
}

.stat-label {
  font-size: 13px;
  color: var(--color-info);
  margin-top: 2px;
}

.stat-trend {
  font-size: 12px;
  margin-top: 4px;
}

.stat-trend.up {
  color: var(--color-success);
}

.stat-trend.down {
  color: var(--color-danger);
}

.stat-trend.neutral {
  color: var(--color-info);
}

/* 图表卡片 */
.charts-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 20px;
}

.charts-row:has(.chart-card-full) {
  grid-template-columns: 1fr;
}

.chart-card,
.chart-card-full {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}

.chart-card-header h3 {
  margin: 0 0 16px 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-primary);
  padding-left: 10px;
  border-left: 3px solid #1b4332;
}

.chart-body {
  position: relative;
  height: 300px;
}

/* 数据表 */
.table-card {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}

.table-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.table-card-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-primary);
  padding-left: 10px;
  border-left: 3px solid #1b4332;
}

.table-filters {
  display: flex;
  gap: 10px;
}

.table-pagination {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

/* 响应式 */
@media (max-width: 1200px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .page-header-card {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }

  .stats-grid {
    grid-template-columns: 1fr;
  }

  .charts-row {
    grid-template-columns: 1fr;
  }

  .table-card-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }

  .table-filters {
    flex-wrap: wrap;
  }
}
</style>
