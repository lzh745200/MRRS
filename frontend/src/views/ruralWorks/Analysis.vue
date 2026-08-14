<template>
  <div class="rural-works-analysis">
    <!-- 页面头部 -->
    <div class="page-header military-border">
      <h1 class="page-title military-title">乡村振兴工作分析</h1>
      <p class="page-subtitle military-subtitle">深度分析乡村振兴工作数据，为决策提供科学依据</p>
      <div class="decoration-line military-decoration"></div>
    </div>

    <!-- 筛选和控制区域 -->
    <div class="filter-control-section military-card">
      <div class="filter-row">
        <el-select
          v-model="timeRange"
          placeholder="选择时间范围"
          class="time-range-select"
          @change="handleTimeRangeChange"
        >
          <el-option label="近30天" value="30" />
          <el-option label="近90天" value="90" />
          <el-option label="近半年" value="180" />
          <el-option label="近一年" value="365" />
          <el-option label="全部" value="all" />
        </el-select>
        <el-select
          v-model="selectedVillage"
          placeholder="选择村庄"
          clearable
          class="village-select"
          @change="handleVillageChange"
        >
          <el-option label="全部村庄" value="" />
          <el-option v-for="village in villages" :key="village" :label="village" :value="village" />
        </el-select>
        <el-select
          v-model="selectedType"
          placeholder="选择工作类型"
          clearable
          class="type-select"
          @change="handleTypeChange"
        >
          <el-option label="全部类型" value="" />
          <el-option label="基础设施建设" value="infrastructure" />
          <el-option label="产业发展" value="industry" />
          <el-option label="教育培训" value="education" />
          <el-option label="医疗健康" value="healthcare" />
          <el-option label="生态环境保护" value="environment" />
        </el-select>
        <div class="right-controls">
          <el-button class="refresh-button" @click="refreshData">
            <el-icon><Refresh /></el-icon> 刷新数据
          </el-button>
          <el-button class="export-button" @click="exportAnalysis">
            <el-icon><Download /></el-icon> 导出分析报告
          </el-button>
        </div>
      </div>
    </div>

    <!-- 核心指标卡片 -->
    <div class="key-indicators">
      <div class="indicator-card military-card">
        <div class="indicator-header">
          <span class="indicator-title">总工作量</span>
          <span class="indicator-icon" style="background-color: var(--color-primary)">
            <el-icon><Document /></el-icon>
          </span>
        </div>
        <div class="indicator-content">
          <div class="indicator-value">{{ totalWorks }}</div>
          <div
            class="indicator-change"
            :class="{
              positive: totalWorksChange > 0,
              negative: totalWorksChange < 0,
            }"
          >
            {{ totalWorksChange > 0 ? '+' : '' }}{{ totalWorksChange }}%
          </div>
        </div>
        <div class="indicator-description">较上期相比</div>
      </div>
      <div class="indicator-card military-card">
        <div class="indicator-header">
          <span class="indicator-title">平均完成率</span>
          <span class="indicator-icon" style="background-color: #67c23a">
            <el-icon><Select /></el-icon>
          </span>
        </div>
        <div class="indicator-content">
          <div class="indicator-value">{{ averageCompletionRate }}%</div>
          <div
            class="indicator-change"
            :class="{
              positive: completionRateChange > 0,
              negative: completionRateChange < 0,
            }"
          >
            {{ completionRateChange > 0 ? '+' : '' }}{{ completionRateChange }}%
          </div>
        </div>
        <div class="indicator-description">较上期相比</div>
      </div>
      <div class="indicator-card military-card">
        <div class="indicator-header">
          <span class="indicator-title">平均延期率</span>
          <span class="indicator-icon" style="background-color: #f56c6c">
            <el-icon><Warning /></el-icon>
          </span>
        </div>
        <div class="indicator-content">
          <div class="indicator-value">{{ averageDelayRate }}%</div>
          <div
            class="indicator-change"
            :class="{
              positive: delayRateChange < 0,
              negative: delayRateChange > 0,
            }"
          >
            {{ delayRateChange > 0 ? '+' : '' }}{{ delayRateChange }}%
          </div>
        </div>
        <div class="indicator-description">较上期相比</div>
      </div>
      <div class="indicator-card military-card">
        <div class="indicator-header">
          <span class="indicator-title">总投入资金</span>
          <span class="indicator-icon" style="background-color: #e6a23c">
            <el-icon><Money /></el-icon>
          </span>
        </div>
        <div class="indicator-content">
          <div class="indicator-value">{{ totalInvestment }}万元</div>
          <div
            class="indicator-change"
            :class="{
              positive: investmentChange > 0,
              negative: investmentChange < 0,
            }"
          >
            {{ investmentChange > 0 ? '+' : '' }}{{ investmentChange }}%
          </div>
        </div>
        <div class="indicator-description">较上期相比</div>
      </div>
    </div>

    <!-- 图表区域 - 第一行 -->
    <div class="charts-row">
      <div class="chart-card military-card">
        <div class="chart-header">
          <h3 class="chart-title">工作类型分布</h3>
          <el-dropdown @command="handleTypeChartView">
            <span class="chart-view-trigger">
              视图 <el-icon class="el-icon--right"><ArrowDown /></el-icon>
            </span>
            <el-dropdown-menu>
              <el-dropdown-item command="pie">饼图</el-dropdown-item>
              <el-dropdown-item command="bar">柱状图</el-dropdown-item>
            </el-dropdown-menu>
          </el-dropdown>
        </div>
        <div class="chart-content">
          <div v-if="typeChartView === 'pie'" class="chart-container">
            <canvas ref="typePieChart" height="300"></canvas>
          </div>
          <div v-else class="chart-container">
            <canvas ref="typeBarChart" height="300"></canvas>
          </div>
        </div>
      </div>
      <div class="chart-card military-card">
        <div class="chart-header">
          <h3 class="chart-title">工作状态分布</h3>
          <el-dropdown @command="handleStatusChartView">
            <span class="chart-view-trigger">
              视图 <el-icon class="el-icon--right"><ArrowDown /></el-icon>
            </span>
            <el-dropdown-menu>
              <el-dropdown-item command="doughnut">环形图</el-dropdown-item>
              <el-dropdown-item command="bar">柱状图</el-dropdown-item>
            </el-dropdown-menu>
          </el-dropdown>
        </div>
        <div class="chart-content">
          <div v-if="statusChartView === 'doughnut'" class="chart-container">
            <canvas ref="statusDoughnutChart" height="300"></canvas>
          </div>
          <div v-else class="chart-container">
            <canvas ref="statusBarChart" height="300"></canvas>
          </div>
        </div>
      </div>
    </div>

    <!-- 图表区域 - 第二行 -->
    <div class="charts-row">
      <div class="chart-card military-card full-width">
        <div class="chart-header">
          <h3 class="chart-title">工作量趋势图</h3>
          <el-select v-model="trendType" placeholder="选择趋势类型" @change="updateTrendChart">
            <el-option label="按工作数量" value="count" />
            <el-option label="按完成率" value="completion" />
            <el-option label="按投入资金" value="investment" />
          </el-select>
        </div>
        <div class="chart-content">
          <canvas ref="trendChart" height="400"></canvas>
        </div>
      </div>
    </div>

    <!-- 图表区域 - 第三行 -->
    <div class="charts-row">
      <div class="chart-card military-card">
        <div class="chart-header">
          <h3 class="chart-title">村庄工作量排名</h3>
        </div>
        <div class="chart-content">
          <canvas ref="villageRankingChart" height="350"></canvas>
        </div>
      </div>
      <div class="chart-card military-card">
        <div class="chart-header">
          <h3 class="chart-title">工作完成质量分析</h3>
        </div>
        <div class="chart-content">
          <canvas ref="qualityAnalysisChart" height="350"></canvas>
        </div>
      </div>
    </div>

    <!-- 详细数据表格 -->
    <div class="data-table-section military-card">
      <div class="table-header">
        <h3 class="table-title">详细工作数据分析</h3>
        <el-select v-model="dataTableSort" placeholder="排序方式" @change="updateDataTable">
          <el-option label="按完成率排序" value="completion" />
          <el-option label="按开始日期排序" value="startDate" />
          <el-option label="按投入资金排序" value="investment" />
        </el-select>
      </div>
      <el-table v-loading="loading" :data="sortedAnalysisData" border stripe style="width: 100%">
        <el-table-column prop="workName" label="工作名称" min-width="200" />
        <el-table-column prop="village" label="所属村庄" width="120" />
        <el-table-column prop="type" label="工作类型" width="120">
          <template #default="scope">
            <el-tag :type="getTypeTagType(scope.row.type)">{{ scope.row.type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="scope">
            <el-tag :type="getStatusTagType(scope.row.status)">{{ scope.row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="completionRate" label="完成率" width="100">
          <template #default="scope">
            <el-progress
              :percentage="scope.row.completionRate"
              :status="getProgressStatus(scope.row.completionRate)"
              :stroke-width="8"
            />
          </template>
        </el-table-column>
        <el-table-column prop="investment" label="投入资金(万元)" width="120" />
        <el-table-column prop="startDate" label="开始日期" width="120" />
        <el-table-column prop="endDate" label="结束日期" width="120" />
        <el-table-column prop="qualityScore" label="质量评分" width="100">
          <template #default="scope">
            <div class="quality-score" :class="getQualityScoreClass(scope.row.qualityScore)">
              {{ scope.row.qualityScore }}
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 装饰元素 -->
    <div class="military-decoration-corner corner-top-left"></div>
    <div class="military-decoration-corner corner-top-right"></div>
    <div class="military-decoration-corner corner-bottom-left"></div>
    <div class="military-decoration-corner corner-bottom-right"></div>
  </div>
</template>

<script lang="ts" setup>
import { logger } from '@/utils/logger'
import { getErrorMessage } from '@/utils/getErrorMessage'
import { chartColor, chartColorPrimary, chartPalette } from '@/utils/chartColors'

import { ref, onMounted, nextTick, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Refresh,
  Download,
  Document,
  Select,
  Warning,
  Money,
  ArrowDown,
} from '@element-plus/icons-vue'
// 导入Chart.js组件 - Chart.js 4.x使用auto版本自动注册所有组件
import { Chart } from 'chart.js/auto'
import { getRuralWorks } from '@/api/ruralWork'

// 定义Chart实例类型
type ChartInstance = InstanceType<typeof Chart> | null

// 状态管理
const loading = ref(false)
const timeRange = ref('90')
const selectedVillage = ref('')
const selectedType = ref('')
const typeChartView = ref('pie')
const statusChartView = ref('doughnut')
const trendType = ref('count')
const dataTableSort = ref('completion')

// 图表引用
const typePieChart = ref<HTMLCanvasElement | null>(null)
const typeBarChart = ref<HTMLCanvasElement | null>(null)
const statusDoughnutChart = ref<HTMLCanvasElement | null>(null)
const statusBarChart = ref<HTMLCanvasElement | null>(null)
const trendChart = ref<HTMLCanvasElement | null>(null)
const villageRankingChart = ref<HTMLCanvasElement | null>(null)
const qualityAnalysisChart = ref<HTMLCanvasElement | null>(null)

// 图表实例 - 使用ChartInstance类型
let typePieChartInstance: ChartInstance = null
let typeBarChartInstance: ChartInstance = null
let statusDoughnutChartInstance: ChartInstance = null
let statusBarChartInstance: ChartInstance = null
let trendChartInstance: ChartInstance = null
let villageRankingChartInstance: ChartInstance = null
let qualityAnalysisChartInstance: ChartInstance = null

// 村庄列表（从真实数据提取）
const villages = ref<string[]>([])

// 分析数据（从API加载）
const analysisData = ref<any[]>([])

// 计算属性
const filteredData = computed(() => {
  let data = [...analysisData.value]

  // 村庄筛选
  if (selectedVillage.value) {
    data = data.filter((item) => item.village === selectedVillage.value)
  }

  // 类型筛选
  if (selectedType.value) {
    const typeMap: Record<string, string> = {
      infrastructure: '基础设施建设',
      industry: '产业发展',
      education: '教育培训',
      healthcare: '医疗健康',
      environment: '生态环境保护',
    }
    data = data.filter((item) => item.type === typeMap[selectedType.value])
  }

  // 时间范围筛选（这里简化处理，实际应该根据timeRange计算日期范围）
  // 在真实应用中，需要根据timeRange计算日期范围并筛选

  return data
})

const sortedAnalysisData = computed(() => {
  const data = [...filteredData.value]

  switch (dataTableSort.value) {
    case 'completion':
      return data.sort((a, b) => b.completionRate - a.completionRate)
    case 'startDate':
      return data.sort((a, b) => new Date(b.startDate).getTime() - new Date(a.startDate).getTime())
    case 'investment':
      return data.sort((a, b) => b.investment - a.investment)
    default:
      return data
  }
})

// 核心指标计算
const totalWorks = computed(() => filteredData.value.length)
const totalWorksChange = ref(0)

const averageCompletionRate = computed(() => {
  const completedOrInProgress = filteredData.value.filter(
    (item) => item.status === '进行中' || item.status === '已完成' || item.status === '已延期'
  )
  if (completedOrInProgress.length === 0) return 0

  const sum = completedOrInProgress.reduce((acc, item) => acc + item.completionRate, 0)
  return Math.round(sum / completedOrInProgress.length)
})
const completionRateChange = ref(0)

const averageDelayRate = computed(() => {
  if (filteredData.value.length === 0) return 0
  const delayedCount = filteredData.value.filter((item) => item.status === '已延期').length
  return Math.round((delayedCount / filteredData.value.length) * 100)
})
const delayRateChange = ref(0)

const totalInvestment = computed(() => {
  const sum = filteredData.value.reduce((acc, item) => acc + item.investment, 0)
  return Math.round(sum)
})
const investmentChange = ref(0)

// 生命周期
onMounted(async () => {
  await loadData()
  await nextTick()
  initCharts()
})

// 监听筛选条件变化
watch([timeRange, selectedVillage, selectedType], async () => {
  await loadData()
  updateCharts()
})

// 方法
const loadData = async () => {
  loading.value = true
  try {
    const res = await getRuralWorks({ limit: 100 })
    const typeMap: Record<string, string> = {
      infrastructure: '基础设施建设',
      industry: '产业发展',
      education: '教育培训',
      healthcare: '医疗健康',
      environment: '生态环境保护',
    }
    const statusMap: Record<string, string> = {
      planned: '计划中',
      in_progress: '进行中',
      completed: '已完成',
      delayed: '已延期',
    }
    const items = res && (res as any).items ? (res as any).items : []
    analysisData.value = items.map((item: any) => ({
      workName: item.name || '',
      village: item.village_name || '',
      type: typeMap[item.type] || item.type || '',
      status: statusMap[item.status] || item.status || '',
      completionRate: item.progress || 0,
      investment: 0,
      startDate: item.start_date || '',
      endDate: item.end_date || '',
      qualityScore: item.progress === 100 ? 4.5 : item.progress > 50 ? 3.8 : 0,
    }))
    // 提取村庄列表
    const villageSet = new Set(items.map((i: any) => i.village_name).filter(Boolean))
    villages.value = Array.from(villageSet) as string[]
  } catch (e) {
    logger.error('加载分析数据失败:', e)
    analysisData.value = []
    ElMessage.error(getErrorMessage(e, '加载数据失败，请稍后重试'))
  } finally {
    loading.value = false
  }
}

const refreshData = async () => {
  await loadData()
  updateCharts()
  ElMessage.success('数据刷新成功')
}

const exportAnalysis = () => {
  const data = filteredData.value
  if (!data || data.length === 0) {
    ElMessage.warning('没有可导出的数据')
    return
  }

  const headers = [
    '工作名称',
    '所属村庄',
    '工作类型',
    '状态',
    '完成率(%)',
    '投入资金(万元)',
    '开始日期',
    '结束日期',
    '质量评分',
  ]
  const rows = data.map((item: any) => [
    item.workName || '',
    item.village || '',
    item.type || '',
    item.status || '',
    item.completionRate ?? 0,
    item.investment ?? 0,
    item.startDate || '',
    item.endDate || '',
    item.qualityScore ?? 0,
  ])

  const BOM = '\uFEFF'
  const csvContent =
    BOM +
    [headers, ...rows]
      .map((row) =>
        row
          .map((cell: any) => {
            const str = String(cell).replace(/"/g, '""')
            return `"${str}"`
          })
          .join(',')
      )
      .join('\n')

  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `数据分析报告_${new Date().toISOString().slice(0, 10)}.csv`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
  ElMessage.success('分析报告导出成功')
}

const handleTimeRangeChange = () => {
  // 处理时间范围变化
}

const handleVillageChange = () => {
  // 处理村庄选择变化
}

const handleTypeChange = () => {
  // 处理类型选择变化
}

const handleTypeChartView = (view: string) => {
  typeChartView.value = view
  updateCharts()
}

const handleStatusChartView = (view: string) => {
  statusChartView.value = view
  updateCharts()
}

const updateTrendChart = () => {
  if (trendChartInstance) {
    trendChartInstance.destroy()
  }
  if (trendChart.value) {
    initTrendChart()
  }
}

const updateDataTable = () => {
  // 表格排序已通过计算属性处理
}

// 初始化所有图表
const initCharts = async () => {
  await nextTick()
  initTypeCharts()
  initStatusCharts()
  initTrendChart()
  initVillageRankingChart()
  initQualityAnalysisChart()
}

// 更新所有图表
const updateCharts = async () => {
  await nextTick()

  // 销毁现有图表
  if (typePieChartInstance) typePieChartInstance.destroy()
  if (typeBarChartInstance) typeBarChartInstance.destroy()
  if (statusDoughnutChartInstance) statusDoughnutChartInstance.destroy()
  if (statusBarChartInstance) statusBarChartInstance.destroy()
  if (trendChartInstance) trendChartInstance.destroy()
  if (villageRankingChartInstance) villageRankingChartInstance.destroy()
  if (qualityAnalysisChartInstance) qualityAnalysisChartInstance.destroy()

  // 重新初始化图表 - 确保图表容器存在
  if (typePieChart.value || typeBarChart.value) {
    initTypeCharts()
  }
  if (statusDoughnutChart.value || statusBarChart.value) {
    initStatusCharts()
  }
  if (trendChart.value) {
    initTrendChart()
  }
  if (villageRankingChart.value) {
    initVillageRankingChart()
  }
  if (qualityAnalysisChart.value) {
    initQualityAnalysisChart()
  }
}

// 初始化工作类型图表
const initTypeCharts = () => {
  const typeData = getTypeDistributionData()

  if (typeChartView.value === 'pie' && typePieChart.value) {
    typePieChartInstance = new Chart(typePieChart.value, {
      type: 'pie',
      data: {
        labels: typeData.labels,
        datasets: [
          {
            data: typeData.values,
            backgroundColor: chartPalette(),
            borderColor: '#fff',
            borderWidth: 2,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'right',
            labels: {
              font: {
                family: 'Arial',
                size: 12,
              },
              padding: 20,
            },
          },
          tooltip: {
            callbacks: {
              label: function (context: any) {
                const label = context.label || ''
                const value = context.raw || 0
                const total = context.dataset.data.reduce((a: number, b: number) => a + b, 0)
                const percentage = Math.round((value / total) * 100)
                return `${label}: ${value} (${percentage}%)`
              },
            },
          },
        },
      },
    })
  } else if (typeBarChart.value) {
    typeBarChartInstance = new Chart(typeBarChart.value, {
      type: 'bar',
      data: {
        labels: typeData.labels,
        datasets: [
          {
            label: '工作数量',
            data: typeData.values,
            backgroundColor: '#003366',
            borderRadius: 4,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: false,
          },
        },
        scales: {
          y: {
            beginAtZero: true,
            ticks: {
              stepSize: 1,
            },
          },
        },
      },
    })
  }
}

// 初始化工作状态图表
const initStatusCharts = () => {
  const statusData = getStatusDistributionData()

  if (statusChartView.value === 'doughnut' && statusDoughnutChart.value) {
    statusDoughnutChartInstance = new Chart(statusDoughnutChart.value, {
      type: 'doughnut',
      data: {
        labels: statusData.labels,
        datasets: [
          {
            data: statusData.values,
            backgroundColor: [
              chartColor('success'), // 已完成 - 绿色
              chartColorPrimary(), // 进行中 - 主色
              chartColor('warning'), // 计划中 - 橙色
              chartColor('danger'), // 已延期 - 红色
            ],
            borderColor: '#fff',
            borderWidth: 2,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'right',
            labels: {
              font: {
                family: 'Arial',
                size: 12,
              },
              padding: 20,
            },
          },
          tooltip: {
            callbacks: {
              label: function (context: any) {
                const label = context.label || ''
                const value = context.raw || 0
                const total = context.dataset.data.reduce((a: number, b: number) => a + b, 0)
                const percentage = Math.round((value / total) * 100)
                return `${label}: ${value} (${percentage}%)`
              },
            },
          },
        },
      },
    })
  } else if (statusBarChart.value) {
    statusBarChartInstance = new Chart(statusBarChart.value, {
      type: 'bar',
      data: {
        labels: statusData.labels,
        datasets: [
          {
            label: '工作数量',
            data: statusData.values,
            backgroundColor: [
              chartColor('success'), // 已完成 - 绿色
              chartColorPrimary(), // 进行中 - 主色
              chartColor('warning'), // 计划中 - 橙色
              chartColor('danger'), // 已延期 - 红色
            ],
            borderRadius: 4,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: false,
          },
        },
        scales: {
          y: {
            beginAtZero: true,
            ticks: {
              stepSize: 1,
            },
          },
        },
      },
    })
  }
}

// 初始化趋势图表
const initTrendChart = () => {
  if (!trendChart.value) return

  const trendData = getTrendData()

  // 没有真实数据时显示提示
  if (!trendData.hasData || trendData.labels.length === 0) {
    const ctx = trendChart.value.getContext('2d')
    if (ctx) {
      ctx.clearRect(0, 0, trendChart.value.width, trendChart.value.height)
      ctx.font = '16px Arial'
      ctx.fillStyle = '#909399'
      ctx.textAlign = 'center'
      ctx.fillText(
        '暂无数据，请先录入乡村工作数据',
        trendChart.value.width / 2,
        trendChart.value.height / 2
      )
    }
    return
  }

  trendChartInstance = new Chart(trendChart.value, {
    type: 'line',
    data: {
      labels: trendData.labels,
      datasets: [
        {
          label:
            trendType.value === 'count'
              ? '工作数量'
              : trendType.value === 'completion'
                ? '平均完成率(%)'
                : '投入资金(万元)',
          data: trendData.values,
          borderColor: '#003366',
          backgroundColor: 'rgba(0, 51, 102, 0.1)',
          borderWidth: 3,
          fill: true,
          tension: 0.4,
          pointBackgroundColor: '#003366',
          pointBorderColor: '#fff',
          pointBorderWidth: 2,
          pointRadius: 5,
          pointHoverRadius: 7,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'top',
          labels: {
            font: {
              family: 'Arial',
              size: 14,
              weight: 'bold',
            },
          },
        },
        tooltip: {
          mode: 'index',
          intersect: false,
        },
      },
      scales: {
        x: {
          grid: {
            display: false,
          },
        },
        y: {
          beginAtZero: true,
          grid: {
            color: 'rgba(0, 0, 0, 0.1)',
          },
        },
      },
    },
  })
}

// 初始化村庄排名图表
const initVillageRankingChart = () => {
  if (!villageRankingChart.value) return

  const villageData = getVillageRankingData()

  villageRankingChartInstance = new Chart(villageRankingChart.value, {
    type: 'bar',
    data: {
      labels: villageData.labels,
      datasets: [
        {
          label: '工作数量',
          data: villageData.values,
          backgroundColor: '#0055aa',
          borderRadius: 4,
        },
      ],
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: false,
        },
      },
      scales: {
        x: {
          beginAtZero: true,
          ticks: {
            stepSize: 1,
          },
        },
      },
    },
  })
}

// 初始化质量分析图表
const initQualityAnalysisChart = () => {
  if (!qualityAnalysisChart.value) return

  const qualityData = getQualityAnalysisData()

  qualityAnalysisChartInstance = new Chart(qualityAnalysisChart.value, {
    type: 'radar',
    data: {
      labels: qualityData.labels,
      datasets: [
        {
          label: '质量评分',
          data: qualityData.values,
          backgroundColor: 'rgba(0, 51, 102, 0.2)',
          borderColor: '#003366',
          borderWidth: 2,
          pointBackgroundColor: '#0055aa',
          pointBorderColor: '#fff',
          pointBorderWidth: 2,
          pointRadius: 4,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        r: {
          beginAtZero: true,
          max: 5,
          ticks: {
            stepSize: 1,
          },
        },
      },
    },
  })
}

// 数据处理辅助函数
const getTypeDistributionData = () => {
  const typeMap: Record<string, number> = {
    基础设施建设: 0,
    产业发展: 0,
    教育培训: 0,
    医疗健康: 0,
    生态环境保护: 0,
  }

  filteredData.value.forEach((item) => {
    if (Object.prototype.hasOwnProperty.call(typeMap, item.type)) {
      typeMap[item.type]++
    }
  })

  return {
    labels: Object.keys(typeMap).filter((key) => typeMap[key] > 0),
    values: Object.keys(typeMap)
      .filter((key) => typeMap[key] > 0)
      .map((key) => typeMap[key]),
  }
}

const getStatusDistributionData = () => {
  const statusMap: Record<string, number> = {
    已完成: 0,
    进行中: 0,
    计划中: 0,
    已延期: 0,
  }

  filteredData.value.forEach((item) => {
    if (Object.prototype.hasOwnProperty.call(statusMap, item.status)) {
      statusMap[item.status]++
    }
  })

  return {
    labels: Object.keys(statusMap).filter((key) => statusMap[key] > 0),
    values: Object.keys(statusMap)
      .filter((key) => statusMap[key] > 0)
      .map((key) => statusMap[key]),
  }
}

const getTrendData = () => {
  // 没有数据时返回空数据，让图表显示"暂无数据"
  if (!filteredData.value || filteredData.value.length === 0) {
    return {
      labels: [],
      values: [],
      hasData: false,
    }
  }

  // 按月分组统计（基于真实数据）
  const monthlyMap: Record<
    string,
    {
      count: number
      completionSum: number
      completionCount: number
      investment: number
    }
  > = {}

  filteredData.value.forEach((item) => {
    if (!item.startDate) return
    const month = item.startDate.substring(0, 7) // YYYY-MM
    if (!monthlyMap[month]) {
      monthlyMap[month] = {
        count: 0,
        completionSum: 0,
        completionCount: 0,
        investment: 0,
      }
    }
    monthlyMap[month].count++
    monthlyMap[month].completionSum += item.completionRate || 0
    monthlyMap[month].completionCount++
    monthlyMap[month].investment += item.investment || 0
  })

  // 排序并取最近6个月
  const sortedMonths = Object.keys(monthlyMap).sort().slice(-6)

  if (sortedMonths.length === 0) {
    return { labels: [], values: [], hasData: false }
  }

  if (trendType.value === 'count') {
    return {
      labels: sortedMonths,
      values: sortedMonths.map((m) => monthlyMap[m].count),
      hasData: true,
    }
  } else if (trendType.value === 'completion') {
    return {
      labels: sortedMonths,
      values: sortedMonths.map((m) =>
        Math.round(monthlyMap[m].completionSum / monthlyMap[m].completionCount)
      ),
      hasData: true,
    }
  } else {
    // investment
    return {
      labels: sortedMonths,
      values: sortedMonths.map((m) => monthlyMap[m].investment),
      hasData: true,
    }
  }
}

const getVillageRankingData = () => {
  const villageMap: Record<string, number> = {}

  filteredData.value.forEach((item) => {
    if (!villageMap[item.village]) {
      villageMap[item.village] = 0
    }
    villageMap[item.village]++
  })

  // 排序并取前5
  const sorted = Object.entries(villageMap)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 5)

  return {
    labels: sorted.map(([village]) => village),
    values: sorted.map(([, count]) => count),
  }
}

const getQualityAnalysisData = () => {
  // 模拟质量分析数据
  return {
    labels: ['基础设施建设', '产业发展', '教育培训', '医疗健康', '生态环境保护'],
    values: [4.3, 4.5, 4.7, 4.2, 4.1],
  }
}

// UI辅助函数
const getTypeTagType = (type: string): 'info' | 'primary' | 'success' | 'warning' | 'danger' => {
  const typeMap: Record<string, 'info' | 'primary' | 'success' | 'warning' | 'danger'> = {
    基础设施建设: 'warning',
    产业发展: 'success',
    教育培训: 'primary',
    医疗健康: 'info',
    生态环境保护: 'danger',
  }
  return typeMap[type] || 'info'
}

const getStatusTagType = (
  status: string
): 'info' | 'primary' | 'success' | 'warning' | 'danger' => {
  const statusMap: Record<string, 'info' | 'primary' | 'success' | 'warning' | 'danger'> = {
    已完成: 'success',
    进行中: 'primary',
    计划中: 'info',
    已延期: 'danger',
  }
  return statusMap[status] || 'info'
}

const getProgressStatus = (progress: number): '' | 'success' | 'warning' | 'exception' => {
  if (progress === 100) return 'success'
  if (progress > 70) return ''
  if (progress > 30) return 'warning'
  return 'exception'
}

const getQualityScoreClass = (score: number) => {
  if (score >= 4.5) return 'excellent'
  if (score >= 4.0) return 'good'
  if (score >= 3.5) return 'average'
  if (score > 0) return 'poor'
  return 'not-evaluated'
}
</script>

<style lang="scss" scoped>
.rural-works-analysis {
  padding: 20px;
  background-color: #f5f7fa;
  min-height: 100vh;
  position: relative;

  // 装饰
  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 5px;
    background: linear-gradient(90deg, #003366, #0055aa, #003366);
  }
}

// 页面头部样式
.page-header {
  margin-bottom: 30px;
  text-align: center;
  padding-bottom: 20px;
  position: relative;

  .page-title {
    font-size: 28px;
    font-weight: bold;
    color: #003366;
    margin-bottom: 10px;
    text-transform: uppercase;
    letter-spacing: 1px;
  }

  .page-subtitle {
    font-size: 16px;
    color: #666;
    margin-bottom: 20px;
  }

  .decoration-line {
    width: 100px;
    height: 3px;
    background: linear-gradient(90deg, #003366, #0055aa);
    margin: 0 auto;
  }
}

// 通用类
.military-border {
  border: 1px solid #003366;
  border-radius: 4px;
  box-shadow: 0 2px 8px rgba(0, 51, 102, 0.15);
}

.military-card {
  background: white;
  border: 1px solid #ddd;
  border-radius: 4px;
  padding: 20px;
  margin-bottom: 20px;
  position: relative;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);

  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    width: 4px;
    height: 100%;
    background: linear-gradient(to bottom, #003366, #0055aa);
  }
}

.military-decoration {
  background: linear-gradient(90deg, #003366, #0055aa);
}

// 角落装饰
.military-decoration-corner {
  position: absolute;
  width: 30px;
  height: 30px;
  border: 2px solid #003366;
  z-index: 10;
}

.corner-top-left {
  top: 20px;
  left: 20px;
  border-right: none;
  border-bottom: none;
}

.corner-top-right {
  top: 20px;
  right: 20px;
  border-left: none;
  border-bottom: none;
}

.corner-bottom-left {
  bottom: 20px;
  left: 20px;
  border-right: none;
  border-top: none;
}

.corner-bottom-right {
  bottom: 20px;
  right: 20px;
  border-left: none;
  border-top: none;
}

// 筛选控制区域样式
.filter-control-section {
  .filter-row {
    display: flex;
    gap: 15px;
    align-items: center;
    flex-wrap: wrap;

    .time-range-select,
    .village-select,
    .type-select {
      flex: 1;
      min-width: 150px;
    }

    .right-controls {
      display: flex;
      gap: 10px;
    }

    .refresh-button {
      background-color: var(--color-primary);
      color: white;

      &:hover {
        background-color: var(--color-primary-light-2);
      }
    }

    .export-button {
      background-color: #67c23a;
      color: white;

      &:hover {
        background-color: #85ce61;
      }
    }
  }
}

// 核心指标卡片样式
.key-indicators {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 20px;
  margin-bottom: 30px;

  .indicator-card {
    background: white;
    border-radius: 8px;
    padding: 20px;
    transition:
      transform 0.3s,
      box-shadow 0.3s;

    &:hover {
      transform: translateY(-5px);
      box-shadow: 0 4px 16px rgba(0, 51, 102, 0.2);
    }

    .indicator-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 15px;

      .indicator-title {
        font-size: 16px;
        color: #666;
        font-weight: 500;
      }

      .indicator-icon {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-size: 18px;
      }
    }

    .indicator-content {
      display: flex;
      align-items: baseline;
      gap: 10px;
      margin-bottom: 8px;

      .indicator-value {
        font-size: 32px;
        font-weight: bold;
        color: #003366;
      }

      .indicator-change {
        font-size: 16px;
        font-weight: 600;

        &.positive {
          color: #67c23a;
        }

        &.negative {
          color: #f56c6c;
        }
      }
    }

    .indicator-description {
      font-size: 14px;
      color: #999;
    }
  }
}

// 图表行样式
.charts-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(450px, 1fr));
  gap: 20px;
  margin-bottom: 20px;

  .chart-card {
    background: white;
    border-radius: 8px;
    overflow: hidden;

    &.full-width {
      grid-column: 1 / -1;
    }

    .chart-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 0 0 15px 0;
      margin-bottom: 15px;
      border-bottom: 2px solid #f0f0f0;

      .chart-title {
        margin: 0;
        font-size: 18px;
        font-weight: 600;
        color: #003366;
      }

      .chart-view-trigger {
        cursor: pointer;
        color: #003366;
        font-size: 14px;
      }
    }

    .chart-content {
      height: 300px;
      position: relative;

      .chart-container {
        height: 100%;
        width: 100%;
      }
    }

    &.full-width .chart-content {
      height: 400px;
    }
  }
}

