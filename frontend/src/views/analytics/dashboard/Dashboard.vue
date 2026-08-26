<template>
  <div class="analytics-dashboard dashboard-modern">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-info">
        <h2 class="page-title">数据分析仪表板</h2>
        <p class="page-desc">帮扶村综合数据分析与可视化</p>
      </div>
      <div class="header-actions">
        <el-select v-model="selectedYear" style="width: 120px" @change="loadData">
          <el-option
            v-for="year in availableYears"
            :key="year"
            :label="`${year}年`"
            :value="year"
          />
        </el-select>
        <el-button @click="handleExport">
          <el-icon><Download /></el-icon>导出报表
        </el-button>
      </div>
    </div>

    <!-- 系统状态栏 -->
    <SystemStatus :poll-interval="30000" :show-refresh="true" />

    <!-- 筛选器 -->
    <div class="filter-card">
      <el-form :model="filters" inline>
        <el-form-item label="部门">
          <el-select
            v-model="filters.department"
            placeholder="全部"
            clearable
            style="width: 140px"
            @change="loadData"
          >
            <el-option
              v-for="dept in filterOptions.departments"
              :key="dept"
              :label="dept"
              :value="dept"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="地域属性">
          <el-select
            v-model="filters.regionType"
            placeholder="全部"
            clearable
            style="width: 140px"
            @change="loadData"
          >
            <el-option label="三区三州" value="isThreeRegions" />
            <el-option label="边疆地区" value="isBorderArea" />
            <el-option label="民族地区" value="isEthnicArea" />
            <el-option label="革命地区" value="isRevolutionaryArea" />
            <el-option label="重点帮扶县" value="isKeyCounty" />
          </el-select>
        </el-form-item>
      </el-form>
    </div>

    <!-- 统计卡片 KPI -->
    <el-row v-loading="loading" :gutter="20" class="stat-row">
      <!-- 卡片1：帮扶村总数 -->
      <el-col :span="6">
        <div class="stat-card primary">
          <div class="stat-icon">
            <el-icon><OfficeBuilding /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-label">帮扶村总数</div>
            <div class="stat-value">
              <span class="data-number data-number--lg">
                {{ (statistics.villages?.totalVillages || 0).toLocaleString() }}
              </span>
              <span class="data-unit">个</span>
            </div>
            <div class="stat-trend" :class="`stat-trend--${dirOf(kpiTrends.villages)}`">
              <span class="trend-tag" :class="`trend-tag--${dirOf(kpiTrends.villages)}`">
                <i class="trend-tag__arrow">{{ arrowOf(kpiTrends.villages) }}</i>
                <template v-if="kpiTrends.villages !== 0"
                  >{{ Math.abs(kpiTrends.villages) }}%</template
                >
                <template v-else>持平</template>
              </span>
              <span class="trend-label">较上月</span>
            </div>
          </div>
          <div ref="sparkVillagesRef" class="stat-sparkline"></div>
        </div>
      </el-col>

      <!-- 卡片2：覆盖人口 -->
      <el-col :span="6">
        <div class="stat-card success">
          <div class="stat-icon">
            <el-icon><User /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-label">覆盖人口</div>
            <div class="stat-value">
              <span class="data-number data-number--lg">
                {{ formatNumber(statistics.population?.totalPopulation || 0) }}
              </span>
            </div>
            <div class="stat-trend" :class="`stat-trend--${dirOf(kpiTrends.population)}`">
              <span class="trend-tag" :class="`trend-tag--${dirOf(kpiTrends.population)}`">
                <i class="trend-tag__arrow">{{ arrowOf(kpiTrends.population) }}</i>
                <template v-if="kpiTrends.population !== 0"
                  >{{ Math.abs(kpiTrends.population) }}%</template
                >
                <template v-else>持平</template>
              </span>
              <span class="trend-label">较去年</span>
            </div>
          </div>
          <div ref="sparkPopulationRef" class="stat-sparkline"></div>
        </div>
      </el-col>

      <!-- 卡片3：人均收入 -->
      <el-col :span="6">
        <div class="stat-card warning">
          <div class="stat-icon">
            <el-icon><Money /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-label">平均人均收入</div>
            <div class="stat-value">
              <span class="data-number data-number--lg">
                {{ format.formatMoney4(statistics.income?.avgPerCapitaIncome) }}
              </span>
              <span class="data-unit">万元</span>
            </div>
            <div class="stat-trend" :class="`stat-trend--${dirOf(kpiTrends.income)}`">
              <span class="trend-tag" :class="`trend-tag--${dirOf(kpiTrends.income)}`">
                <i class="trend-tag__arrow">{{ arrowOf(kpiTrends.income) }}</i>
                <template v-if="kpiTrends.income !== 0">{{ Math.abs(kpiTrends.income) }}%</template>
                <template v-else>持平</template>
              </span>
              <span class="trend-label">较去年</span>
            </div>
          </div>
          <div ref="sparkIncomeRef" class="stat-sparkline"></div>
        </div>
      </el-col>

      <!-- 卡片4：帮扶投入 -->
      <el-col :span="6">
        <div class="stat-card danger">
          <div class="stat-icon">
            <el-icon><TrendCharts /></el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-label">帮扶投入</div>
            <div class="stat-value">
              <span class="data-number data-number--lg">
                {{ formatNumber(totalInvestment) }}
              </span>
              <span class="data-unit">万元</span>
            </div>
            <div class="stat-trend" :class="`stat-trend--${dirOf(kpiTrends.investment)}`">
              <span class="trend-tag" :class="`trend-tag--${dirOf(kpiTrends.investment)}`">
                <i class="trend-tag__arrow">{{ arrowOf(kpiTrends.investment) }}</i>
                <template v-if="kpiTrends.investment !== 0"
                  >{{ Math.abs(kpiTrends.investment) }}%</template
                >
                <template v-else>持平</template>
              </span>
              <span class="trend-label">较上月</span>
            </div>
          </div>
          <div ref="sparkInvestmentRef" class="stat-sparkline"></div>
        </div>
      </el-col>
    </el-row>

    <!-- 图表区域 -->
    <el-row :gutter="20">
      <el-col :span="12">
        <div class="chart-card">
          <h3 class="chart-title">地域分布</h3>
          <div ref="regionChartRef" class="chart-container"></div>
        </div>
      </el-col>
      <el-col :span="12">
        <div class="chart-card">
          <h3 class="chart-title">帮扶投入构成</h3>
          <div ref="investmentChartRef" class="chart-container"></div>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="24">
        <div class="chart-card">
          <h3 class="chart-title">年度趋势对比</h3>
          <div ref="trendChartRef" class="chart-container" style="height: 350px"></div>
        </div>
      </el-col>
    </el-row>

    <!-- 钻取面板 -->
    <div v-if="drillDownData" class="drill-down-panel">
      <div class="panel-header">
        <h3>{{ drillDownTitle }}</h3>
        <el-button text @click="closeDrillDown">
          <el-icon><Close /></el-icon>
        </el-button>
      </div>
      <el-table :data="drillDownData.items" border max-height="300">
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="value" label="数量" width="100" align="right" />
        <el-table-column prop="totalPopulation" label="人口" width="100" align="right" />
      </el-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { logger } from '@/utils/logger'
