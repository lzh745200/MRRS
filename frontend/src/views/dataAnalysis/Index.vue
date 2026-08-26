<template>
  <div class="data-analysis-page">
    <div class="page-header">
      <div>
        <h2 class="page-title">数据统计分析</h2>
        <p class="page-desc">帮扶项目数据多维度统计与分析</p>
      </div>
      <el-button :loading="loading" type="primary" plain @click="loadAnalysisData">
        <el-icon><Refresh /></el-icon>
        刷新数据
      </el-button>
    </div>

    <div class="stats-row">
      <div class="stat-card">
        <div class="stat-value">{{ overview.total_villages }}</div>
        <div class="stat-label">帮扶村总数</div>
      </div>
      <div class="stat-card">
        <div class="stat-value text-primary">{{ overview.total_investment }}万</div>
        <div class="stat-label">总投入资金</div>
      </div>
      <div class="stat-card">
        <div class="stat-value text-success">{{ overview.completeness }}%</div>
        <div class="stat-label">数据完整率</div>
      </div>
      <div class="stat-card">
        <div class="stat-value text-warning">
          {{ overview.active_projects }}
        </div>
        <div class="stat-label">进行中项目</div>
      </div>
    </div>

    <el-card>
      <el-tabs v-model="activeTab" type="border-card">
        <el-tab-pane label="投入分析" name="investment">
          <div class="analysis-content">
            <h3>经费投入趋势</h3>
            <el-table :data="investmentTrend" border>
              <el-table-column prop="year" label="年份" width="100" />
              <el-table-column prop="military" label="专项投入(万)" align="right" />
              <el-table-column prop="local" label="地方投入(万)" align="right" />
              <el-table-column prop="total" label="合计(万)" align="right" />
              <el-table-column prop="growth" label="增长率" width="100">
                <template #default="{ row }">
                  <span :style="{ color: row.growth >= 0 ? '#40916c' : 'var(--color-danger)' }"
                    >{{ row.growth >= 0 ? '+' : '' }}{{ row.growth }}%</span
                  >
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-tab-pane>

        <el-tab-pane label="帮扶分类统计" name="category">
          <div class="analysis-content">
            <h3>各类帮扶项目统计</h3>
            <el-table :data="categoryStats" border>
              <el-table-column prop="category" label="帮扶类型" min-width="120" />
              <el-table-column prop="count" label="项目数" width="100" align="right" />
              <el-table-column prop="investment" label="投入(万)" width="120" align="right" />
              <el-table-column prop="beneficiaries" label="受益人数" width="120" align="right" />
              <el-table-column prop="ratio" label="占比" width="100">
                <template #default="{ row }">
                  <el-progress :percentage="row.ratio" :stroke-width="6" :color="'#40916c'" />
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-tab-pane>

        <el-tab-pane label="地区分布" name="region">
          <div class="analysis-content">
            <h3>帮扶村地区分布</h3>
            <el-table :data="regionStats" border>
              <el-table-column prop="region" label="地区" min-width="120" />
              <el-table-column prop="villages" label="帮扶村数" width="100" align="right" />
              <el-table-column prop="investment" label="总投入(万)" width="120" align="right" />
              <el-table-column prop="avgIncome" label="人均收入(元)" width="120" align="right" />
            </el-table>
          </div>
        </el-tab-pane>

        <el-tab-pane label="年度对比" name="yearly">
          <div class="analysis-content">
            <h3>年度关键指标对比</h3>
            <div style="margin-bottom: 16px; display: flex; align-items: center; gap: 8px">
              <span>对比年份：</span>
              <el-select v-model="compareYearA" style="width: 110px">
                <el-option v-for="y in yearOptions" :key="'a' + y" :label="`${y}年`" :value="y" />
              </el-select>
              <span>vs</span>
              <el-select v-model="compareYearB" style="width: 110px">
                <el-option v-for="y in yearOptions" :key="'b' + y" :label="`${y}年`" :value="y" />
              </el-select>
            </div>
            <EmptyState
              v-if="!yearlyComparison.years.length"
              text="暂无年度数据，请先在帮扶村年度数据管理中录入数据"
              :size="80"
            />
            <template v-else>
              <el-descriptions :column="2" border>
                <el-descriptions-item :label="`${compareYearA}年帮扶村总数`">{{
                  comparisonA.villages
                }}</el-descriptions-item>
                <el-descriptions-item :label="`${compareYearB}年帮扶村总数`">{{
                  comparisonB.villages
                }}</el-descriptions-item>
                <el-descriptions-item :label="`${compareYearA}年总投入(万元)`">{{
                  comparisonA.investment
                }}</el-descriptions-item>
                <el-descriptions-item :label="`${compareYearB}年总投入(万元)`">{{
                  comparisonB.investment
                }}</el-descriptions-item>
                <el-descriptions-item :label="`${compareYearA}年人均收入(万元)`">{{
                  comparisonA.income
                }}</el-descriptions-item>
                <el-descriptions-item :label="`${compareYearB}年人均收入(万元)`">{{
                  comparisonB.income
                }}</el-descriptions-item>
              </el-descriptions>
              <!-- 年度投入对比柱状图 -->
              <div ref="compareChartRef" class="compare-chart"></div>
            </template>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import EmptyState from '@/components/business/EmptyState/EmptyState.vue'
