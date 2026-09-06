<template>
  <div class="report-export">
    <el-card class="page-header">
      <div class="header-content">
        <h2>报表导出中心</h2>
        <p class="description">导出各类统计报表和数据汇总</p>
      </div>
    </el-card>

    <!-- 报表类型选择 -->
    <el-card class="report-types">
      <h3 class="section-title">选择报表类型</h3>
      <div class="type-grid">
        <div
          v-for="report in reportTypes"
          :key="report.type"
          class="type-card"
          :class="{ active: selectedType === report.type }"
          @click="selectReportType(report.type)"
        >
          <el-icon :size="32" :color="report.color">
            <component :is="report.icon" />
          </el-icon>
          <div class="type-info">
            <span class="type-name">{{ report.name }}</span>
            <span class="type-desc">{{ report.description }}</span>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 导出配置 -->
    <el-card v-if="selectedType" class="export-config">
      <h3 class="section-title">导出配置</h3>
      <el-form :model="exportForm" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="时间范围">
              <el-date-picker
                v-model="exportForm.dateRange"
                type="daterange"
                range-separator="至"
                start-placeholder="开始日期"
                end-placeholder="结束日期"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="数据范围">
              <el-select v-model="exportForm.scope" style="width: 100%">
                <el-option label="本单位数据" value="self" />
                <el-option label="含下级单位" value="all" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="导出格式">
              <el-radio-group v-model="exportForm.format">
                <!-- 同步导出仅支持 Excel；PDF/Word 请使用下方「官方报表导出」区 -->
                <el-radio-button value="xlsx">Excel</el-radio-button>
              </el-radio-group>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="包含图表">
              <el-switch v-model="exportForm.includeCharts" />
            </el-form-item>
          </el-col>
        </el-row>

        <!-- 报表特定选项 -->
        <template v-if="selectedType === 'village_summary'">
          <el-form-item label="统计维度">
            <el-checkbox-group v-model="exportForm.dimensions">
              <el-checkbox value="region">按地区</el-checkbox>
              <el-checkbox value="status">按状态</el-checkbox>
              <el-checkbox value="year">按年度</el-checkbox>
            </el-checkbox-group>
          </el-form-item>
        </template>

        <template v-if="selectedType === 'fund_analysis'">
          <el-form-item label="资金类型">
            <el-checkbox-group v-model="exportForm.fundTypes">
              <el-checkbox value="budget">预算资金</el-checkbox>
              <el-checkbox value="actual">实际支出</el-checkbox>
              <el-checkbox value="balance">结余资金</el-checkbox>
            </el-checkbox-group>
          </el-form-item>
        </template>

        <template v-if="selectedType === 'project_progress'">
          <el-form-item label="项目状态">
            <el-checkbox-group v-model="exportForm.projectStatus">
              <el-checkbox value="planning">规划中</el-checkbox>
              <el-checkbox value="in_progress">进行中</el-checkbox>
              <el-checkbox value="completed">已完成</el-checkbox>
            </el-checkbox-group>
          </el-form-item>
        </template>

        <el-form-item>
          <el-button type="primary" :loading="exporting" @click="handleExport">
            <el-icon><Download /></el-icon>
            开始导出
          </el-button>
          <el-button @click="handlePrintPreview">打印预览</el-button>
          <el-button @click="resetForm">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 公文报告导出 -->
    <el-card class="official-report-export">
      <h3 class="section-title">公文报告导出</h3>
      <p class="section-desc">一键生成 Word / PDF 格式帮扶公文</p>

      <el-form :model="officialForm" label-width="80px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="年度">
              <el-date-picker
                v-model="officialForm.year"
                type="year"
                placeholder="选择年度"
                style="width: 100%"
                value-format="YYYY"
              />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>

      <div class="official-report-list">
        <div v-for="report in officialReportTypes" :key="report.type" class="official-report-item">
          <div class="report-info">
            <el-icon :size="24" :color="report.color">
              <component :is="report.icon" />
            </el-icon>
            <div class="report-text">
              <span class="report-name">{{ report.name }}</span>
              <span class="report-desc">{{ report.description }}</span>
            </div>
          </div>
          <div class="report-actions">
            <el-button
              type="primary"
              :loading="officialLoading[report.type + '_word']"
              @click="handleExportOfficial(report.type, 'word')"
            >
              <el-icon><Document /></el-icon>
              导出 Word
            </el-button>
            <el-button
              type="danger"
              :loading="officialLoading[report.type + '_pdf']"
              @click="handleExportOfficial(report.type, 'pdf')"
            >
              <el-icon><DocumentChecked /></el-icon>
              导出 PDF
            </el-button>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 订阅管理（工单 003：到期自动生成 + 站内消息送达，也可手动立即生成） -->
    <el-card class="subscription-management">
      <div class="history-header">
        <h3 class="section-title">订阅管理</h3>
        <div>
          <el-button text type="primary" @click="loadSubscriptions">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
          <el-button type="primary" @click="openSubscriptionDialog">
            <el-icon><Plus /></el-icon>
            新建订阅
          </el-button>
        </div>
      </div>
      <p class="section-desc">
        到期自动生成报表并保存到报表输出目录，站内消息通知；生成失败会逐条留痕，不影响其余订阅。
      </p>
      <el-table v-loading="loadingSubs" :data="subscriptions" stripe>
        <el-table-column prop="name" label="订阅名称" min-width="150" />
        <el-table-column label="频率" width="80">
          <template #default="{ row }">{{ freqLabel(row.frequency) }}</template>
        </el-table-column>
        <el-table-column label="发送时间" min-width="130">
          <template #default="{ row }">{{ freqDetail(row) }}</template>
        </el-table-column>
        <el-table-column label="上次生成" width="160">
          <template #default="{ row }">
            <span>{{
              row.last_sent_at ? String(row.last_sent_at).replace('T', ' ').slice(0, 19) : '从未'
            }}</span>
          </template>
        </el-table-column>
        <el-table-column label="下次生成" width="160">
          <template #default="{ row }">
            <span>{{
              row.next_send_at ? String(row.next_send_at).replace('T', ' ').slice(0, 19) : '—'
            }}</span>
          </template>
        </el-table-column>
        <el-table-column label="启用" width="70">
          <template #default="{ row }">
            <el-switch :model-value="row.is_active" @change="handleToggleSub(row)" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="190" fixed="right">
          <template #default="{ row }">
            <el-button
              size="small"
              type="primary"
              :disabled="!row.is_active"
              :loading="generatingId === row.id"
              @click="handleGenerateNow(row)"
            >
              立即生成
            </el-button>
            <el-button size="small" type="danger" @click="handleDeleteSub(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新建订阅对话框 -->
    <el-dialog v-model="subDialogVisible" title="新建报表订阅" width="520px">
      <el-form :model="subForm" label-width="90px">
        <el-form-item label="订阅名称" required>
          <el-input v-model="subForm.name" placeholder="如：每月帮扶村汇总" maxlength="100" />
        </el-form-item>
        <el-form-item label="报表类型" required>
          <el-select v-model="subForm.report_type" style="width: 100%">
            <el-option v-for="t in reportTypes" :key="t.type" :label="t.name" :value="t.type" />
          </el-select>
        </el-form-item>
        <el-form-item label="频率" required>
          <el-select v-model="subForm.frequency" style="width: 100%" @change="handleFreqChange">
            <el-option label="每天" value="daily" />
            <el-option label="每周" value="weekly" />
            <el-option label="每月" value="monthly" />
            <el-option label="每季度" value="quarterly" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="subForm.frequency === 'weekly'" label="星期">
          <el-select v-model="subForm.send_day" style="width: 100%">
            <el-option
              v-for="(label, idx) in ['周一', '周二', '周三', '周四', '周五', '周六', '周日']"
              :key="idx"
              :label="label"
              :value="idx + 1"
            />
          </el-select>
        </el-form-item>
        <el-form-item
          v-if="subForm.frequency === 'monthly' || subForm.frequency === 'quarterly'"
          label="日期"
        >
          <el-select v-model="subForm.send_day" style="width: 100%">
            <el-option v-for="d in 31" :key="d" :label="`${d} 号`" :value="d" />
          </el-select>
        </el-form-item>
        <el-form-item label="发送时间">
          <el-time-select
            v-model="subForm.send_time"
            start="00:00"
            step="00:30"
            end="23:30"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="文件格式">
          <el-select v-model="subForm.format" style="width: 100%">
            <el-option label="Excel（.xlsx）" value="xlsx" />
            <el-option label="PDF" value="pdf" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="subDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="creatingSub" @click="handleCreateSub"
          >创建订阅</el-button
        >
      </template>
    </el-dialog>

    <!-- 导出历史 -->
    <el-card class="export-history">
      <div class="history-header">
        <h3 class="section-title">导出历史</h3>
        <el-button text type="primary" @click="loadHistory">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>

      <el-table v-loading="loadingHistory" :data="exportHistory" stripe>
        <el-table-column prop="report_type" label="报表类型" width="150">
          <template #default="{ row }">
            {{ getReportTypeName(row.export_type || row.report_type) }}
          </template>
        </el-table-column>
        <el-table-column prop="file_name" label="文件名" min-width="200" />
        <el-table-column prop="file_size" label="大小" width="100">
          <template #default="{ row }">
            {{ formatFileSize(row.file_size) }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getExportStatusType(row.status)">
              {{ getExportStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="导出时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'completed'"
              link
              type="primary"
              @click="downloadExport(row)"
            >
              下载
            </el-button>
            <el-button v-if="row.status === 'processing'" link type="info" disabled>
              处理中...
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { logger } from '@/utils/logger'
import { post, downloadBlob } from '@/api/request'

import { ref, reactive, onMounted } from 'vue'
import { Download, Refresh, Document, DocumentChecked, Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getExportHistory,
  downloadExportFile,
  formatFileSize,
  exportReportWord,
  exportReportPdf,
} from '@/api/export'
import {
  listSubscriptions,
  createSubscription,
  toggleSubscription,
  deleteSubscription,
  generateSubscriptionNow,
} from '@/api/reportSubscription'

// 报表类型定义
// _exportReport 函数在模板中通过动态组件方式使用

const officialReportTypes = [
  {
    type: 'summary',
    name: '年度帮扶工作总结',
    description: '汇总年度帮扶村庄、学校、项目及资金情况',
    icon: 'DataAnalysis',
    color: '#40916c',
  },
  {
    type: 'fund_detail',
    name: '帮扶资金拨付明细表',
    description: '按年度列示资金拨付明细及状态',
    icon: 'Money',
    color: '#e91e63',
  },
  {
    type: 'project_progress',
    name: '帮扶项目进度统计表',
    description: '按年度统计项目预算、进度及健康标识',
    icon: 'Folder',
    color: '#ff9800',
  },
]

const reportTypes = [
  {
    type: 'village_summary',
    name: '帮扶村汇总报表',
    description: '帮扶村基本情况统计汇总',
    icon: 'Location',
    color: '#40916c',
  },
  {
    type: 'fund_analysis',
    name: '资金使用分析报表',
    description: '资金预算、支出、结余分析',
    icon: 'Money',
    color: '#e91e63',
  },
  {
    type: 'project_progress',
    name: '项目进度报表',
    description: '项目实施进度跟踪统计',
    icon: 'Folder',
    color: '#ff9800',
  },
  {
    type: 'school_statistics',
    name: '学校援建统计报表',
    description: '援建学校情况统计',
    icon: 'School',
    color: '#2196f3',
  },
  {
    type: 'annual_summary',
    name: '年度工作总结报表',
    description: '年度工作成效汇总',
    icon: 'DataAnalysis',
    color: '#9c27b0',
  },
  {
    type: 'comprehensive',
    name: '综合数据报表',
    description: '全面数据导出',
    icon: 'Document',
    color: '#607d8b',
  },
]

// 状态
const selectedType = ref('')
const exporting = ref(false)
const loadingHistory = ref(false)
const exportHistory = ref<any[]>([])

// ── 订阅管理（工单 003）──
const subscriptions = ref<any[]>([])
const loadingSubs = ref(false)
const generatingId = ref<number | null>(null)
const creatingSub = ref(false)
const subDialogVisible = ref(false)

const subForm = reactive({
  name: '',
  report_type: 'comprehensive',
  frequency: 'monthly' as 'daily' | 'weekly' | 'monthly' | 'quarterly',
  send_day: 1 as number | null,
  send_time: '08:00',
  format: 'xlsx',
})

const FREQ_LABELS: Record<string, string> = {
  daily: '每天',
  weekly: '每周',
  monthly: '每月',
  quarterly: '每季度',
}
const WEEKDAY_LABELS = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']

function freqLabel(f: string) {
  return FREQ_LABELS[f] || f
}

function freqDetail(row: any): string {
  const time = row.send_time || '08:00'
  if (row.frequency === 'daily') return `每天 ${time}`
  if (row.frequency === 'weekly') return `${WEEKDAY_LABELS[(row.send_day || 1) - 1]} ${time}`
  if (row.frequency === 'monthly') return `每月 ${row.send_day || 1} 号 ${time}`
  return `每季度 ${row.send_day || 1} 号 ${time}`
}

function openSubscriptionDialog() {
  subForm.name = ''
  subForm.report_type = 'comprehensive'
  subForm.frequency = 'monthly'
  subForm.send_day = 1
  subForm.send_time = '08:00'
  subForm.format = 'xlsx'
  subDialogVisible.value = true
}

function handleFreqChange() {
  // 切频次时重置 send_day 到该频次的默认档（weekly=周一1；monthly/quarterly=1 号）
  subForm.send_day = 1
}

async function loadSubscriptions() {
  loadingSubs.value = true
  try {
    const res = await listSubscriptions({ page: 1, page_size: 50 })
    const body = res?.data ?? res
    subscriptions.value = body?.items ?? []
  } catch (err: any) {
    logger.error('[ReportExport] 加载订阅列表失败', err)
    ElMessage.error(err?.userMessage || '加载订阅列表失败')
  } finally {
    loadingSubs.value = false
  }
}

async function handleCreateSub() {
  if (!subForm.name.trim()) {
    ElMessage.warning('请填写订阅名称')
    return
  }
  creatingSub.value = true
  try {
    await createSubscription({
      name: subForm.name.trim(),
      report_type: subForm.report_type,
      format: subForm.format,
      frequency: subForm.frequency,
      send_day: subForm.frequency === 'daily' ? null : subForm.send_day,
      send_time: subForm.send_time,
      output_format: subForm.format,
    })
    ElMessage.success('订阅创建成功，到期将自动生成并站内通知')
    subDialogVisible.value = false
    await loadSubscriptions()
  } catch (err: any) {
    ElMessage.error(err?.userMessage || err?.response?.data?.detail || '创建订阅失败')
  } finally {
    creatingSub.value = false
  }
}

async function handleToggleSub(row: any) {
  try {
    await toggleSubscription(row.id)
    ElMessage.success(row.is_active ? '订阅已禁用' : '订阅已启用')
    await loadSubscriptions()
  } catch (err: any) {
    ElMessage.error(err?.userMessage || '切换订阅状态失败')
  }
}

async function handleGenerateNow(row: any) {
  generatingId.value = row.id
  try {
    await generateSubscriptionNow(row.id)
    ElMessage.success(`「${row.name}」已生成，文件信息见站内消息`)
    await loadSubscriptions()
  } catch (err: any) {
    ElMessage.error(err?.userMessage || err?.response?.data?.detail || '生成失败')
  } finally {
    generatingId.value = null
  }
}

async function handleDeleteSub(row: any) {
  try {
    await ElMessageBox.confirm(`确认删除订阅「${row.name}」？删除后不再生成报表。`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await deleteSubscription(row.id)
    ElMessage.success('订阅已删除')
    await loadSubscriptions()
  } catch (err: any) {
    ElMessage.error(err?.userMessage || '删除订阅失败')
  }
}

const officialLoading = reactive<Record<string, boolean>>({
  summary_word: false,
  summary_pdf: false,
  fund_detail_word: false,
  fund_detail_pdf: false,
  project_progress_word: false,
  project_progress_pdf: false,
})

const officialForm = reactive({
  year: new Date().getFullYear().toString(),
})

const exportForm = reactive({
  dateRange: null as [Date, Date] | null,
  scope: 'self',
  format: 'xlsx',
  includeCharts: true,
  dimensions: ['region', 'status'],
  fundTypes: ['budget', 'actual'],
  projectStatus: ['planning', 'in_progress', 'completed'],
})

// 标签映射
const exportStatusLabels: Record<string, string> = {
  pending: '等待中',
  processing: '处理中',
  completed: '已完成',
  failed: '失败',
}

const exportStatusTypes: Record<string, 'info' | 'primary' | 'success' | 'warning' | 'danger'> = {
  pending: 'info',
  processing: 'warning',
  completed: 'success',
  failed: 'danger',
}

// 方法
function selectReportType(type: string) {
  selectedType.value = type
}

function getReportTypeName(type: string): string {
  const report = reportTypes.find((r) => r.type === type)
  return report?.name || type
}

function getExportStatusLabel(status: string): string {
  return exportStatusLabels[status] || status
}

function getExportStatusType(
  status: string
): 'success' | 'info' | 'warning' | 'danger' | 'primary' {
  return exportStatusTypes[status] || 'info'
}

function formatDate(dateStr?: string): string {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

function resetForm() {
  exportForm.dateRange = null
  exportForm.scope = 'self'
  exportForm.format = 'xlsx'
  exportForm.includeCharts = true
}

function handlePrintPreview() {
  if (!selectedType.value) {
    ElMessage.warning('请先选择报表类型')
    return
  }
  window.print()
}

async function handleExportOfficial(reportType: string, format: 'word' | 'pdf') {
  const loadingKey = `${reportType}_${format}`
  officialLoading[loadingKey] = true
  try {
    const yearNum = officialForm.year ? Number(officialForm.year) : undefined
    if (format === 'word') {
      await exportReportWord(reportType, yearNum)
    } else {
      await exportReportPdf(reportType, yearNum)
    }

    const reportName = officialReportTypes.find((r) => r.type === reportType)?.name || reportType
    ElMessage.success(`${reportName} 导出成功`)
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || `${format.toUpperCase()} 导出失败`)
  } finally {
    officialLoading[loadingKey] = false
  }
}

async function handleExport() {
  if (!selectedType.value) {
    ElMessage.warning('请选择报表类型')
    return
  }

  exporting.value = true
  try {
    const params = {
      report_type: selectedType.value,
      format: exportForm.format,
      scope: exportForm.scope,
      include_charts: exportForm.includeCharts,
      start_date: exportForm.dateRange?.[0]?.toISOString(),
      end_date: exportForm.dateRange?.[1]?.toISOString(),
      options: {
        dimensions: exportForm.dimensions,
        fund_types: exportForm.fundTypes,
        project_status: exportForm.projectStatus,
      },
    }

    // 同步导出报表，直接下载文件
    const response = await post('/async-export/reports', params, {
      responseType: 'blob',
    })

    if (response instanceof Blob) {
      const blob = response
      const filename = getReportFileName(selectedType.value, exportForm.format)
      downloadBlob(blob, filename)
      ElMessage.success('报表导出成功')
    } else {
      ElMessage.warning('报表导出中，请稍后在导出历史查看进度')
      loadHistory()
    }
  } catch (error) {
    ElMessage.error((error as Error).message || '导出失败')
  } finally {
    exporting.value = false
  }
}

function getReportFileName(reportType: string, format: string): string {
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)
  const reportNames: Record<string, string> = {
    village_summary: '帮扶村汇总报表',
    fund_analysis: '资金使用分析报表',
    project_progress: '项目进度报表',
    school_statistics: '学校援建统计报表',
    annual_summary: '年度工作总结报表',
    comprehensive: '综合数据报表',
  }
  const name = reportNames[reportType] || '报表导出'
  return `${name}_${timestamp}.${format}`
}

async function loadHistory() {
  loadingHistory.value = true
  try {
    const response = await getExportHistory({ page: 1, page_size: 10 })
    exportHistory.value = response.items || []
  } catch (error) {
    logger.error('加载导出历史失败:', error)
  } finally {
    loadingHistory.value = false
  }
}

async function downloadExport(record: any) {
  try {
    await downloadExportFile(record.task_id)
  } catch (error) {
    ElMessage.error('下载失败')
  }
}

// 生命周期
onMounted(() => {
  loadHistory()
  loadSubscriptions()
})
</script>

<style scoped lang="scss">
.report-export {
  padding: 20px;

  .page-header {
    margin-bottom: 20px;

    .header-content {
      h2 {
        margin: 0 0 8px 0;
      }

      .description {
        margin: 0;
        color: var(--color-text-secondary);
        font-size: 14px;
      }
    }
  }

  .section-title {
    font-size: 16px;
    font-weight: 600;
    color: $military-dark;
    margin: 0 0 16px 0;
  }

  .report-types {
    margin-bottom: 20px;

    .type-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 16px;
    }

    .type-card {
      display: flex;
      align-items: center;
      padding: 16px;
      border: 2px solid var(--color-border-light);
      border-radius: 8px;
      cursor: pointer;
      transition: all 0.3s;

      &:hover {
        border-color: var(--color-primary-light-1);
        background-color: #f0f9f4;
      }

      &.active {
        border-color: var(--color-primary-light-1);
        background-color: #e8f5e9;
      }

      .el-icon {
        margin-right: 12px;
      }

      .type-info {
        display: flex;
        flex-direction: column;

        .type-name {
          font-weight: 600;
          color: var(--color-text-primary);
          margin-bottom: 4px;
        }

        .type-desc {
          font-size: 12px;
          color: var(--color-text-secondary);
        }
      }
    }
  }

  .export-config {
    margin-bottom: 20px;
  }

  .official-report-export {
    margin-bottom: 20px;

    .section-desc {
      margin: 0 0 16px 0;
      color: var(--color-text-secondary);
      font-size: 14px;
    }

    .official-report-list {
      display: flex;
      flex-direction: column;
      gap: 12px;
    }

    .official-report-item {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 16px;
      border: 1px solid var(--color-border-light);
      border-radius: 8px;
      transition: all 0.3s;

      &:hover {
        background-color: var(--color-bg-hover);
        border-color: var(--color-text-placeholder, $color-border);
      }
    }

    .report-info {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .report-text {
      display: flex;
      flex-direction: column;
    }

    .report-name {
      font-weight: 600;
      color: var(--color-text-primary);
      font-size: 15px;
    }

    .report-desc {
      color: var(--color-text-secondary);
      font-size: 12px;
      margin-top: 4px;
    }

    .report-actions {
      display: flex;
      gap: 8px;
    }
  }

  .subscription-management {
    margin-bottom: 20px;

    .section-desc {
      margin: 0 0 12px 0;
      color: var(--color-text-secondary);
      font-size: 14px;
    }

    .history-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 8px;

      > div {
        display: flex;
        gap: 8px;
      }
    }
  }

  .export-history {
    .history-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;

      .section-title {
        margin: 0;
      }
    }
  }
}

@media (max-width: 1200px) {
  .report-export .type-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .report-export .type-grid {
    grid-template-columns: 1fr;
  }
}
</style>
