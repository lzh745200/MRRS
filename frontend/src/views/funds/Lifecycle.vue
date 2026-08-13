<template>
  <div class="lifecycle-container">
    <el-page-header title="返回" @back="pushSafe('/funds')">
      <template #content>
        <span class="page-title">项目经费生命周期管理</span>
      </template>
    </el-page-header>

    <!-- 无项目参数（菜单直接进入）：项目选择视图 -->
    <el-card v-if="invalidProject" class="steps-card" shadow="never">
      <el-empty description="请选择项目以查看资金周期">
        <div class="selector-row">
          <el-select
            v-model="selectedProjectId"
            placeholder="选择项目"
            filterable
            style="width: 320px"
          >
            <el-option v-for="p in projectOptions" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
          <el-button type="primary" :disabled="!selectedProjectId" @click="goSelectedProject">
            查看资金周期
          </el-button>
        </div>
      </el-empty>
    </el-card>

    <template v-else>
      <!-- 七阶段步骤条 -->
      <el-card class="steps-card" shadow="never">
        <el-steps :active="currentPhase - 1" finish-status="success" align-center>
          <el-step
            v-for="phase in phases"
            :key="phase.phase"
            :title="phase.phase_label"
            :status="getStepStatus(phase)"
            :description="getStepDesc(phase)"
          />
        </el-steps>
        <div v-if="phases.length" class="phase-actions">
          <el-button
            type="warning"
            size="small"
            :disabled="currentPhase <= 1"
            @click="handleRollback"
          >
            退回上一阶段
          </el-button>
          <el-button type="primary" size="small" @click="handleAdvance">
            {{ currentPhaseObj?.status === 'not_started' ? '开始当前阶段' : '推进到下一阶段' }}
          </el-button>
        </div>
      </el-card>

      <!-- 阶段内容面板 -->
      <el-tabs v-model="activeTab" type="border-card" class="phase-tabs">
        <!-- 阶段1 - 论证立项 -->
        <el-tab-pane label="论证立项" name="phase1">
          <div class="phase-content">
            <el-button type="primary" :loading="loading" @click="handleInitiate"
              >启动论证立项</el-button
            >
            <el-descriptions
              v-if="reportData"
              title="项目论证报告数据"
              :column="2"
              border
              class="mt-4"
            >
              <el-descriptions-item label="项目名称">{{
                reportData.project?.name
              }}</el-descriptions-item>
              <el-descriptions-item label="项目类型">{{
                reportData.project?.type
              }}</el-descriptions-item>
              <el-descriptions-item label="预算金额"
                >{{ reportData.project?.budget }} 万元</el-descriptions-item
              >
              <el-descriptions-item label="计划总额"
                >{{ reportData.fund_summary?.total_planned }} 万元</el-descriptions-item
              >
              <el-descriptions-item label="项目负责人">{{
                reportData.project?.leader || '未指定'
              }}</el-descriptions-item>
              <el-descriptions-item label="经费笔数">{{
                reportData.fund_summary?.fund_count
              }}</el-descriptions-item>
            </el-descriptions>
          </div>
        </el-tab-pane>

        <!-- 阶段2 - 汇总审核 -->
        <el-tab-pane label="汇总审核" name="phase2">
          <div class="phase-content">
            <div class="action-bar">
              <el-button type="primary" :loading="loading" @click="handleLockBudget"
                >锁定预算基线</el-button
              >
              <el-button :loading="loading" @click="handleComplianceCheck">合规性校验</el-button>
            </div>
            <div v-if="complianceResult" class="mt-4">
              <el-alert
                :title="
                  complianceResult.compliant
                    ? '合规性校验通过'
                    : `发现 ${complianceResult.total_issues} 个问题`
                "
                :type="complianceResult.compliant ? 'success' : 'warning'"
                show-icon
              />
              <el-table
                v-if="complianceResult.issues?.length"
                :data="complianceResult.issues"
                class="mt-3"
                size="small"
              >
                <el-table-column prop="fund_name" label="经费名称" width="200" />
                <el-table-column prop="type" label="问题类型" width="150" />
                <el-table-column prop="message" label="说明" />
                <el-table-column prop="severity" label="严重程度" width="100">
                  <template #default="{ row }">
                    <el-tag
                      :type="
                        row.severity === 'danger'
                          ? 'danger'
                          : row.severity === 'warning'
                            ? 'warning'
                            : 'info'
                      "
                      size="small"
                    >
                      {{
                        row.severity === 'danger'
                          ? '严重'
                          : row.severity === 'warning'
                            ? '警告'
                            : '提示'
                      }}
                    </el-tag>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </div>
        </el-tab-pane>

        <!-- 阶段3 - 计划下达与拨付 -->
        <el-tab-pane label="计划下达" name="phase3">
          <div class="phase-content">
            <el-button :loading="loading" @click="loadAllocationPlan">加载拨付计划</el-button>
            <el-table
              v-if="allocationItems.length"
              :data="allocationItems"
              class="mt-3"
              size="small"
            >
              <el-table-column prop="fund_name" label="经费名称" width="200" />
              <el-table-column prop="planned_amount" label="计划金额" width="120" />
              <el-table-column prop="approved_amount" label="批准金额" width="120" />
              <el-table-column prop="allocated_amount" label="拨付金额" width="120" />
              <el-table-column prop="baseline_amount" label="基线金额" width="120" />
              <el-table-column label="预算锁定" width="100">
                <template #default="{ row }">
                  <el-tag :type="row.budget_locked ? 'success' : 'info'" size="small">
                    {{ row.budget_locked ? '已锁定' : '未锁定' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="120">
                <template #default="{ row }">
                  <el-button
                    v-if="row.budget_locked"
                    size="small"
                    type="primary"
                    @click="handleQuotaLock(row.fund_id)"
                  >
                    额度锁定
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-tab-pane>

        <!-- 阶段4 - 对接 -->
        <el-tab-pane label="对接" name="phase4">
          <div class="phase-content">
            <el-button type="primary" @click="pushSafe('/funds/transfer?project_id=' + projectId)">
              管理划转凭证
            </el-button>
            <el-button :loading="loading" @click="loadTransferLedger">查看协调台账</el-button>
            <div v-if="ledgerData" class="mt-4">
              <el-row :gutter="16">
                <el-col :span="8">
                  <el-statistic
                    title="专项→地方"
                    :value="ledgerData.total_military_to_local"
                    suffix="万元"
                  />
                </el-col>
                <el-col :span="8">
                  <el-statistic
                    title="地方→专项"
                    :value="ledgerData.total_local_to_military"
                    suffix="万元"
                  />
                </el-col>
                <el-col :span="8">
                  <el-statistic title="净划转" :value="ledgerData.net_transfer" suffix="万元" />
                </el-col>
              </el-row>
            </div>
          </div>
        </el-tab-pane>

        <!-- 阶段5 - 实施监管 -->
        <el-tab-pane label="实施监管" name="phase5">
          <div class="phase-content">
            <div class="action-bar">
              <el-button
                type="primary"
                @click="pushSafe('/funds/contract?project_id=' + projectId)"
              >
                合同管理
              </el-button>
              <el-button :loading="loading" @click="loadDeviation">偏差分析</el-button>
            </div>
            <el-table v-if="deviations.length" :data="deviations" class="mt-3" size="small">
              <el-table-column prop="fund_name" label="经费名称" width="200" />
              <el-table-column prop="project_progress" label="项目进度(%)" width="120" />
              <el-table-column prop="fund_progress" label="资金进度(%)" width="120" />
              <el-table-column prop="deviation" label="偏差(%)" width="100" />
              <el-table-column label="状态" width="100">
                <template #default="{ row }">
                  <el-tag
                    :type="
                      row.status === 'danger'
                        ? 'danger'
                        : row.status === 'warning'
                          ? 'warning'
                          : 'success'
                    "
                    size="small"
                  >
                    {{
                      row.status === 'danger'
                        ? '严重偏差'
                        : row.status === 'warning'
                          ? '偏差'
                          : '正常'
                    }}
                  </el-tag>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-tab-pane>

        <!-- 阶段6 - 核查督查 -->
        <el-tab-pane label="核查督查" name="phase6">
          <div class="phase-content">
            <div class="action-bar">
              <el-button type="warning" :loading="loading" @click="handleDetect"
                >触发异常检测</el-button
              >
              <el-button @click="pushSafe('/funds/anomaly?project_id=' + projectId)"
                >查看异常列表</el-button
              >
            </div>
            <el-alert
              v-if="detectResult"
              :title="detectResult"
              type="info"
              show-icon
              class="mt-3"
            />
          </div>
        </el-tab-pane>

        <!-- 阶段7 - 决算与绩效 -->
        <el-tab-pane label="决算绩效" name="phase7">
          <div class="phase-content">
            <div class="action-bar">
              <el-button type="primary" :loading="loading" @click="handleCreateSettlement"
                >生成决算报告</el-button
              >
              <el-button @click="pushSafe('/funds/settlement/' + projectId)">查看详情</el-button>
            </div>
            <div v-if="performanceData" class="mt-4">
              <el-descriptions title="绩效概览" :column="2" border>
                <el-descriptions-item label="预算总额"
                  >{{ performanceData.budget_summary?.total_budget }} 万元</el-descriptions-item
                >
                <el-descriptions-item label="已用金额"
                  >{{ performanceData.budget_summary?.total_used }} 万元</el-descriptions-item
                >
                <el-descriptions-item label="执行率"
                  >{{ performanceData.budget_summary?.execution_rate }}%</el-descriptions-item
                >
                <el-descriptions-item label="异常解决率"
                  >{{ performanceData.anomaly_summary?.resolution_rate }}%</el-descriptions-item
                >
              </el-descriptions>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>

      <!-- 健康度卡片 -->
      <el-card class="health-card" shadow="never">
        <template #header>资金健康度</template>
        <div v-if="healthData" class="health-content">
          <el-progress
            type="dashboard"
            :percentage="healthData.health_score"
            :color="
              healthData.health_score >= 80
                ? '#67c23a'
                : healthData.health_score >= 60
                  ? '#e6a23c'
                  : '#f56c6c'
            "
            :width="120"
          />
          <div class="health-details">
            <div v-for="(detail, key) in healthData.details" :key="key" class="detail-item">
              <span class="label">{{ detailLabels[key] || key }}</span>
              <el-progress
                :percentage="detail.score"
                :stroke-width="10"
                :color="
                  detail.score >= 80
                    ? 'var(--color-success)'
                    : detail.score >= 60
                      ? 'var(--color-warning)'
                      : 'var(--color-danger)'
                "
              />
            </div>
          </div>
        </div>
        <el-button v-else size="small" @click="loadHealth">加载健康度</el-button>
      </el-card>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useRouterSafe, safeRouteParam } from '@/composables/useRouterSafe'
import { ElMessage, ElMessageBox } from 'element-plus'
import { fundLifecycleApi } from '@/api/fundLifecycle'
import type { PhaseInfo, HealthScore } from '@/api/fundLifecycle'
import { projectsApi } from '@/api/projects'

const route = useRoute()
const { pushSafe } = useRouterSafe()
const projectId = computed(() => safeRouteParam(route.params.projectId))
const invalidProject = computed(() => !projectId.value || projectId.value <= 0)

// 无有效 projectId 时模板渲染项目选择视图，此处仅为处理器兜底守卫
function requireProject(): boolean {
  if (invalidProject.value) {
    ElMessage.warning('请先选择具体项目')
    return false
  }
  return true
}

// 项目选择视图（菜单无参进入时）
const projectOptions = ref<any[]>([])
const selectedProjectId = ref<number | null>(null)

async function loadProjectOptions() {
  try {
    const res: any = await projectsApi.list({ page: 1, page_size: 100 })
    const list = res?.items ?? res?.data?.items ?? (Array.isArray(res) ? res : [])
    projectOptions.value = Array.isArray(list) ? list : []
  } catch {
    projectOptions.value = []
  }
}

function goSelectedProject() {
  if (!selectedProjectId.value) return
  pushSafe(`/funds/lifecycle/${selectedProjectId.value}`)
}

const loading = ref(false)
const phases = ref<PhaseInfo[]>([])
const currentPhase = ref(1)
const activeTab = ref('phase1')

// 各阶段数据
const reportData = ref<any>(null)
const complianceResult = ref<any>(null)
const allocationItems = ref<any[]>([])
const ledgerData = ref<any>(null)
const deviations = ref<any[]>([])
const detectResult = ref('')
const performanceData = ref<any>(null)
const healthData = ref<HealthScore | null>(null)

const detailLabels: Record<string, string> = {
  budget_execution: '预算执行率',
  payment_timeliness: '支付及时率',
  voucher_completeness: '凭证完整率',
  anomaly_count: '异常指标',
  contract_fulfillment: '合同履约率',
  settlement_completion: '决算完成度',
}

const currentPhaseObj = computed(() => phases.value.find((p) => p.phase === currentPhase.value))

function getStepStatus(phase: PhaseInfo) {
  if (phase.status === 'completed') return 'success'
  if (phase.status === 'in_progress') return 'process'
  if (phase.status === 'skipped') return 'error'
  return 'wait'
}

function getStepDesc(phase: PhaseInfo) {
  if (phase.status === 'completed')
    return phase.completed_at ? phase.completed_at.slice(0, 10) : '已完成'
  if (phase.status === 'in_progress') return '进行中'
  return ''
}

async function loadPhases() {
  try {
    const data = await fundLifecycleApi.getPhases(projectId.value)
    phases.value = data.phases || []
    currentPhase.value = data.current_phase || 1
    activeTab.value = `phase${currentPhase.value}`
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '加载阶段数据失败')
  }
}

