<template>
  <div class="data-management">
    <PageHeader title="数据概览" subtitle="数据资产、流转记录与质量状况总览">
      <template #extra>
        <el-button
          data-test="refresh-overview"
          :icon="Refresh"
          :loading="loading"
          @click="loadStats"
        >
          刷新
        </el-button>
      </template>
    </PageHeader>

    <!-- 核心指标：管理员多一张「本月导出」（导出审计仅管理员可读） -->
    <el-row :gutter="20" class="kpi-row">
      <el-col :span="kpiSpan">
        <el-card class="kpi-card">
          <el-statistic title="帮扶村总数" :value="stats.villageCount" />
        </el-card>
      </el-col>
      <el-col :span="kpiSpan">
        <el-card class="kpi-card">
          <el-statistic title="本月导入" :value="stats.monthlyImports" suffix="次" />
        </el-card>
      </el-col>
      <el-col v-if="isAdmin" :span="kpiSpan">
        <el-card class="kpi-card">
          <el-statistic title="本月导出" :value="stats.monthlyExports" suffix="次" />
        </el-card>
      </el-col>
      <el-col :span="kpiSpan">
        <el-card class="kpi-card">
          <el-statistic title="备份数量" :value="stats.backupCount" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 最近流转记录：直接展示真实记录，不再用「前往…」空壳入口 -->
    <div class="flow-grid">
      <section class="app-card flow-card">
        <div class="section-head">
          <h3 class="section-title">最近导入</h3>
          <span class="section-hint">本人最近 5 条</span>
        </div>
        <table v-if="recentImports.length" class="flow-table">
          <thead>
            <tr>
              <th scope="col">文件</th>
              <th scope="col">数据类型</th>
              <th scope="col">记录数</th>
              <th scope="col">结果</th>
              <th scope="col">时间</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in recentImports" :key="row.id">
              <td class="file-cell" :title="row.file_name">{{ row.file_name || '—' }}</td>
              <td>{{ entityText(row.entity_type) }}</td>
              <td>{{ row.success_rows ?? 0 }}/{{ row.total_rows ?? 0 }}</td>
              <td>
                <el-tag :type="statusTag(row.status)" size="small">{{
                  statusText(row.status)
                }}</el-tag>
              </td>
              <td class="time-cell">{{ formatDateTimeLocale(rowTime(row), '—') }}</td>
            </tr>
          </tbody>
        </table>
        <el-empty v-else description="暂无导入记录" :image-size="60" />
      </section>

      <section v-if="isAdmin" class="app-card flow-card">
        <div class="section-head">
          <h3 class="section-title">最近导出</h3>
          <span class="section-hint">最近 5 条</span>
        </div>
        <table v-if="recentExports.length" class="flow-table">
          <thead>
            <tr>
              <th scope="col">导出类型</th>
              <th scope="col">记录数</th>
              <th scope="col">格式</th>
              <th scope="col">结果</th>
              <th scope="col">时间</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in recentExports" :key="row.id">
              <td>{{ exportTypeText(row.export_type) }}</td>
              <td>{{ row.record_count ?? 0 }}</td>
              <td>{{ row.file_format || '—' }}</td>
              <td>
                <el-tag :type="statusTag(row.status)" size="small">{{
                  statusText(row.status)
                }}</el-tag>
              </td>
              <td class="time-cell">{{ formatDateTimeLocale(rowTime(row), '—') }}</td>
            </tr>
          </tbody>
        </table>
        <el-empty v-else description="暂无导出记录" :image-size="60" />
      </section>
    </div>

    <!-- 数据质量：原「数据质量」页签内容改为常驻区块 -->
    <QualitySection :stats="qualityStats" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, defineAsyncComponent } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { get, apiRequest } from '@/api/request'
