<template>
  <div class="sentiment-page">
    <div class="page-header">
      <div class="header-info">
        <h2 class="page-title">舆情监测</h2>
        <p class="page-desc">监控帮扶相关舆情动态，分析情感倾向，预警风险信息</p>
      </div>
      <div class="header-actions">
        <el-button type="primary" :loading="collecting" @click="handleCollect">
          <el-icon><Refresh /></el-icon>采集新闻
        </el-button>
        <el-button type="success" :loading="analyzing" @click="handleAnalyze">
          <el-icon><DataAnalysis /></el-icon>分析情感
        </el-button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div v-if="!statsError" class="stats-row">
      <div class="stat-item" :class="statLoading ? 'stat-loading' : ''">
        <div class="stat-value" style="color: var(--color-success)">
          {{ statLoading ? '-' : stats.positive }}
        </div>
        <div class="stat-label">正面舆情</div>
      </div>
      <div class="stat-item">
        <div class="stat-value" style="color: var(--color-info)">
          {{ statLoading ? '-' : stats.neutral }}
        </div>
        <div class="stat-label">中性舆情</div>
      </div>
      <div class="stat-item">
        <div class="stat-value" style="color: var(--color-danger)">
          {{ statLoading ? '-' : stats.negative }}
        </div>
        <div class="stat-label">负面舆情</div>
      </div>
      <div class="stat-item">
        <div class="stat-value" style="color: var(--color-warning)">
          {{ statLoading ? '-' : stats.alerts }}
        </div>
        <div class="stat-label">预警信息</div>
      </div>
      <div class="stat-item">
        <div class="stat-value">{{ statLoading ? '-' : stats.total }}</div>
        <div class="stat-label">总条数</div>
      </div>
    </div>

    <!-- 加载错误提示 -->
    <div v-if="statsError" class="error-hint" style="margin-bottom: 20px">
      <el-alert title="统计数据加载失败" type="warning" show-icon :closable="false" />
    </div>

    <el-row :gutter="20">
      <!-- 热词云 -->
      <el-col :span="12">
        <div class="section-card">
          <div class="section-header">
            <h3>热门关键词</h3>
            <el-select v-model="keywordDays" style="width: 100px" @change="loadKeywords">
              <el-option label="近7天" :value="7" />
              <el-option label="近30天" :value="30" />
            </el-select>
          </div>
          <div v-if="keywordsLoading" class="section-loading">
            <el-icon class="is-loading"><Loading /></el-icon>
            <span>加载中...</span>
          </div>
          <div v-else-if="keywords.length === 0" class="section-empty">
            <EmptyState text="暂无数据" :size="60" />
          </div>
          <div v-else class="keyword-cloud">
            <el-tag
              v-for="kw in keywords"
              :key="kw.word"
              :style="{ fontSize: tagFontSize(kw.count) + 'px', margin: '4px' }"
              :type="tagType(kw.sentiment || 'neutral')"
              effect="plain"
            >
              {{ kw.word }}
              <span class="kw-count">({{ kw.count }})</span>
            </el-tag>
          </div>
        </div>
      </el-col>

      <!-- 预警列表 -->
      <el-col :span="12">
        <div class="section-card">
          <div class="section-header">
            <h3>预警信息</h3>
            <el-tag v-if="alerts.length > 0" type="danger" size="small">
              {{ alerts.length }}条
            </el-tag>
          </div>
          <div v-if="alertsLoading" class="section-loading">
            <el-icon class="is-loading"><Loading /></el-icon>
            <span>加载中...</span>
          </div>
          <div v-else-if="alerts.length === 0" class="section-empty">
            <EmptyState text="暂无预警信息" :size="60" />
          </div>
          <div v-else class="alert-list">
            <div v-for="alert in alerts" :key="alert.id" class="alert-item">
              <div class="alert-header">
                <el-tag
                  :type="alert.sentiment_label === 'negative' ? 'danger' : 'warning'"
                  size="small"
                >
                  {{ alert.sentiment_label || '预警' }}
                </el-tag>
                <span class="alert-source">{{ alert.source || '未知来源' }}</span>
                <span class="alert-time">{{
                  formatDate(alert.published_at || alert.created_at)
                }}</span>
              </div>
              <div class="alert-title">{{ alert.title }}</div>
            </div>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 新闻列表 -->
    <div class="section-card" style="margin-top: 20px">
      <div class="section-header">
        <h3>舆情新闻列表</h3>
        <el-select v-model="newsFilter" style="width: 120px" @change="loadNews">
          <el-option label="全部" value="" />
          <el-option label="正面" value="positive" />
          <el-option label="负面" value="negative" />
          <el-option label="中性" value="neutral" />
          <el-option label="预警" value="alert" />
        </el-select>
      </div>
      <div v-if="newsLoading" class="section-loading">
        <el-icon class="is-loading"><Loading /></el-icon>
        <span>加载中...</span>
      </div>
      <div v-else-if="newsList.length === 0" class="section-empty">
        <EmptyState text="暂无新闻数据" :size="60" />
      </div>
      <el-table v-else :data="newsList" size="small">
        <el-table-column prop="title" label="标题" min-width="280" show-overflow-tooltip />
        <el-table-column label="情感" width="100" align="center">
          <template #default="scope">
            <el-tag :type="sentimentTagType(scope.row.sentiment_label)" size="small">
              {{ sentimentLabel(scope.row.sentiment_label) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="source" label="来源" width="120" show-overflow-tooltip />
        <el-table-column label="发布时间" width="110" align="center">
          <template #default="scope">
            {{ formatDate(scope.row.published_at || scope.row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="预警" width="70" align="center">
          <template #default="scope">
            <el-tag v-if="scope.row.is_alert" type="danger" size="small">预警</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import EmptyState from '@/components/business/EmptyState/EmptyState.vue'
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Loading, Refresh, DataAnalysis } from '@element-plus/icons-vue'
import {
  collectNews,
  analyzeNews,
  getNews,
  getStatistics,
  getHotKeywords,
  getAlerts,
} from '@/api/sentiment'

const stats = reactive({
  positive: 0,
  negative: 0,
  neutral: 0,
  alerts: 0,
  total: 0,
})
const statLoading = ref(false)
const statsError = ref(false)

const keywords = ref<any[]>([])
const keywordsLoading = ref(false)
const keywordDays = ref(7)

const alerts = ref<any[]>([])
const alertsLoading = ref(false)

const newsList = ref<any[]>([])
const newsLoading = ref(false)
const newsFilter = ref('')

const collecting = ref(false)
const analyzing = ref(false)

function formatDate(d: string) {
  if (!d) return '-'
  return d.split('T')[0]
}

function sentimentLabel(label: string) {
  const map: Record<string, string> = {
    positive: '正面',
    negative: '负面',
    neutral: '中性',
  }
  return map[label] || label || '-'
}

function sentimentTagType(label: string) {
  if (label === 'positive') return 'success'
  if (label === 'negative') return 'danger'
  return 'info'
}

function tagFontSize(count: number) {
  const base = Math.min(Math.max(count, 1), 50)
  return 12 + (base / 50) * 8
}

function tagType(sentiment: string): 'success' | 'danger' | 'info' {
  if (sentiment === 'positive') return 'success'
  if (sentiment === 'negative') return 'danger'
  return 'info'
}

async function loadStats() {
  statLoading.value = true
  statsError.value = false
  try {
    const response = await getStatistics(7)
    const data = response?.data ?? response
    if (data) {
      stats.positive = data.positive_count ?? data.positive ?? 0
      stats.negative = data.negative_count ?? data.negative ?? 0
      stats.neutral = data.neutral_count ?? data.neutral ?? 0
      stats.alerts = data.alert_count ?? data.alerts ?? 0
      stats.total = data.total_count ?? data.total ?? 0
    }
  } catch {
    statsError.value = true
  } finally {
    statLoading.value = false
  }
}

async function loadKeywords() {
  keywordsLoading.value = true
  try {
    const response = await getHotKeywords(keywordDays.value, 30)
    const data = response?.data ?? response
    keywords.value = data?.items ?? data?.keywords ?? (Array.isArray(data) ? data : [])
  } catch {
    // 静默
  } finally {
    keywordsLoading.value = false
  }
}

async function loadAlerts() {
  alertsLoading.value = true
  try {
    const response = await getAlerts(7, 20)
    const data = response?.data ?? response
    alerts.value = data?.items ?? (Array.isArray(data) ? data : [])
  } catch {
    // 静默
  } finally {
    alertsLoading.value = false
  }
}

async function loadNews() {
  newsLoading.value = true
  try {
    const params: Record<string, any> = { limit: 20 }
    if (newsFilter.value === 'alert') {
      params.is_alert = true
    } else if (newsFilter.value) {
      params.sentiment_label = newsFilter.value
    }
    const response = await getNews(params)
    const data = response?.data ?? response
    newsList.value = data?.items ?? (Array.isArray(data) ? data : [])
  } catch {
    // 静默
  } finally {
    newsLoading.value = false
  }
}

async function handleCollect() {
  collecting.value = true
  try {
    await collectNews({
      keywords: ['乡村振兴', '帮扶', '帮扶', '助学兴教'],
    })
    ElMessage.success('新闻采集已触发')
    setTimeout(() => {
      loadStats()
      loadNews()
    }, 2000)
  } catch {
    ElMessage.error('采集失败')
  } finally {
    collecting.value = false
  }
}

async function handleAnalyze() {
  analyzing.value = true
  try {
    const response = await analyzeNews(100)
    const data = response?.data ?? response
    ElMessage.success(`分析完成：处理 ${data?.processed ?? 'N/A'} 条`)
    loadStats()
    loadKeywords()
    loadAlerts()
    loadNews()
  } catch {
    ElMessage.error('分析失败')
  } finally {
    analyzing.value = false
  }
}

onMounted(() => {
  loadStats()
  loadKeywords()
  loadAlerts()
  loadNews()
})
</script>

<style scoped>
.sentiment-page {
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

.stats-row {
  display: flex;
  gap: 16px;
  margin-bottom: 20px;
}

.stat-item {
  flex: 1;
  background: white;
  border: 1px solid var(--color-border-light);
  border-radius: 8px;
  padding: 16px 20px;
  text-align: center;
  transition: all 0.3s;
}

.stat-item:hover {
  border-color: rgba(45, 106, 79, 0.5);
  box-shadow: 0 2px 12px rgba(27, 67, 50, 0.12);
}

.stat-loading {
  opacity: 0.6;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--color-primary-dark-1);
  line-height: 1.2;
}

.stat-label {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin-top: 4px;
}

.section-card {
  background: white;
  border-radius: 8px;
  border: 1px solid var(--color-border-light);
  overflow: hidden;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: var(--color-bg-hover);
  border-bottom: 1px solid var(--color-border-light);
}

.section-header h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--color-primary-dark-1);
}

.section-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 40px;
  color: var(--color-text-secondary);
  gap: 8px;
}

.section-empty {
  padding: 20px;
}

.keyword-cloud {
  padding: 16px;
  min-height: 200px;
  line-height: 2;
}

.kw-count {
  font-size: 10px;
  color: var(--color-info);
  margin-left: 2px;
}

.alert-list {
  max-height: 400px;
  overflow-y: auto;
}

.alert-item {
  padding: 12px 16px;
  border-bottom: 1px solid var(--color-bg-hover);
}

.alert-item:last-child {
  border-bottom: none;
}

.alert-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.alert-source {
  font-size: 12px;
  color: var(--color-info);
}

.alert-time {
  font-size: 12px;
  color: var(--color-text-placeholder, var(--color-text-disabled));
  margin-left: auto;
}

.alert-title {
  font-size: 14px;
  color: var(--color-text-primary);
  line-height: 1.5;
}

.error-hint {
  /* placeholder */
}
</style>