async function handleAdvance() {
  try {
    await ElMessageBox.confirm('确认推进到下一阶段？', '确认')
    loading.value = true
    const res = await fundLifecycleApi.advancePhase(projectId.value)
    ElMessage.success(res.message || '操作成功')
    await loadPhases()
  } catch (e: any) {
    if (e !== 'cancel') ElMessage.error(e?.response?.data?.detail || '推进失败')
  } finally {
    loading.value = false
  }
}

async function handleRollback() {
  try {
    await ElMessageBox.confirm('确认退回上一阶段？', '确认')
    loading.value = true
    const res = await fundLifecycleApi.rollbackPhase(projectId.value)
    ElMessage.success(res.message || '操作成功')
    await loadPhases()
  } catch (e: any) {
    if (e !== 'cancel') ElMessage.error(e?.response?.data?.detail || '退回失败')
  } finally {
    loading.value = false
  }
}

// 阶段1
async function handleInitiate() {
  if (!requireProject()) return
  loading.value = true
  try {
    await fundLifecycleApi.initiate(projectId.value)
    reportData.value = await fundLifecycleApi.getReportTemplate(projectId.value)
    ElMessage.success('论证立项已启动')
    await loadPhases()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '操作失败')
  } finally {
    loading.value = false
  }
}

// 阶段2
async function handleLockBudget() {
  loading.value = true
  try {
    const res = await fundLifecycleApi.lockBudget(projectId.value)
    ElMessage.success(res.message || '预算基线已锁定')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '锁定失败')
  } finally {
    loading.value = false
  }
}