import { unwrapList } from '@/utils/unwrapList'
import { getErrorMessage } from '@/utils/getErrorMessage'
import { formatDateTimeLocale } from '@/utils/datetime'
import { isAdminUser } from '@/utils/roleAccess'
import { logger } from '@/utils/logger'
import PageHeader from '@/components/common/PageHeader.vue'

// 异步加载子组件：保持原有分包策略（该组件有独立测试文件覆盖）
const QualitySection = defineAsyncComponent(() => import('./components/QualitySection.vue'))

interface ImportRow {
  id: number
  file_name?: string
  entity_type?: string
  status?: string
  success_rows?: number | null
  total_rows?: number | null
  created_at?: string
  createdAt?: string
}

interface ExportRow {
  id: number
  export_type?: string
  record_count?: number | null
  file_format?: string | null
  status?: string
  created_at?: string
  createdAt?: string
}

interface QualityStats {
  totalRecords: number
  validRecords: number
  invalidRecords: number
  completenessRate: number
  lastCheckTime: string
}

const loading = ref(false)
// 导出审计端点（/system/audit/exports）仅管理员可读；非管理员不请求、不展示导出卡片，
// 避免每轮刷新都打一次 403，也避免用恒 0 的假数字误导用户。
const isAdmin = computed(() => isAdminUser())
const kpiSpan = computed(() => (isAdmin.value ? 6 : 8))

const stats = ref({
  villageCount: 0,
  monthlyImports: 0,
  monthlyExports: 0,
  backupCount: 0,
})

const qualityStats = ref<QualityStats>({
  totalRecords: 0,
  validRecords: 0,
  invalidRecords: 0,
  completenessRate: 0,
  lastCheckTime: '',
})

const recentImports = ref<ImportRow[]>([])
const recentExports = ref<ExportRow[]>([])

/** 当前月份前缀（YYYY-MM），用于统计「本月」 */
function monthPrefix(): string {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}

/** 兼容后端 snake_case 与历史 camelCase 两种时间字段 */
function rowTime(row: { created_at?: string; createdAt?: string }): string {
  return String(row.created_at || row.createdAt || '')
}

const ENTITY_TEXT: Record<string, string> = {
  village: '帮扶村',
  supported_village: '帮扶村',
  fund: '经费',
  project: '项目',
  school: '学校',
  rural_work: '乡村工作',
  user: '用户',
}

function entityText(type?: string): string {
  return ENTITY_TEXT[type ?? ''] ?? (type || '—')
}

const EXPORT_TYPE_TEXT: Record<string, string> = {
  village: '帮扶村',
  fund: '经费',
  project: '项目',
  school: '学校',
  user: '用户',
  comprehensive: '综合报表',
}

function exportTypeText(type?: string): string {
  return EXPORT_TYPE_TEXT[type ?? ''] ?? (type || '综合')
}

const STATUS_TEXT: Record<string, string> = {
  success: '成功',
  completed: '成功',
  failed: '失败',
  partial: '部分成功',
  pending: '待处理',
  running: '进行中',
  processing: '处理中',
}

function statusText(status?: string): string {
  return STATUS_TEXT[status ?? ''] ?? (status || '未知')
}

function statusTag(status?: string): 'success' | 'warning' | 'danger' | 'info' {
  if (status === 'success' || status === 'completed') return 'success'
  if (status === 'failed') return 'danger'
  if (
    status === 'partial' ||
    status === 'pending' ||
    status === 'running' ||
    status === 'processing'
  )
    return 'warning'
  return 'info'
}

