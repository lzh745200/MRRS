<template>
  <div class="data-overview-page">
    <div class="page-header">
      <h2 class="page-title">数据总览</h2>
      <p class="page-desc">全面查看系统数据概况与健康状态</p>
    </div>

    <!-- 顶部汇总统计 -->
    <div class="stats-row">
      <div class="stat-card primary" @click="navigateTo('/villages')">
        <div class="stat-icon">
          <el-icon><Location /></el-icon>
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ overview.villages }}</div>
          <div class="stat-label">帮扶村</div>
        </div>
      </div>
      <div class="stat-card success" @click="navigateTo('/projects')">
        <div class="stat-icon">
          <el-icon><Folder /></el-icon>
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ overview.projects }}</div>
          <div class="stat-label">帮扶项目</div>
        </div>
      </div>
      <div class="stat-card warning" @click="navigateTo('/schools')">
        <div class="stat-icon">
          <el-icon><School /></el-icon>
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ overview.schools }}</div>
          <div class="stat-label">帮扶学校</div>
        </div>
      </div>
      <div class="stat-card info" @click="navigateTo('/funds')">
        <div class="stat-icon">
          <el-icon><Money /></el-icon>
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ fundsLabel }}</div>
          <div class="stat-label">经费总投入</div>
        </div>
      </div>
      <div class="stat-card" @click="navigateTo('/data-management/quality')">
        <div class="stat-icon">
          <el-icon><CircleCheck /></el-icon>
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ overview.completeness.toFixed(1) }}%</div>
          <div class="stat-label">数据完整率</div>
        </div>
      </div>
      <div class="stat-card highlight">
        <div class="stat-icon">
          <el-icon><TrendCharts /></el-icon>
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ overview.users }}</div>
          <div class="stat-label">系统用户</div>
        </div>
      </div>
    </div>

    <!-- 中部核心内容 -->
    <el-row :gutter="20">
      <!-- 左栏：数据模块详细状态 -->
      <el-col :span="14">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>数据模块状态</span>
              <el-button link @click="loadOverview"
                ><el-icon><Refresh /></el-icon
              ></el-button>
            </div>
          </template>
          <el-table
            v-loading="loading"
            :data="overview.modules"
            stripe
            @row-click="handleModuleClick"
          >
            <el-table-column prop="module" label="模块" min-width="120">
              <template #default="{ row }">
                <div style="display: flex; align-items: center; gap: 8px">
                  <el-icon :color="getModuleIconColor(row)"
                    ><component :is="getModuleIcon(row.module)"
                  /></el-icon>
                  <span>{{ row.module }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="records" label="记录数" width="100" align="right">
              <template #default="{ row }">
                <span style="font-weight: 600">{{ row.records || 0 }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="lastUpdate" label="最后更新" width="160">
              <template #default="{ row }">{{ formatTime(row.lastUpdate) }}</template>
            </el-table-column>
            <el-table-column label="趋势" width="100">
              <template #default="{ row }">
                <el-tag :type="getTrendType(row.trend)" size="small">
                  {{ row.trend > 0 ? `+${row.trend}` : row.trend || '0' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="row.healthy ? 'success' : 'warning'" size="small">
                  {{ row.healthy ? '正常' : '待检查' }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <!-- 右栏：数据完整率与填报进度 -->
      <el-col :span="10">
        <el-card>
          <template #header><span>数据质量概览</span></template>
          <!-- 完整率雷达图区域 -->
          <div class="completeness-section">
            <div class="completeness-score">
              <el-progress
                type="dashboard"
                :percentage="overview.completeness"
                :width="140"
                :stroke-width="12"
                :color="getCompletenessColor(overview.completeness)"
              >
                <template #default="{ percentage }">
                  <div class="percentage-content">
                    <div class="percentage-value">{{ percentage.toFixed(1) }}%</div>
                    <div class="percentage-label">数据完整率</div>
                  </div>
                </template>
              </el-progress>
            </div>
          </div>

          <!-- 各模块填报率进度条 -->
          <div class="filing-progress">
            <div class="progress-title">各模块填报进度</div>
            <div v-for="item in overview.filing_rates" :key="item.module" class="progress-item">
              <div class="progress-label">{{ item.module }}</div>
              <el-progress :percentage="item.rate" :stroke-width="10" :show-text="true">
                <template #default="{ percentage }">
                  <span style="font-size: 12px; margin-left: 4px">{{ percentage }}%</span>
                </template>
              </el-progress>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 底部：最近操作日志 + 快捷操作入口 -->
    <el-row :gutter="20">
      <el-col :span="18">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>最近操作日志</span>
              <el-button link type="primary" @click="navigateTo('/data-management/logs')"
                >查看更多</el-button
              >
            </div>
          </template>
          <div v-if="overview.recent_logs.length === 0" class="empty-placeholder">
            <el-empty description="暂无操作记录" :image-size="80" />
          </div>
          <div v-else class="logs-list">
            <div v-for="log in overview.recent_logs" :key="log.id" class="log-item">
              <div class="log-icon">
                <el-icon :color="getActionColor(log.action_type)"
                  ><component :is="getActionIcon(log.action_type)"
                /></el-icon>
              </div>
              <div class="log-content">
                <div class="log-text">{{ log.action }}</div>
                <div class="log-meta">
                  <span class="log-user">{{ log.user }}</span>
                  <span class="log-separator">·</span>
                  <span class="log-time">{{ formatTime(log.time) }}</span>
                  <el-tag
                    v-if="log.status"
                    :type="log.status === 'success' ? 'success' : 'danger'"
                    size="small"
                    style="margin-left: 8px"
                  >
                    {{ log.status === 'success' ? '成功' : '失败' }}
                  </el-tag>
                </div>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card>
          <template #header><span>快捷操作</span></template>
          <div class="quick-actions">
            <el-button
              type="primary"
              class="quick-action-btn"
              @click="navigateTo('/data-entry/comprehensive')"
            >
              <el-icon><Edit /></el-icon>
              数据录入
            </el-button>
            <el-button
              type="success"
              class="quick-action-btn"
              @click="navigateTo('/data-import/batch')"
            >
              <el-icon><Upload /></el-icon>
              批量导入
            </el-button>
            <el-button
              type="warning"
              class="quick-action-btn"
              @click="navigateTo('/system/backup')"
            >
              <el-icon><FolderAdd /></el-icon>
              数据备份
            </el-button>
            <el-button
              class="quick-action-btn last"
              @click="navigateTo('/data-management/quality')"
            >
              <el-icon><Monitor /></el-icon>
              质量监控
            </el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouterSafe } from '@/composables/useRouterSafe'
import {
  Location,
  Folder,
  School,
  Money,
  CircleCheck,
  TrendCharts,
  Refresh,
  Edit,
  Upload,
  FolderAdd,
  Monitor,
  Document,
  User,
  DataBoard,
  Check,
} from '@element-plus/icons-vue'
import { get } from '@/api/request'

const { pushSafe } = useRouterSafe()

const loading = ref(false)

const overview = reactive({
  villages: 0,
  projects: 0,
  schools: 0,
  funds_amount: 0,
  users: 0,
  completeness: 0,
  modules: [] as any[],
  filing_rates: [] as any[],
  recent_logs: [] as any[],
})

const fundsLabel = computed(() => {
  const amount = overview.funds_amount
  return amount >= 10000 ? `${(amount / 10000).toFixed(0)}万` : `${amount}`
})

function formatTime(val: string | null) {
  if (!val || val === 'None') return '-'
  try {
    const d = new Date(val)
    if (isNaN(d.getTime())) return val
    return d.toLocaleString('zh-CN')
  } catch {
    return val
  }
}

function getCompletenessColor(percentage: number) {
  // el-progress :color 走内联样式，可直接使用 CSS 变量
  if (percentage >= 90) return 'var(--color-success)'
  if (percentage >= 70) return 'var(--color-warning)'
  return 'var(--color-danger)'
}

function getModuleIcon(module: string) {
  const iconMap: Record<string, any> = {
    帮扶村: Location,
    帮扶项目: Folder,
    帮扶学校: School,
    经费管理: Money,
    用户管理: User,
    数据分析: DataBoard,
  }
  return iconMap[module] || Document
}

function getModuleIconColor(row: any) {
  // el-icon :color 走内联样式，可直接使用 CSS 变量
  if (!row.healthy) return 'var(--color-warning)'
  return 'var(--color-success)'
}

function getTrendType(trend: number) {
  if (trend > 0) return 'success'
  if (trend < 0) return 'danger'
  return 'info'
}

function getActionIcon(actionType: string) {
  const iconMap: Record<string, any> = {
    create: Edit,
    update: Edit,
    delete: Document,
    import: Upload,
    export: FolderAdd,
    backup: FolderAdd,
  }
  return iconMap[actionType] || Check
}

function getActionColor(actionType: string) {
  // el-icon color 走内联样式，可直接使用 CSS 变量（tokens.scss 语义色）
  const colorMap: Record<string, string> = {
    create: 'var(--color-success)',
    update: 'var(--color-primary)',
    delete: 'var(--color-danger)',
    import: 'var(--color-warning)',
    export: 'var(--color-info)',
    backup: 'var(--color-success)',
  }
  return colorMap[actionType] || 'var(--color-info)'
}

function navigateTo(path: string) {
  pushSafe(path)
}

function handleModuleClick(row: any) {
  const routeMap: Record<string, string> = {
    帮扶村: '/villages',
    帮扶项目: '/projects',
    帮扶学校: '/schools',
    经费管理: '/funds',
    用户管理: '/system/users-orgs',
  }
  const route = routeMap[row.module]
  if (route) navigateTo(route)
}

async function loadOverview() {
  loading.value = true
  try {
    const res: any = await get('/statistics/overview')
    // 后端裸返回统计对象（拦截器已解包）
    const d = res?.data ?? res
    Object.assign(overview, {
      villages: d.villages ?? 0,
      projects: d.projects ?? 0,
      schools: d.schools ?? 0,
      funds_amount: d.funds_amount ?? 0,
      users: d.users ?? 0,
      completeness: d.completeness ?? 0,
      modules: d.modules ?? [],
      filing_rates: d.filing_rates ?? [
        { module: '帮扶村', rate: d.village_filing_rate ?? 0 },
        { module: '帮扶项目', rate: d.project_filing_rate ?? 0 },
        { module: '帮扶学校', rate: d.school_filing_rate ?? 0 },
        { module: '经费管理', rate: d.funds_filing_rate ?? 0 },
      ],
      recent_logs: d.recent_logs ?? [],
    })
  } catch {
    // keep defaults
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadOverview()
})
</script>

<style scoped>
.data-overview-page {
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

/* 顶部统计卡片 */
.stats-row {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 16px;
}
.stat-card {
  background: white;
  padding: 20px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  gap: 16px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  cursor: pointer;
  transition: all 0.3s;
  border: 2px solid transparent;
}
.stat-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
}
.stat-card.highlight {
  background: linear-gradient(135deg, #1b4332 0%, #2d6a4f 100%);
  color: white;
}
.stat-card.primary .stat-icon {
  color: var(--color-primary);
  background: var(--color-primary-light-8);
}
.stat-card.success .stat-icon {
  color: var(--color-success);
  background: var(--color-primary-light-8);
}
.stat-card.warning .stat-icon {
  color: var(--color-warning);
  background: var(--color-warning-lightest);
}
.stat-card.info .stat-icon {
  color: #909399;
  background: #f4f4f5;
}
.stat-icon {
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  font-size: 24px;
}
.stat-content {
  flex: 1;
}
.stat-value {
  font-size: 26px;
  font-weight: 700;
  color: #1b4332;
  margin-bottom: 4px;
}
.stat-card.highlight .stat-value {
  color: #d4af37;
}
.stat-label {
  font-size: 13px;
  color: #666;
}
.stat-card.highlight .stat-label {
  color: #a8dadc;
}

/* 卡片头部 */
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

/* 完整率区域 */
.completeness-section {
  display: flex;
  justify-content: center;
  padding: 20px 0;
  margin-bottom: 24px;
  border-bottom: 1px solid #f0f0f0;
}
.percentage-content {
  text-align: center;
}
.percentage-value {
  font-size: 28px;
  font-weight: 700;
  color: #1b4332;
}
.percentage-label {
  font-size: 12px;
  color: #999;
  margin-top: 4px;
}

/* 填报进度 */
.filing-progress {
  padding: 0 12px;
}
.progress-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin-bottom: 16px;
}
.progress-item {
  margin-bottom: 16px;
}
.progress-item:last-child {
  margin-bottom: 0;
}
.progress-label {
  font-size: 13px;
  color: #666;
  margin-bottom: 6px;
  display: flex;
  justify-content: space-between;
}

/* 日志列表 */
.empty-placeholder {
  padding: 40px 0;
}
.logs-list {
  max-height: 400px;
  overflow-y: auto;
}
.log-item {
  padding: 12px 0;
  border-bottom: 1px solid #f0f0f0;
  display: flex;
  align-items: flex-start;
  gap: 12px;
}
.log-item:last-child {
  border-bottom: none;
}
.log-icon {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: #f5f7fa;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.log-content {
  flex: 1;
}
.log-text {
  font-size: 14px;
  color: #333;
  margin-bottom: 4px;
}
.log-meta {
  font-size: 12px;
  color: #999;
  display: flex;
  align-items: center;
  gap: 4px;
}
.log-user {
  color: var(--color-primary);
}
.log-separator {
  color: #ddd;
}

/* 快捷操作 */
.quick-actions {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 8px 0;
}
.quick-action-btn {
  width: 100%;
  margin-left: 0 !important;
}

/* 响应式适配 */
@media (max-width: 1200px) {
  .stats-row {
    grid-template-columns: repeat(3, 1fr);
  }
}
@media (max-width: 768px) {
  .stats-row {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