// 数据表格样式
.data-table-section {
  .table-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0 0 15px 0;
    margin-bottom: 15px;
    border-bottom: 2px solid #f0f0f0;

    .table-title {
      margin: 0;
      font-size: 18px;
      font-weight: 600;
      color: #003366;
    }
  }

  .quality-score {
    text-align: center;
    font-weight: bold;
    padding: 4px 8px;
    border-radius: 4px;

    &.excellent {
      background-color: #f0f9ff;
      color: #096dd9;
    }

    &.good {
      background-color: #f6ffed;
      color: #52c41a;
    }

    &.average {
      background-color: #fff7e6;
      color: #fa8c16;
    }

    &.poor {
      background-color: #fff1f0;
      color: #f5222d;
    }

    &.not-evaluated {
      background-color: #f5f5f5;
      color: #999;
    }
  }
}

// 响应式设计
@media (max-width: 768px) {
  .rural-works-analysis {
    padding: 10px;
  }

  .page-title {
    font-size: 24px !important;
  }

  .filter-row {
    flex-direction: column;
    align-items: stretch !important;

    .time-range-select,
    .village-select,
    .type-select {
      width: 100% !important;
      min-width: unset !important;
    }

    .right-controls {
      width: 100%;
      justify-content: center;
    }
  }

  .key-indicators {
    grid-template-columns: 1fr;
  }

  .charts-row {
    grid-template-columns: 1fr;

    .chart-card {
      &.full-width {
        grid-column: unset;
      }
    }
  }

  .military-decoration-corner {
    display: none;
  }

  .chart-header {
    flex-direction: column;
    align-items: flex-start !important;
    gap: 10px;
  }

  .table-header {
    flex-direction: column;
    align-items: flex-start !important;
    gap: 10px;
  }
}

@media (max-width: 1200px) {
  .charts-row {
    grid-template-columns: 1fr;
  }
}
</style>