import { format } from '@/utils'

import { ref, reactive, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { Download, OfficeBuilding, User, Money, TrendCharts, Close } from '@element-plus/icons-vue'
import echarts from '@/utils/echarts'
import { getCurrentTheme } from '@/utils/echarts-theme'
import SystemStatus from '@/components/business/SystemStatus.vue'
import { getSummaryStatistics, getFilterOptions, drillDown } from '@/api/analytics'
import { getDashboardStats, getYearlyTrends } from '@/api/dashboard'
import type { SummaryStatistics, FilterOptions, DrillDownResult } from '@/types/analytics'

// =========================================================================
// 年份与筛选
// =========================================================================

const currentYear = new Date().getFullYear()
const availableYears = Array.from({ length: currentYear - 2014 }, (_, i) => currentYear - i)
const selectedYear = ref(currentYear)

const filters = reactive({
  department: '',
  regionType: '',
})

const filterOptions = ref<FilterOptions>({
  departments: [],
  supportUnits: [],
  regionScopes: [],
  isRevitalizationTier: undefined,
  years: [],
})

// =========================================================================
// 统计数据
// =========================================================================

const statistics = ref<SummaryStatistics>({
  year: currentYear,
  villages: {
    totalVillages: 0,
    threeRegionsCount: 0,
    keyCountyCount: 0,
    provincialDemoCount: 0,
    crossProvinceCount: 0,
  },
  population: { totalPopulation: 0, totalHouseholds: 0, povertyHouseholds: 0 },
  income: { avgPerCapitaIncome: 0, totalCollectiveIncome: 0 },
  investment: {
    industry: 0,
    infrastructure: 0,
    infrastructureRoadKm: 0,
    education: 0,
    educationAidedStudents: 0,
  },
})

const loading = ref(false)
const drillDownData = ref<DrillDownResult | null>(null)
const drillDownTitle = ref('')

const totalInvestment = computed(() => {
  const inv = statistics.value.investment
  return (inv.industry || 0) + (inv.infrastructure || 0) + (inv.education || 0)
})

// =========================================================================
// KPI 环比趋势 — 从后端 API 获取真实年度同比数据
// =========================================================================

interface KpiTrends {
  villages: number
  population: number
  income: number
  investment: number
}

const kpiTrends = ref<KpiTrends>({ villages: 0, population: 0, income: 0, investment: 0 })

type TrendDir = 'up' | 'down' | 'flat'
const dirOf = (v?: number): TrendDir => ((v ?? 0) > 0 ? 'up' : (v ?? 0) < 0 ? 'down' : 'flat')
const arrowOf = (v?: number): string => ((v ?? 0) > 0 ? '↑' : (v ?? 0) < 0 ? '↓' : '→')

const sparkReal = ref<Record<'villages' | 'population' | 'income' | 'investment', number[]>>({
  villages: [],
  population: [],
  income: [],
  investment: [],
})

async function fetchKpiTrends() {
  try {
    const [statsRes, yearlyRes] = await Promise.all([getDashboardStats(false), getYearlyTrends(5)])
    const t = (statsRes as any)?.trends ?? {}
    kpiTrends.value = {
      villages: t.villages ?? 0,
      population: t.population_yoy ?? 0,
      income: t.income_yoy ?? 0,
      investment: t.funds ?? 0,
    }
    sparkReal.value = {
      villages: (yearlyRes as any)?.villages ?? [],
      population: (yearlyRes as any)?.population ?? [],
      income: (yearlyRes as any)?.income ?? [],
      investment: ((yearlyRes as any)?.trends ?? []).map((r: any) => r?.total_actual ?? 0),
    }
  } catch (e) {
    logger.warn('KPI趋势获取失败，使用默认值', e)
  }
}

// =========================================================================
// Sparkline 微型趋势图数据（真实近 5 年年度序列，取自 /dashboard/yearly-trends）
// =========================================================================

const takeSeries = (arr: number[]): number[] => {
  const a = (arr || []).filter((n) => Number.isFinite(n))
  return a.length ? a : [0]
}

// =========================================================================
// 图表引用
// =========================================================================

const regionChartRef = ref<HTMLElement>()
const investmentChartRef = ref<HTMLElement>()
const trendChartRef = ref<HTMLElement>()

// Sparkline 容器引用
const sparkVillagesRef = ref<HTMLElement>()
const sparkPopulationRef = ref<HTMLElement>()
const sparkIncomeRef = ref<HTMLElement>()
const sparkInvestmentRef = ref<HTMLElement>()

let regionChart: echarts.ECharts | null = null
let investmentChart: echarts.ECharts | null = null
let trendChart: echarts.ECharts | null = null

// Sparkline 实例
let sparkVillagesChart: echarts.ECharts | null = null
let sparkPopulationChart: echarts.ECharts | null = null
let sparkIncomeChart: echarts.ECharts | null = null
let sparkInvestmentChart: echarts.ECharts | null = null

// =========================================================================
// 工具函数
// =========================================================================

const formatNumber = (num: number) => {
  if (num >= 10000) return (num / 10000).toFixed(1) + '万'
  return num.toLocaleString()
}

// =========================================================================
// Sparkline 配置生成
// =========================================================================

interface SparkConfig {
  /** 线条/面积渐变顶部颜色（hex 格式） */
  color: string
  /** 面积渐变底部颜色（rgba 格式，高透明度） */
  colorStop: string
  /** 预计算的 rgba 中间色（用于渐变顶部，约 18% 不透明度） */
  colorAlpha: string
}

const SPARK_CONFIGS: Record<string, SparkConfig> = {
  villages: {
    color: '#1e4d8c',
    colorAlpha: 'rgba(30, 77, 140, 0.18)',
    colorStop: 'rgba(30, 77, 140, 0.02)',
  },
  population: {
    color: '#2d6a4f',
    colorAlpha: 'rgba(45, 106, 79, 0.18)',
    colorStop: 'rgba(45, 106, 79, 0.02)',
  },
  income: {
    color: '#f59e0b',
    colorAlpha: 'rgba(245, 158, 11, 0.18)',
    colorStop: 'rgba(245, 158, 11, 0.02)',
  },
  investment: {
    color: '#ef4444',
    colorAlpha: 'rgba(239, 68, 68, 0.18)',
    colorStop: 'rgba(239, 68, 68, 0.02)',
  },
}

const createSparkOption = (data: number[], config: SparkConfig): echarts.EChartsCoreOption => ({
  grid: {
    left: 0,
    right: 0,
    top: 4,
    bottom: 0,
  },
  xAxis: {
    type: 'category',
    data: data.map((_, i) => i),
    show: false,
  },
  yAxis: {
    type: 'value',
    show: false,
    min: (val: { min: number; max: number }) => Math.floor(val.min * 0.92),
    max: (val: { min: number; max: number }) => Math.ceil(val.max * 1.06),
  },
  series: [
    {
      type: 'line',
      data,
      smooth: true,
      symbol: 'none',
      lineStyle: {
        width: 2,
        color: config.color,
      },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: config.colorAlpha },
          { offset: 0.5, color: config.colorStop },
          { offset: 1, color: 'rgba(255,255,255,0)' },
        ]),
      },
      animation: true,
      animationDuration: 1200,
      animationEasing: 'cubicOut',
    },
  ],
  tooltip: {
    show: false,
  },
})

