<template>
  <div v-loading="loading" class="yearly-overview-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-info">
        <el-button text @click="handleBack"
          ><el-icon><ArrowLeft /></el-icon>返回详情</el-button
        >
        <h2 class="page-title">{{ villageName }} — 年度数据管理</h2>
      </div>
      <div class="header-actions">
        <el-select v-model="selectedYear" style="width: 120px" @change="loadAllData">
          <el-option
            v-for="year in availableYears"
            :key="year"
            :label="`${year}年`"
            :value="year"
          />
        </el-select>
        <el-button type="primary" :loading="downloadingAll" @click="handleDownloadAllTemplates"
          ><el-icon><Download /></el-icon>全部模板下载</el-button
        >
        <el-upload
          :show-file-list="false"
          :before-upload="() => false"
          :on-change="handleImportAll"
          accept=".xlsx,.xls"
          class="inline-upload"
        >
          <el-button type="success" :loading="importingAll">
            <el-icon><Upload /></el-icon>全部导入
          </el-button>
        </el-upload>
      </div>
    </div>

    <!-- 板块卡片网格 -->
    <div class="section-grid">
      <div v-for="section in sections" :key="section.key" class="section-card">
        <div class="section-card-header">
          <el-icon class="section-icon"><component :is="section.icon" /></el-icon>
          <h3>{{ section.title }}</h3>
        </div>
        <div class="section-summary">
          <div v-for="stat in section.stats" :key="stat.label" class="summary-item">
            <span class="summary-value">{{ stat.value }}</span>
            <span class="summary-label">{{ stat.label }}</span>
          </div>
          <div v-if="!section.stats.length" class="no-data-hint">暂无数据</div>
        </div>
        <div class="section-card-actions">
          <el-button size="small" type="primary" @click="openEditDialog(section.key)"
            ><el-icon><Edit /></el-icon>填写</el-button
          >
          <el-button size="small" @click="handleDownloadTemplate(section.key)"
            ><el-icon><Download /></el-icon>模板</el-button
          >
          <el-popconfirm
            v-if="section.stats.length > 0"
            :title="`确认删除 ${selectedYear} 年「${section.title}」数据？删除后可重新填写恢复（数据不可找回）`"
            @confirm="deleteSection(section.key)"
          >
            <template #reference>
              <el-button size="small" type="danger" link>删除</el-button>
            </template>
          </el-popconfirm>
          <el-upload
            :show-file-list="false"
            :before-upload="() => false"
            :on-change="(file: any) => handleImportSection(section.key, file)"
            accept=".xlsx,.xls"
            class="inline-upload"
          >
            <el-button size="small">
              <el-icon><Upload /></el-icon>导入
            </el-button>
          </el-upload>
        </div>
      </div>
    </div>

    <!-- 数据可视化 -->
    <el-row :gutter="20" class="chart-row">
      <el-col :xs="24" :lg="12">
        <el-card shadow="never" class="chart-card">
          <template #header>
            <div class="chart-card-header">
              <span class="chart-title">收入趋势</span>
              <span class="chart-hint">近六年人均 / 集体收入（万元）</span>
            </div>
          </template>
          <div ref="incomeTrendChartRef" class="chart-box"></div>
        </el-card>
      </el-col>
      <el-col :xs="24" :lg="12">
        <el-card shadow="never" class="chart-card">
          <template #header>
            <div class="chart-card-header">
              <span class="chart-title">投入分布</span>
              <span class="chart-hint">{{ selectedYear }}年各板块帮扶投入（万元）</span>
            </div>
          </template>
          <div ref="investmentPieChartRef" class="chart-box"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 年度数据编辑弹窗（按板块独立填写） -->
    <el-dialog
      v-model="editDialogVisible"
      append-to-body
      :title="`${editSectionTitle} — 数据填写`"
      :width="DIALOG_LG"
      destroy-on-close
    >
      <SectionDataForm
        v-if="editDialogVisible"
        :village-id="villageId"
        :village-name="villageName"
        :section-key="editSectionKey"
        :initial-year="selectedYear"
        @close="editDialogVisible = false"
        @saved="loadAllData"
      />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { DIALOG_LG } from '@/config/dialog'
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick, markRaw } from 'vue'
import { useRoute } from 'vue-router'
import { useRouterSafe, safeRouteParam } from '@/composables/useRouterSafe'
import { logger } from '@/utils/logger'
import { deleteYearlySection } from '@/api/supportedVillage'
import {
  ArrowLeft,
  Edit,
  Download,
  Upload,
  User,
  Money,
  Medal,
  OfficeBuilding,
  Tools,
  Stamp,
  FirstAidKit,
  ShoppingCart,
  Briefcase,
  Reading,
  House,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import {
  getSupportedVillage,
  getYearlyData,
  downloadTemplate,
  importSectionData,
  downloadAllTemplates,
  importAllSectionsData,
} from '@/api/supportedVillage'
import type { YearlyDataSummary } from '@/types/analytics'
import SectionDataForm from './components/SectionDataForm.vue'
import echarts from '@/utils/echarts'
import { getYearOptions } from '@/utils/yearOptions'
import { format } from '@/utils'

const route = useRoute()
const { pushSafe } = useRouterSafe()

const villageId = computed(() => safeRouteParam(route.params.id))
const villageName = ref('')
const loading = ref(false)
const downloadingAll = ref(false)
const importingAll = ref(false)
const sectionImporting = ref('')
const selectedYear = ref(new Date().getFullYear())
const yearlyData = ref<YearlyDataSummary | null>(null)

// 可选年份：2017 ~ 当前年+10（滚动窗口，见 utils/yearOptions）
const availableYears = computed(() => getYearOptions({ start: 2017 }))

// 弹窗
const editDialogVisible = ref(false)
const editSectionKey = ref('')
const editSectionTitle = ref('')

// 板块定义
// 注意：后端 /yearly/{year} 按 section 原始 key 返回（force-investment/party-building/industry 等），
// 读取时用与实际返回一致的 key，不能臆造 camelCase 别名
const sections = computed(() => {
  const d: any = yearlyData.value
  return [
    {
      key: 'population',
      title: '人口数据',
      icon: markRaw(User),
      stats: d?.population
        ? [
            { label: '总人口', value: d.population.totalPopulation ?? 0 },
            { label: '总户数', value: d.population.totalHouseholds ?? 0 },
            { label: '常住人口', value: d.population.residentPopulation ?? 0 },
          ]
        : [],
    },
    {
      key: 'income',
      title: '收入数据',
      icon: markRaw(Money),
      stats: d?.income
        ? [
            {
              label: '人均收入(万)',
              value: format.formatMoney4(d.income.perCapitaIncome),
            },
            {
              label: '集体收入(万)',
              value: format.formatMoney4(d.income.collectiveIncome),
            },
          ]
        : [],
    },
    {
      key: 'force_investment',
      title: '力量投入',
      icon: markRaw(Medal),
      stats: d?.['force-investment']
        ? [
            {
              label: '领导到村(人次)',
              value: d['force-investment'].seniorLeaderVisits ?? 0,
            },
            {
              label: '人员到村(人次)',
              value: d['force-investment'].unitSoldierVisits ?? 0,
            },
          ]
        : [],
    },
    {
      key: 'industry',
      title: '产业帮扶',
      icon: markRaw(OfficeBuilding),
      stats: d?.industry
        ? [
            {
              label: '当年投入(万)',
              value: format.formatMoney4(d.industry.investment),
            },
          ]
        : [],
    },
    {
      key: 'infrastructure',
      title: '基础设施',
      icon: markRaw(Tools),
      stats: d?.infrastructure
        ? [
            {
              label: '当年投入(万)',
              value: format.formatMoney4(d.infrastructure.investment),
            },
          ]
        : [],
    },
    {
      key: 'party_building',
      title: '党建帮扶',
      icon: markRaw(Stamp),
      stats: d?.['party-building']
        ? [
            {
              label: '投入(万)',
              value: format.formatMoney4(d['party-building'].investment),
            },
            {
              label: '联建活动(次)',
              value: d['party-building'].jointActivities ?? 0,
            },
          ]
        : [],
    },
    {
      key: 'medical',
      title: '医疗帮扶',
      icon: markRaw(FirstAidKit),
      stats: d?.medical
        ? [
            {
              label: '投入(万)',
              value: format.formatMoney4(d.medical.investment),
            },
            {
              label: '巡诊(人次)',
              value: d.medical.patientsServed ?? 0,
            },
          ]
        : [],
    },
    {
      key: 'consumption',
      title: '消费帮扶',
      icon: markRaw(ShoppingCart),
      stats: d?.consumption
        ? [
            {
              label: '采购产品(万)',
              value: format.formatMoney4(d.consumption.villageProductsPurchase),
            },
          ]
        : [],
    },
    {
      key: 'employment',
      title: '就业帮扶',
      icon: markRaw(Briefcase),
      stats: d?.employment
        ? [
            {
              label: '聘用(人)',
              value: d.employment.hiredPopulation ?? 0,
            },
            {
              label: '培训(人次)',
              value: d.employment.trainedPopulation ?? 0,
            },
          ]
        : [],
    },
    {
      key: 'education',
      title: '教育帮扶',
      icon: markRaw(Reading),
      stats: d?.education
        ? [
            {
              label: '投入(万)',
              value: format.formatMoney4(d.education.investment),
            },
            {
              label: '资助学生(人)',
              value: d.education.aidedStudents ?? 0,
            },
          ]
        : [],
    },
    {
      key: 'committee',
      title: '村委会情况',
      icon: markRaw(House),
      stats: d?.committee
        ? [
            {
              label: '成员数',
              value: d.committee.members?.length ?? 0,
            },
            {
              label: '集体收入(万)',
              value: format.formatMoney4(d.committee.collectiveIncomeAmount),
            },
          ]
        : [],
    },
  ]
})

// ==================== 数据可视化图表 ====================
const incomeTrendChartRef = ref<HTMLElement | null>(null)
const investmentPieChartRef = ref<HTMLElement | null>(null)
let incomeTrendChart: ReturnType<typeof echarts.init> | null = null
let investmentPieChart: ReturnType<typeof echarts.init> | null = null

// 多年收入趋势（近六年）
const trendData = ref<{
  years: number[]
  perCapita: (number | null)[]
  collective: (number | null)[]
}>({ years: [], perCapita: [], collective: [] })

async function loadTrendData() {
  const currentYear = new Date().getFullYear()
  const yearList = Array.from({ length: 6 }, (_, i) => currentYear - i + 1)
  const records: Array<{ year: number; perCapita: number | null; collective: number | null }> = []
  for (const year of yearList) {
    try {
      const data = await getYearlyData(villageId.value, year)
      const income = (data as any)?.income
      if (income && (income.perCapitaIncome != null || income.collectiveIncome != null)) {
        records.push({
          year,
          perCapita: income.perCapitaIncome != null ? Number(income.perCapitaIncome) : null,
          collective: income.collectiveIncome != null ? Number(income.collectiveIncome) : null,
        })
      }
    } catch {
      // 跳过无数据年份
    }
  }
  records.sort((a, b) => a.year - b.year)
  trendData.value = {
    years: records.map((r) => r.year),
    perCapita: records.map((r) => r.perCapita),
    collective: records.map((r) => r.collective),
  }
  await nextTick()
  renderTrendChart()
}

function renderTrendChart() {
  if (!incomeTrendChartRef.value) return
  if (!incomeTrendChart) {
    incomeTrendChart = echarts.init(incomeTrendChartRef.value)
  }
  const hasData = trendData.value.years.length > 0
  incomeTrendChart.setOption(
    {
      title: hasData
        ? undefined
        : {
            text: '暂无收入数据',
            left: 'center',
            top: 'middle',
            textStyle: { color: '#bbb', fontSize: 14, fontWeight: 400 },
          },
      tooltip: {
        trigger: 'axis',
        formatter: (params: any) => {
          const list = Array.isArray(params) ? params : [params]
          const lines = list.map(
            (p: any) => `${p.marker}${p.seriesName}：${format.formatMoney4(p.value)} 万元`
          )
          return `${list[0]?.axisValue ?? ''}<br/>${lines.join('<br/>')}`
        },
      },
      legend: { data: ['人均纯收入', '集体收入'], bottom: 0 },
      grid: { left: '3%', right: '4%', top: 30, bottom: 40, containLabel: true },
      xAxis: {
        type: 'category',
        boundaryGap: false,
        data: trendData.value.years.map((y) => `${y}年`),
      },
      yAxis: { type: 'value', name: '万元' },
      series: [
        {
          name: '人均纯收入',
          type: 'line',
          smooth: true,
          data: trendData.value.perCapita,
          areaStyle: { opacity: 0.15 },
          itemStyle: { color: '#40916c' },
          lineStyle: { width: 3 },
        },
        {
          name: '集体收入',
          type: 'line',
          smooth: true,
          data: trendData.value.collective,
          itemStyle: { color: '#b08968' },
          lineStyle: { width: 3 },
        },
      ],
    },
    { notMerge: true }
  )
}

// 当年各板块投入分布
const investmentDistribution = computed(() => {
  const d: any = yearlyData.value
  const items: Array<{ name: string; value: number }> = []
  if (!d) return items
  const push = (name: string, value: number | undefined) => {
    const v = Number(value ?? 0)
    if (v > 0) items.push({ name, value: v })
  }
  push('产业帮扶', d.industry?.investment)
  push('基础设施', d.infrastructure?.investment)
  push('党建帮扶', d['party-building']?.investment)
  push('医疗帮扶', d.medical?.investment)
  push('教育帮扶', d.education?.investment)
  return items
})

function renderPieChart() {
  if (!investmentPieChartRef.value) return
  if (!investmentPieChart) {
    investmentPieChart = echarts.init(investmentPieChartRef.value)
  }
  const data = investmentDistribution.value
  investmentPieChart.setOption(
    {
      title: data.length
        ? undefined
        : {
            text: '暂无投入数据',
            left: 'center',
            top: 'middle',
            textStyle: { color: '#bbb', fontSize: 14, fontWeight: 400 },
          },
      tooltip: {
        trigger: 'item',
        formatter: (p: any) =>
          `${p.marker}${p.name}<br/>投入：${format.formatMoney4(p.value)} 万元（${p.percent}%）`,
      },
      legend: { bottom: 0 },
      color: ['#1b4332', '#2d6a4f', '#40916c', '#52b788', '#95d5b2'],
      series: [
        {
          name: '投入分布',
          type: 'pie',
          radius: ['42%', '68%'],
          center: ['50%', '45%'],
          itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
          label: { formatter: '{b}\n{d}%' },
          emphasis: {
            itemStyle: { shadowBlur: 12, shadowColor: 'rgba(0, 0, 0, 0.2)' },
          },
          data,
        },
      ],
    },
    { notMerge: true }
  )
}

// 年度数据变化后刷新饼图
watch(yearlyData, async () => {
  await nextTick()
  renderPieChart()
})

// 防抖 resize
let chartResizeTimer: ReturnType<typeof setTimeout> | null = null
function handleChartResize() {
  if (chartResizeTimer) clearTimeout(chartResizeTimer)
  chartResizeTimer = setTimeout(() => {
    incomeTrendChart?.resize()
    investmentPieChart?.resize()
  }, 200)
}

async function deleteSection(sectionKey: string) {
  const vid = safeRouteParam(route.params.id)
  if (!vid) return
  try {
    await deleteYearlySection(Number(vid), selectedYear.value, sectionKey)
    ElMessage.success('已删除')
    await loadAllData()
  } catch (e) {
    logger.error('删除年度板块失败:', e)
    ElMessage.error('删除失败，请稍后重试')
  }
}

async function loadAllData() {
  loading.value = true
  try {
    const _v = await getSupportedVillage(villageId.value)
    const village = _v
    villageName.value = village.villageName
    const _raw = await getYearlyData(villageId.value, selectedYear.value)
    yearlyData.value = _raw
    // 刷新多年收入趋势（不阻塞主流程）
    loadTrendData()
  } catch (e: any) {
    ElMessage.error(e?.message || '加载数据失败')
  } finally {
    loading.value = false
  }
}

function openEditDialog(key: string) {
  editSectionKey.value = key
  editSectionTitle.value = sections.value.find((s) => s.key === key)?.title || ''
  editDialogVisible.value = true
}

async function handleDownloadTemplate(_sectionKey: string) {
  try {
    await downloadTemplate()
    // 模板下载成功 — 浏览器已确认
  } catch {
    ElMessage.error('模板下载失败')
  }
}

async function handleImportSection(sectionKey: string, file: any) {
  const rawFile = file?.raw || file
  // File validation
  if (!rawFile) return
  const isExcel = rawFile.name?.endsWith('.xlsx') || rawFile.name?.endsWith('.xls')
  if (!isExcel) {
    ElMessage.error('只能上传 Excel 文件(.xlsx/.xls)')
    return
  }
  if (rawFile.size > 10 * 1024 * 1024) {
    ElMessage.error('文件大小不能超过 10MB')
    return
  }
  sectionImporting.value = sectionKey
  try {
    const result = (await importSectionData(
      villageId.value,
      selectedYear.value,
      sectionKey,
      rawFile
    )) as any
    ElMessage.success(`导入成功 ${result.imported || result.rows || 0} 条`)
    if (result.failed > 0) {
      ElMessage.warning(`${result.failed} 条导入失败`)
    }
    loadAllData()
  } catch (e: any) {
    const msg = e?.response?.data?.detail || e?.message || '导入失败'
    ElMessage.error(typeof msg === 'string' ? msg : '导入失败，请检查文件格式')
  } finally {
    sectionImporting.value = ''
  }
}

async function handleDownloadAllTemplates() {
  downloadingAll.value = true
  try {
    await downloadAllTemplates(selectedYear.value)
    ElMessage.success('全部板块模板下载成功')
  } catch (e: any) {
    ElMessage.error(e?.message || '模板下载失败')
  } finally {
    downloadingAll.value = false
  }
}

async function handleImportAll(file: any) {
  const rawFile = file.raw || file
  importingAll.value = true
  try {
    const result = (await importAllSectionsData(
      villageId.value,
      selectedYear.value,
      rawFile
    )) as any
    const secCount = result.sections?.length || result.sheets || 0
    ElMessage.success(
      `全部导入完成：成功 ${result.imported || result.rows || 0} 条（${secCount} 个板块）`
    )
    if (result.failed > 0) {
      ElMessage.warning(`${result.failed} 条数据导入失败`)
    }
    loadAllData()
  } catch (e: any) {
    ElMessage.error(e?.message || '全部导入失败')
  } finally {
    importingAll.value = false
  }
}

function handleBack() {
  pushSafe(`/supported-villages/${villageId.value}`)
}

onMounted(() => {
  window.addEventListener('resize', handleChartResize)
  loadAllData()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleChartResize)
  if (chartResizeTimer) clearTimeout(chartResizeTimer)
  if (incomeTrendChart) {
    incomeTrendChart.dispose()
    incomeTrendChart = null
  }
  if (investmentPieChart) {
    investmentPieChart.dispose()
    investmentPieChart = null
  }
})
</script>

