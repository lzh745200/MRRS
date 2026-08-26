<template>
  <!-- 单根包裹（display:contents）：避免 transition 内多根导致 setAttribute('0') 崩溃 -->
  <div style="display: contents">
    <div v-loading="loading" class="village-detail-page">
      <!-- 页面头部 -->
      <div class="page-header">
        <div class="header-info">
          <el-button text @click="handleBack">
            <el-icon><ArrowLeft /></el-icon>返回列表
          </el-button>
          <h2 class="page-title">{{ pageTitle }}</h2>
        </div>
        <div v-if="pageMode === 'view'" class="header-actions">
          <el-button @click="handleEdit">
            <el-icon><Edit /></el-icon>编辑
          </el-button>
          <el-button type="primary" @click="handleYearlyData">
            <el-icon><Calendar /></el-icon>年度数据
          </el-button>
          <el-button @click="openChangeHistory">变更历史</el-button>
        </div>
      </div>

      <!-- 编辑 / 创建模式 -->
      <template v-if="pageMode === 'edit' || pageMode === 'create'">
        <div class="info-card">
          <SupportedVillageForm
            :village="village"
            :mode="pageMode"
            @submit="handleFormSubmit"
            @cancel="handleFormCancel"
          />
        </div>
      </template>

      <!-- 查看模式 -->
      <template v-if="pageMode === 'view' && village">
        <!-- 基本信息卡片 -->
        <div class="info-card">
          <h3 class="card-title">基本信息</h3>
          <el-descriptions :column="3" border>
            <el-descriptions-item label="序号">{{
              village.sequenceNo || '-'
            }}</el-descriptions-item>
            <el-descriptions-item label="部门">{{ village.department }}</el-descriptions-item>
            <el-descriptions-item label="帮扶单位">{{ village.supportUnit }}</el-descriptions-item>
            <el-descriptions-item label="帮扶村名称">{{
              village.villageName
            }}</el-descriptions-item>
            <el-descriptions-item label="地区范围">{{
              village.regionScope || '-'
            }}</el-descriptions-item>
            <el-descriptions-item label="振兴梯队">{{
              village.isRevitalizationTier ? '是' : '否'
            }}</el-descriptions-item>
          </el-descriptions>
        </div>

        <!-- 属性标签卡片 -->
        <div class="info-card">
          <h3 class="card-title">属性标签</h3>
          <div class="tag-sections">
            <div class="tag-section">
              <span class="section-label">地域属性：</span>
              <div class="tag-list">
                <el-tag v-if="village.isThreeRegions" type="danger">三区三州</el-tag>
                <el-tag v-if="village.isBorderArea" type="warning">边疆地区</el-tag>
                <el-tag v-if="village.isEthnicArea" type="info">民族地区</el-tag>
                <el-tag v-if="village.isRevolutionaryArea" type="success">革命地区</el-tag>
                <el-tag v-if="village.isKeyCounty">重点帮扶县</el-tag>
                <span v-if="!hasRegionTags" class="no-data">无</span>
              </div>
            </div>
            <div class="tag-section">
              <span class="section-label">振兴属性：</span>
              <div class="tag-list">
                <el-tag v-if="village.isRevitalizationTier" type="danger">振兴梯队</el-tag>
                <el-tag v-if="village.isProvincialDemo" type="success">省级示范</el-tag>
                <el-tag v-if="village.isHundredVillageDemo" type="primary">百村示范</el-tag>
                <el-tag v-if="village.isTieredDevelopment">梯次发展</el-tag>
                <span v-if="!hasRevitalizationTags" class="no-data">无</span>
              </div>
            </div>
            <div class="tag-section">
              <span class="section-label">跨域帮扶：</span>
              <div class="tag-list">
                <el-tag v-if="village.isCrossProvince" type="danger">跨省帮扶</el-tag>
                <el-tag v-if="village.isCrossCity" type="warning">跨市帮扶</el-tag>
                <span v-if="!village.isCrossProvince && !village.isCrossCity" class="no-data"
                  >无</span
                >
              </div>
            </div>
            <div class="tag-section">
              <span class="section-label">协作情况：</span>
              <div class="tag-list">
                <el-tag v-if="village.isCrossUnitCooperation" type="info">跨单位协作</el-tag>
                <el-tag v-if="village.isInOverallPlan" type="success">纳入总盘子</el-tag>
                <span
                  v-if="!village.isCrossUnitCooperation && !village.isInOverallPlan"
                  class="no-data"
                  >无</span
                >
              </div>
            </div>
          </div>
        </div>

        <!-- 表彰情况 -->
        <div v-if="village.honors" class="info-card">
          <h3 class="card-title">表彰情况</h3>
          <p class="honors-text">{{ village.honors }}</p>
        </div>

        <!-- 年度数据概览 -->
        <div class="info-card">
          <h3 class="card-title">
            {{ selectedYear }}年数据概览
            <el-select
              v-model="selectedYear"
              size="small"
              style="width: 100px; margin-left: 12px"
              @change="loadYearlyData"
            >
              <el-option
                v-for="year in availableYears"
                :key="year"
                :label="`${year}年`"
                :value="year"
              />
            </el-select>
          </h3>
          <el-row v-loading="yearlyLoading" :gutter="20">
            <el-col :span="6">
              <div class="stat-card">
                <div class="stat-value">
                  {{ yearlyData?.population?.totalPopulation || 0 }}
                </div>
                <div class="stat-label">总人口(人)</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="stat-card">
                <div class="stat-value">
                  {{ format.formatMoney4(yearlyData?.income?.perCapitaIncome) }}
                </div>
                <div class="stat-label">人均收入(万元)</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="stat-card">
                <div class="stat-value">
                  {{ format.formatMoney4(yearlyData?.income?.collectiveIncome) }}
                </div>
                <div class="stat-label">集体收入(万元)</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="stat-card">
                <div class="stat-value">{{ format.formatMoney4(totalInvestment) }}</div>
                <div class="stat-label">帮扶投入(万元)</div>
              </div>
            </el-col>
          </el-row>
        </div>

        <!-- 多年趋势图 -->
        <div class="info-card">
          <h3 class="card-title">人均收入多年趋势</h3>
          <div ref="trendChartRef" class="trend-chart"></div>
        </div>
      </template>
    </div>

    <ChangeHistoryDialog
      v-model:visible="changeHistoryVisible"
      :history="changeHistory"
      :loading="changeHistoryLoading"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { useRouterSafe, safeRouteParam } from '@/composables/useRouterSafe'