// =========================================================================
// 主图表配置生成（升级版——渐变面积 + 平滑曲线）
// =========================================================================

const updateCharts = async () => {
  // ── 地域分布饼图（升级版） ──
  if (regionChart) {
    const v = statistics.value.villages
    regionChart.setOption({
      color: ['#1e4d8c', '#2d6a4f', '#f59e0b', '#ef4444', '#94a3b8'],
      tooltip: {
        trigger: 'item',
        backgroundColor: 'rgba(255,255,255,0.96)',
        borderColor: '#e2e8f0',
        borderWidth: 1,
        borderRadius: 8,
        padding: [10, 14],
        textStyle: {
          color: '#1e293b',
          fontSize: 13,
        },
        formatter: (params: { marker: string; name: string; value: number; percent: number }) =>
          `${params.marker} ${params.name}<br/>
           <span  style="font-family:'DIN Alternate',monospace;font-size:18px;font-weight:700">${params.value}</span>
           <span  style="color:var(----color-border-dark)"> (${params.percent}%)</span>`,
      },
      legend: {
        bottom: 0,
        textStyle: { color: '#64748b', fontSize: 12 },
      },
      series: [
        {
          type: 'pie',
          radius: ['48%', '75%'],
          center: ['50%', '46%'],
          avoidLabelOverlap: false,
          itemStyle: {
            borderRadius: 4,
            borderColor: '#fff',
            borderWidth: 3,
          },
          label: { show: false },
          emphasis: {
            label: {
              show: true,
              fontSize: 16,
              fontWeight: 'bold',
            },
            itemStyle: {
              shadowBlur: 20,
              shadowOffsetX: 0,
              shadowColor: 'rgba(0, 0, 0, 0.15)',
              scaleSize: 8,
            },
          },
          data: [
            { value: v.threeRegionsCount, name: '三区三州' },
            { value: v.keyCountyCount, name: '重点帮扶县' },
            { value: v.provincialDemoCount, name: '省级示范' },
            { value: v.crossProvinceCount, name: '跨省帮扶' },
            {
              value: Math.max(0, v.totalVillages - v.threeRegionsCount - v.keyCountyCount),
              name: '其他',
            },
          ],
        },
      ],
    })
  }

  // ── 投入构成饼图（升级版） ──
  if (investmentChart) {
    const inv = statistics.value.investment
    investmentChart.setOption({
      color: ['#2d6a4f', '#1e4d8c', '#f59e0b'],
      tooltip: {
        trigger: 'item',
        backgroundColor: 'rgba(255,255,255,0.96)',
        borderColor: '#e2e8f0',
        borderWidth: 1,
        borderRadius: 8,
        padding: [10, 14],
        textStyle: { color: '#1e293b', fontSize: 13 },
        formatter: (params: { marker: string; name: string; value: number; percent: number }) =>
          `${params.marker} ${params.name}<br/>
           <span  style="font-family:'DIN Alternate',monospace;font-size:18px;font-weight:700">${params.value}万</span>
           <span  style="color:var(----color-border-dark)"> (${params.percent}%)</span>`,
      },
      legend: {
        bottom: 0,
        textStyle: { color: '#64748b', fontSize: 12 },
      },
      series: [
        {
          type: 'pie',
          radius: '62%',
          center: ['50%', '46%'],
          itemStyle: {
            borderRadius: 4,
            borderColor: '#fff',
            borderWidth: 3,
          },
          label: { show: false },
          emphasis: {
            label: {
              show: true,
              fontSize: 16,
              fontWeight: 'bold',
            },
            itemStyle: {
              shadowBlur: 20,
              shadowOffsetX: 0,
              shadowColor: 'rgba(0, 0, 0, 0.15)',
              scaleSize: 8,
            },
          },
          data: [
            { value: inv.industry, name: '产业帮扶' },
            { value: inv.infrastructure, name: '基础设施' },
            { value: inv.education, name: '教育帮扶' },
          ],
        },
      ],
    })
  }

  // ── 年度趋势对比（从后端 API 获取真实历史数据） ──
  if (trendChart) {
    let years: number[] = availableYears.slice().reverse()
    let villagesData: number[] = years.map(() => 0)
    let populationData: number[] = years.map(() => 0)
    let incomeData: number[] = years.map(() => 0)

    try {
      // 后端 years 参数上限 10（ge=1, le=10），超限会 422
      const trendData = (await getYearlyTrends(Math.min(years.length, 10))) as any
      if (trendData && trendData.years) {
        years = trendData.years
        villagesData = trendData.villages ?? villagesData
        populationData = trendData.population ?? populationData
        incomeData = trendData.income ?? incomeData
      }
    } catch (e) {
      logger.warn('年度趋势数据获取失败，使用默认值', e)
    }

    trendChart.setOption({
      color: ['#1e4d8c', '#2d6a4f', '#f59e0b'],
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(255,255,255,0.96)',
        borderColor: '#e2e8f0',
        borderWidth: 1,
        borderRadius: 8,
        padding: [12, 16],
        textStyle: { color: '#1e293b', fontSize: 13 },
        axisPointer: {
          type: 'cross',
          crossStyle: { color: '#94a3b8' },
        },
      },
      legend: {
        data: ['帮扶村数', '覆盖人口(百人)', '人均收入(万)'],
        bottom: 0,
        textStyle: { color: '#64748b', fontSize: 12 },
        itemGap: 24,
      },
      grid: {
        left: 16,
        right: 48,
        top: 20,
        bottom: 40,
      },
      xAxis: {
        type: 'category',
        data: years.map((y) => `${y}年`),
        boundaryGap: false,
        axisLine: { lineStyle: { color: '#e2e8f0' } },
        axisTick: { show: false },
        axisLabel: { color: '#94a3b8', fontSize: 11 },
      },
      yAxis: [
        {
          type: 'value',
          name: '数量',
          nameTextStyle: { color: '#94a3b8', fontSize: 11 },
          splitLine: { lineStyle: { color: '#f1f5f9', type: 'dashed' } },
          axisLabel: { color: '#94a3b8', fontSize: 11 },
        },
        {
          type: 'value',
          name: '收入(万)',
          position: 'right',
          nameTextStyle: { color: '#94a3b8', fontSize: 11 },
          splitLine: { show: false },
          axisLabel: { color: '#94a3b8', fontSize: 11 },
        },
      ],
      series: [
        {
          name: '帮扶村数',
          type: 'bar',
          barWidth: 18,
          itemStyle: {
            borderRadius: [6, 6, 0, 0],
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: '#3b82f6' },
              { offset: 1, color: '#1e4d8c' },
            ]),
          },
          data: villagesData,
        },
        {
          name: '覆盖人口(百人)',
          type: 'bar',
          barWidth: 18,
          itemStyle: {
            borderRadius: [6, 6, 0, 0],
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: '#52b788' },
              { offset: 1, color: '#2d6a4f' },
            ]),
          },
          data: populationData,
        },
        {
          name: '人均收入(万)',
          type: 'line',
          yAxisIndex: 1,
          smooth: true,
          symbol: 'circle',
          symbolSize: 6,
          lineStyle: { width: 3 },
          itemStyle: {
            color: '#f59e0b',
            borderColor: '#fff',
            borderWidth: 2,
          },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(245, 158, 11, 0.2)' },
              { offset: 1, color: 'rgba(245, 158, 11, 0.0)' },
            ]),
          },
          data: incomeData,
        },
      ],
    })
  }

  // ── 更新 Sparkline 微型图 ──
  updateSparklines()
}

