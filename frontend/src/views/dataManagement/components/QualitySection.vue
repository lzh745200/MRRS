<template>
  <div class="quality-section">
    <!-- 数据质量概览 -->
    <el-row :gutter="20">
      <el-col :span="6">
        <el-card class="stat-card">
          <el-statistic title="总记录数" :value="props.stats.totalRecords" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card success">
          <el-statistic title="有效记录" :value="props.stats.validRecords">
            <template #suffix>
              <el-tag type="success" size="small"> {{ validRate }}% </el-tag>
            </template>
          </el-statistic>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card warning">
          <el-statistic title="问题记录" :value="props.stats.invalidRecords">
            <template #suffix>
              <el-tag type="danger" size="small"> {{ invalidRate }}% </el-tag>
            </template>
          </el-statistic>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <el-statistic
            title="数据完整率"
            :value="props.stats.completenessRate"
            suffix="%"
            :precision="2"
          />
        </el-card>
      </el-col>
    </el-row>

    <!-- 数据质量检查 -->
    <el-card class="check-card">
      <template #header>
        <div class="card-header">
          <span>数据质量检查</span>
          <div class="header-actions">
            <span v-if="props.stats.lastCheckTime" class="last-check">
              上次检查：{{ props.stats.lastCheckTime }}
            </span>
            <el-button type="primary" :loading="checking" @click="handleCheck">
              <el-icon><Search /></el-icon>
              开始检查
            </el-button>
          </div>
        </div>
      </template>

      <!-- 检查项列表 -->
      <el-table :data="checkItems" stripe>
        <el-table-column prop="name" label="检查项" min-width="200" />
        <el-table-column prop="description" label="说明" min-width="250" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag
              :type="
                row.status === 'pass' ? 'success' : row.status === 'warning' ? 'warning' : 'danger'
              "
              size="small"
            >
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="问题数" width="100">
          <template #default="{ row }">
            <span :class="{ 'text-danger': row.issues > 0 }">{{ row.issues }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button
              v-if="row.issues > 0"
              type="primary"
              link
              size="small"
              @click="handleViewIssues(row as CheckItem)"
            >
              查看详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 问题详情对话框 -->
    <el-dialog
      v-model="showIssuesDialog"
      :title="`问题详情 - ${selectedCheck?.name}`"
      width="700px"
    >
      <el-table :data="issueDetails" max-height="400">
        <el-table-column prop="record_id" label="记录ID" width="100" />
        <el-table-column prop="field" label="字段" width="120" />
        <el-table-column prop="issue" label="问题描述" />
        <el-table-column prop="suggestion" label="建议" min-width="150" />
      </el-table>
      <template #footer>
        <el-button @click="showIssuesDialog = false">关闭</el-button>
        <el-button type="primary" :loading="fixing" :disabled="!canAutoFix" @click="handleAutoFix">
          自动修复
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import { post } from '@/api/request'

interface QualityStats {
  totalRecords: number
  validRecords: number
  invalidRecords: number
  completenessRate: number
  lastCheckTime: string
}

interface CheckItem {
  id: string
  name: string
  description: string
  status: 'pass' | 'warning' | 'fail' | 'pending'
  issues: number
}

interface IssueDetail {
  record_id: number
  field: string
  issue: string
  suggestion: string
}

const props = defineProps<{
  stats: QualityStats
}>()

// 状态
const checking = ref(false)
const fixing = ref(false)
const showIssuesDialog = ref(false)
const selectedCheck = ref<CheckItem | null>(null)
const issueDetails = ref<IssueDetail[]>([])
const canAutoFix = ref(false)
const formattedCheckTime = ref(props.stats.lastCheckTime || '')
const lastIssues = ref<any[]>([])

// 检查项列表
const checkItems = ref<CheckItem[]>([
  {
    id: 'required_fields',
    name: '必填字段检查',
    description: '检查帮扶村名称、部门、帮扶单位等必填字段是否完整',
    status: 'pass',
    issues: 0,
  },
  {
    id: 'data_format',
    name: '数据格式检查',
    description: '检查日期、数值、枚举等字段的格式是否正确',
    status: 'pass',
    issues: 0,
  },
  {
    id: 'region_validity',
    name: '地区有效性检查',
    description: '检查县/市是否在黔南州12个县市范围内',
    status: 'pass',
    issues: 0,
  },
  {
    id: 'data_consistency',
    name: '数据一致性检查',
    description: '检查关联数据的一致性，如年度数据与主记录的关联',
    status: 'pass',
    issues: 0,
  },
  {
    id: 'duplicate_check',
    name: '重复数据检查',
    description: '检查是否存在重复的帮扶村记录',
    status: 'pass',
    issues: 0,
  },
  {
    id: 'calculation_check',
    name: '计算正确性检查',
    description: '检查合计、汇总等计算字段是否正确',
    status: 'pass',
    issues: 0,
  },
])

// 计算属性
const validRate = computed(() => {
  if (props.stats.totalRecords === 0) return 0
  return ((props.stats.validRecords / props.stats.totalRecords) * 100).toFixed(1)
})

const invalidRate = computed(() => {
  if (props.stats.totalRecords === 0) return 0
  return ((props.stats.invalidRecords / props.stats.totalRecords) * 100).toFixed(1)
})

// 获取状态文本
function getStatusText(status: string): string {
  const statusMap: Record<string, string> = {
    pass: '通过',
    warning: '警告',
    fail: '失败',
    pending: '待检查',
  }
  return statusMap[status] || status
}

// 执行检查 — 使用真实后端全量质量检查 /data-quality/full-check
async function handleCheck() {
  checking.value = true
  try {
    const res = await post('/data-quality/full-check')
    const data = res?.data ?? res
    const issues: any[] = data?.issues ?? []
    const valid = (data?.valid ?? true) && issues.length === 0

    checkItems.value = checkItems.value.map((item) => ({
      ...item,
      status: valid ? 'pass' : 'warning',
      issues: valid ? 0 : issues.length,
    }))
    formattedCheckTime.value = new Date().toLocaleString('zh-CN')
    lastIssues.value = issues
    ElMessage.success(valid ? '数据质量检查通过' : `发现 ${issues.length} 个问题`)
  } catch (e: any) {
    checkItems.value = checkItems.value.map((item) => ({
      ...item,
      status: 'pending',
      issues: 0,
    }))
    ElMessage.error(e?.response?.data?.detail || '质量检查执行失败，请稍后重试')
  } finally {
    checking.value = false
  }
}

// 查看问题详情 — 使用最近一次 full-check 结果
async function handleViewIssues(check: CheckItem) {
  selectedCheck.value = check
  try {
    const issues = lastIssues.value?.length
      ? lastIssues.value
      : (async () => {
          const res = await post('/data-quality/full-check')
          return (res?.data ?? res)?.issues ?? []
        })()
    const list = await issues
    issueDetails.value = (Array.isArray(list) ? list : []).map((d: any) => ({
      record_id: d.record_id ?? d.id ?? 0,
      field: d.field ?? d.field_name ?? '',
      issue: d.message ?? d.issue ?? d.description ?? '',
      suggestion: d.suggestion ?? '请检查并修正该字段的值',
    }))
    canAutoFix.value = check.id === 'data_format' || check.id === 'calculation_check'
  } catch {
    issueDetails.value = []
    canAutoFix.value = false
  }
  showIssuesDialog.value = true
}

// 自动修复 — 使用真实后端 /data-quality/clean
async function handleAutoFix() {
  if (!selectedCheck.value) return
  fixing.value = true
  try {
    // 从当前问题详情中提取需要修复的记录 ID（去重）
    const recordIds = [...new Set(issueDetails.value.map((d) => d.record_id))]
    const res = await post('/data-quality/clean', {
      records: recordIds,
      cleaning_rules: { trim_whitespace: true, normalize_empty: true },
    })
    const data = res?.data ?? res
    const cleaned = data?.cleaned_count ?? 0
    ElMessage.success(`自动修复完成，处理了 ${cleaned} 条记录`)
    showIssuesDialog.value = false
    handleCheck()
  } catch {
    ElMessage.warning('自动修复失败，请手动修正问题数据')
  } finally {
    fixing.value = false
  }
}
</script>

<style scoped lang="scss">
.quality-section {
  .stat-card {
    text-align: center;

    &.success {
      :deep(.el-statistic__number) {
        color: #67c23a;
      }
    }

    &.warning {
      :deep(.el-statistic__number) {
        color: #e6a23c;
      }
    }
  }

  .check-card {
    margin-top: 20px;

    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;

      .header-actions {
        display: flex;
        align-items: center;
        gap: 15px;

        .last-check {
          font-size: 12px;
          color: #909399;
        }
      }
    }
  }

  .text-danger {
    color: #f56c6c;
    font-weight: 600;
  }
}
</style>
