<template>
  <div class="ai-interactive-page">
    <div class="page-header">
      <div class="header-info">
        <h2 class="page-title">AI 智能分析</h2>
        <p class="page-desc">利用AI技术进行数据分析、趋势预测、异常检测和智能推荐</p>
      </div>
      <el-tag :type="serviceStatus === 'available' ? 'success' : 'info'" size="small">
        {{ serviceStatus === 'available' ? '服务可用' : '加载中...' }}
      </el-tag>
    </div>

    <!-- Tab导航 -->
    <el-tabs v-model="activeTab" type="border-card">
      <!-- 数据分析 -->
      <el-tab-pane label="数据分析" name="analyze">
        <div class="tab-content">
          <el-form :model="analyzeForm" label-width="100px">
            <el-form-item label="分析类型">
              <el-radio-group v-model="analyzeForm.type">
                <el-radio value="summary">数据摘要</el-radio>
                <el-radio value="trend">趋势分析</el-radio>
                <el-radio value="statistics">统计分析</el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="分析说明">
              <el-input
                v-model="analyzeForm.description"
                type="textarea"
                :rows="3"
                placeholder="描述您想分析的内容（可选）"
              />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="analyzeLoading" @click="runAnalyze">
                <el-icon><DataAnalysis /></el-icon>开始分析
              </el-button>
            </el-form-item>
          </el-form>

          <div v-if="analyzeResult" class="result-block">
            <el-divider />
            <h4>{{ analyzeResult.analysis_type || '分析结果' }}</h4>
            <el-descriptions :column="2" border>
              <el-descriptions-item
                v-for="(value, key) in analyzeResult.flattened"
                :key="key"
                :label="String(key)"
              >
                {{ String(value) }}
              </el-descriptions-item>
            </el-descriptions>
          </div>
        </div>
      </el-tab-pane>

      <!-- 趋势预测 -->
      <el-tab-pane label="趋势预测" name="forecast">
        <div class="tab-content">
          <el-row :gutter="20">
            <el-col :span="12">
              <el-card shadow="hover">
                <template #header>
                  <span>收入趋势预测</span>
                </template>
                <el-form label-width="100px">
                  <el-form-item label="预测年数">
                    <el-select v-model="forecastYears" style="width: 120px">
                      <el-option :value="1" label="1年" />
                      <el-option :value="2" label="2年" />
                      <el-option :value="3" label="3年" />
                      <el-option :value="5" label="5年" />
                    </el-select>
                  </el-form-item>
                  <el-button type="primary" :loading="forecastLoading" @click="runForecastIncome">
                    预测
                  </el-button>
                </el-form>
                <div v-if="forecastResult" class="result-text">
                  <p v-for="(item, i) in forecastItems" :key="i">
                    {{ item.year || item.label }}: {{ item.value }}
                  </p>
                </div>
              </el-card>
            </el-col>
            <el-col :span="12">
              <el-card shadow="hover">
                <template #header>
                  <span>经费完成率预测</span>
                </template>
                <p class="card-desc">预测年度经费的完成率趋势</p>
                <el-button type="success" :loading="fundForecastLoading" @click="runForecastFunds">
                  执行预测
                </el-button>
                <div v-if="fundForecastResult" class="result-text">
                  <p v-for="(item, i) in fundForecastItems" :key="i">
                    {{ item.year || item.label }}: {{ item.value }}
                  </p>
                </div>
              </el-card>
            </el-col>
          </el-row>
        </div>
      </el-tab-pane>

      <!-- 异常检测 -->
      <el-tab-pane label="异常检测" name="anomaly">
        <div class="tab-content">
          <el-form :model="anomalyForm" label-width="100px">
            <el-form-item label="检测方式">
              <el-select v-model="anomalyForm.method" style="width: 200px">
                <el-option label="统计方法" value="statistical" />
                <el-option label="孤立森林" value="isolation_forest" />
                <el-option label="Z-Score" value="zscore" />
              </el-select>
            </el-form-item>
            <el-form-item label="敏感度">
              <el-slider
                v-model="anomalyForm.contamination"
                :min="1"
                :max="50"
                show-input
                style="width: 300px"
              />
              <span class="hint-text">值越小越敏感（1%~50%）</span>
            </el-form-item>
            <el-form-item label="数据输入">
              <el-input
                v-model="anomalyInput"
                type="textarea"
                :rows="4"
                placeholder='输入JSON数组格式的数据&#10;例如：[{"year": 2021, "value": 100}, {"year": 2022, "value": 150}]'
              />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="anomalyLoading" @click="runAnomalyDetection">
                <el-icon><Warning /></el-icon>检测异常
              </el-button>
            </el-form-item>
          </el-form>

          <div v-if="anomalyResult" class="result-block">
            <el-divider />
            <h4>异常检测结果</h4>
            <el-table
              v-if="anomalyResult.anomalies?.length"
              :data="anomalyResult.anomalies"
              stripe
              size="small"
            >
              <el-table-column type="index" label="#" width="50" />
              <el-table-column v-for="col in anomalyColumns" :key="col" :prop="col" :label="col" />
              <el-table-column label="异常" width="80">
                <template #default="scope">
                  <el-tag :type="scope.row.is_anomaly ? 'danger' : 'success'" size="small">
                    {{ scope.row.is_anomaly ? '是' : '否' }}
                  </el-tag>
                </template>
              </el-table-column>
            </el-table>
            <el-empty v-else description="未检测到异常数据" :image-size="60" />
          </div>
        </div>
      </el-tab-pane>

      <!-- 智能推荐 -->
      <el-tab-pane label="智能推荐" name="recommend">
        <div class="tab-content">
          <el-row :gutter="20">
            <el-col :span="12">
              <el-card shadow="hover">
                <template #header>
                  <span>项目推荐</span>
                </template>
                <el-form label-width="80px">
                  <el-form-item label="村庄ID">
                    <el-input-number
                      v-model="recommendVillageId"
                      :min="1"
                      placeholder="输入村庄ID"
                    />
                  </el-form-item>
                  <el-form-item label="推荐数">
                    <el-select v-model="recommendLimit" style="width: 100px">
                      <el-option :value="3" label="3个" />
                      <el-option :value="5" label="5个" />
                      <el-option :value="10" label="10个" />
                    </el-select>
                  </el-form-item>
                  <el-button
                    type="primary"
                    :loading="recommendLoading"
                    @click="runRecommendProjects"
                  >
                    推荐项目
                  </el-button>
                </el-form>
                <div v-if="recommendResults.length" class="result-list">
                  <div v-for="(rec, i) in recommendResults" :key="i" class="rec-item">
                    <span class="rec-name">{{ rec.name || rec.title || `推荐${i + 1}` }}</span>
                    <el-tag v-if="rec.score" size="small" type="success">
                      {{ Number(rec.score).toFixed(1) }}
                    </el-tag>
                  </div>
                </div>
              </el-card>
            </el-col>
            <el-col :span="12">
              <el-card shadow="hover">
                <template #header>
                  <span>系统推荐</span>
                </template>
                <el-button
                  type="success"
                  :loading="sysRecommendLoading"
                  @click="runSystemRecommend"
                >
                  获取系统建议
                </el-button>
                <div v-if="systemRecommendations.length" class="result-list">
                  <div v-for="(rec, i) in systemRecommendations" :key="i" class="rec-item">
                    <el-tag
                      :type="
                        rec.priority === 'high'
                          ? 'danger'
                          : rec.priority === 'medium'
                            ? 'warning'
                            : 'info'
                      "
                      size="small"
                    >
                      {{ rec.priority || 'info' }}
                    </el-tag>
                    <span>{{ rec.content || rec.title || rec }}</span>
                  </div>
                </div>
              </el-card>
            </el-col>
          </el-row>
        </div>
      </el-tab-pane>

      <!-- NLP查询 -->
      <el-tab-pane label="NLP查询" name="nlp">
        <div class="tab-content">
          <el-form :model="nlpForm" inline>
            <el-form-item label="自然语言查询">
              <el-input
                v-model="nlpForm.query"
                placeholder="例如：哪个村庄的人均收入最高？"
                style="width: 480px"
                clearable
                @keyup.enter="runNlpQuery"
              />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="nlpLoading" @click="runNlpQuery">
                <el-icon><Search /></el-icon>查询
              </el-button>
            </el-form-item>
          </el-form>

          <div v-if="nlpResult" class="result-block">
            <el-divider />
            <h4>查询结果</h4>
            <div class="nlp-answer">
              <el-alert
                :title="
                  nlpResult.explanation ||
                  nlpResult.answer ||
                  nlpResult.error ||
                  nlpResult.result ||
                  JSON.stringify(nlpResult)
                "
                :type="nlpResult.success === false ? 'error' : 'info'"
                :closable="false"
                show-icon
              />
            </div>
          </div>

          <div v-if="nlpHistory.length" class="history-block">
            <el-divider />
            <h4>查询历史</h4>
            <el-tag
              v-for="(h, i) in nlpHistory"
              :key="i"
              size="small"
              style="margin: 4px; cursor: pointer"
              @click="nlpForm.query = h"
            >
              {{ h }}
            </el-tag>
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { DataAnalysis, Warning, Search } from '@element-plus/icons-vue'
import {
  getStatus,
  analyze,
  getRecommendations,
  forecastIncome,
  forecastFunds,
  detectAnomalies,
  recommendProjects,
  nlpQuery,
} from '@/api/ai'