// =========================================================================
// Sparkline 更新
// =========================================================================

const updateSparklines = () => {
  const sparkData = [
    {
      chart: sparkVillagesChart,
      data: takeSeries(sparkReal.value.villages),
      config: SPARK_CONFIGS.villages,
    },
    {
      chart: sparkPopulationChart,
      data: takeSeries(sparkReal.value.population),
      config: SPARK_CONFIGS.population,
    },
    {
      chart: sparkIncomeChart,
      data: takeSeries(sparkReal.value.income),
      config: SPARK_CONFIGS.income,
    },
    {
      chart: sparkInvestmentChart,
      data: takeSeries(sparkReal.value.investment),
      config: SPARK_CONFIGS.investment,
    },
  ]

  sparkData.forEach(({ chart, data, config }) => {
    if (chart && !chart.isDisposed()) {
      chart.setOption(createSparkOption(data, config))
    }
  })
}

// =========================================================================
// 数据加载
// =========================================================================

const loadData = async () => {
  loading.value = true
  try {
    const params: Record<string, unknown> = { year: selectedYear.value }
    if (filters.department) params.department = filters.department
    if (filters.regionType === 'isThreeRegions') params.isThreeRegions = true
    if (filters.regionType === 'isKeyCounty') params.isKeyCounty = true

    const result = await getSummaryStatistics(params as Parameters<typeof getSummaryStatistics>[0])

    statistics.value = {
      year: result?.year || selectedYear.value,
      villages: {
        totalVillages: result?.villages?.totalVillages || 0,
        threeRegionsCount: result?.villages?.threeRegionsCount || 0,
        keyCountyCount: result?.villages?.keyCountyCount || 0,
        provincialDemoCount: result?.villages?.provincialDemoCount || 0,
        crossProvinceCount: result?.villages?.crossProvinceCount || 0,
      },
      population: {
        totalPopulation: result?.population?.totalPopulation || 0,
        totalHouseholds: result?.population?.totalHouseholds || 0,
        povertyHouseholds: result?.population?.povertyHouseholds || 0,
      },
      income: {
        avgPerCapitaIncome: result?.income?.avgPerCapitaIncome || 0,
        totalCollectiveIncome: result?.income?.totalCollectiveIncome || 0,
      },
      investment: {
        industry: result?.investment?.industry || 0,
        infrastructure: result?.investment?.infrastructure || 0,
        infrastructureRoadKm: result?.investment?.infrastructureRoadKm || 0,
        education: result?.investment?.education || 0,
        educationAidedStudents: result?.investment?.educationAidedStudents || 0,
      },
    }

    updateCharts()
  } catch (error) {
    logger.error('加载统计数据失败:', error)
    statistics.value = {
      year: selectedYear.value,
      villages: {
        totalVillages: 0,
        threeRegionsCount: 0,
        keyCountyCount: 0,
        provincialDemoCount: 0,
        crossProvinceCount: 0,
      },
      population: {
        totalPopulation: 0,
        totalHouseholds: 0,
        povertyHouseholds: 0,
      },
      income: { avgPerCapitaIncome: 0, totalCollectiveIncome: 0 },
      investment: {
        industry: 0,
        infrastructure: 0,
        infrastructureRoadKm: 0,
        education: 0,
        educationAidedStudents: 0,
      },
    }
  } finally {
    loading.value = false
  }
}