<style scoped>
.yearly-overview-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.header-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.page-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--color-primary-dark-1);
  margin: 0;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.section-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}

.section-card {
  background: white;
  border-radius: 10px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  transition:
    transform 0.2s,
    box-shadow 0.2s;
}

.section-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
}

.section-card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.section-card-header h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-primary-dark-1);
}

.section-icon {
  font-size: 20px;
  color: var(--color-primary);
}

.section-summary {
  display: flex;
  gap: 16px;
  margin-bottom: 14px;
  min-height: 48px;
  flex-wrap: wrap;
}

.summary-item {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.summary-value {
  font-size: 18px;
  font-weight: 700;
  color: var(--color-primary-light-1);
}

.summary-label {
  font-size: 12px;
  color: var(--color-text-secondary);
}

.no-data-hint {
  color: var(--color-text-placeholder);
  font-size: 13px;
  display: flex;
  align-items: center;
}

.section-card-actions {
  display: flex;
  gap: 8px;
  border-top: 1px solid var(--color-bg-hover);
  padding-top: 12px;
}

.inline-upload {
  display: inline-block;
}

/* 数据可视化卡片 */
.chart-card {
  border-radius: 10px;
}

.chart-card :deep(.el-card__header) {
  padding: 12px 20px;
  border-bottom: 1px solid var(--color-bg-hover);
}

.chart-card-header {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.chart-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-primary-dark-1);
}

.chart-hint {
  font-size: 12px;
  color: var(--color-text-secondary);
}

.chart-box {
  width: 100%;
  height: 320px;
}
</style>