const activeTab = ref('analyze')
const serviceStatus = ref('loading')

// --- 数据分析 ---
const analyzeForm = reactive({ type: 'summary', description: '' })
const analyzeLoading = ref(false)
const analyzeResult = ref<any>(null)

// --- 趋势预测 ---
const forecastYears = ref(2)
const forecastLoading = ref(false)
const forecastResult = ref<any>(null)
const forecastItems = ref<any[]>([])
const fundForecastLoading = ref(false)
const fundForecastResult = ref<any>(null)
const fundForecastItems = ref<any[]>([])

// --- 异常检测 ---
const anomalyForm = reactive({ method: 'zscore', contamination: 5 })
const anomalyInput = ref('')
const anomalyLoading = ref(false)
const anomalyResult = ref<any>(null)
const anomalyColumns = ref<string[]>([])

// --- 智能推荐 ---
const recommendVillageId = ref(1)
const recommendLimit = ref(5)
const recommendLoading = ref(false)
const recommendResults = ref<any[]>([])
const sysRecommendLoading = ref(false)
const systemRecommendations = ref<any[]>([])

// --- NLP ---
const nlpForm = reactive({ query: '' })
const nlpLoading = ref(false)
const nlpResult = ref<any>(null)
const nlpHistory = ref<string[]>([])

