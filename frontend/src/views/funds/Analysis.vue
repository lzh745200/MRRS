<template>
  <div class="fund-analysis">
    <!-- 维度切换 Tab -->
    <el-card class="filter-card">
      <div style="display: flex; align-items: center; gap: 20px; margin-bottom: 12px">
        <span style="font-weight: 600; color: #1b4332">分析维度：</span>
        <el-radio-group v-model="dimension" @change="handleDimensionChange">
          <el-radio-button value="period">时间维度</el-radio-button>
          <el-radio-button value="type">类型维度</el-radio-button>
          <el-radio-button value="source">来源维度</el-radio-button>
          <el-radio-button value="status">状态维度</el-radio-button>
        </el-radio-group>
      </div>
      <el-form :model="filterForm" inline>
        <el-form-item v-if="dimension === 'period'" label="时间粒度">
          <el-select v-model="filterForm.periodType" style="width: 120px" @change="handleSearch">
            <el-option label="月度" value="monthly" />
            <el-option label="季度" value="quarterly" />
            <el-option label="年度" value="yearly" />
          </el-select>
        </el-form-item>
        <el-form-item label="年份范围">
          <el-select v-model="filterForm.yearStart" placeholder="起始年份" style="width: 120px">
            <el-option v-for="y in yearOptions" :key="'s' + y" :label="`${y}年`" :value="y" />
          </el-select>
          <span style="margin: 0 8px">至</span>
          <el-select v-model="filterForm.yearEnd" placeholder="结束年份" style="width: 120px">
            <el-option v-for="y in yearOptions" :key="'e' + y" :label="`${y}年`" :value="y" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch"
            ><el-icon><Search /></el-icon>查询</el-button
          >
          <el-button @click="handleExportStats"
            ><el-icon><Download /></el-icon>导出统计</el-button
          >
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 汇总统计卡片 -->
    <el-card class="overview-card">
      <template #header>
        <span class="title">经费使用分析</span>
      </template>
      <el-row :gutter="20">
        <el-col :span="6">
          <div class="stat-box">
            <div class="stat-value">{{ summary.total }}</div>
            <div class="stat-label">总经费（万元）</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-box">
            <div class="stat-value">{{ summary.used }}</div>
            <div class="stat-label">已使用（万元）</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-box">
            <div class="stat-value">{{ summary.remain }}</div>
            <div class="stat-label">剩余（万元）</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-box">
            <div class="stat-value">{{ summary.rate }}%</div>
            <div class="stat-label">使用率</div>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <!-- 多维度统计图表 -->
    <el-row :gutter="20">
      <el-col :span="12">
        <el-card class="chart-card">
          <template #header><span class="title">分布图</span></template>
          <BaseChart :option="pieChartOption" height="300px" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card class="chart-card">
          <template #header><span class="title">利用率分析</span></template>
          <BaseChart :option="barChartOption" height="300px" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 年度趋势图表 -->
    <el-row :gutter="20">
      <el-col :span="12">
        <el-card class="chart-card">
          <template #header><span class="title">年度经费趋势</span></template>
          <BaseChart v-if="yearlyTrendAreaOption" :option="yearlyTrendAreaOption" height="300px" />
          <el-empty v-else description="暂无年度趋势数据" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card class="chart-card">
          <template #header><span class="title">利用率趋势</span></template>
          <BaseChart
            v-if="utilizationTrendOption"
            :option="utilizationTrendOption"
            height="300px"
          />
          <el-empty v-else description="暂无利用率趋势数据" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 年度对比图表 -->
    <YearlyComparisonChart
      ref="yearlyChartRef"
      :year-start="filterForm.yearStart"
      :year-end="filterForm.yearEnd"
      :department="filterForm.department"
      style="margin-top: 20px"
    />

    <!-- 统计明细表格 -->
    <el-card class="ranking-card">
      <template #header><span class="title">统计明细</span></template>
      <el-table :data="dimensionData" stripe border>
        <el-table-column type="index" label="序号" width="70" align="center" />
        <el-table-column prop="label" label="分组" min-width="160" />
        <el-table-column prop="count" label="记录数" width="100" align="center" />
        <el-table-column prop="total_amount" label="总金额(万元)" width="130" align="right">
          <template #default="{ row }">{{
            row.total_amount?.toLocaleString('zh-CN', {
              minimumFractionDigits: 2,
            })
          }}</template>
        </el-table-column>
        <el-table-column prop="total_allocated" label="已拨付(万元)" width="130" align="right">
          <template #default="{ row }">{{
            row.total_allocated?.toLocaleString('zh-CN', {
              minimumFractionDigits: 2,
            })
          }}</template>
        </el-table-column>
        <el-table-column prop="total_used" label="已使用(万元)" width="130" align="right">
          <template #default="{ row }">{{
            row.total_used?.toLocaleString('zh-CN', {
              minimumFractionDigits: 2,
            })
          }}</template>
        </el-table-column>
        <el-table-column prop="utilization_rate" label="利用率" width="120" align="center">
          <template #default="{ row }">
            <el-progress
              :percentage="row.utilization_rate"
              :status="
                row.utilization_rate >= 90
                  ? 'success'
                  : row.utilization_rate >= 60
                    ? 'warning'
                    : 'exception'
              "
            />
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { logger } from '@/utils/logger'
import { chartColorPrimary, chartColor } from '@/utils/chartColors'