async function loadStats() {
  loading.value = true
  const prefix = monthPrefix()
  try {
    // 1) 帮扶村总数（数据域由后端按当前用户收敛）
    const dash: any = await get('/dashboard/stats')
    const data = dash?.data ?? dash ?? {}
    stats.value.villageCount = Number(data.total_villages ?? data.villageCount ?? 0) || 0

    // 2) 导入历史（当前用户维度）：本月次数 + 最近 5 条
    try {
      const hist: any = await get('/import/history', { page: 1, page_size: 100 })
      const items = unwrapList<ImportRow>(hist).items
      recentImports.value = items.slice(0, 5)
      stats.value.monthlyImports = items.filter((row) => rowTime(row).startsWith(prefix)).length
    } catch {
      recentImports.value = []
      stats.value.monthlyImports = 0
    }

    // 3) 导出审计（仅管理员）：本月次数 + 最近 5 条
    if (isAdmin.value) {
      try {
        const exp: any = await get('/system/audit/exports', { page: 1, page_size: 100 })
        const items = unwrapList<ExportRow>(exp).items
        recentExports.value = items.slice(0, 5)
        stats.value.monthlyExports = items.filter((row) => rowTime(row).startsWith(prefix)).length
      } catch {
        recentExports.value = []
        stats.value.monthlyExports = 0
      }
    }

    // 4) 备份数量
    try {
      const bk: any = await get('/system/backup', { page: 1, page_size: 1000 })
      stats.value.backupCount = unwrapList(bk).total
    } catch {
      stats.value.backupCount = 0
    }

    // 5) 帮扶村抽样用于质量统计（后端 page_size 上限 200）
    const villageRes: any = await apiRequest({
      method: 'GET',
      url: '/supported-villages',
      params: { page: 1, page_size: 200 },
    })
    const villages = unwrapList<any>(villageRes).items
    const totalRecords = villages.length
    const validRecords = villages.filter((v) => v.department && v.village_name && v.county).length
    qualityStats.value = {
      totalRecords,
      validRecords,
      invalidRecords: totalRecords - validRecords,
      completenessRate:
        totalRecords > 0 ? Math.round((validRecords / totalRecords) * 10000) / 100 : 0,
      lastCheckTime: new Date().toLocaleString('zh-CN'),
    }
  } catch (error) {
    logger.error('加载数据概览失败:', error)
    ElMessage.error(getErrorMessage(error, '加载数据概览失败，请稍后重试'))
  } finally {
    loading.value = false
  }
}

onMounted(loadStats)
</script>

<style scoped lang="scss">
.data-management {
  padding: var(--spacing-lg, 20px);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg, 20px);
  max-width: 1440px;
  margin: 0 auto;
}

.app-card {
  background: var(--color-bg-card);
  border: 1px solid var(--color-card-border, var(--color-border-light));
  border-radius: var(--radius-card, 8px);
  padding: var(--spacing-lg, 20px);
  box-shadow: var(--shadow-card);
}

.kpi-row {
  margin-bottom: 0;
}

.kpi-card {
  text-align: center;
}

.flow-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 420px), 1fr));
  gap: var(--spacing-lg, 20px);
  align-items: start;
}

.flow-card {
  min-width: 0;
}

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-sm, 12px);
  margin-bottom: var(--spacing-md, 16px);
}

.section-title {
  margin: 0;
  font-size: var(--text-lg, 16px);
  font-weight: 600;
  color: var(--color-text-primary);
  display: flex;
  align-items: center;
  gap: 8px;

  &::before {
    content: '';
    display: inline-block;
    width: 4px;
    height: 16px;
    border-radius: 2px;
    background: var(--color-primary);
  }
}

.section-hint {
  font-size: var(--text-xs, 12px);
  color: var(--color-text-secondary);
}

.flow-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;

  th,
  td {
    padding: 10px 8px;
    text-align: left;
    font-size: var(--text-sm, 13px);
    border-bottom: 1px solid var(--color-border-lighter);
  }

  th {
    font-weight: 600;
    color: var(--color-text-secondary);
    white-space: nowrap;
  }

  td {
    color: var(--color-text-primary);
  }

  tbody tr:last-child td {
    border-bottom: none;
  }
}

.file-cell {
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.time-cell {
  white-space: nowrap;
  color: var(--color-text-secondary);
}
</style>