function flattenObject(obj: any): Record<string, any> {
  if (!obj || typeof obj !== 'object') return {}
  const result: Record<string, any> = {}
  for (const [key, value] of Object.entries(obj)) {
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      Object.assign(result, flattenObject(value))
    } else {
      result[key] = value
    }
  }
  return result
}

async function checkStatus() {
  try {
    const response = await getStatus()
    const data = response?.data ?? response
    const svc = data?.data?.services || data?.services
    if (svc?.local_analysis) {
      serviceStatus.value = svc.local_analysis.status || 'available'
    } else {
      serviceStatus.value = 'available'
    }
  } catch {
    serviceStatus.value = 'unavailable'
  }
}

async function runAnalyze() {
  analyzeLoading.value = true
  analyzeResult.value = null
  try {
    const response = await analyze({
      analysis_type: analyzeForm.type,
      description: analyzeForm.description || undefined,
    })
    const data = response?.data ?? response
    const inner = data?.data || data
    analyzeResult.value = {
      ...inner,
      flattened: flattenObject(inner?.result || inner || {}),
    }
    ElMessage.success('分析完成')
  } catch {
    ElMessage.error('分析失败')
  } finally {
    analyzeLoading.value = false
  }
}

async function runForecastIncome() {
  forecastLoading.value = true
  forecastResult.value = null
  try {
    const response = await forecastIncome(forecastYears.value)
    const data = response?.data ?? response
    forecastResult.value = data?.data || data
    // 后端返回 {historical:[...], forecast:[{year, avg_per_capita_income, ...}]}
    const fc = forecastResult.value?.forecast
    forecastItems.value = Array.isArray(fc)
      ? fc.map((f: any) => ({
          year: f.year,
          value: `人均 ${f.avg_per_capita_income ?? '-'} / 集体 ${f.avg_collective_income ?? '-'}`,
        }))
      : []
    ElMessage.success('预测完成')
  } catch {
    ElMessage.error('预测失败')
  } finally {
    forecastLoading.value = false
  }
}

async function runForecastFunds() {
  fundForecastLoading.value = true
  fundForecastResult.value = null
  try {
    const response = await forecastFunds()
    const data = response?.data ?? response
    fundForecastResult.value = data?.data || data
    // 后端返回 {current:{usage_rate}, projected_year_end_usage_rate, risk_label, ...}
    const r = fundForecastResult.value || {}
    const pct = (v: any) => (v == null ? '-' : `${Math.round(Number(v) * 100)}%`)
    fundForecastItems.value = [
      { label: '当年使用率', value: pct(r.current?.usage_rate) },
      { label: '预计年末使用率', value: pct(r.projected_year_end_usage_rate) },
      { label: '风险评估', value: r.risk_label || r.risk_level || '-' },
    ]
    ElMessage.success('预测完成')
  } catch {
    ElMessage.error('预测失败')
  } finally {
    fundForecastLoading.value = false
  }
}