import { ref, reactive, computed, onMounted } from 'vue'
import { Search, Download } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import BaseChart from '@/components/common/BaseChart.vue'
import YearlyComparisonChart from '@/components/funds/YearlyComparisonChart.vue'
import type { EChartsOption } from 'echarts'
import { useFundsStore } from '@/stores/funds'
import { fundApi } from '@/api/funds'
import {
  getFundStatisticsByType,
  getYearlyFundComparison,
  type FundStatistics,
  type YearlyFundSummary,
} from '@/api/fundStatistics'
import { exportUtil } from '@/utils/exportUtil'

const fundsStore = useFundsStore()
const yearlyChartRef = ref()

const currentYear = new Date().getFullYear()
const yearOptions = Array.from({ length: currentYear - 2000 + 2 }, (_, i) => 2000 + i)

const dimension = ref<string>('period')

const filterForm = reactive({
  yearStart: currentYear - 5,
  yearEnd: currentYear,
  department: '',
  periodType: 'yearly',
})

// 多维度统计数据
const dimensionData = ref<any[]>([])
const fundStatsByType = ref<Record<string, FundStatistics>>({})
// 年度趋势数据
const yearlyTrend = ref<YearlyFundSummary[]>([])

const summary = computed(() => {
  const total = Number(fundsStore.totalFunds) || 0
  const used = Number(fundsStore.usedFunds) || 0
  const remain = Math.max(0, total - used)
  const rate = total > 0 ? parseFloat(((used / total) * 100).toFixed(2)) : 0
  return { total, used, remain, rate }
})

// 饼图
const pieChartOption = computed<EChartsOption>(() => {
  const rawData = dimensionData.value || []
  const data = rawData.map((d) => ({
    value: Number(d.total_amount) || 0,
    name: d.label || '未知',
  }))
  const colors = [
    '#40916c',
    '#2d6a4f',
    '#1b4332',
    '#d4af37',
    '#b8860b',
    '#8b6914',
    chartColorPrimary(),
    chartColor('warning'),
  ]
  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c}万元 ({d}%)' },
    legend: { orient: 'vertical', left: 'left' },
    series: [
      {
        name: '分布',
        type: 'pie',
        radius: '60%',
        data: data.length ? data : [{ value: 0, name: '无数据' }],
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0,0,0,0.5)',
          },
        },
        itemStyle: { color: (p: any) => colors[p.dataIndex % colors.length] },
      },
    ],
  }
})

// 柱状图
const barChartOption = computed<EChartsOption>(() => {
  const rawData = dimensionData.value || []
  const labels = rawData.map((d) => d.label || '未知')
  const rates = rawData.map((d) => Number(d.utilization_rate) || 0)
  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: '{b}: {c}%',
    },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'value', max: 100, axisLabel: { formatter: '{value}%' } },
    yAxis: { type: 'category', data: labels.length ? labels : ['无数据'] },
    series: [
      {
        name: '利用率',
        type: 'bar',
        data: rates.length ? rates : [0],
        itemStyle: {
          color: (p: any) => (p.value >= 90 ? '#67c23a' : p.value >= 60 ? '#e6a23c' : '#f56c6c'),
        },
        label: { show: true, position: 'right', formatter: '{c}%' },
      },
    ],
  }
})

// 年度经费趋势面积图
const yearlyTrendAreaOption = computed<EChartsOption | null>(() => {
  const data = yearlyTrend.value
  if (!data.length) return null
  const years = data.map((d) => `${d.year}年`)
  const totals = data.map(
    (d) => Number(d.total_actual ?? (d.total_military || 0) + (d.total_local || 0)) || 0
  )
  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
    },
    legend: { data: ['经费总额'] },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', boundaryGap: false, data: years },
    yAxis: { type: 'value', name: '万元' },
    series: [
      {
        name: '经费总额',
        type: 'line',
        smooth: true,
        symbolSize: 7,
        data: totals,
        lineStyle: { width: 2, color: '#40916c' },
        itemStyle: { color: '#40916c' },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(64, 145, 108, 0.45)' },
              { offset: 1, color: 'rgba(64, 145, 108, 0.05)' },
            ],
          },
        },
      },
    ],
  }
})

