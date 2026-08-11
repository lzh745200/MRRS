<template>
  <div class="zero-trust-page">
    <!-- 页面标题 -->
    <el-card class="page-header">
      <div class="header-content">
        <div class="header-left">
          <h2>零信任安全</h2>
          <p class="description">零信任安全态势感知与策略管理</p>
        </div>
        <div class="header-right">
          <el-button :icon="Refresh" :loading="refreshingAll" @click="refreshAll">
            刷新全部
          </el-button>
        </div>
      </div>
    </el-card>

    <!-- 第1部分: 信任评估仪表盘 -->
    <el-card class="assessment-card">
      <template #header>
        <div class="section-header">
          <span class="section-title">信任评估</span>
          <el-button
            :icon="Refresh"
            size="small"
            :loading="loadingAssessment"
            @click="loadAssessment"
          >
            刷新
          </el-button>
        </div>
      </template>

      <div v-if="loadingAssessment" class="loading-placeholder">
        <el-skeleton :rows="6" animated />
      </div>

      <div v-else-if="assessment" class="assessment-body">
        <!-- 评分展示 -->
        <div class="score-section">
          <div class="score-ring" :class="scoreColorClass">
            <span class="score-number">{{ assessment.score }}</span>
            <span class="score-label">信任评分</span>
          </div>
          <div class="level-info">
            <el-tag :type="levelTagType" size="large" effect="dark">
              {{ assessment.level }}
            </el-tag>
            <span class="assessed-time">
              评估时间: {{ formatDateTime(assessment.assessed_at) }}
            </span>
          </div>
        </div>

        <!-- 评估因子 -->
        <div class="factors-section">
          <h4>评估因子</h4>
          <el-table :data="assessment.factors" size="small" border style="width: 100%">
            <el-table-column prop="factor" label="因子" min-width="140" />
            <el-table-column prop="score" label="评分" width="80" align="center">
              <template #default="{ row }">
                <span :class="getScoreClass(row.score)">{{ row.score }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="100" align="center">
              <template #default="{ row }">
                <el-tag :type="getFactorStatusType(row.status)" size="small">
                  {{ row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="detail" label="说明" min-width="200" show-overflow-tooltip />
          </el-table>
        </div>

        <!-- 建议 -->
        <div v-if="assessment.recommendations.length > 0" class="recommendations-section">
          <h4>安全建议</h4>
          <ul class="recommendation-list">
            <li v-for="(rec, idx) in assessment.recommendations" :key="idx">
              <el-icon><Check /></el-icon>
              {{ rec }}
            </li>
          </ul>
        </div>
      </div>

      <el-empty v-else description="暂无信任评估数据" />
    </el-card>

    <!-- 第2部分: 事件统计摘要卡片 -->
    <el-card class="stats-card">
      <template #header>
        <div class="section-header">
          <span class="section-title">安全事件统计</span>
          <el-button :icon="Refresh" size="small" :loading="loadingStats" @click="loadStats">
            刷新
          </el-button>
        </div>
      </template>

      <div v-if="loadingStats" class="loading-placeholder">
        <el-skeleton :rows="3" animated />
      </div>

      <div v-else-if="eventStats" class="stats-body">
        <!-- 统计卡片行 -->
        <el-row :gutter="16" class="stats-row">
          <el-col :span="8">
            <el-card shadow="hover" class="stat-card">
              <el-statistic title="事件总数" :value="eventStats.total_events" />
            </el-card>
          </el-col>
          <el-col :span="8">
            <el-card shadow="hover" class="stat-card stat-card-warning">
              <el-statistic
                title="高危事件"
                :value="eventStats.high_severity_count"
                :value-style="{
                  color: eventStats.high_severity_count > 0 ? '#f56c6c' : '#67c23a',
                }"
              />
            </el-card>
          </el-col>
          <el-col :span="8">
            <el-card shadow="hover" class="stat-card">
              <template #header>
                <span>安全态势</span>
              </template>
              <el-tag :type="postureTagType" size="large" effect="dark">
                {{ postureLabel }}
              </el-tag>
            </el-card>
          </el-col>
        </el-row>

        <!-- 按严重程度分布 -->
        <div class="breakdown-section">
          <h4>按严重程度分布</h4>
          <div class="tag-list">
            <el-tag
              v-for="(count, severity) in eventStats.by_severity"
              :key="severity"
              :type="getSeverityTagType(severity)"
              effect="plain"
              size="default"
            >
              {{ severity }}: {{ count }}
            </el-tag>
            <el-tag v-if="Object.keys(eventStats.by_severity).length === 0" type="info">
              暂无数据
            </el-tag>
          </div>
        </div>

        <!-- 按事件类型分布 -->
        <div class="breakdown-section">
          <h4>按事件类型分布</h4>
          <div class="tag-list">
            <el-tag
              v-for="(count, type) in eventStats.by_type"
              :key="type"
              type="info"
              effect="plain"
              size="default"
            >
              {{ type }}: {{ count }}
            </el-tag>
            <el-tag v-if="Object.keys(eventStats.by_type).length === 0" type="info">
              暂无数据
            </el-tag>
          </div>
        </div>
      </div>

      <el-empty v-else description="暂无安全事件统计数据" />
    </el-card>

    <!-- 第3部分: 安全策略列表 -->
    <el-card class="policies-card">
      <template #header>
        <div class="section-header">
          <span class="section-title">安全策略</span>
          <span class="enabled-hint">
            已启用 {{ policyEnabledCount }} / {{ policyTotal }} 条策略
          </span>
        </div>
      </template>

      <!-- 过滤器 -->
      <div class="filter-bar">
        <el-select
          v-model="policyFilterCategory"
          placeholder="按类别筛选"
          clearable
          style="width: 180px"
          @change="loadPolicies"
        >
          <el-option label="全部类别" value="" />
          <el-option label="身份认证" value="authentication" />
          <el-option label="访问控制" value="access_control" />
          <el-option label="数据保护" value="data_protection" />
          <el-option label="网络安全" value="network" />
          <el-option label="端点安全" value="endpoint" />
          <el-option label="审计日志" value="audit" />
        </el-select>
        <el-checkbox v-model="policyFilterEnabledOnly" @change="loadPolicies">
          仅显示已启用
        </el-checkbox>
      </div>

      <el-table
        v-loading="loadingPolicies"
        :data="policies"
        border
        stripe
        style="width: 100%"
        row-key="id"
      >
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="policy-expand-detail">
              <el-descriptions :column="2" border size="small">
                <el-descriptions-item label="描述">
                  {{ row.description || '无' }}
                </el-descriptions-item>
                <el-descriptions-item label="类别">
                  <el-tag size="small">{{ row.category }}</el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="条件" :span="2">
                  <pre v-if="row.conditions" class="json-pre">{{
                    JSON.stringify(row.conditions, null, 2)
                  }}</pre>
                  <span v-else>无</span>
                </el-descriptions-item>
                <el-descriptions-item label="动作" :span="2">
                  <template v-if="row.actions && row.actions.length > 0">
                    <el-tag
                      v-for="action in row.actions"
                      :key="action"
                      size="small"
                      style="margin-right: 6px"
                    >
                      {{ action }}
                    </el-tag>
                  </template>
                  <span v-else>无</span>
                </el-descriptions-item>
              </el-descriptions>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="策略名称" min-width="180" />
        <el-table-column prop="category" label="类别" width="120" align="center">
          <template #default="{ row }">
            <el-tag size="small">{{ row.category }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="severity" label="严重程度" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getSeverityTagType(row.severity)" size="small">
              {{ row.severity }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="enabled" label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'info'" size="small">
              {{ row.enabled ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="250" show-overflow-tooltip />
      </el-table>
    </el-card>

    <!-- 第4部分: 访问评估表单 -->
    <el-card class="evaluate-card">
      <template #header>
        <span class="section-title">访问评估</span>
      </template>

      <el-form
        ref="evaluateFormRef"
        :model="evaluateForm"
        :rules="evaluateRules"
        label-width="100px"
      >
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="资源" prop="resource">
              <el-input v-model="evaluateForm.resource" placeholder="例如: /api/v1/funds" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="操作" prop="action">
              <el-input v-model="evaluateForm.action" placeholder="例如: read, write, delete" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="上下文(JSON)" prop="context">
          <el-input
            v-model="evaluateForm.contextText"
            type="textarea"
            :rows="4"
            placeholder='可选，例如: {"ip": "192.168.1.1", "device": "desktop"}'
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="evaluating" @click="handleEvaluate">
            评估访问
          </el-button>
          <el-button @click="resetEvaluateForm">重置</el-button>
        </el-form-item>
      </el-form>

      <!-- 评估结果 -->
      <div v-if="evaluateResult" class="evaluate-result">
        <el-alert
          :title="evaluateResult.result === 'allowed' ? '允许访问' : '拒绝访问'"
          :type="evaluateResult.result === 'allowed' ? 'success' : 'error'"
          :closable="false"
          show-icon
        >
          <template #default>
            <div class="result-detail">
              <p><strong>资源:</strong> {{ evaluateResult.resource }}</p>
              <p><strong>操作:</strong> {{ evaluateResult.action }}</p>
              <p><strong>用户:</strong> {{ evaluateResult.username }}</p>
              <p><strong>原因:</strong> {{ evaluateResult.message }}</p>
              <p class="evaluated-time">
                评估时间: {{ formatDateTime(evaluateResult.evaluated_at) }}
              </p>
            </div>
          </template>
        </el-alert>
      </div>
    </el-card>

    <!-- 第5部分: 最近安全事件 -->
    <el-card class="events-card">
      <template #header>
        <div class="section-header">
          <span class="section-title">最近安全事件</span>
          <el-button :icon="Refresh" size="small" :loading="loadingEvents" @click="loadEvents">
            刷新
          </el-button>
        </div>
      </template>

      <!-- 事件过滤器 -->
      <div class="filter-bar">
        <el-select
          v-model="eventFilterSeverity"
          placeholder="按严重程度筛选"
          clearable
          style="width: 160px"
          @change="handleEventFilterChange"
        >
          <el-option label="全部" value="" />
          <el-option label="严重" value="critical" />
          <el-option label="高" value="high" />
          <el-option label="中" value="medium" />
          <el-option label="低" value="low" />
          <el-option label="信息" value="info" />
        </el-select>
        <el-select
          v-model="eventFilterType"
          placeholder="按事件类型筛选"
          clearable
          style="width: 180px; margin-left: 10px"
          @change="handleEventFilterChange"
        >
          <el-option label="全部类型" value="" />
          <el-option label="认证失败" value="auth_failure" />
          <el-option label="未授权访问" value="unauthorized_access" />
          <el-option label="异常登录" value="abnormal_login" />
          <el-option label="权限变更" value="permission_change" />
          <el-option label="数据泄露" value="data_leak" />
          <el-option label="配置变更" value="config_change" />
        </el-select>
      </div>

      <el-table v-loading="loadingEvents" :data="events" border stripe style="width: 100%">
        <el-table-column
          prop="timestamp"
          label="时间"
          width="180"
          :formatter="(row: SecurityEvent) => formatDateTime(row.timestamp)"
        />
        <el-table-column prop="event_type" label="类型" width="140">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ row.event_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="source" label="来源" width="140" />
        <el-table-column prop="severity" label="严重程度" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getSeverityTagType(row.severity)" size="small">
              {{ row.severity }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="message" label="消息" min-width="300" show-overflow-tooltip />
      </el-table>

      <!-- 分页 -->
      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="eventPage"
          v-model:page-size="eventPageSize"
          :total="eventTotal"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          @current-change="loadEvents"
          @size-change="loadEvents"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Check } from '@element-plus/icons-vue'
import {
  zeroTrustApi,
  type TrustAssessment,
  type SecurityPolicy,
  type SecurityEvent,
  type SecurityEventStats,
  type AccessEvaluationResult,
} from '@/api/zeroTrust'

// ==================== 刷新全部 ====================

const refreshingAll = ref(false)

async function refreshAll() {
  refreshingAll.value = true
  try {
    await Promise.all([loadAssessment(), loadStats(), loadPolicies(), loadEvents()])
    ElMessage.success('刷新完成')
    /* c8 ignore start */
  } catch {
    ElMessage.error('刷新失败')
    /* c8 ignore stop */
  } finally {
    refreshingAll.value = false
  }
}

// ==================== 第1部分: 信任评估 ====================

const loadingAssessment = ref(false)
const assessment = ref<TrustAssessment | null>(null)

const scoreColorClass = computed(() => {
  if (!assessment.value) return 'score-green'
  const s = assessment.value.score
  if (s < 40) return 'score-red'
  if (s <= 70) return 'score-yellow'
  return 'score-green'
})

const levelTagType = computed(() => {
  if (!assessment.value) return 'info'
  const s = assessment.value.score
  if (s < 40) return 'danger'
  if (s <= 70) return 'warning'
  return 'success'
})

function getScoreClass(score: number): string {
  if (score < 40) return 'score-text-red'
  if (score <= 70) return 'score-text-yellow'
  return 'score-text-green'
}

function getFactorStatusType(status?: string): 'success' | 'warning' | 'danger' | 'info' {
  const s = (status ?? '').toLowerCase()
  if (s === 'pass' || s === 'passed' || s === 'ok' || s === 'good') return 'success'
  if (s === 'warn' || s === 'warning') return 'warning'
  if (s === 'fail' || s === 'failed' || s === 'error') return 'danger'
  return 'info'
}

async function loadAssessment() {
  loadingAssessment.value = true
  try {
    const res = await zeroTrustApi.getAssessment()
    if (res.success && res.data) {
      assessment.value = res.data
    } else {
      assessment.value = null
    }
  } catch (e: any) {
    assessment.value = null
    ElMessage.error(e?.response?.data?.detail || e?.message || '加载信任评估失败')
  } finally {
    loadingAssessment.value = false
  }
}

// ==================== 第2部分: 事件统计 ====================

const loadingStats = ref(false)
const eventStats = ref<SecurityEventStats | null>(null)

const postureTagType = computed(() => {
  if (!eventStats.value) return 'info'
  const posture = eventStats.value.security_posture
  if (posture === 'secure') return 'success'
  if (posture === 'warning') return 'danger'
  return 'warning'
})

const postureLabel = computed(() => {
  if (!eventStats.value) return '未知'
  const posture = eventStats.value.security_posture
  if (posture === 'secure') return '安全'
  if (posture === 'warning') return '警告'
  return '一般'
})

function getSeverityTagType(severity?: string): 'danger' | 'warning' | 'success' | 'info' {
  const s = (severity ?? '').toLowerCase()
  if (s === 'critical') return 'danger'
  if (s === 'high') return 'warning'
  if (s === 'medium') return 'info'
  if (s === 'low') return 'success'
  return 'info'
}

async function loadStats() {
  loadingStats.value = true
  try {
    const res = await zeroTrustApi.getEventStats()
    if (res.success && res.data) {
      eventStats.value = res.data
    } else {
      eventStats.value = null
    }
  } catch (e: any) {
    eventStats.value = null
    ElMessage.error(e?.response?.data?.detail || e?.message || '加载安全事件统计失败')
  } finally {
    loadingStats.value = false
  }
}

// ==================== 第3部分: 安全策略 ====================

const loadingPolicies = ref(false)
const policies = ref<SecurityPolicy[]>([])
const policyTotal = ref(0)
const policyEnabledCount = ref(0)
const policyFilterCategory = ref('')
const policyFilterEnabledOnly = ref(false)

async function loadPolicies() {
  loadingPolicies.value = true
  try {
    const params: Record<string, any> = {}
    if (policyFilterCategory.value) {
      params.category = policyFilterCategory.value
    }
    if (policyFilterEnabledOnly.value) {
      params.enabled_only = true
    }
    const res = await zeroTrustApi.listPolicies(params)
    if (res.success && res.data) {
      policies.value = res.data.policies || []
      policyTotal.value = res.data.total || 0
      policyEnabledCount.value = res.data.enabled_count || 0
    } else {
      policies.value = []
      policyTotal.value = 0
      policyEnabledCount.value = 0
    }
  } catch (e: any) {
    policies.value = []
    policyTotal.value = 0
    policyEnabledCount.value = 0
    ElMessage.error(e?.response?.data?.detail || e?.message || '加载安全策略失败')
  } finally {
    loadingPolicies.value = false
  }
}

// ==================== 第4部分: 访问评估 ====================

const evaluateFormRef = ref()
const evaluating = ref(false)
const evaluateResult = ref<AccessEvaluationResult | null>(null)

const evaluateForm = reactive({
  resource: '',
  action: '',
  contextText: '',
})

const evaluateRules = {
  resource: [{ required: true, message: '请输入资源路径', trigger: 'blur' }],
  action: [{ required: true, message: '请输入操作类型', trigger: 'blur' }],
}

function parseContextJson(text: string): Record<string, any> | undefined {
  if (!text || !text.trim()) return undefined
  try {
    return JSON.parse(text)
  } catch {
    ElMessage.warning('上下文JSON格式无效，已忽略')
    return undefined
  }
}

async function handleEvaluate() {
  const valid = await evaluateFormRef.value?.validate().catch(() => false)
  if (!valid) return

  evaluating.value = true
  evaluateResult.value = null
  try {
    const context = parseContextJson(evaluateForm.contextText)
    const res = await zeroTrustApi.evaluateAccess({
      resource: evaluateForm.resource,
      action: evaluateForm.action,
      context,
    })
    if (res.success && res.data) {
      evaluateResult.value = res.data
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '访问评估失败')
  } finally {
    evaluating.value = false
  }
}

function resetEvaluateForm() {
  evaluateFormRef.value?.resetFields()
  evaluateResult.value = null
}

// ==================== 第5部分: 安全事件 ====================

const loadingEvents = ref(false)
const events = ref<SecurityEvent[]>([])
const eventTotal = ref(0)
const eventPage = ref(1)
const eventPageSize = ref(20)
const eventFilterSeverity = ref('')
const eventFilterType = ref('')

function handleEventFilterChange() {
  eventPage.value = 1
  loadEvents()
}

async function loadEvents() {
  loadingEvents.value = true
  try {
    const params: Record<string, any> = {
      page: eventPage.value,
      page_size: eventPageSize.value,
    }
    if (eventFilterSeverity.value) {
      params.severity = eventFilterSeverity.value
    }
    if (eventFilterType.value) {
      params.event_type = eventFilterType.value
    }
    const res = await zeroTrustApi.listEvents(params)
    if (res.success && res.data) {
      events.value = res.data.items || []
      eventTotal.value = res.data.total || 0
    } else {
      events.value = []
      eventTotal.value = 0
    }
  } catch (e: any) {
    events.value = []
    eventTotal.value = 0
    ElMessage.error(e?.response?.data?.detail || e?.message || '加载安全事件失败')
  } finally {
    loadingEvents.value = false
  }
}

// ==================== 工具函数 ====================

function formatDateTime(dateStr: string): string {
  if (!dateStr) return '-'
  try {
    const d = new Date(dateStr)
    if (isNaN(d.getTime())) return dateStr
    const pad = (n: number) => String(n).padStart(2, '0')
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
    /* c8 ignore start */
  } catch {
    return dateStr
  }
  /* c8 ignore stop */
}

// ==================== 初始化 ====================

onMounted(() => {
  loadAssessment()
  loadStats()
  loadPolicies()
  loadEvents()
})
</script>

<style scoped lang="scss">
.zero-trust-page {
  padding: 0;
}

.page-header {
  margin-bottom: 16px;

  .header-content {
    display: flex;
    justify-content: space-between;
    align-items: center;

    .header-left {
      h2 {
        margin: 0 0 4px 0;
        font-size: 20px;
        color: #303133;
      }

      .description {
        margin: 0;
        color: #909399;
        font-size: 14px;
      }
    }
  }
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.enabled-hint {
  font-size: 13px;
  color: #909399;
}

.loading-placeholder {
  padding: 20px 0;
}

// 评估仪表盘
.assessment-card {
  margin-bottom: 16px;

  .assessment-body {
    .score-section {
      display: flex;
      align-items: center;
      gap: 40px;
      margin-bottom: 24px;
      padding: 16px 0;

      .score-ring {
        width: 130px;
        height: 130px;
        border-radius: 50%;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        border: 6px solid;
        transition: all 0.3s;

        &.score-red {
          border-color: #f56c6c;
          background: #fef0f0;

          .score-number {
            color: #f56c6c;
          }
        }

        &.score-yellow {
          border-color: #e6a23c;
          background: #fdf6ec;

          .score-number {
            color: #e6a23c;
          }
        }

        &.score-green {
          border-color: #67c23a;
          background: #f0f9eb;

          .score-number {
            color: #67c23a;
          }
        }

        .score-number {
          font-size: 36px;
          font-weight: bold;
          line-height: 1;
        }

        .score-label {
          font-size: 12px;
          color: #909399;
          margin-top: 4px;
        }
      }

      .level-info {
        display: flex;
        flex-direction: column;
        gap: 8px;

        .assessed-time {
          font-size: 13px;
          color: #909399;
        }
      }
    }

    .factors-section {
      margin-bottom: 20px;

      h4 {
        margin: 0 0 10px 0;
        font-size: 15px;
        color: #303133;
      }
    }

    .recommendations-section {
      h4 {
        margin: 0 0 10px 0;
        font-size: 15px;
        color: #303133;
      }

      .recommendation-list {
        list-style: none;
        padding: 0;
        margin: 0;

        li {
          display: flex;
          align-items: flex-start;
          gap: 6px;
          padding: 6px 0;
          font-size: 14px;
          color: #606266;

          .el-icon {
            color: #67c23a;
            margin-top: 2px;
            flex-shrink: 0;
          }
        }
      }
    }
  }
}

.score-text-red {
  color: #f56c6c;
  font-weight: 600;
}

.score-text-yellow {
  color: #e6a23c;
  font-weight: 600;
}

.score-text-green {
  color: #67c23a;
  font-weight: 600;
}

// 事件统计
.stats-card {
  margin-bottom: 16px;

  .stats-body {
    .stats-row {
      margin-bottom: 20px;
    }

    .stat-card {
      text-align: center;

      &.stat-card-warning {
        // accent handled via value-style
      }
    }

    .breakdown-section {
      margin-bottom: 16px;

      h4 {
        margin: 0 0 8px 0;
        font-size: 15px;
        color: #303133;
      }

      .tag-list {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }
    }
  }
}

// 安全策略
.policies-card {
  margin-bottom: 16px;

  .filter-bar {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 12px;
  }

  .policy-expand-detail {
    padding: 12px 20px;

    .json-pre {
      margin: 0;
      padding: 8px;
      background: #f5f7fa;
      border-radius: 4px;
      font-size: 12px;
      max-height: 200px;
      overflow: auto;
      white-space: pre-wrap;
    }
  }
}

// 访问评估
.evaluate-card {
  margin-bottom: 16px;

  .evaluate-result {
    margin-top: 16px;

    .result-detail {
      p {
        margin: 4px 0;
        font-size: 14px;

        &.evaluated-time {
          color: #909399;
          font-size: 12px;
          margin-top: 8px;
        }
      }
    }
  }
}

// 安全事件
.events-card {
  .filter-bar {
    display: flex;
    align-items: center;
    margin-bottom: 12px;
  }

  .pagination-wrapper {
    display: flex;
    justify-content: flex-end;
    margin-top: 16px;
  }
}
</style>