const loadFilterOptions = async () => {
  try {
    filterOptions.value = await getFilterOptions()
  } catch (error) {
    logger.error('加载筛选选项失败:', error)
  }
}

// =========================================================================
// 图表初始化与销毁
// =========================================================================

const initCharts = () => {
  // 销毁旧实例（防止热更新重复初始化）
  regionChart?.dispose()
  investmentChart?.dispose()
  trendChart?.dispose()
  sparkVillagesChart?.dispose()
  sparkPopulationChart?.dispose()
  sparkIncomeChart?.dispose()
  sparkInvestmentChart?.dispose()

  regionChart = null
  investmentChart = null
  trendChart = null
  sparkVillagesChart = null
  sparkPopulationChart = null
  sparkIncomeChart = null
  sparkInvestmentChart = null

  // 主图表
  if (regionChartRef.value) {
    regionChart = echarts.init(regionChartRef.value, getCurrentTheme())
    regionChart.on('click', handleRegionClick as any)
  }
  if (investmentChartRef.value) {
    investmentChart = echarts.init(investmentChartRef.value, getCurrentTheme())
  }
  if (trendChartRef.value) {
    trendChart = echarts.init(trendChartRef.value, getCurrentTheme())
  }

  // Sparkline 微型图
  if (sparkVillagesRef.value) {
    sparkVillagesChart = echarts.init(sparkVillagesRef.value, getCurrentTheme())
  }
  if (sparkPopulationRef.value) {
    sparkPopulationChart = echarts.init(sparkPopulationRef.value, getCurrentTheme())
  }
  if (sparkIncomeRef.value) {
    sparkIncomeChart = echarts.init(sparkIncomeRef.value, getCurrentTheme())
  }
  if (sparkInvestmentRef.value) {
    sparkInvestmentChart = echarts.init(sparkInvestmentRef.value, getCurrentTheme())
  }
}