// 利用率趋势折线图
const utilizationTrendOption = computed<EChartsOption | null>(() => {
  const data = yearlyTrend.value
  if (!data.length) return null
  const years = data.map((d) => `${d.year}年`)
  const rates = data.map((d) => Number(d.utilization_rate) || 0)
  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
    },
    legend: { data: ['利用率'] },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', boundaryGap: false, data: years },
    yAxis: { type: 'value', max: 100, axisLabel: { formatter: '{value}%' } },
    series: [
      {
        name: '利用率',
        type: 'line',
        smooth: true,
        symbolSize: 8,
        data: rates,
        lineStyle: { width: 2, color: '#b8960c' },
        itemStyle: { color: '#b8960c' },
        label: { show: true, formatter: '{c}%' },
      },
    ],
  }
})

// 加载多维度统计
const loadDimensionStats = async () => {
  try {
    const params: Record<string, any> = {
      group_by: dimension.value,
      start_date: `${filterForm.yearStart}-01-01`,
      end_date: `${filterForm.yearEnd}-12-31`,
    }
    if (dimension.value === 'period') {
      params.period_type = filterForm.periodType
    }
    const res = await fundApi.statisticsMultiDimension(params)
    if (res?.success) {
      dimensionData.value = res.data || []
    }
  } catch (error) {
    logger.error('加载统计数据失败:', error)
    ElMessage.error('加载统计数据失败，请稍后重试')
  }
}

const loadFundStatsByType = async () => {
  try {
    const res = await getFundStatisticsByType({
      year_start: filterForm.yearStart,
      year_end: filterForm.yearEnd,
      department: filterForm.department || undefined,
    })
    if (res.success) {
      fundStatsByType.value = res.data
    }
  } catch (error) {
    logger.error('加载经费分类统计失败:', error)
    ElMessage.error('加载经费分类统计失败，请稍后重试')
  }
}

const loadYearlyTrend = async () => {
  try {
    const res = await getYearlyFundComparison({
      year_start: filterForm.yearStart,
      year_end: filterForm.yearEnd,
      department: filterForm.department || undefined,
    })
    if (res?.success) {
      yearlyTrend.value = res.data || []
    }
  } catch (error) {
    logger.error('加载年度趋势数据失败:', error)
    ElMessage.error('加载年度趋势数据失败，请稍后重试')
  }
}

function handleDimensionChange() {
  // 切换维度时清除旧数据，避免图表用错误格式的数据渲染
  dimensionData.value = []
  loadDimensionStats()
}

const handleSearch = () => {
  loadDimensionStats()
  loadFundStatsByType()
  loadYearlyTrend()
  yearlyChartRef.value?.refresh()
}

function handleExportStats() {
  if (!dimensionData.value.length) {
    ElMessage.warning('没有可导出的数据')
    return
  }
  exportUtil.exportToCSV(dimensionData.value, '经费统计分析', {
    label: '分组',
    count: '记录数',
    total_amount: '总金额(万元)',
    total_allocated: '已拨付(万元)',
    total_used: '已使用(万元)',
    utilization_rate: '利用率(%)',
  })
  // 导出成功 — 浏览器已确认
}

onMounted(() => {
  fundsStore.fetchFunds()
  loadDimensionStats()
  loadFundStatsByType()
  loadYearlyTrend()
})
</script>

<style scoped>
.fund-analysis {
  padding: 20px;
}

.filter-card {
  margin-bottom: 20px;
  background: white;
  border-radius: 8px;
}

.overview-card,
.chart-card,
.ranking-card {
  margin-bottom: 20px;
  background: rgba(10, 30, 20, 0.5);
  border: 1px solid rgba(64, 145, 108, 0.3);
}

.title {
  font-size: 16px;
  font-weight: bold;
  color: #fff;
}

.stat-box {
  text-align: center;
  padding: 20px;
  background: rgba(64, 145, 108, 0.1);
  border-radius: 8px;
  border: 1px solid rgba(64, 145, 108, 0.3);
}

.stat-value {
  font-size: 32px;
  font-weight: bold;
  color: #40916c;
  margin-bottom: 8px;
}

.stat-label {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.7);
}

:deep(.el-card__header) {
  background: linear-gradient(135deg, #2d6a4f 0%, #1b4332 100%);
  border-bottom: 1px solid rgba(64, 145, 108, 0.3);
  color: #fff;
}
</style>