async function handleComplianceCheck() {
  loading.value = true
  try {
    complianceResult.value = await fundLifecycleApi.complianceCheck(projectId.value)
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '校验失败')
  } finally {
    loading.value = false
  }
}

// 阶段3
async function loadAllocationPlan() {
  loading.value = true
  try {
    const data = await fundLifecycleApi.allocationPlan(projectId.value)
    allocationItems.value = data.items || []
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '加载失败')
  } finally {
    loading.value = false
  }
}

async function handleQuotaLock(fundId: number) {
  try {
    const res = await fundLifecycleApi.quotaLock(fundId)
    ElMessage.success(res.message || '额度已锁定')
    await loadAllocationPlan()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '锁定失败')
  }
}

// 阶段4
async function loadTransferLedger() {
  loading.value = true
  try {
    ledgerData.value = await fundLifecycleApi.transferLedger(projectId.value)
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '加载失败')
  } finally {
    loading.value = false
  }
}

// 阶段5
async function loadDeviation() {
  loading.value = true
  try {
    const data = await fundLifecycleApi.monitoringDeviation(projectId.value)
    deviations.value = data.deviations || []
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '加载失败')
  } finally {
    loading.value = false
  }
}

// 阶段6
async function handleDetect() {
  loading.value = true
  try {
    const res = await fundLifecycleApi.detectAnomalies(projectId.value)
    detectResult.value = res.message || '检测完成'
    ElMessage.success(res.message || '检测完成')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '检测失败')
  } finally {
    loading.value = false
  }
}

