<template>
  <div class="data-verify-page">
    <div class="page-header">
      <h2 class="page-title">数据校验审核</h2>
      <p class="page-desc">审核帮扶项目数据的完整性、准确性和一致性</p>
    </div>

    <div class="stats-row">
      <div class="stat-card">
        <div class="stat-value">{{ stats.pending }}</div>
        <div class="stat-label">待审核</div>
      </div>
      <div class="stat-card">
        <div class="stat-value text-success">{{ stats.approved }}</div>
        <div class="stat-label">已通过</div>
      </div>
      <div class="stat-card">
        <div class="stat-value text-danger">{{ stats.rejected }}</div>
        <div class="stat-label">已驳回</div>
      </div>
      <div class="stat-card">
        <div class="stat-value text-warning">{{ stats.issues }}</div>
        <div class="stat-label">数据问题</div>
      </div>
    </div>

    <el-card class="query-check-card">
      <template #header>
        <div class="card-header">
          <span>条件查询校验（小白友好：下拉选择字段与关系，快速筛查数据）</span>
        </div>
      </template>
      <el-form :inline="false" label-width="80px">
        <el-form-item label="数据模块">
          <el-select v-model="qc.module" style="width: 180px" @change="qcLoadFields">
            <el-option label="帮扶村" value="village" />
            <el-option label="学校" value="school" />
            <el-option label="项目" value="project" />
            <el-option label="经费" value="fund" />
          </el-select>
          <el-radio-group v-model="qc.logic" style="margin-left: 16px">
            <el-radio value="and">全部满足（与）</el-radio>
            <el-radio value="or">任一满足（或）</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item
          v-for="(cond, idx) in qc.conditions"
          :key="idx"
          :label="idx === 0 ? '校验条件' : ''"
        >
          <el-select v-model="cond.field" placeholder="选择字段" style="width: 180px" filterable>
            <el-option v-for="f in qc.fields" :key="f.key" :label="f.label" :value="f.key" />
          </el-select>
          <el-select v-model="cond.operator" style="width: 140px; margin-left: 8px">
            <el-option label="等于" value="eq" />
            <el-option label="不等于" value="ne" />
            <el-option label="大于" value="gt" />
            <el-option label="大于等于" value="gte" />
            <el-option label="小于" value="lt" />
            <el-option label="小于等于" value="lte" />
            <el-option label="包含" value="contains" />
            <el-option label="不包含" value="not_contains" />
            <el-option label="为空" value="empty" />
            <el-option label="不为空" value="not_empty" />
          </el-select>
          <el-input
            v-if="!['empty', 'not_empty'].includes(cond.operator)"
            v-model="cond.value"
            placeholder="输入比较值"
            style="width: 160px; margin-left: 8px"
          />
          <el-button
            v-if="qc.conditions.length > 1"
            link
            type="danger"
            style="margin-left: 8px"
            @click="qcRemoveCondition(idx)"
          >
            删除
          </el-button>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="qcLoading" @click="qcRunCheck">执行校验</el-button>
          <el-button @click="qcAddCondition">添加条件</el-button>
          <el-button @click="qcReset">重置</el-button>
        </el-form-item>
      </el-form>

      <el-alert
        v-if="qcResult"
        :type="qcResult.unmatched === 0 ? 'success' : 'warning'"
        :title="qcResult.message"
        :closable="false"
        show-icon
        style="margin-bottom: 12px"
      />
      <el-table
        v-if="qcResult"
        v-loading="qcLoading"
        :data="qcResult.results"
        size="small"
        stripe
        max-height="360"
      >
        <el-table-column prop="id" label="记录ID" width="80" />
        <el-table-column label="是否满足" width="90">
          <template #default="{ row }">
            <el-tag :type="row.matched ? 'success' : 'danger'" size="small">
              {{ row.matched ? '满足' : '不满足' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column
          v-for="c in qc.conditions"
          :key="c.field"
          :label="qcFieldLabel(c.field)"
          min-width="110"
        >
          <template #default="{ row }">
            {{ row.values?.[c.field] ?? '-' }}
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card>
      <template #header>
        <div class="card-header">
          <span>待审核数据列表</span>
          <div>
            <el-button type="primary" :loading="batchChecking" @click="handleBatchCheck"
              >批量校验</el-button
            >
            <el-button @click="loadData">刷新</el-button>
          </div>
        </div>
      </template>

      <el-table v-loading="loading" :data="dataList" stripe>
        <el-table-column type="selection" width="50" />
        <el-table-column prop="villageName" label="帮扶村" min-width="120" />
        <el-table-column prop="department" label="部门单位" min-width="120" />
        <el-table-column prop="submitter" label="提交人" width="100" />
        <el-table-column prop="submitTime" label="提交时间" width="160" />
        <el-table-column label="数据完整率" width="120">
          <template #default="{ row }">
            <el-progress
              :percentage="row.completeness"
              :color="
                row.completeness >= 80
                  ? cssVarValue('--color-primary-light-1', '#40916c')
                  : chartColor('danger')
              "
              :stroke-width="6"
            />
          </template>
        </el-table-column>
        <el-table-column label="校验状态" width="100">
          <template #default="{ row }">
            <el-tag
              :type="
                row.verifyStatus === 'pass'
                  ? 'success'
                  : row.verifyStatus === 'fail'
                    ? 'danger'
                    : 'info'
              "
              size="small"
              :style="row.verifyStatus === 'fail' ? 'cursor:pointer' : ''"
              @click="
                row.verifyStatus === 'fail' && row.verifyErrors?.length ? showErrors(row) : null
              "
            >
              {{ getVerifyStatusText(row.verifyStatus) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="handleReview(row)">审核</el-button>
            <el-button type="success" link size="small" @click="handleApprove(row)">通过</el-button>
            <el-button type="danger" link size="small" @click="handleReject(row)">驳回</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 校验错误详情弹窗 -->
    <el-dialog v-model="errorDialogVisible" :title="`${errorDialogTitle} - 校验问题`" width="520px">
      <div v-if="currentErrors.length">
        <div v-for="(err, idx) in currentErrors" :key="idx" class="error-item">
          <el-tag type="danger" size="small" style="margin-right: 8px">{{
            err.field_label || err.field
          }}</el-tag>
          <span>{{ err.message }}</span>
        </div>
      </div>
      <div v-else class="no-errors">没有校验问题</div>
      <template #footer>
        <el-button @click="errorDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 批量校验结果汇总弹窗 -->
    <el-dialog v-model="batchResultVisible" title="批量校验结果" width="560px">
      <div class="batch-summary">
        <span
          >共校验 <b>{{ batchResult.total }}</b> 条数据，</span
        >
        <span style="color: #40916c"
          >通过 <b>{{ batchResult.passed }}</b> 条</span
        >，
        <span style="color: var(--color-danger)"
          >未通过 <b>{{ batchResult.failed }}</b> 条</span
        >
      </div>
      <el-table
        v-if="batchResult.failedRows.length"
        :data="batchResult.failedRows"
        max-height="360"
        stripe
        style="margin-top: 12px"
      >
        <el-table-column prop="villageName" label="帮扶村" min-width="100" />
        <el-table-column label="问题详情" min-width="240">
          <template #default="{ row }">
            <div v-for="(e, i) in row.errors" :key="i" class="error-line">
              <el-tag type="danger" size="small" style="margin-right: 4px">{{
                e.field_label || e.field
              }}</el-tag>
              {{ e.message }}
            </div>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="batchResultVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { logger } from '@/utils/logger'

import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { post, apiRequest } from '@/api/request'
import { chartColor, cssVarValue } from '@/utils/chartColors'

const loading = ref(false)
const batchChecking = ref(false)
const stats = reactive({ pending: 0, approved: 0, rejected: 0, issues: 0 })
const dataList = ref<any[]>([])

// 原始村庄数据（用于后端校验）
const rawVillages = ref<any[]>([])

// 错误详情弹窗
const errorDialogVisible = ref(false)
const errorDialogTitle = ref('')
const currentErrors = ref<any[]>([])

// 批量校验结果弹窗
const batchResultVisible = ref(false)
const batchResult = reactive({
  total: 0,
  passed: 0,
  failed: 0,
  failedRows: [] as any[],
})

// ── 条件查询校验（小白友好：下拉字段+运算符+值与/或组合） ──
const qcLoading = ref(false)
const qcResult = ref<any>(null)
const qc = reactive({
  module: 'village',
  logic: 'and',
  fields: [] as Array<{ key: string; label: string }>,
  conditions: [{ field: '', operator: 'eq', value: '' }],
})

const qcFieldLabel = (key: string) => {
  const f = qc.fields.find((x) => x.key === key)
  return f?.label || key
}

async function qcLoadFields() {
  try {
    const res: any = await apiRequest({
      method: 'GET',
      url: '/validation/fields',
      params: { module: qc.module },
    })
    qc.fields = res.data?.fields || []
  } catch {
    qc.fields = []
  }
}

function qcAddCondition() {
  qc.conditions.push({ field: '', operator: 'eq', value: '' })
}

function qcRemoveCondition(idx: number) {
  qc.conditions.splice(idx, 1)
}

function qcReset() {
  qc.conditions = [{ field: '', operator: 'eq', value: '' }]
  qcResult.value = null
  qcLoadFields()
}

async function qcRunCheck() {
  const valid = qc.conditions.filter((c) => c.field)
  if (valid.length === 0) {
    ElMessage.warning('请至少选择一个字段')
    return
  }
  qcLoading.value = true
  try {
    const res: any = await post('/validation/query-check', {
      module: qc.module,
      logic: qc.logic,
      conditions: valid.map((c) => ({
        field: c.field,
        operator: c.operator,
        value: c.value || null,
      })),
    })
    const d = res.data || res
    qcResult.value = d
    if (d.unmatched > 0) {
      ElMessage.warning(`发现 ${d.unmatched} 条记录不满足条件`)
    } else {
      ElMessage.success(`全部 ${d.total} 条记录均满足条件`)
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '校验执行失败')
  } finally {
    qcLoading.value = false
  }
}

onMounted(() => {
  qcLoadFields()
  loadData()
})

// 状态文本映射
const getVerifyStatusText = (status: string): string => {
  const statusMap: Record<string, string> = {
    pass: '通过',
    fail: '未通过',
    pending: '待校验',
  }
  return statusMap[status] || status
}

async function loadData() {
  loading.value = true
  try {
    const res = await apiRequest({
      method: 'GET',
      url: '/supported-villages',
      params: { page: 1, page_size: 50 },
    })
    const data = res.data
    const items = data?.items || (Array.isArray(data) ? data : [])
    rawVillages.value = items
    dataList.value = items.map((v: any) => {
      const fields = [
        'department',
        'support_unit',
        'village_name',
        'county',
        'transition_fund_military_total',
      ]
      const filled = fields.filter((f) => v[f] != null && v[f] !== '' && v[f] !== 0).length
      const completeness = Math.round((filled / fields.length) * 100)
      return {
        id: v.id,
        villageName: v.village_name || v.name || '',
        department: v.department || '',
        submitter: v.support_unit || '',
        submitTime: v.created_at ? String(v.created_at).replace('T', ' ').slice(0, 16) : '',
        completeness,
        verifyStatus: completeness >= 80 ? 'pass' : completeness >= 50 ? 'pending' : 'fail',
        verifyErrors: [] as any[],
      }
    })
    updateStats()
  } catch (e) {
    logger.error('加载审核数据失败:', e)
  } finally {
    loading.value = false
  }
}

function updateStats() {
  stats.pending = dataList.value.filter((d) => d.verifyStatus === 'pending').length
  stats.approved = dataList.value.filter((d) => d.verifyStatus === 'pass').length
  stats.rejected = dataList.value.filter((d) => d.verifyStatus === 'fail').length
  stats.issues = dataList.value.filter((d) => d.completeness < 60).length
}

async function handleBatchCheck() {
  if (!rawVillages.value.length) {
    await loadData()
  }
  batchChecking.value = true
  let passed = 0
  let failed = 0
  const failedRows: any[] = []

  for (let i = 0; i < rawVillages.value.length; i++) {
    const raw = rawVillages.value[i]
    const row = dataList.value[i]
    if (!row) continue

    try {
      const resp = await post('/validation/validate', raw, {
        params: { module: 'village' },
      })
      // post() 已自动解包，后端裸返回 {valid, errors}
      const result = resp?.data ?? resp
      if (result?.valid) {
        // 后端规则通过，再检查完整度
        row.verifyStatus = row.completeness >= 80 ? 'pass' : 'pending'
        row.verifyErrors = []
        passed++
      } else {
        row.verifyStatus = 'fail'
        row.verifyErrors = result?.errors || []
        failed++
        failedRows.push({
          villageName: row.villageName,
          errors: result?.errors || [],
        })
      }
    } catch {
      // 后端无校验规则时回退到完整度判断
      row.verifyStatus =
        row.completeness >= 80 ? 'pass' : row.completeness >= 50 ? 'pending' : 'fail'
      row.verifyErrors = []
      if (row.verifyStatus === 'pass') passed++
      else failed++
    }
  }

  batchChecking.value = false
  updateStats()

  batchResult.total = rawVillages.value.length
  batchResult.passed = passed
  batchResult.failed = failed
  batchResult.failedRows = failedRows

  if (failed === 0) {
    ElMessage.success(`批量校验完成，全部 ${passed} 条数据通过`)
  } else {
    ElMessage.warning(`校验完成：${passed} 条通过，${failed} 条未通过`)
    batchResultVisible.value = true
  }
}

function showErrors(row: any) {
  errorDialogTitle.value = row.villageName
  currentErrors.value = row.verifyErrors || []
  errorDialogVisible.value = true
}

const handleReview = (row: any) => {
  showErrors(row)
}
const handleApprove = (row: any) => {
  row.verifyStatus = 'pass'
  updateStats()
  ElMessage.success('已通过')
}
const handleReject = (row: any) => {
  row.verifyStatus = 'fail'
  updateStats()
  ElMessage.warning('已驳回')
}

onMounted(() => {
  qcLoadFields()
  loadData()
})
</script>

<style scoped>
.data-verify-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.page-title {
  font-size: 20px;
  font-weight: 600;
  color: #1b4332;
  margin: 0 0 4px;
}
.page-desc {
  font-size: 14px;
  color: #666;
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
  color: #1b4332;
}
.stat-value.text-success {
  color: #40916c;
}
.stat-value.text-danger {
  color: var(--color-danger);
}
.stat-value.text-warning {
  color: var(--color-warning);
}
.stat-label {
  font-size: 14px;
  color: #666;
  margin-top: 4px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.error-item {
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
  font-size: 14px;
  color: #333;
}
.error-item:last-child {
  border-bottom: none;
}
.error-line {
  margin-bottom: 4px;
  font-size: 13px;
  color: #333;
}
.error-line:last-child {
  margin-bottom: 0;
}
.no-errors {
  text-align: center;
  color: #999;
  padding: 20px;
}
.batch-summary {
  font-size: 15px;
  color: #333;
}
</style>