import { ArrowLeft, Edit, Calendar } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import ChangeHistoryDialog from '@/components/common/ChangeHistoryDialog.vue'
import { getChangeHistory } from '@/api/supportedVillage'
import { logger } from '@/utils/logger'
import { format } from '@/utils'
import echarts from '@/utils/echarts'

const changeHistoryVisible = ref(false)
const changeHistoryLoading = ref(false)
const changeHistory = ref<any[]>([])

async function openChangeHistory() {
  changeHistoryVisible.value = true
  changeHistoryLoading.value = true
  try {
    const res: any = await getChangeHistory(safeRouteParam(route.params.id))
    const items = res?.items || res?.data?.items || res || []
    // 后端结构 {timestamp, username, action, changes[]} → 弹窗结构 {time, action, user}
    changeHistory.value = Array.isArray(items)
      ? items.map((item: any) => ({
          time: item.timestamp || item.time || '',
          action: item.action || 'update',
          user: item.username || item.user || '未知用户',
          changes: Array.isArray(item?.changes) ? item.changes : [],
        }))
      : []
  } catch {
    ElMessage.error('加载变更历史失败')
  } finally {
    changeHistoryLoading.value = false
  }
}

import {
  getSupportedVillage,
  getYearlyData,
  createSupportedVillage,
  updateSupportedVillage,
  saveTransitionFunding,
} from '@/api/supportedVillage'
import type { SupportedVillage, SupportedVillageCreate, YearlyDataSummary } from '@/types/analytics'
import SupportedVillageForm from './components/SupportedVillageForm.vue'

const route = useRoute()
const { pushSafe } = useRouterSafe()

const loading = ref(false)
const yearlyLoading = ref(false)
const village = ref<SupportedVillage | null>(null)
const yearlyData = ref<YearlyDataSummary | null>(null)

