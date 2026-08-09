<template>
  <div class="settlement-container">
    <el-page-header title="返回" @back="pushSafe('/funds')">
      <template #content><span class="page-title">决算与绩效评估</span></template>
    </el-page-header>

    <!-- 绩效概览 -->
    <el-card v-if="performance" class="mt-4" shadow="never">
      <template #header>绩效概览</template>
      <el-row :gutter="20">
        <el-col :span="6">
          <el-statistic
            title="预算总额(万元)"
            :value="performance.budget_summary?.total_budget || 0"
          />
        </el-col>
        <el-col :span="6">
          <el-statistic
            title="已用金额(万元)"
            :value="performance.budget_summary?.total_used || 0"
          />
        </el-col>
        <el-col :span="6">
          <el-statistic
            title="预算执行率"
            :value="performance.budget_summary?.execution_rate || 0"
            suffix="%"
          />
        </el-col>
        <el-col :span="6">
          <el-statistic
            title="异常解决率"
            :value="performance.anomaly_summary?.resolution_rate || 0"
            suffix="%"
          />
        </el-col>
      </el-row>
    </el-card>

    <!-- 决算详情 -->
    <el-card v-if="settlement" class="mt-4" shadow="never">
      <template #header>
        <div class="card-header">
          <span>决算报告 - {{ settlement.settlement_no }}</span>
          <div>
            <el-tag
              :type="
                settlement.status === 'approved'
                  ? 'success'
                  : settlement.status === 'submitted'
                    ? 'warning'
                    : 'info'
              "
              size="default"
            >
              {{ settlement.status_label }}
            </el-tag>
            <el-button
              v-if="settlement.status !== 'approved'"
              type="primary"
              size="small"
              class="ml-2"
              @click="showApproveDialog = true"
            >
              审批决算
            </el-button>
          </div>
        </div>
      </template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="决算编号">{{ settlement.settlement_no }}</el-descriptions-item>
        <el-descriptions-item label="决算日期">{{
          settlement.settlement_date
        }}</el-descriptions-item>
        <el-descriptions-item label="总预算"
          >{{ settlement.total_budget }} 万元</el-descriptions-item
        >
        <el-descriptions-item label="总支出"
          >{{ settlement.total_spent }} 万元</el-descriptions-item
        >
        <el-descriptions-item label="总结余"
          >{{ settlement.total_remaining }} 万元</el-descriptions-item
        >
        <el-descriptions-item label="审核人">{{
          settlement.auditor || '未审核'
        }}</el-descriptions-item>
        <el-descriptions-item label="审核意见" :span="2">{{
          settlement.audit_opinion || '无'
        }}</el-descriptions-item>
        <el-descriptions-item label="绩效评分">
          <span v-if="settlement.performance_score !== null">
            {{ settlement.performance_score }} 分
            <el-tag
              :type="
                settlement.performance_level === 'A'
                  ? 'success'
                  : settlement.performance_level === 'B'
                    ? 'primary'
                    : settlement.performance_level === 'C'
                      ? 'warning'
                      : 'danger'
              "
              size="small"
              class="ml-2"
            >
              {{ settlement.performance_level_label || settlement.performance_level }}
            </el-tag>
          </span>
          <span v-else>未评分</span>
        </el-descriptions-item>
        <el-descriptions-item label="创建人">{{ settlement.created_by }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-empty v-if="!settlement && !loading" description="暂无决算记录">
      <el-button type="primary" @click="handleCreate">生成决算报告</el-button>
    </el-empty>

    <!-- 审批对话框 -->
    <el-dialog v-model="showApproveDialog" title="审批决算" width="500px">
      <el-form ref="approveFormRef" :model="approveForm" :rules="approveRules" label-width="100px">
        <el-form-item label="绩效评分" prop="performance_score">
          <el-input-number v-model="approveForm.performance_score" :min="0" :max="100" />
        </el-form-item>
        <el-form-item label="绩效等级" prop="performance_level">
          <el-radio-group v-model="approveForm.performance_level">
            <el-radio value="A">A (优秀)</el-radio>
            <el-radio value="B">B (良好)</el-radio>
            <el-radio value="C">C (合格)</el-radio>
            <el-radio value="D">D (不合格)</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="审核意见">
          <el-input
            v-model="approveForm.audit_opinion"
            type="textarea"
            :rows="3"
            maxlength="500"
            show-word-limit
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showApproveDialog = false">取消</el-button>
        <el-button type="primary" :loading="loading" @click="handleApprove">审批通过</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, type FormInstance } from 'element-plus'
import { fundLifecycleApi } from '@/api/fundLifecycle'
import { parseError } from '@/utils/errorHandler'
import { safeRouteParam, useRouterSafe } from '@/composables/useRouterSafe'

const { pushSafe } = useRouterSafe()

interface BudgetSummary {
  total_budget?: number
  total_used?: number
  execution_rate?: number
}

interface AnomalySummary {
  resolution_rate?: number
}

interface SettlementData {
  id: number
  settlement_no: string
  settlement_date: string
  total_budget: number
  total_spent: number
  total_remaining: number
  auditor?: string
  audit_opinion?: string
  performance_score: number | null
  performance_level: string | null
  performance_level_label?: string
  status: string
  status_label: string
  created_by: string
}

interface PerformanceData {
  budget_summary?: BudgetSummary
  anomaly_summary?: AnomalySummary
  settlement?: SettlementData
}

const route = useRoute()
const projectId = computed(() => safeRouteParam(route.params.projectId))
const invalidProject = computed(() => !projectId.value || projectId.value <= 0)

const loading = ref(false)
const performance = ref<PerformanceData | null>(null)
const settlement = ref<SettlementData | null>(null)
const showApproveDialog = ref(false)
const approveFormRef = ref<FormInstance | null>(null)
const approveForm = reactive({
  performance_score: 80,
  performance_level: '',
  audit_opinion: '',
})

const approveRules = {
  performance_score: [
    { required: true, message: '请输入绩效评分', trigger: 'change' },
    {
      type: 'number' as const,
      min: 0,
      max: 100,
      message: '绩效评分范围为 0-100',
      trigger: 'change',
    },
  ],
  performance_level: [{ required: true, message: '请选择绩效等级', trigger: 'change' }],
}

async function loadData() {
  if (invalidProject.value) {
    ElMessage.warning('请先从「经费管理 → 列表」选择具体项目，再进入决算结算')
    pushSafe('/funds')
    return
  }
  loading.value = true
  try {
    const data = await fundLifecycleApi.getPerformance(projectId.value)
    performance.value = data
    settlement.value = data.settlement
  } catch {
    settlement.value = null
    performance.value = null
  } finally {
    loading.value = false
  }
}

async function handleCreate() {
  loading.value = true
  try {
    await fundLifecycleApi.createSettlement(projectId.value)
    ElMessage.success('决算报告已生成')
    await loadData()
  } catch (e: unknown) {
    ElMessage.error(parseError(e).message || '生成失败')
  } finally {
    loading.value = false
  }
}

async function handleApprove() {
  if (!settlement.value || !approveFormRef.value) return
  const valid = await approveFormRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    await fundLifecycleApi.approveSettlement(settlement.value.id, approveForm)
    ElMessage.success('决算已审批通过')
    showApproveDialog.value = false
    await loadData()
  } catch (e: unknown) {
    ElMessage.error(parseError(e).message || '审批失败')
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.settlement-container {
  padding: 20px;
}
.mt-4 {
  margin-top: 16px;
}
.ml-2 {
  margin-left: 8px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.page-title {
  font-size: 18px;
  font-weight: 600;
}
</style>
