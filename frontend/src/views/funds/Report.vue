<template>
  <div class="fund-report">
    <el-card class="filter-card">
      <el-form :inline="true" :model="filterForm">
        <el-form-item label="报表类型">
          <el-select
            v-model="filterForm.reportType"
            placeholder="请选择报表类型"
            clearable
            style="width: 140px"
          >
            <el-option label="月度报表" value="monthly" />
            <el-option label="季度报表" value="quarterly" />
            <el-option label="年度报表" value="yearly" />
          </el-select>
        </el-form-item>
        <el-form-item label="时间范围">
          <el-date-picker
            v-model="filterForm.dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            value-format="YYYY-MM-DD"
          />
        </el-form-item>
        <el-form-item label="经费类型">
          <el-select
            v-model="filterForm.fundType"
            placeholder="全部"
            clearable
            style="width: 140px"
          >
            <el-option v-for="(label, key) in FUND_TYPES" :key="key" :label="label" :value="key" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="generateReport">生成报表</el-button>
          <el-button @click="exportReport">导出报表</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="report-card">
      <template #header>
        <div class="card-header">
          <span class="title">经费使用报表</span>
          <div class="actions">
            <el-button type="primary" @click="printReport">打印</el-button>
            <el-button @click="exportReport">导出</el-button>
          </div>
        </div>
      </template>

      <div class="report-header">
        <h2>帮扶管理信息系统 — 经费使用报表</h2>
        <p>报表周期：{{ reportPeriod }}</p>
        <p>生成时间：{{ currentTime }}</p>
      </div>

      <el-table :data="reportData" stripe border show-summary>
        <el-table-column prop="date" label="日期" width="120" />
        <el-table-column prop="projectName" label="项目名称" min-width="180" />
        <el-table-column prop="fundType" label="经费类型" width="100" align="center">
          <template #default="{ row }">
            <el-tag>{{ getFundTypeName(row.fundType) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="amount" label="金额（万元）" width="120" align="center" />
        <!-- 数据键为 used_amount（见 loadReportData 映射），勿改成 usedAmount 否则列空白 -->
        <el-table-column prop="used_amount" label="已使用（万元）" width="120" align="center" />
        <el-table-column prop="balance" label="余额（万元）" width="120" align="center" />
        <el-table-column prop="usageRate" label="使用率" width="100" align="center">
          <template #default="{ row }"> {{ row.usageRate }}% </template>
        </el-table-column>
        <el-table-column prop="unit" label="使用单位" min-width="150" />
        <el-table-column prop="manager" label="负责人" width="100" />
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{ getStatusName(row.status) }}</el-tag>
          </template>
        </el-table-column>
      </el-table>

      <div class="report-summary">
        <h3>统计汇总</h3>
        <el-row :gutter="20">
          <el-col :span="6">
            <div class="summary-item">
              <div class="summary-label">总经费</div>
              <div class="summary-value">{{ summary.total }}万元</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="summary-item">
              <div class="summary-label">已使用</div>
              <div class="summary-value">{{ summary.used }}万元</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="summary-item">
              <div class="summary-label">剩余</div>
              <div class="summary-value">{{ summary.balance }}万元</div>
            </div>
          </el-col>
          <el-col :span="6">
            <div class="summary-item">
              <div class="summary-label">平均使用率</div>
              <div class="summary-value">{{ summary.avgUsageRate }}%</div>
            </div>
          </el-col>
        </el-row>
      </div>

      <div class="report-charts">
        <el-row :gutter="20">
          <el-col :span="12">
            <BaseChart :option="fundTypeChart" height="300px" />
          </el-col>
          <el-col :span="12">
            <BaseChart :option="usageTrendChart" height="300px" />
          </el-col>
        </el-row>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { logger } from '@/utils/logger'

import { ref, reactive, computed, onMounted } from 'vue'
import BaseChart from '@/components/common/BaseChart.vue'
import { ElMessage } from 'element-plus'
import { format } from '@/utils'
import { fundApi } from '@/api/funds'
import { FUND_TYPES, FUND_STATUSES } from '@/api/fundStatistics'
import { exportUtil } from '@/utils/exportUtil'

const loading = ref(false)

const filterForm = reactive({
  reportType: 'monthly',
  dateRange: [] as string[],
  fundType: '',
})

const reportData = ref<any[]>([])
const typeStatsData = ref<any[]>([])
const trendData = ref<any[]>([])

const summary = computed(() => {
  const total = reportData.value.reduce((s, i) => s + (i.amount || 0), 0)
  const used = reportData.value.reduce((s, i) => s + (i.used_amount || 0), 0)
  const balance = total - used
  const avgUsageRate = total > 0 ? parseFloat(((used / total) * 100).toFixed(2)) : 0
  return { total, used, balance, avgUsageRate }
})

const reportPeriod = computed(() => {
  if (filterForm.dateRange?.length === 2) {
    return `${filterForm.dateRange[0]} 至 ${filterForm.dateRange[1]}`
  }
  const now = new Date()
  return `${now.getFullYear()}年${now.getMonth() + 1}月`
})

const currentTime = computed(() => format.formatDateTime(new Date()))

const fundTypeChart = computed(() => {
  const data = typeStatsData.value.map((d) => ({
    value: d.total_amount,
    name: d.label,
  }))
  return {
    title: {
      text: '经费类型分布',
      left: 'center',
      textStyle: { color: '#fff' },
    },
    tooltip: { trigger: 'item' as const, formatter: '{b}: {c}万元 ({d}%)' },
    legend: {
      orient: 'horizontal' as const,
      bottom: 10,
      textStyle: { color: '#ccc' },
    },
    series: [
      {
        type: 'pie' as const,
        radius: ['40%', '70%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 10,
          borderColor: 'rgba(0,0,0,0.3)',
          borderWidth: 2,
        },
        data: data.length ? data : [{ value: 0, name: '暂无数据' }],
      },
    ],
  }
})

const usageTrendChart = computed(() => {
  const labels = trendData.value.map((d) => d.label)
  const amounts = trendData.value.map((d) => d.total_amount)
  const usedAmounts = trendData.value.map((d) => d.total_used)
  return {
    title: { text: '使用趋势', left: 'center', textStyle: { color: '#fff' } },
    tooltip: { trigger: 'axis' as const },
    legend: {
      data: ['总金额', '已使用'],
      bottom: 0,
      textStyle: { color: '#ccc' },
    },
    xAxis: {
      type: 'category' as const,
      data: labels.length ? labels : ['暂无'],
    },
    yAxis: { type: 'value' as const, axisLabel: { formatter: '{value}万' } },
    series: [
      {
        name: '总金额',
        data: amounts,
        type: 'line' as const,
        smooth: true,
        itemStyle: { color: '#40916c' },
      },
      {
        name: '已使用',
        data: usedAmounts,
        type: 'line' as const,
        smooth: true,
        itemStyle: { color: '#d4af37' },
      },
    ],
  }
})

const getFundTypeName = (type: string) => (FUND_TYPES as Record<string, string>)[type] || type
const getStatusName = (status: string) =>
  (FUND_STATUSES as Record<string, string>)[status] || status
const getStatusType = (status: string) => {
  const m: Record<string, 'info' | 'primary' | 'success' | 'warning' | 'danger'> = {
    pending: 'info',
    approved: 'success',
    allocated: 'success',
    in_use: 'warning',
    completed: 'info',
    audited: 'success',
    rejected: 'danger',
  }
  return m[status] as 'info' | 'primary' | 'success' | 'warning' | 'danger' | undefined
}

const loadReportData = async () => {
  loading.value = true
  try {
    const params: Record<string, any> = {}
    if (filterForm.fundType) params.type = filterForm.fundType
    if (filterForm.dateRange?.length === 2) {
      params.start_date = filterForm.dateRange[0]
      params.end_date = filterForm.dateRange[1]
    }
    // 加载经费列表数据
    const listRes = await fundApi.list({
      page: 1,
      page_size: 200,
      fund_type: params.type,
    })
    reportData.value = (listRes.items || []).map((f: any) => ({
      date: f.application_date || f.created_at?.slice(0, 10) || '-',
      projectName: f.name || '-',
      fundType: f.fund_type || f.type || '-',
      amount: f.amount || 0,
      used_amount: f.used_amount || 0,
      balance: (f.amount || 0) - (f.used_amount || 0),
      usageRate:
        f.amount > 0 ? parseFloat((((f.used_amount || 0) / f.amount) * 100).toFixed(2)) : 0,
      unit: f.source || f.fund_source || '-',
      manager: f.applicant || f.operator || '-',
      status: f.status || '-',
    }))
    // 加载类型分布
    const typeRes = await fundApi.statisticsMultiDimension({
      group_by: 'type',
      ...params,
    })
    if (typeRes?.success) typeStatsData.value = typeRes.data || []
    // 加载趋势（按月/季/年）
    const trendRes = await fundApi.statisticsMultiDimension({
      group_by: 'period',
      period_type: filterForm.reportType,
      ...params,
    })
    if (trendRes?.success) trendData.value = trendRes.data || []
  } catch (e) {
    logger.error('加载报表数据失败:', e)
  } finally {
    loading.value = false
  }
}

const generateReport = () => {
  loadReportData()
}

const exportReport = () => {
  if (!reportData.value.length) {
    ElMessage.warning('没有可导出的数据')
    return
  }
  exportUtil.exportToCSV(reportData.value, '经费使用报表', {
    date: '日期',
    projectName: '项目名称',
    fundType: '经费类型',
    amount: '总金额(万元)',
    used_amount: '已使用(万元)',
    balance: '余额(万元)',
    usageRate: '使用率(%)',
    unit: '使用单位',
    manager: '负责人',
    status: '状态',
  })
  ElMessage.success('报表导出成功')
}

const printReport = () => {
  window.print()
}

onMounted(() => {
  loadReportData()
})
</script>

<style scoped>
.fund-report {
  padding: 20px;
}

.filter-card,
.report-card {
  margin-bottom: 20px;
  background: rgba(10, 30, 20, 0.5);
  border: 1px solid rgba(64, 145, 108, 0.3);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.title {
  font-size: 16px;
  font-weight: bold;
  color: #fff;
}

.report-header {
  text-align: center;
  margin-bottom: 30px;
}

.report-header h2 {
  color: #fff;
  margin-bottom: 10px;
}

.report-header p {
  color: rgba(255, 255, 255, 0.7);
  margin: 5px 0;
}

.report-summary {
  margin: 30px 0;
}

.report-summary h3 {
  color: #fff;
  margin-bottom: 20px;
}

.summary-item {
  text-align: center;
  padding: 20px;
  background: rgba(64, 145, 108, 0.1);
  border-radius: 8px;
  border: 1px solid rgba(64, 145, 108, 0.3);
}

.summary-label {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.7);
  margin-bottom: 8px;
}

.summary-value {
  font-size: 24px;
  font-weight: bold;
  color: var(--color-primary-light-1);
}

.report-charts {
  margin-top: 30px;
}

:deep(.el-card__header) {
  background: linear-gradient(135deg, var(--color-primary) 0%, #1b4332 100%);
  border-bottom: 1px solid rgba(64, 145, 108, 0.3);
  color: #fff;
}

:deep(.el-table) {
  background: transparent;
  color: rgba(255, 255, 255, 0.9);
}

:deep(.el-table th.el-table__cell) {
  background: linear-gradient(135deg, #1b4332 0%, var(--color-primary) 100%);
  color: #fff;
  font-weight: bold;
}
</style>