async function runAnomalyDetection() {
  // 空输入场景在下方 else 分支统一处理（生成演示数据）
  anomalyLoading.value = true
  anomalyResult.value = null
  try {
    let dataInput: any[] = []
    if (anomalyInput.value.trim()) {
      try {
        dataInput = JSON.parse(anomalyInput.value)
        if (!Array.isArray(dataInput)) dataInput = [dataInput]
      } catch {
        ElMessage.error('数据格式错误，请检查JSON格式')
        anomalyLoading.value = false
        return
      }
    } else {
      // 用户未输入数据时，生成随机示例数据用于功能演示
      ElMessage.info('未输入数据，已使用随机示例数据进行演示')
      for (let i = 0; i < 20; i++) {
        dataInput.push({ index: i, value: Math.random() * 100 })
      }
    }
    const response = await detectAnomalies({
      data: dataInput,
      value_field: 'value',
      method: anomalyForm.method,
      contamination: anomalyForm.contamination / 100,
    })
    const data = response?.data ?? response
    // 后端裸返回异常记录数组（非 envelope）；归一化为 {anomalies, anomaly_count}
    const raw = Array.isArray(data) ? data : data?.anomalies || data?.data?.anomalies || []
    anomalyResult.value = {
      anomalies: (Array.isArray(raw) ? raw : []).map((r: any) => ({
        ...r,
        is_anomaly: true,
      })),
      anomaly_count: Array.isArray(raw) ? raw.length : 0,
    }
    if (anomalyResult.value?.anomalies?.length) {
      const first = anomalyResult.value.anomalies[0]
      anomalyColumns.value = Object.keys(first).filter((k) => k !== 'is_anomaly')
    } else {
      anomalyColumns.value = []
    }
    ElMessage.success(`检测完成：发现 ${anomalyResult.value?.anomaly_count ?? 'N/A'} 个异常`)
  } catch {
    ElMessage.error('异常检测失败')
  } finally {
    anomalyLoading.value = false
  }
}

async function runRecommendProjects() {
  if (!recommendVillageId.value) {
    ElMessage.warning('请输入村庄ID')
    return
  }
  recommendLoading.value = true
  recommendResults.value = []
  try {
    const response = await recommendProjects(recommendVillageId.value, recommendLimit.value)
    const data = response?.data ?? response
    const items = data?.data?.items || data?.items || data || []
    recommendResults.value = Array.isArray(items) ? items : []
    ElMessage.success('推荐完成')
  } catch {
    ElMessage.error('推荐失败')
  } finally {
    recommendLoading.value = false
  }
}

async function runSystemRecommend() {
  sysRecommendLoading.value = true
  systemRecommendations.value = []
  try {
    const response = await getRecommendations({ context: {} })
    const data = response?.data ?? response
    const recs = data?.data?.recommendations || data?.recommendations || []
    systemRecommendations.value = Array.isArray(recs) ? recs : []
    ElMessage.success('获取推荐成功')
  } catch {
    ElMessage.error('获取推荐失败')
  } finally {
    sysRecommendLoading.value = false
  }
}

async function runNlpQuery() {
  if (!nlpForm.query.trim()) {
    ElMessage.warning('请输入查询内容')
    return
  }
  nlpLoading.value = true
  nlpResult.value = null
  try {
    const response = await nlpQuery(nlpForm.query.trim())
    // 后端裸返回 {success, data, explanation, sql, query} 或 {success:false, error}
    const body = response?.success !== undefined ? response : response?.data
    nlpResult.value = body
    nlpHistory.value.unshift(nlpForm.query.trim())
    if (nlpHistory.value.length > 10) nlpHistory.value.pop()
    ElMessage.success('查询完成')
  } catch {
    ElMessage.error('查询失败')
  } finally {
    nlpLoading.value = false
  }
}

// 初始化
checkStatus()
</script>

<style scoped>
.ai-interactive-page {
  padding: 20px;
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
  color: #1b4332;
}

.page-desc {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--color-text-secondary);
}

.tab-content {
  padding: 20px;
  min-height: 300px;
}

.result-block {
  margin-top: 16px;
}

.result-block h4 {
  margin: 0 0 12px;
  color: #1b4332;
}

.result-text {
  margin-top: 12px;
  padding: 12px;
  background: var(--color-bg-hover);
  border-radius: 6px;
}

.result-text p {
  margin: 4px 0;
  font-size: 13px;
  color: var(--color-text-primary);
}

.card-desc {
  font-size: 13px;
  color: var(--color-info);
  margin-bottom: 12px;
}

.result-list {
  margin-top: 12px;
}

.rec-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  border-bottom: 1px solid var(--color-bg-hover);
}

.rec-name {
  font-size: 14px;
  flex: 1;
}

.nlp-answer {
  max-width: 700px;
}

.history-block {
  margin-top: 16px;
}

.history-block h4 {
  margin: 0 0 8px;
  color: #1b4332;
}

.hint-text {
  margin-left: 12px;
  font-size: 12px;
  color: var(--color-info);
}
</style>