import { logger } from '@/utils/logger'
import { getYearOptions } from '@/utils/yearOptions'

import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { get } from '@/api/request'
import echarts from '@/utils/echarts'

const activeTab = ref('investment')
const loading = ref(false)

const overview = ref({
  total_villages: 0,
  total_investment: 0,
  completeness: 0,
  active_projects: 0,
})
const investmentTrend = ref<any[]>([])
const categoryStats = ref<any[]>([])
const regionStats = ref<any[]>([])

const currentYear = new Date().getFullYear()
// 对比年份范围：2000 ~ 当前年+10（滚动窗口，见 utils/yearOptions）
const yearOptions = getYearOptions({ descending: false })
const compareYearA = ref(currentYear - 1)
const compareYearB = ref(currentYear)
// 后端返回按年份聚合的指标：{ years: string[], villages: {}, investment: {}, income: {} }
const yearlyComparison = ref<{
  years: string[]
  villages: Record<string, number>
  investment: Record<string, number>
  income: Record<string, number>
}>({ years: [], villages: {}, investment: {}, income: {} })

// 按所选年份取指标（无数据时显示 '-'）
const comparisonA = computed(() => pickYear(compareYearA.value))
const comparisonB = computed(() => pickYear(compareYearB.value))

function pickYear(year: number) {
  const y = String(year)
  return {
    villages: yearlyComparison.value.villages[y] ?? '-',
    investment: yearlyComparison.value.investment[y] ?? '-',
    income: yearlyComparison.value.income[y] ?? '-',
  }
}

// ── 年度投入对比柱状图 ──
const compareChartRef = ref<HTMLElement | null>(null)
let compareChart: ReturnType<typeof echarts.init> | null = null

function renderCompareChart() {
  if (!compareChartRef.value || !yearlyComparison.value.years.length) return
  if (!compareChart) {
    compareChart = echarts.init(compareChartRef.value)
  }
  const years = [...yearlyComparison.value.years].sort()
  compareChart.setOption(
    {
      tooltip: { trigger: 'axis' },
      legend: { data: ['总投入(万元)', '人均收入(万元)'], bottom: 0 },
      grid: { left: '3%', right: '4%', top: 30, bottom: 40, containLabel: true },
      xAxis: { type: 'category', data: years.map((y) => `${y}年`) },
      yAxis: [
        { type: 'value', name: '万元' },
        { type: 'value', name: '万元' },
      ],
      series: [
        {
          name: '总投入(万元)',
          type: 'bar',
          barMaxWidth: 36,
          data: years.map((y) => yearlyComparison.value.investment[y] ?? 0),
          itemStyle: { color: '#40916c' },
        },
        {
          name: '人均收入(万元)',
          type: 'line',
          smooth: true,
          yAxisIndex: 1,
          data: years.map((y) => yearlyComparison.value.income[y] ?? 0),
          itemStyle: { color: '#d4af37' },
        },
      ],
    },
    { notMerge: true }
  )
}

function handleChartResize() {
  compareChart?.resize()
}

watch(
  () => [compareYearA.value, compareYearB.value, yearlyComparison.value.years],
  async () => {
    await nextTick()
    renderCompareChart()
  }
)

async function loadAnalysisData() {
  loading.value = true
  try {
    const res: any = await get('/statistics/analysis')
    // get() 已自动解包信封，后端返回裸对象 → 直接用 res（避免 res?.data 双重解包导致恒空）
    const data =
      res?.data &&
      typeof res.data === 'object' &&
      !Array.isArray(res.data) &&
      'overview' in res.data
        ? res.data
        : (res ?? {})
    overview.value = data.overview || overview.value
    // 处理后端返回小数形式的完整率（如 0.85 → 85）
    if (overview.value.completeness > 0 && overview.value.completeness <= 1) {
      overview.value.completeness = Math.round(overview.value.completeness * 100)
    }
    investmentTrend.value = data.investment_trend || []
    categoryStats.value = data.category_stats || []
    regionStats.value = data.region_stats || []
    if (data.yearly_comparison) {
      const yc = data.yearly_comparison
      yearlyComparison.value = {
        years: Array.isArray(yc.years) ? yc.years : Object.keys(yc.villages || {}),
        villages: yc.villages || {},
        investment: yc.investment || {},
        income: yc.income || {},
      }
    }
  } catch (e) {
    logger.error('加载分析数据失败:', e)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadAnalysisData()
  window.addEventListener('resize', handleChartResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleChartResize)
  if (compareChart) {
    compareChart.dispose()
    compareChart = null
  }
})
</script>

<style scoped>
.data-analysis-page {
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
  margin: 0 0 4px;
}
.page-desc {
  font-size: 14px;
  color: var(--color-text-secondary);
  margin: 0;
}
.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}
.stat-card {
  background: white;
  padding: 20px;
  border-radius: 8px;
  text-align: center;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
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
  color: var(--color-primary-light-1);
}
.stat-value.text-warning {
  color: var(--color-warning);
}
.stat-label {
  font-size: 14px;
  color: var(--color-text-secondary);
  margin-top: 4px;
}
.analysis-content {
  padding: 16px 0;
}
.analysis-content h3 {
  margin: 0 0 16px;
  font-size: 16px;
  color: var(--color-primary-dark-1);
}
.compare-chart {
  width: 100%;
  height: 300px;
  margin-top: 16px;
}
</style>
