<template>
  <div class="data-tier-page">
    <!-- 页头 -->
    <div class="page-header">
      <h2>数据分级存储管理</h2>
      <el-button :icon="Refresh" :loading="loading" @click="refreshAll"> 刷新 </el-button>
    </div>

    <!-- 分级摘要卡片 -->
    <el-row :gutter="20" class="stats-row">
      <el-col :span="8">
        <el-card shadow="hover" class="tier-card tier-hot">
          <el-statistic title="热数据（近 30 天）" :value="stats.hot_count ?? 0">
            <template #suffix>
              <span class="stat-suffix">条</span>
            </template>
          </el-statistic>
          <div class="tier-size">
            {{ formatSize(stats.hot_size_mb) }}
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover" class="tier-card tier-warm">
          <el-statistic title="温数据（30-365 天）" :value="stats.warm_count ?? 0">
            <template #suffix>
              <span class="stat-suffix">条</span>
            </template>
          </el-statistic>
          <div class="tier-size">
            {{ formatSize(stats.warm_size_mb) }}
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover" class="tier-card tier-cold">
          <el-statistic title="冷数据（> 365 天）" :value="stats.cold_count ?? 0">
            <template #suffix>
              <span class="stat-suffix">条</span>
            </template>
          </el-statistic>
          <div class="tier-size">
            {{ formatSize(stats.cold_size_mb) }}
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 分级分布图表 -->
    <el-row :gutter="20" class="charts-row">
      <el-col :span="12">
        <el-card>
          <template #header>
            <span>数据量分布</span>
          </template>
          <div class="tier-bars">
            <div class="bar-item">
              <span class="bar-label">热数据</span>
              <div class="bar-track">
                <div class="bar-fill bar-hot" :style="{ width: countPercent('hot') + '%' }"></div>
              </div>
              <span class="bar-value">{{ stats.hot_count ?? 0 }}</span>
            </div>
            <div class="bar-item">
              <span class="bar-label">温数据</span>
              <div class="bar-track">
                <div class="bar-fill bar-warm" :style="{ width: countPercent('warm') + '%' }"></div>
              </div>
              <span class="bar-value">{{ stats.warm_count ?? 0 }}</span>
            </div>
            <div class="bar-item">
              <span class="bar-label">冷数据</span>
              <div class="bar-track">
                <div class="bar-fill bar-cold" :style="{ width: countPercent('cold') + '%' }"></div>
              </div>
              <span class="bar-value">{{ stats.cold_count ?? 0 }}</span>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <template #header>
            <span>存储空间分布</span>
          </template>
          <div class="tier-bars">
            <div class="bar-item">
              <span class="bar-label">热数据</span>
              <div class="bar-track">
                <div class="bar-fill bar-hot" :style="{ width: sizePercent('hot') + '%' }"></div>
              </div>
              <span class="bar-value">{{ formatSize(stats.hot_size_mb) }}</span>
            </div>
            <div class="bar-item">
              <span class="bar-label">温数据</span>
              <div class="bar-track">
                <div class="bar-fill bar-warm" :style="{ width: sizePercent('warm') + '%' }"></div>
              </div>
              <span class="bar-value">{{ formatSize(stats.warm_size_mb) }}</span>
            </div>
            <div class="bar-item">
              <span class="bar-label">冷数据</span>
              <div class="bar-track">
                <div class="bar-fill bar-cold" :style="{ width: sizePercent('cold') + '%' }"></div>
              </div>
              <span class="bar-value">{{ formatSize(stats.cold_size_mb) }}</span>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 归档控制 -->
    <el-card class="section-card">
      <template #header>
        <div class="card-header">
          <span class="title">归档控制</span>
          <el-tag v-if="archiveResult" type="success" effect="plain">
            最近归档：{{ archiveResult.model }}，{{ archiveResult.archived_count }}
            条
          </el-tag>
        </div>
      </template>
      <el-form :inline="true" :model="archiveForm" class="archive-form">
        <el-form-item label="数据模型">
          <el-input
            v-model="archiveForm.modelName"
            placeholder="例如：WorkLog"
            style="width: 180px"
          />
        </el-form-item>
        <el-form-item label="天数阈值">
          <el-input-number
            v-model="archiveForm.beforeDays"
            :min="1"
            :max="3650"
            style="width: 140px"
          />
        </el-form-item>
        <el-form-item label="批次大小">
          <el-input-number
            v-model="archiveForm.batchSize"
            :min="100"
            :max="50000"
            :step="100"
            style="width: 140px"
          />
        </el-form-item>
        <el-form-item>
          <el-button
            type="primary"
            :loading="archiving"
            :icon="FolderOpened"
            @click="handleArchive"
          >
            执行归档
          </el-button>
        </el-form-item>
      </el-form>
      <el-alert
        v-if="archiveResult"
        :title="archiveResult.message"
        type="success"
        :closable="false"
        style="margin-top: 12px"
      />
    </el-card>

    <!-- 归档文件列表 -->
    <el-card class="section-card">
      <template #header>
        <span class="title">归档文件列表</span>
      </template>
      <el-tabs v-model="archiveTab" @tab-change="handleArchiveTabChange">
        <el-tab-pane label="冷归档" name="cold">
          <el-table :data="coldArchives" style="width: 100%" empty-text="暂无非归档文件">
            <el-table-column prop="name" label="文件名" min-width="200" />
            <el-table-column label="大小" width="120">
              <template #default="{ row }">
                {{ formatSize(row.size_mb) }}
              </template>
            </el-table-column>
            <el-table-column label="修改时间" width="200">
              <template #default="{ row }">
                {{ row.modified }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120">
              <template #default="{ row }">
                <el-button type="primary" size="small" link @click="handleRestore(row)">
                  恢复
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
        <el-tab-pane label="温归档" name="warm">
          <el-table :data="warmArchives" style="width: 100%" empty-text="暂无温归档文件">
            <el-table-column prop="name" label="文件名" min-width="200" />
            <el-table-column label="大小" width="120">
              <template #default="{ row }">
                {{ formatSize(row.size_mb) }}
              </template>
            </el-table-column>
            <el-table-column label="修改时间" width="200">
              <template #default="{ row }">
                {{ row.modified }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120">
              <template #default="{ row }">
                <el-button type="primary" size="small" link @click="handleRestore(row)">
                  恢复
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 分级查询 -->
    <el-card class="section-card">
      <template #header>
        <span class="title">分级查询</span>
      </template>
      <el-form :inline="true">
        <el-form-item label="记录日期">
          <el-date-picker
            v-model="lookupDate"
            type="date"
            placeholder="选择日期"
            value-format="YYYY-MM-DD"
            style="width: 180px"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" :loading="lookingUp" @click="handleLookup">
            查询分级
          </el-button>
        </el-form-item>
      </el-form>
      <div v-if="tierInfo" class="tier-lookup-result">
        <el-descriptions :column="3" border size="small">
          <el-descriptions-item label="记录日期">
            {{ tierInfo.record_date }}
          </el-descriptions-item>
          <el-descriptions-item label="分级">
            <el-tag
              :type="
                tierInfo.tier === 'hot' ? 'danger' : tierInfo.tier === 'warm' ? 'warning' : 'info'
              "
            >
              {{ tierLabel(tierInfo.tier) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="数据年龄"> {{ tierInfo.age_days }} 天 </el-descriptions-item>
        </el-descriptions>
      </div>
    </el-card>

    <!-- 清理 -->
    <el-card class="section-card cleanup-section">
      <template #header>
        <span class="title">归档清理</span>
      </template>
      <div class="cleanup-controls">
        <el-input-number
          v-model="cleanupMaxAge"
          :min="1"
          :max="3650"
          style="width: 160px; margin-right: 16px"
        />
        <span class="cleanup-label">天前的归档文件</span>
        <el-button type="danger" :loading="cleaningUp" @click="handleCleanup">
          清理过期归档
        </el-button>
      </div>
      <el-alert
        v-if="cleanupResult"
        :title="cleanupResult.message"
        type="success"
        :closable="false"
        style="margin-top: 12px"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, FolderOpened, Search } from '@element-plus/icons-vue'
import { dataTierApi } from '@/api/dataTier'
import type {
  StorageStats,
  ArchiveFile,
  ArchiveResult,
  CleanupResult,
  RecordTierInfo,
} from '@/api/dataTier'

// ==================== 响应式状态 ====================

const loading = ref(false)
const archiving = ref(false)
const cleaningUp = ref(false)
const lookingUp = ref(false)

const stats = ref<StorageStats>({})
const archiveTab = ref('cold')
const coldArchives = ref<ArchiveFile[]>([])
const warmArchives = ref<ArchiveFile[]>([])
const archiveResult = ref<ArchiveResult | null>(null)
const cleanupResult = ref<CleanupResult | null>(null)
const tierInfo = ref<RecordTierInfo | null>(null)

const archiveForm = ref({
  modelName: '',
  beforeDays: 365,
  batchSize: 1000,
})

const lookupDate = ref<string>('')
const cleanupMaxAge = ref(365)

// ==================== 计算属性 ====================

const totalCount = computed(() => {
  return (
    (Number(stats.value.hot_count) || 0) +
    (Number(stats.value.warm_count) || 0) +
    (Number(stats.value.cold_count) || 0)
  )
})

const totalSize = computed(() => {
  return (
    (Number(stats.value.hot_size_mb) || 0) +
    (Number(stats.value.warm_size_mb) || 0) +
    (Number(stats.value.cold_size_mb) || 0)
  )
})

function countPercent(tier: string): number {
  if (totalCount.value === 0) return 0
  const val = Number((stats.value as any)[`${tier}_count`]) || 0
  return Math.round((val / totalCount.value) * 100)
}

function sizePercent(tier: string): number {
  if (totalSize.value === 0) return 0
  const val = Number((stats.value as any)[`${tier}_size_mb`]) || 0
  return Math.round((val / totalSize.value) * 100)
}

// ==================== 工具函数 ====================

function formatSize(mb: number | undefined): string {
  if (mb === undefined || mb === null) return '-'
  const n = Number(mb)
  if (n >= 1024) return (n / 1024).toFixed(2) + ' GB'
  return n.toFixed(2) + ' MB'
}

function tierLabel(tier: string): string {
  const map: Record<string, string> = {
    hot: '热数据',
    warm: '温数据',
    cold: '冷数据',
  }
  return map[tier] || tier
}

// ==================== 数据加载 ====================

async function loadStats() {
  try {
    const data: any = (await dataTierApi.getStats()) || {}
    // 后端返回 by_tier.{hot,warm,cold}.{count,size_mb} 嵌套结构 → 归一化为扁平字段
    const byTier = data.by_tier || {}
    const flat = {
      hot_count: byTier.hot?.count ?? data.hot_count ?? 0,
      hot_size_mb: byTier.hot?.size_mb ?? data.hot_size_mb ?? 0,
      warm_count: byTier.warm?.count ?? data.warm_count ?? 0,
      warm_size_mb: byTier.warm?.size_mb ?? data.warm_size_mb ?? 0,
      cold_count: byTier.cold?.count ?? data.cold_count ?? 0,
      cold_size_mb: byTier.cold?.size_mb ?? data.cold_size_mb ?? 0,
    }
    stats.value = { ...data, ...flat }
  } catch {
    ElMessage.error('加载存储统计失败')
  }
}

async function loadArchives() {
  try {
    const data = await dataTierApi.listArchives()
    // handle both ArchiveList shape and Record<string, any> shape
    if (data && 'cold_archives' in data) {
      coldArchives.value = (data as any).cold_archives || []
      warmArchives.value = (data as any).warm_archives || []
    } else {
      coldArchives.value = []
      warmArchives.value = []
    }
  } catch {
    ElMessage.error('加载归档列表失败')
  }
}

async function refreshAll() {
  loading.value = true
  try {
    await Promise.all([loadStats(), loadArchives()])
    ElMessage.success('刷新完成')
  } finally {
    loading.value = false
  }
}

// ==================== 归档操作 ====================

async function handleArchive() {
  if (!archiveForm.value.modelName.trim()) {
    ElMessage.warning('请输入数据模型名称')
    return
  }

  archiving.value = true
  try {
    const result = await dataTierApi.archiveModel(
      archiveForm.value.modelName.trim(),
      archiveForm.value.beforeDays,
      archiveForm.value.batchSize
    )
    archiveResult.value = result
    ElMessage.success(result.message || '归档完成')
    await loadStats()
  } catch {
    ElMessage.error('归档失败')
  } finally {
    archiving.value = false
  }
}

// ==================== 恢复操作 ====================

async function handleRestore(file: ArchiveFile | Record<string, any>) {
  try {
    await ElMessageBox.confirm(`确定要恢复归档文件「${file.name}」吗？`, '确认恢复', {
      type: 'warning',
      confirmButtonText: '恢复',
      cancelButtonText: '取消',
    })
  } catch {
    return // user cancelled
  }

  // Extract model name from archive file name (convention: model_name_*.json)
  const modelName = file.name.split('_')[0] || ''

  try {
    const result = await dataTierApi.restore(file.name, modelName)
    ElMessage.success(result.message || '恢复完成')
    await refreshAll()
  } catch {
    ElMessage.error('恢复失败')
  }
}

function handleArchiveTabChange() {
  // tabs already bound to coldArchives/warmArchives via v-model
}

// ==================== 分级查询 ====================

async function handleLookup() {
  if (!lookupDate.value) {
    ElMessage.warning('请选择日期')
    return
  }

  lookingUp.value = true
  tierInfo.value = null
  try {
    const result = await dataTierApi.getTierForRecord(lookupDate.value)
    tierInfo.value = result
  } catch {
    ElMessage.error('分级查询失败')
  } finally {
    lookingUp.value = false
  }
}

// ==================== 清理操作 ====================

async function handleCleanup() {
  try {
    await ElMessageBox.confirm(
      `确定要清理 ${cleanupMaxAge.value} 天前的归档文件吗？此操作不可撤销。`,
      '确认清理',
      {
        type: 'warning',
        confirmButtonText: '确认清理',
        cancelButtonText: '取消',
      }
    )
  } catch {
    return // user cancelled
  }

  cleaningUp.value = true
  cleanupResult.value = null
  try {
    const result = await dataTierApi.cleanup(cleanupMaxAge.value)
    cleanupResult.value = result
    ElMessage.success(result.message || '清理完成')
    await loadArchives()
  } catch {
    ElMessage.error('清理失败')
  } finally {
    cleaningUp.value = false
  }
}

// ==================== 生命周期 ====================

onMounted(() => {
  loadStats()
  loadArchives()
})
</script>

<style scoped>
.data-tier-page {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

/* Tier cards */
.stats-row {
  margin-bottom: 20px;
}

.tier-card {
  border-left: 4px solid #ccc;
}

.tier-card.tier-hot {
  border-left-color: #f56c6c;
}

.tier-card.tier-warm {
  border-left-color: #e6a23c;
}

.tier-card.tier-cold {
  border-left-color: #409eff;
}

.tier-size {
  margin-top: 8px;
  color: #909399;
  font-size: 14px;
}

.stat-suffix {
  font-size: 14px;
  color: #909399;
}

/* Bar charts */
.charts-row {
  margin-bottom: 20px;
}

.tier-bars {
  padding: 10px 0;
}

.bar-item {
  display: flex;
  align-items: center;
  margin-bottom: 16px;
}

.bar-item:last-child {
  margin-bottom: 0;
}

.bar-label {
  width: 60px;
  font-size: 13px;
  color: #606266;
  flex-shrink: 0;
}

.bar-track {
  flex: 1;
  height: 20px;
  background: #f0f2f5;
  border-radius: 4px;
  overflow: hidden;
  margin: 0 12px;
}

.bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.6s ease;
  min-width: 4px;
}

.bar-fill.bar-hot {
  background: #f56c6c;
}

.bar-fill.bar-warm {
  background: #e6a23c;
}

.bar-fill.bar-cold {
  background: #409eff;
}

.bar-value {
  width: 60px;
  font-size: 13px;
  color: #303133;
  text-align: right;
  flex-shrink: 0;
}

/* Sections */
.section-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.title {
  font-size: 16px;
  font-weight: 600;
}

.archive-form {
  margin-bottom: 0;
}

/* Lookup result */
.tier-lookup-result {
  margin-top: 12px;
}

/* Cleanup */
.cleanup-section {
  border-left: 4px solid #f56c6c;
}

.cleanup-controls {
  display: flex;
  align-items: center;
}

.cleanup-label {
  margin-right: 16px;
  color: #606266;
  font-size: 14px;
}
</style>