// 阶段7
async function handleCreateSettlement() {
  loading.value = true
  try {
    const res = await fundLifecycleApi.createSettlement(projectId.value)
    ElMessage.success(res.message || '决算报告已生成')
    performanceData.value = await fundLifecycleApi.getPerformance(projectId.value)
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '生成失败')
  } finally {
    loading.value = false
  }
}

// 健康度
async function loadHealth() {
  if (!projectId.value) return
  try {
    healthData.value = await fundLifecycleApi.getHealth(projectId.value)
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '加载失败')
  }
}

onMounted(async () => {
  if (invalidProject.value) {
    // 菜单无参进入 → 加载项目列表供选择，不再弹回经费总览
    await loadProjectOptions()
    return
  }
  await loadPhases()
  try {
    reportData.value = await fundLifecycleApi.getReportTemplate(projectId.value)
  } catch {
    /* ignore */
  }
  loadHealth()
})
</script>

<style scoped>
.lifecycle-container {
  padding: 20px;
}
.steps-card {
  margin: 20px 0;
}
.phase-actions {
  display: flex;
  justify-content: center;
  gap: 12px;
  margin-top: 20px;
}
.phase-tabs {
  margin-bottom: 20px;
}
.phase-content {
  padding: 16px 0;
}
.action-bar {
  display: flex;
  gap: 8px;
}
.mt-3 {
  margin-top: 12px;
}
.mt-4 {
  margin-top: 16px;
}
.health-card {
  margin-bottom: 20px;
}
.health-content {
  display: flex;
  gap: 40px;
  align-items: flex-start;
}
.health-details {
  flex: 1;
}
.detail-item {
  margin-bottom: 12px;
}
.detail-item .label {
  display: block;
  margin-bottom: 4px;
  font-size: 13px;
  color: var(--color-text-secondary);
}
.selector-row {
  display: flex;
  gap: 12px;
  justify-content: center;
}
.page-title {
  font-size: 18px;
  font-weight: 600;
}
</style>