// =========================================================================
// 事件处理
// =========================================================================

const handleRegionClick = async (params: { name: string }) => {
  try {
    drillDownTitle.value = `${params.name} - 详细数据`
    drillDownData.value = await drillDown({
      // 后端钻取维度为 province（非 region）
      dimension: 'province',
      value: params.name,
      targetDimension: 'department',
    })
  } catch (error) {
    logger.error('钻取查询失败:', error)
  }
}

const closeDrillDown = () => {
  drillDownData.value = null
}

const handleExport = () => {
  const exportData = {
    year: selectedYear.value,
    statistics: statistics.value,
    filters: { ...filters },
    exportTime: new Date().toISOString(),
  }
  const blob = new Blob([JSON.stringify(exportData, null, 2)], {
    type: 'application/json',
  })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `仪表板数据_${selectedYear.value}.json`
  a.click()
  URL.revokeObjectURL(url)
}

const handleResize = () => {
  regionChart?.resize()
  investmentChart?.resize()
  trendChart?.resize()
  sparkVillagesChart?.resize()
  sparkPopulationChart?.resize()
  sparkIncomeChart?.resize()
  sparkInvestmentChart?.resize()
}

// =========================================================================
// 生命周期
// =========================================================================

onMounted(async () => {
  await loadFilterOptions()
  await nextTick()
  initCharts()
  await loadData()
  await fetchKpiTrends()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  regionChart?.dispose()
  investmentChart?.dispose()
  trendChart?.dispose()
  sparkVillagesChart?.dispose()
  sparkPopulationChart?.dispose()
  sparkIncomeChart?.dispose()
  sparkInvestmentChart?.dispose()

  regionChart = null
  investmentChart = null
  trendChart = null
  sparkVillagesChart = null
  sparkPopulationChart = null
  sparkIncomeChart = null
  sparkInvestmentChart = null
})
</script>

<style lang="scss" scoped>
.analytics-dashboard {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 20px;
}

.stat-row {
  margin-bottom: 0;
}

.stat-trend--up {
  color: $color-success;
}

.stat-trend--down {
  color: $color-danger;
}

.stat-trend--flat {
  color: $color-info;
}

.trend-tag--up {
  color: $color-success;
  background: var(--color-success-lightest);
}

.trend-tag--down {
  color: $color-danger;
  background: var(--color-danger-lightest);
}

.trend-tag--flat {
  color: $color-info;
  background: var(--color-info-lightest);
}
</style>
