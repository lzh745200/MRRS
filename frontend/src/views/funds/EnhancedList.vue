<template>
  <div v-watermark class="fund-list-page">
    <!-- 页面头部 -->
    <!-- 页面头部区（PageHeader 标准件 · T1 契约） -->
    <PageHeader title="经费管理" subtitle="管理帮扶经费记录，跟踪资金流向与使用情况">
      <template #extra>
        <el-button type="primary" @click="handleCreate">
          <el-icon><Plus /></el-icon>新增经费
        </el-button>
        <el-button @click="pushSafe('/funds/budget')">
          <el-icon><Tickets /></el-icon>预算管理
        </el-button>
        <el-button @click="handleDownloadTemplate">
          <el-icon><Download /></el-icon>下载模板
        </el-button>
        <el-button :loading="exporting" :disabled="exporting" @click="handleExport">
          <el-icon><Download /></el-icon>导出
        </el-button>
      </template>
    </PageHeader>

    <!-- 经费管理全流程步骤条 -->
    <el-card class="flow-card">
      <el-steps
        :active="flowActiveStep"
        align-center
        finish-status="success"
        class="fund-flow-steps"
      >
        <el-step
          v-for="step in fundFlowSteps"
          :key="step.key"
          :title="step.label"
          :description="step.desc"
          class="fund-flow-step"
        >
          <template #icon>
            <el-icon @click="goFlowStep(step.path)"
              ><component :is="flowIcons[step.icon]"
            /></el-icon>
          </template>
        </el-step>
      </el-steps>
      <div class="flow-guide">
        <el-icon><InfoFilled /></el-icon>
        <span
          >当前流程阶段：<b>{{ currentFlowLabel }}</b
          >。点击步骤图标可跳转对应功能页，操作按钮下方均有前置条件说明。</span
        >
      </div>
    </el-card>

    <!-- 年度经费总览 -->
    <el-card class="year-overview-card">
      <div class="year-overview-header">
        <span class="year-overview-title">年度经费总览</span>
        <el-select v-model="overviewYear" style="width: 120px" @change="loadYearOverview">
          <el-option v-for="y in yearOptions" :key="y" :label="`${y}年`" :value="y" />
        </el-select>
      </div>
      <div class="year-overview-row">
        <div
          class="overview-item"
          role="button"
          tabindex="0"
          @click="pushSafe('/funds/budget')"
          @keydown.enter.prevent="pushSafe('/funds/budget')"
        >
          <div class="overview-value text-primary">{{ overview.budgetTotal }}</div>
          <div class="overview-label">年度预算(万元)</div>
          <div class="overview-hint">预算管理</div>
        </div>
        <div
          class="overview-item"
          role="button"
          tabindex="0"
          @click="pushSafe('/funds/budget')"
          @keydown.enter.prevent="pushSafe('/funds/budget')"
        >
          <div class="overview-value text-warning">{{ overview.budgetExecuted }}</div>
          <div class="overview-label">预算已执行(万元)</div>
          <div class="overview-hint">执行率 {{ overview.usageRate }}%</div>
        </div>
        <div
          class="overview-item"
          role="button"
          tabindex="0"
          @click="pushSafe('/funds')"
          @keydown.enter.prevent="pushSafe('/funds')"
        >
          <div class="overview-value">{{ overview.appliedAmount }}</div>
          <div class="overview-label">经费申请(万元)</div>
          <div class="overview-hint">{{ overview.appliedCount }} 笔</div>
        </div>
        <div
          class="overview-item"
          role="button"
          tabindex="0"
          @click="pushSafe('/funds')"
          @keydown.enter.prevent="pushSafe('/funds')"
        >
          <div class="overview-value text-success">{{ overview.allocatedAmount }}</div>
          <div class="overview-label">已拨付(万元)</div>
          <div class="overview-hint">{{ overview.allocatedCount }} 笔</div>
        </div>
        <div
          class="overview-item"
          role="button"
          tabindex="0"
          @click="pushSafe('/funds/analysis')"
          @keydown.enter.prevent="pushSafe('/funds/analysis')"
        >
          <div class="overview-value text-danger">{{ overview.usedAmount }}</div>
          <div class="overview-label">已使用(万元)</div>
          <div class="overview-hint">经费分析</div>
        </div>
        <div class="overview-item">
          <div class="overview-value">{{ overview.remaining }}</div>
          <div class="overview-label">预算结余(万元)</div>
          <div class="overview-hint">年度统计</div>
        </div>
      </div>
    </el-card>

    <!-- 统计卡片 -->
    <div class="stats-row">
      <div class="stat-item">
        <div class="stat-value">{{ stats.totalAmount }}</div>
        <div class="stat-label">经费总额(万元)</div>
      </div>
      <div
        class="stat-item stat-item--clickable"
        role="button"
        tabindex="0"
        @click="filterByStatus('allocated')"
        @keydown.enter.prevent="filterByStatus('allocated')"
        @keydown.space.prevent="filterByStatus('allocated')"
      >
        <div class="stat-value text-success">{{ stats.allocatedAmount }}</div>
        <div class="stat-label">已拨付(万元)</div>
      </div>
      <div
        class="stat-item stat-item--clickable"
        role="button"
        tabindex="0"
        @click="filterByStatus('pending')"
        @keydown.enter.prevent="filterByStatus('pending')"
        @keydown.space.prevent="filterByStatus('pending')"
      >
        <div class="stat-value text-warning">{{ stats.pendingCount }}</div>
        <div class="stat-label">待审批</div>
      </div>
      <div
        class="stat-item stat-item--clickable"
        role="button"
        tabindex="0"
        @click="filterByStatus('planned')"
        @keydown.enter.prevent="filterByStatus('planned')"
        @keydown.space.prevent="filterByStatus('planned')"
      >
        <div class="stat-value text-info">{{ stats.plannedCount }}</div>
        <div class="stat-label">规划中</div>
      </div>
      <div class="stat-item">
        <div class="stat-value text-primary">{{ stats.totalCount }}</div>
        <div class="stat-label">记录总数</div>
      </div>
    </div>

    <!-- 快速入口 -->
    <div class="quick-nav-row">
      <div class="quick-nav-card" @click="pushSafe('/funds/budget')">
        <el-icon size="22"><Tickets /></el-icon>
        <span>预算管理</span>
      </div>
      <div class="quick-nav-card" @click="pushSafe('/funds/user')">
        <el-icon size="22"><EditPen /></el-icon>
        <span>经费申请</span>
      </div>
      <div class="quick-nav-card" @click="pushSafe('/funds/contract')">
        <el-icon size="22"><Document /></el-icon>
        <span>合同管理</span>
      </div>
      <div class="quick-nav-card" @click="pushSafe('/funds/transfer')">
        <el-icon size="22"><Money /></el-icon>
        <span>转账凭证</span>
      </div>
      <div class="quick-nav-card" @click="pushSafe('/funds/anomaly')">
        <el-icon size="22"><Warning /></el-icon>
        <span>异常监控</span>
      </div>
      <div class="quick-nav-card" @click="pushSafe('/funds/analysis')">
        <el-icon size="22"><DataAnalysis /></el-icon>
        <span>经费分析</span>
      </div>
    </div>

    <!-- 搜索筛选 -->
    <div class="filter-card">
      <el-form :model="filterForm" inline @submit.prevent>
        <el-form-item label="经费名称">
          <el-input
            v-model="filterForm.keyword"
            placeholder="名称/项目/来源"
            clearable
            style="width: 200px"
            @keyup.enter="handleSearch"
          />
        </el-form-item>
        <el-form-item label="经费类型">
          <el-select
            v-model="filterForm.type"
            placeholder="全部类型"
            clearable
            style="width: 130px"
          >
            <el-option label="项目经费" value="project" />
            <el-option label="运营经费" value="operation" />
            <el-option label="教育帮扶" value="education" />
            <el-option label="基础设施" value="infrastructure" />
            <el-option label="应急经费" value="emergency" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select
            v-model="filterForm.status"
            placeholder="全部状态"
            clearable
            style="width: 130px"
          >
            <el-option label="待审批" value="pending" />
            <el-option label="已计划" value="planned" />
            <el-option label="已批准" value="approved" />
            <el-option label="已拨付" value="allocated" />
            <el-option label="使用中" value="in_use" />
            <el-option label="已完成" value="completed" />
            <el-option label="已审计" value="audited" />
            <el-option label="已驳回" value="rejected" />
          </el-select>
        </el-form-item>
        <el-form-item label="帮扶村">
          <el-select
            v-model="filterForm.village_id"
            placeholder="全部村"
            clearable
            filterable
            style="width: 160px"
          >
            <el-option v-for="v in villageOptions" :key="v.id" :label="v.name" :value="v.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="帮扶学校">
          <el-select
            v-model="filterForm.school_id"
            placeholder="全部学校"
            clearable
            filterable
            style="width: 160px"
          >
            <el-option v-for="s in schoolOptions" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">
            <el-icon><Search /></el-icon>搜索
          </el-button>
          <el-button @click="handleReset">重置</el-button>
          <el-form-item>
            <el-tooltip
              v-if="canViewDeleted"
              content="切换显示已软删的经费（管理员可见）"
              placement="top"
            >
              <el-switch
                v-model="showDeletedOnly"
                inline-prompt
                active-text="回收站"
                inactive-text="正常"
                style="margin-left: 12px"
                @change="handleToggleDeleted"
              />
            </el-tooltip>
          </el-form-item>
        </el-form-item>
      </el-form>
    </div>

    <!-- 数据表格 -->
    <div class="table-card">
      <!-- 批量操作工具栏 -->
      <div v-if="selectedRows.length > 0" class="batch-toolbar">
        <span class="batch-info">已选择 {{ selectedRows.length }} 项</span>
        <el-button
          type="danger"
          size="small"
          :loading="batchDeleting"
          :disabled="batchDeleting"
          @click="handleBatchDelete"
        >
          批量删除
        </el-button>
        <el-button
          size="small"
          :loading="exporting"
          :disabled="exporting"
          @click="handleBatchExport"
        >
          导出选中
        </el-button>
        <el-button size="small" text @click="clearSelection">取消选择</el-button>
      </div>
      <div v-if="error && tableData.length === 0" class="error-placeholder">
        <el-result icon="error" title="数据加载失败" :sub-title="errorMsg || '请稍后重试'">
          <template #extra>
            <el-button type="primary" :loading="loading" @click="fetchData">重试</el-button>
          </template>
        </el-result>
      </div>
      <el-table
        v-else
        ref="tableRef"
        v-loading="loading"
        :data="tableData"
        stripe
        @selection-change="handleSelectionChange"
      >
        <template #empty>
          <EmptyState text="暂无数据" />
        </template>
        <el-table-column type="selection" width="45" />
        <el-table-column type="index" label="序号" width="60" align="center" />
        <el-table-column prop="name" label="经费名称" min-width="180">
          <template #default="scope">
            <el-link type="primary" @click="handleView(scope.row)">{{ scope.row.name }}</el-link>
          </template>
        </el-table-column>
        <el-table-column prop="type" label="类型" width="110" align="center">
          <template #default="scope">
            <el-tag size="small">{{ getFundTypeLabel(scope.row.type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="amount" label="金额(万元)" width="120" align="right">
          <template #default="scope">
            <span class="amount-text">{{ formatAmount(scope.row.amount) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="project_name" label="关联项目" width="160" show-overflow-tooltip>
          <template #default="scope">
            {{ scope.row.project_name || scope.row.project || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="scope">
            <el-tag :type="getStatusType(scope.row.status)" size="small">
              {{ getFundStatusLabel(scope.row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="source" label="经费来源" width="120" show-overflow-tooltip />
        <el-table-column label="健康度" width="100" align="center">
          <template #default="scope">
            <el-progress
              v-if="scope.row.health_score != null"
              type="circle"
              :percentage="scope.row.health_score"
              :width="36"
              :stroke-width="4"
              :color="
                scope.row.health_score >= 80
                  ? chartColor('success')
                  : scope.row.health_score >= 60
                    ? chartColor('warning')
                    : chartColor('danger')
              "
            />
            <span v-else class="text-muted">--</span>
          </template>
        </el-table-column>
        <el-table-column label="阶段" width="110" align="center">
          <template #default="scope">
            <el-tag v-if="scope.row.lifecycle_phase" size="small" effect="plain">
              {{ phaseLabels[scope.row.lifecycle_phase] || `阶段${scope.row.lifecycle_phase}` }}
            </el-tag>
            <span v-else class="text-muted">--</span>
          </template>
        </el-table-column>
        <el-table-column prop="date" label="日期" width="110" align="center">
          <template #default="scope">
            {{
              scope.row.date || (scope.row.created_at ? scope.row.created_at.split('T')[0] : '-')
            }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="280">
          <template #default="scope">
            <el-button type="primary" link size="small" @click="handleView(scope.row)"
              >查看</el-button
            >
            <el-button
              v-if="scope.row.project_id"
              type="primary"
              link
              size="small"
              @click="pushSafe('/funds/lifecycle/' + scope.row.project_id)"
              >生命周期</el-button
            >
            <el-button type="primary" link size="small" @click="handleEdit(scope.row)"
              >编辑</el-button
            >
            <el-button
              v-if="scope.row.status === 'pending'"
              type="success"
              link
              size="small"
              :loading="approving[scope.row.id]"
              :disabled="approving[scope.row.id]"
              @click="quickApprove(scope.row)"
              >审批</el-button
            >
            <el-button
              v-if="scope.row.status === 'approved'"
              type="warning"
              link
              size="small"
              :loading="allocating[scope.row.id]"
              :disabled="allocating[scope.row.id]"
              @click="quickAllocate(scope.row)"
              >拨付</el-button
            >
            <template v-if="!showDeletedOnly">
              <el-popconfirm title="确定删除该经费记录吗？" @confirm="handleDelete(scope.row)">
                <template #reference>
                  <el-button
                    type="danger"
                    link
                    size="small"
                    :loading="deleting[scope.row.id]"
                    :disabled="deleting[scope.row.id]"
                    >删除</el-button
                  >
                </template>
              </el-popconfirm>
            </template>
            <template v-else>
              <el-button type="success" link size="small" @click="handleRestore(scope.row)"
                >恢复</el-button
              >
              <el-button type="danger" link size="small" @click="handlePurge(scope.row)"
                >彻底删除</el-button
              >
            </template>
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
    </div>
  </div>
</template>

<script setup lang="ts">
import EmptyState from '@/components/business/EmptyState/EmptyState.vue'
import PageHeader from '@/components/common/PageHeader.vue'
import { logger } from '@/utils/logger'
import { getErrorMessage } from '@/utils/getErrorMessage'
import { getYearOptions } from '@/utils/yearOptions'

import { ref, reactive, computed, onMounted } from 'vue'
import { useRouterSafe } from '@/composables/useRouterSafe'
import { ElMessage, ElMessageBox, ElNotification } from 'element-plus'
import {
  Plus,
  Download,
  Search,
  Tickets,
  EditPen,
  Document,
  Money,
  Warning,
  DataAnalysis,
  Stamp,
  Coin,
  DocumentChecked,
  FolderOpened,
  InfoFilled,
} from '@element-plus/icons-vue'
import { get, del, apiRequest } from '@/api/request'
import { fundApi } from '@/api/funds'
import { restoreFund, previewPurgeFund, purgeFund } from '@/api/fundsRecycle'
import { useAuthStore } from '@/stores/auth'
import { getSupportedVillages } from '@/api/supportedVillage'
import { schoolsApi } from '@/api/schools'
import { downloadImportTemplateAndSave } from '@/api/import'
import { getFundTypeLabel, getFundStatusLabel } from '@/config/enums'
import { chartColor } from '@/utils/chartColors'

const phaseLabels: Record<number, string> = {
  1: '论证立项',
  2: '汇总审核',
  3: '计划拨付',
  4: '对接',
  5: '实施监管',
  6: '核查督查',
  7: '决算绩效',
}

const { pushSafe } = useRouterSafe()
const tableData = ref<any[]>([])
const loading = ref(false)
const error = ref(false)
const errorMsg = ref('')
const exporting = ref(false)
const approving = ref<Record<number, boolean>>({})
const allocating = ref<Record<number, boolean>>({})
const deleting = ref<Record<number, boolean>>({})
const batchDeleting = ref(false)
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const selectedRows = ref<any[]>([])
const tableRef = ref<any>(null)

const filterForm = reactive({
  keyword: '',
  type: '',
  status: '',
  village_id: '' as string | number,
  school_id: '' as string | number,
})

// 帮扶村/学校下拉选项
const villageOptions = ref<{ id: number; name: string }[]>([])
const schoolOptions = ref<{ id: number; name: string }[]>([])

// 服务端统计数据（全量准确）
const serverStats = ref<any>(null)
const stats = computed(() => {
  const s = serverStats.value
  if (s) {
    const byStatus = s.by_status || {}
    return {
      totalAmount: formatAmount(s.total_amount || 0),
      allocatedAmount: formatAmount(s.total_allocated || 0),
      pendingCount: byStatus.pending?.count || 0,
      plannedCount: byStatus.planned?.count || 0,
      totalCount: s.total_count || total.value,
    }
  }
  // 回退：服务端统计不可用时使用当前页数据
  const list = tableData.value
  const totalAmount = list.reduce((sum, f) => sum + (Number(f.amount) || 0), 0)
  const allocatedAmount = list
    .filter((f) => f.status === 'allocated' || f.status === 'completed' || f.status === 'audited')
    .reduce((sum, f) => sum + (Number(f.amount) || 0), 0)
  return {
    totalAmount: formatAmount(totalAmount),
    allocatedAmount: formatAmount(allocatedAmount),
    pendingCount: list.filter((f) => f.status === 'pending').length,
    plannedCount: list.filter((f) => f.status === 'planned').length,
    totalCount: total.value || list.length,
  }
})

async function loadStats() {
  try {
    const res: any = await get('/funds/statistics/overview')
    // 防御：兼容信封/裸数据两种形态（信封保留 data 键，裸数据直接使用）
    const d = res?.data ?? res
    if (d && d.total_amount !== undefined) serverStats.value = d
  } catch {
    /* 统计加载失败不阻塞主流程 */
  }
}

// ========== 年度经费总览 ==========
const overviewYear = ref(new Date().getFullYear())
// 年份范围：当前年-9 ~ 当前年+10（滚动窗口，见 utils/yearOptions）
const yearOptions = computed(() => getYearOptions({ start: new Date().getFullYear() - 9 }))
const overview = reactive({
  budgetTotal: '0.00',
  budgetExecuted: '0.00',
  usageRate: 0,
  appliedAmount: '0.00',
  appliedCount: 0,
  allocatedAmount: '0.00',
  allocatedCount: 0,
  usedAmount: '0.00',
  remaining: '0.00',
})

// ── 经费管理全流程步骤条（预算编制 → 申请 → 审批 → 拨付 → 使用 → 核销 → 结算 → 归档） ──
const fundFlowSteps = [
  {
    key: 'budget',
    label: '预算编制',
    desc: '年度预算管理',
    path: '/funds/budget',
    icon: 'Tickets',
  },
  { key: 'apply', label: '经费申请', desc: '提交经费申请', path: '/funds/user', icon: 'EditPen' },
  { key: 'approve', label: '审批', desc: '审批通过', path: '/approval/pending', icon: 'Stamp' },
  { key: 'allocate', label: '拨付', desc: '经费拨付到账', path: '/funds', icon: 'Money' },
  { key: 'use', label: '使用执行', desc: '投入使用', path: '/funds', icon: 'Coin' },
  {
    key: 'reimburse',
    label: '报销核销',
    desc: '发票与报销',
    path: '/funds/contract',
    icon: 'DocumentChecked',
  },
  {
    key: 'settle',
    label: '决算结算',
    desc: '项目结算',
    path: '/funds/settlement',
    icon: 'DataAnalysis',
  },
  { key: 'archive', label: '归档', desc: '审计归档', path: '/funds/report', icon: 'FolderOpened' },
] as const

// 图标组件映射（字符串 → 组件，供模板 <component :is> 使用）
const flowIcons: Record<string, any> = {
  Tickets,
  EditPen,
  Stamp,
  Money,
  Coin,
  DocumentChecked,
  DataAnalysis,
  FolderOpened,
}

// 当前已到达的流程阶段（根据年度总览统计启发式计算）
const flowActiveStep = computed(() => {
  let step = 0
  if (Number(overview.budgetTotal) > 0) step = 1
  if (overview.appliedCount > 0) step = 2
  if (overview.allocatedCount > 0) step = 3
  if (Number(overview.usedAmount) > 0) step = 4
  return step
})

const currentFlowLabel = computed(() => {
  const steps = fundFlowSteps
  const idx = Math.min(flowActiveStep.value, steps.length - 1)
  return steps[idx].label
})

function goFlowStep(path: string) {
  pushSafe(path)
}

async function loadYearOverview() {
  try {
    const res = await get('/funds/statistics/overview', { year: overviewYear.value })
    const d = res.data || res
    if (!d || d.total_amount === undefined) return
    overview.budgetTotal = formatAmount(d.budget_total || 0)
    overview.budgetExecuted = formatAmount(d.budget_executed || 0)
    overview.usageRate = Number(d.usage_rate || 0)
    overview.appliedAmount = formatAmount(d.total_amount || 0)
    overview.appliedCount = d.total_count || 0
    overview.allocatedAmount = formatAmount(d.allocated_amount || 0)
    overview.allocatedCount = d.allocated_count || 0
    overview.usedAmount = formatAmount(d.used_amount || 0)
    overview.remaining = formatAmount(
      d.budget_remaining ?? Number(d.budget_total || 0) - Number(d.budget_executed || 0)
    )
  } catch {
    /* 年度总览加载失败不阻塞主流程 */
  }
}

function formatAmount(val: any) {
  const num = Number(val)
  if (isNaN(num)) return '0'
  return num.toLocaleString('zh-CN', {
    maximumFractionDigits: 4,
  })
}

async function fetchData() {
  loading.value = true
  error.value = false
  errorMsg.value = ''
  try {
    const response = await apiRequest({
      method: 'GET',
      url: '/funds',
      params: {
        page: currentPage.value,
        page_size: pageSize.value,
        include_deleted: showDeletedOnly.value || undefined,
        keyword: filterForm.keyword || undefined,
        fund_type: filterForm.type || undefined,
        status: filterForm.status || undefined,
        village_id: filterForm.village_id || undefined,
        school_id: filterForm.school_id || undefined,
      },
    })
    // 防御：apiRequest 已解包；信封保留 data 键，裸数据直接使用
    const resData = (response as any)?.data ?? response
    tableData.value =
      resData?.items || resData?.data?.items || (Array.isArray(resData) ? resData : [])
    total.value = resData?.total || resData?.data?.total || tableData.value.length
  } catch (e) {
    error.value = true
    logger.error('加载数据失败:', e)
    // 内联错误态展示真实原因（不再弹全局提示）
    errorMsg.value = getErrorMessage(e, '数据加载失败，请稍后重试')
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
  filterForm.village_id = ''
  filterForm.school_id = ''
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
  pushSafe('/funds/create')
}
function handleView(row: any) {
  pushSafe(`/funds/${row.id}`)
}
function handleEdit(row: any) {
  pushSafe(`/funds/${row.id}/edit`)
}
async function handleDelete(row: any) {
  if (deleting.value[row.id]) return
  deleting.value[row.id] = true
  try {
    await del(`/funds/${row.id}`)
    // 成功静默：仅刷新列表（关键反馈留给审批/拨付等动作）
    // 立即从前端列表中移除，确保界面及时更新
    tableData.value = tableData.value.filter((item: any) => item.id !== row.id)
    total.value = Math.max(0, total.value - 1)
    currentPage.value = 1 // 重置到第1页，确保新建/编辑后的数据可见
    fetchData()
    loadStats()
    loadYearOverview() // 年度总览卡与流程步骤条同步刷新
  } catch (e: any) {
    const detail = e?.response?.data?.detail || e?.message || '删除失败'
    ElMessage.error(`删除失败: ${detail}`)
  } finally {
    delete deleting.value[row.id]
  }
}
async function handleDownloadTemplate() {
  try {
    await downloadImportTemplateAndSave('fund', '经费')
  } catch {
    ElMessage.error('模板下载失败，请重试')
  }
}

async function handleExport() {
  if (exporting.value) return
  exporting.value = true
  try {
    await fundApi.exportList({
      search: filterForm.keyword || undefined,
      type: filterForm.type || undefined,
      status: filterForm.status || undefined,
    })
    // 导出成功 — 浏览器已确认（下载完成）
  } catch (e) {
    ElMessage.error(getErrorMessage(e, '导出失败'))
  } finally {
    exporting.value = false
  }
}

async function quickApprove(row: any) {
  if (approving.value[row.id]) return
  approving.value[row.id] = true
  try {
    await fundApi.approve(row.id, {})
    ElNotification({
      title: '审批通过',
      message: `经费「${row.name || row.id}」已审批通过`,
      type: 'success',
    })
    currentPage.value = 1 // 重置到第1页，确保新建/编辑后的数据可见
    fetchData()
    loadStats()
    loadYearOverview() // 年度总览卡与流程步骤条同步刷新
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '审批失败')
  } finally {
    delete approving.value[row.id]
  }
}
async function quickAllocate(row: any) {
  if (allocating.value[row.id]) return
  allocating.value[row.id] = true
  try {
    await fundApi.allocate(row.id, {})
    ElNotification({
      title: '经费拨付',
      message: `经费「${row.name || row.id}」已拨付到账`,
      type: 'success',
    })
    currentPage.value = 1 // 重置到第1页，确保新建/编辑后的数据可见
    fetchData()
    loadStats()
    loadYearOverview() // 年度总览卡与流程步骤条同步刷新
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '拨付失败')
  } finally {
    delete allocating.value[row.id]
  }
}

function getStatusType(status: string): 'success' | 'info' | 'warning' | 'danger' | 'primary' {
  const m: Record<string, 'success' | 'info' | 'warning' | 'danger' | 'primary'> = {
    pending: 'warning',
    planned: 'info',
    approved: 'primary',
    allocated: 'info',
    in_use: 'primary',
    completed: 'success',
    audited: 'success',
  }
  return m[status] || 'info'
}

// 批量操作
function handleSelectionChange(rows: any[]) {
  selectedRows.value = rows
}
function clearSelection() {
  tableRef.value?.clearSelection?.()
  selectedRows.value = []
}
async function handleBatchDelete() {
  if (!selectedRows.value.length || batchDeleting.value) return
  const count = selectedRows.value.length
  try {
    await ElMessageBox.confirm(`确定删除选中的 ${count} 条经费记录吗？`, '批量删除确认', {
      type: 'warning',
    })
  } catch {
    return
  }
  batchDeleting.value = true
  try {
    let deleted = 0
    let failed = 0
    const deletedIds: any[] = []
    for (const row of selectedRows.value) {
      try {
        await del(`/funds/${row.id}`)
        deleted++
        deletedIds.push(row.id)
      } catch {
        failed++
      }
    }
    // 立即从前端列表中移除已删除的记录
    tableData.value = tableData.value.filter((item: any) => !deletedIds.includes(item.id))
    total.value = Math.max(0, total.value - deleted)
    if (deleted > 0) ElMessage.success(`成功删除 ${deleted} 条记录`)
    if (failed > 0) ElMessage.warning(`${failed} 条记录删除失败`)
    clearSelection()
    currentPage.value = 1 // 重置到第1页，确保新建/编辑后的数据可见
    fetchData()
    loadStats()
    loadYearOverview() // 年度总览卡与流程步骤条同步刷新
  } finally {
    batchDeleting.value = false
  }
}
async function handleBatchExport() {
  if (exporting.value) return
  exporting.value = true
  try {
    await fundApi.exportList({})
    // 导出成功 — 浏览器已确认（下载完成）
  } catch (e) {
    ElMessage.error(getErrorMessage(e, '导出失败'))
  } finally {
    exporting.value = false
  }
}

async function loadVillageOptions() {
  try {
    const res = await getSupportedVillages({ page: 1, page_size: 200 })
    const body: any = res.data || res
    const items = body?.items || body?.data?.items || (Array.isArray(body) ? body : [])
    villageOptions.value = items.map((v: any) => ({
      id: v.id,
      name: v.village_name || v.name || `村${v.id}`,
    }))
  } catch {
    /* 非关键路径，静默失败 */
  }
}

async function loadSchoolOptions() {
  try {
    const res = await schoolsApi.list({ page: 1, page_size: 200 })
    const body: any = res.data || res
    const items = body?.items || body?.data?.items || (Array.isArray(body) ? body : [])
    schoolOptions.value = items.map((s: any) => ({
      id: s.id,
      name: s.school_name || s.name || `学校${s.id}`,
    }))
  } catch {
    /* 非关键路径，静默失败 */
  }
}

onMounted(() => {
  fetchData()
  loadStats()
  loadYearOverview()
  loadVillageOptions()
  loadSchoolOptions()
})

// ── 回收站（Phase C 推广）──
const authStore = useAuthStore()
const canViewDeleted = computed(() => authStore.canViewDeleted)
const showDeletedOnly = ref(false)

function handleToggleDeleted() {
  currentPage.value = 1
  fetchData()
}

async function handleRestore(row: any) {
  try {
    await ElMessageBox.confirm(`确定恢复经费【${row.name || row.id}】吗？`, '恢复确认', {
      confirmButtonText: '确认恢复',
      cancelButtonText: '取消',
      type: 'info',
    })
  } catch {
    return
  }
  try {
    await restoreFund(row.id)
    ElMessage.success('恢复成功')
    fetchData()
  } catch {
    ElMessage.error('恢复失败')
  }
}

async function handlePurge(row: any) {
  let totalRefs = 0
  try {
    const pv: any = await previewPurgeFund(row.id)
    totalRefs = Number((pv?.data || pv)?.total_references || 0)
  } catch {
    // 预览失败不阻断流程
  }
  try {
    await ElMessageBox.confirm(
      `彻底删除后该经费及其关联的 ${totalRefs} 条数据将无法恢复！不可撤销。`,
      '彻底删除警告',
      { confirmButtonText: '继续', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }
  let confirmPassword = ''
  try {
    const r = await ElMessageBox.prompt('请输入登录密码以确认彻底删除：', '二次确认', {
      confirmButtonText: '确认彻底删除',
      inputType: 'password',
      inputValidator: (v: string) => (v ? true : '密码不能为空'),
    })
    confirmPassword = r.value || ''
  } catch {
    return
  }
  loading.value = true
  try {
    await purgeFund(row.id, confirmPassword)
    ElMessage.success('已彻底删除')
    fetchData()
  } catch {
    ElMessage.error('彻底删除失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.fund-list-page {
  padding: 20px;
}

/* 经费管理全流程步骤条 */
.flow-card {
  margin-bottom: 16px;
}
.fund-flow-steps {
  padding: 8px 0;
}
.fund-flow-step {
  cursor: pointer;
}
.flow-guide {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 10px;
  padding: 8px 12px;
  background: var(--color-primary-light-9, #f0f9f4);
  border-radius: 6px;
  font-size: 12px;
  color: var(--color-text-secondary);
}
.flow-guide .el-icon {
  color: var(--color-primary);
}
.flow-guide b {
  color: var(--color-primary-dark-1);
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
  gap: 10px;
}

/* 统计卡片 */
.stats-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-md);
  margin-bottom: 20px;
}

.stat-item {
  flex: 1;
  min-width: 160px;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-lighter);
  border-radius: var(--radius-lg);
  padding: 16px 20px;
  text-align: center;
  box-shadow: var(--shadow-sm);
  transition: all 0.3s;
}

.stat-item--clickable {
  cursor: pointer;
}

.stat-item--clickable:hover {
  border-color: var(--color-primary-light-3);
}

.stat-value {
  font-size: 26px;
  font-weight: 700;
  color: var(--color-primary-dark-1);
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

/* 年度经费总览 */
.year-overview-card {
  margin-bottom: 16px;
}

.year-overview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.year-overview-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.year-overview-row {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 12px;
}

.overview-item {
  background: #f7f9fc;
  border-radius: 8px;
  padding: 14px;
  cursor: pointer;
  transition: all 0.3s;
  border: 1px solid transparent;
}

.overview-item:hover {
  border-color: var(--color-primary-light-3);
  background: #f0f5ff;
}

.overview-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--color-primary-dark-1);
  line-height: 1.2;
}

.overview-label {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin-top: 4px;
}

.overview-hint {
  font-size: 12px;
  color: var(--color-info);
  margin-top: 4px;
}

.text-danger {
  color: var(--color-danger);
}

@media (max-width: 1400px) {
  .year-overview-row {
    grid-template-columns: repeat(3, 1fr);
  }
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

.amount-text {
  font-weight: 600;
  color: var(--color-primary-dark-1);
}

.batch-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  background: var(--color-bg-active);
  border: 1px solid var(--color-primary-light-3);
  border-radius: 6px;
  margin-bottom: 12px;
}

.batch-info {
  font-size: 13px;
  color: var(--color-primary-dark-1);
  font-weight: 500;
}

.pagination-wrapper {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

/* 快速入口卡片 */
.quick-nav-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 20px;
}
.quick-nav-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  min-width: 100px;
  padding: 14px 18px;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-lighter);
  border-radius: var(--radius-lg);
  cursor: pointer;
  transition: all 0.25s;
  color: var(--color-primary-dark-1);
}
.quick-nav-card:hover {
  border-color: var(--color-primary-light-3);
  background: var(--color-bg-active);
  transform: translateY(-2px);
  box-shadow: var(--shadow-sm);
}
.quick-nav-card span {
  font-size: 13px;
  font-weight: 500;
}
</style>