const currentYear = new Date().getFullYear()
const availableYears = Array.from({ length: 6 }, (_, i) => currentYear - i + 1)
const selectedYear = ref(currentYear)

// 页面模式：根据路由自动判断
const pageMode = computed(() => {
  const path = route.path
  if (path.endsWith('/edit') || route.query.mode === 'edit') return 'edit'
  if (path.includes('/create') || !route.params.id) return 'create'
  return 'view'
})

const pageTitle = computed(() => {
  if (pageMode.value === 'create') return '新增帮扶村'
  if (pageMode.value === 'edit') return `编辑 - ${village.value?.villageName || '帮扶村'}`
  return village.value?.villageName || '帮扶村详情'
})

const hasRegionTags = computed(() => {
  if (!village.value) return false
  return (
    village.value.isThreeRegions ||
    village.value.isBorderArea ||
    village.value.isEthnicArea ||
    village.value.isRevolutionaryArea ||
    village.value.isKeyCounty
  )
})

const hasRevitalizationTags = computed(() => {
  if (!village.value) return false
  return (
    village.value.isRevitalizationTier ||
    village.value.isProvincialDemo ||
    village.value.isHundredVillageDemo ||
    village.value.isTieredDevelopment
  )
})

const totalInvestment = computed(() => {
  if (!yearlyData.value) return 0
  const d: any = yearlyData.value
  let total = 0
  // 后端 yearly 接口按 section 原始 key 返回（industry/infrastructure/education 等）
  if (d.industry) total += Number(d.industry.investment) || 0
  if (d.infrastructure) total += Number(d.infrastructure.investment) || 0
  if (d.education) total += Number(d.education.investment) || 0
  if (d.medical) total += Number(d.medical.investment) || 0
  if (d['party-building']) total += Number(d['party-building'].investment) || 0
  if (d.consumption) total += Number(d.consumption.villageProductsPurchase) || 0
  return total
})

// ==================== 多年趋势图 ====================
const trendChartRef = ref<HTMLElement | null>(null)
let trendChart: ReturnType<typeof echarts.init> | null = null
const trendData = ref<{ years: number[]; incomes: number[] }>({ years: [], incomes: [] })

async function loadTrendData() {
  if (!village.value) return
  const years: number[] = []
  const incomes: number[] = []
  for (const year of availableYears) {
    try {
      const data = await getYearlyData(village.value.id, year)
      const income = (data as any)?.income?.perCapitaIncome
      if (income != null) {
        years.push(year)
        incomes.push(Number(income))
      }
    } catch {
      // skip years with no data
    }
  }
  // Sort ascending by year
  const paired = years.map((y, i) => ({ year: y, income: incomes[i] }))
  paired.sort((a, b) => a.year - b.year)
  trendData.value = {
    years: paired.map((p) => p.year),
    incomes: paired.map((p) => p.income),
  }
  renderTrendChart()
}

function renderTrendChart() {
  if (!trendChartRef.value) return
  if (!trendChart) {
    trendChart = echarts.init(trendChartRef.value)
  }
  trendChart.setOption({
    tooltip: {
      trigger: 'axis',
      formatter: '{b}年<br/>人均纯收入：{c} 万元',
    },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: trendData.value.years.map((y) => `${y}`),
      axisLabel: { formatter: '{value}年' },
    },
    yAxis: {
      type: 'value',
      name: '万元',
      axisLabel: { formatter: '{value}' },
    },
    series: [
      {
        name: '人均纯收入',
        type: 'line',
        smooth: true,
        data: trendData.value.incomes,
        areaStyle: { opacity: 0.15 },
        itemStyle: { color: '#40916c' },
        lineStyle: { width: 3 },
      },
    ],
  })
}

// Debounced resize handler
let resizeTimer: ReturnType<typeof setTimeout> | null = null
function handleChartResize() {
  if (resizeTimer) clearTimeout(resizeTimer)
  resizeTimer = setTimeout(() => {
    trendChart?.resize()
  }, 200)
}

const loadVillage = async () => {
  const id = safeRouteParam(route.params.id)
  if (!id) return

  loading.value = true
  try {
    const _raw = await getSupportedVillage(id)
    village.value = _raw
    if (pageMode.value === 'view') {
      await loadYearlyData()
      // Load trend data and render chart after DOM update
      await nextTick()
      loadTrendData()
    }
  } catch (error) {
    logger.error('加载帮扶村详情失败:', error)
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

const loadYearlyData = async () => {
  if (!village.value) return

  yearlyLoading.value = true
  try {
    const _raw = await getYearlyData(village.value.id, selectedYear.value)
    yearlyData.value = _raw
  } catch (error) {
    logger.error('加载年度数据失败:', error)
    yearlyData.value = null
  } finally {
    yearlyLoading.value = false
  }
}

const handleBack = () => {
  pushSafe('/supported-villages')
}

const handleEdit = () => {
  if (village.value) {
    pushSafe(`/supported-villages/${village.value.id}?mode=edit`)
  }
}

const handleYearlyData = () => {
  if (village.value) {
    pushSafe(`/supported-villages/${village.value.id}/yearly`)
  }
}

/** 表单提交（创建或编辑） */
const handleFormSubmit = async (data: SupportedVillageCreate) => {
  loading.value = true
  try {
    // 提取创建模式下的过渡期年度经费数据（不传给 create API）
    const fundingItems = (data as any)._transitionFundingItems
    delete (data as any)._transitionFundingItems

    if (pageMode.value === 'create') {
      const created = (await createSupportedVillage(data)) as any
      const villageId = created?.data?.id || created?.id
      // 创建成功后保存过渡期经费按年度数据
      if (fundingItems?.length && villageId) {
        try {
          await saveTransitionFunding(villageId, { items: fundingItems })
        } catch (fundErr: any) {
          logger.error('[Detail] 保存过渡资金失败', fundErr)
          ElMessage.warning('村记录已创建，但过渡资金保存失败，请在编辑页面重新填写')
        }
      }
      ElMessage.success('创建成功')
      pushSafe(`/supported-villages/${villageId}`)
    } else {
      const id = safeRouteParam(route.params.id)
      await updateSupportedVillage(id, data)
      ElMessage.success('保存成功')
      // 刷新数据后切换回查看模式
      const _raw = await getSupportedVillage(id)
      village.value = _raw
      pushSafe(`/supported-villages/${id}`)
    }
  } catch (error: any) {
    const msg = error?.response?.data?.detail || error?.message || '操作失败'
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}

/** 表单取消 */
const handleFormCancel = () => {
  if (pageMode.value === 'create') {
    pushSafe('/supported-villages')
  } else {
    const id = safeRouteParam(route.params.id)
    pushSafe(`/supported-villages/${id}`)
  }
}

// 监听路由变化重新加载数据
watch(
  () => route.params.id,
  (newId) => {
    if (newId) loadVillage()
  },
  { immediate: false }
)

onMounted(() => {
  if (pageMode.value !== 'create') {
    loadVillage()
  }
  window.addEventListener('resize', handleChartResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleChartResize)
  if (resizeTimer) clearTimeout(resizeTimer)
  if (trendChart) {
    trendChart.dispose()
    trendChart = null
  }
})
</script>

<style scoped>
.village-detail-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.page-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--color-primary-dark-1);
  margin: 0;
}

.header-actions {
  display: flex;
  gap: 12px;
}

.info-card {
  background: white;
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-primary-dark-1);
  margin: 0 0 16px 0;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--color-bg-hover);
  display: flex;
  align-items: center;
}

.tag-sections {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.tag-section {
  display: flex;
  align-items: center;
  gap: 12px;
}

.section-label {
  font-weight: 500;
  color: var(--color-text-regular);
  min-width: 80px;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.no-data {
  color: var(--color-text-secondary);
  font-size: 14px;
}

.honors-text {
  color: var(--color-text-regular);
  line-height: 1.6;
  margin: 0;
}

.stat-card {
  background: var(--color-bg-hover);
  padding: 20px;
  border-radius: 8px;
  text-align: center;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--color-primary-light-1);
}

.stat-label {
  font-size: 14px;
  color: var(--color-info);
  margin-top: 8px;
}

.trend-chart {
  width: 100%;
  height: 360px;
}
</style>
