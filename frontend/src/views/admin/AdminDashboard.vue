<template>
  <!-- 单根包裹：避免 transition 内多根导致 setAttribute('0') 崩溃 -->
  <div style="display: contents">
    <template v-if="isAdmin">
      <div class="admin-dashboard">
        <!-- 管理员欢迎横幅 -->
        <div class="admin-banner">
          <div class="banner-content">
            <h2 class="welcome-title">管理控制台</h2>
            <p class="welcome-subtitle">{{ currentDate }}</p>
          </div>
          <div class="admin-actions">
            <button class="action-btn gold" @click="pushSafe('/system/users')">
              <el-icon><UserFilled /></el-icon> 用户管理
            </button>
            <button class="action-btn gold" @click="pushSafe('/system/backup')">
              <el-icon><Files /></el-icon> 数据备份
            </button>
            <button class="action-btn gold" @click="pushSafe('/system/audit')">
              <el-icon><Document /></el-icon> 操作审计
            </button>
            <button class="action-btn gold" @click="pushSafe('/system/config')">
              <el-icon><Setting /></el-icon> 系统配置
            </button>
          </div>
        </div>

        <!-- 系统概览统计 -->
        <div class="admin-stats-grid">
          <div v-for="stat in adminStats" :key="stat.label" class="admin-stat-card">
            <div class="stat-header">
              <span class="stat-icon"
                ><el-icon><component :is="stat.icon" /></el-icon
              ></span>
              <span class="stat-label">{{ stat.label }}</span>
            </div>
            <div class="stat-value">{{ stat.value }}</div>
            <div class="stat-trend" :class="stat.trendClass">
              {{ stat.trend }}
            </div>
          </div>
        </div>

        <!-- 双列布局 -->
        <div class="admin-main-grid">
          <!-- 左列 -->
          <div class="admin-left-col">
            <!-- 系统状态 -->
            <div class="admin-card">
              <div class="card-header">
                <h3>
                  <el-icon><Monitor /></el-icon> 系统状态
                </h3>
              </div>
              <div class="system-status">
                <div v-if="!panelsLoaded" class="empty-tip">加载中...</div>
                <div v-else-if="panelError.status" class="empty-tip error-tip">
                  {{ panelError.status }}
                </div>
                <div v-else-if="systemStatus.length === 0" class="empty-tip">暂无状态数据</div>
                <div v-for="status in systemStatus" :key="status.name" class="status-item">
                  <span class="status-name">{{ status.name }}</span>
                  <span class="status-value" :class="status.status">
                    <span class="status-dot"></span>
                    {{ status.statusText }}
                  </span>
                </div>
              </div>
            </div>

            <!-- 最近登录用户 -->
            <div class="admin-card">
              <div class="card-header">
                <h3>
                  <el-icon><Lock /></el-icon> 最近登录
                </h3>
              </div>
              <div class="login-list">
                <div v-if="!panelsLoaded" class="empty-tip">加载中...</div>
                <div v-else-if="panelError.logins" class="empty-tip error-tip">
                  {{ panelError.logins }}
                </div>
                <div v-else-if="recentLogins.length === 0" class="empty-tip">暂无登录记录</div>
                <div v-for="login in recentLogins" :key="login.id" class="login-item">
                  <div class="login-avatar">
                    {{ login.avatar }}
                  </div>
                  <div class="login-info">
                    <span class="login-name">{{ login.name }}</span>
                    <span class="login-time">{{ login.time }}</span>
                  </div>
                  <span class="login-ip">{{ login.ip }}</span>
                </div>
              </div>
            </div>

            <!-- 审计日志 -->
            <div class="admin-card">
              <div class="card-header">
                <h3>
                  <el-icon><EditPen /></el-icon> 审计日志
                </h3>
                <button class="text-btn" @click="pushSafe('/system/audit')">查看全部</button>
              </div>
              <div class="audit-list">
                <div v-if="!panelsLoaded" class="empty-tip">加载中...</div>
                <div v-else-if="panelError.audit" class="empty-tip error-tip">
                  {{ panelError.audit }}
                </div>
                <div v-else-if="auditLogs.length === 0" class="empty-tip">暂无审计记录</div>
                <div v-for="log in auditLogs" :key="log.id" class="audit-item">
                  <span class="audit-action" :class="log.type">{{ log.action }}</span>
                  <span class="audit-user">{{ log.user }}</span>
                  <span class="audit-target">{{ log.target }}</span>
                  <span class="audit-time">{{ log.time }}</span>
                </div>
              </div>
            </div>
          </div>

          <!-- 右列 -->
          <div class="admin-right-col">
            <!-- 快捷操作 -->
            <div class="admin-card">
              <div class="card-header">
                <h3>
                  <el-icon><Cpu /></el-icon> 快捷操作
                </h3>
              </div>
              <div class="quick-actions-grid">
                <div
                  v-for="action in quickActions"
                  :key="action.path"
                  class="quick-action"
                  @click="pushSafe(action.path)"
                >
                  <span class="action-icon"
                    ><el-icon><component :is="action.icon" /></el-icon
                  ></span>
                  <span class="action-label">{{ action.label }}</span>
                </div>
              </div>
            </div>

            <!-- 待处理事项 -->
            <div class="admin-card">
              <div class="card-header">
                <h3>
                  <el-icon><Bell /></el-icon> 待处理事项
                </h3>
                <span class="pending-count">{{ pendingItems.length }}</span>
              </div>
              <div class="pending-list">
                <div v-if="!panelsLoaded" class="empty-tip">加载中...</div>
                <div v-else-if="panelError.pending" class="empty-tip error-tip">
                  {{ panelError.pending }}
                </div>
                <div v-else-if="pendingItems.length === 0" class="empty-tip">暂无待处理事项</div>
                <div
                  v-for="item in pendingItems"
                  :key="item.id"
                  class="pending-item"
                  :class="item.priority"
                >
                  <span class="pending-type">{{ item.type }}</span>
                  <span class="pending-desc">{{ item.description }}</span>
                  <span class="pending-time">{{ item.time }}</span>
                </div>
              </div>
            </div>

            <!-- 存储使用 -->
            <div class="admin-card">
              <div class="card-header">
                <h3>
                  <el-icon><Files /></el-icon> 存储使用
                </h3>
              </div>
              <div class="storage-info">
                <div v-if="storageError" class="empty-tip error-tip">
                  {{ panelError.storage || '存储信息加载失败' }}
                </div>
                <div v-else class="storage-bar">
                  <div class="storage-used" :style="{ width: storagePercent + '%' }"></div>
                </div>
                <div v-if="!storageError" class="storage-text">
                  已使用 {{ formatSize(storageUsed) }} /
                  {{ formatSize(storageTotal) }}
                </div>
              </div>
              <div v-if="!storageError" class="storage-breakdown">
                <div class="breakdown-item">
                  <span class="breakdown-label">数据库</span>
                  <span class="breakdown-value">{{ formatSize(dbSize) }}</span>
                </div>
                <div class="breakdown-item">
                  <span class="breakdown-label">备份文件</span>
                  <span class="breakdown-value">{{ formatSize(backupSize) }}</span>
                </div>
                <div class="breakdown-item">
                  <span class="breakdown-label">日志文件</span>
                  <span class="breakdown-value">{{ formatSize(logSize) }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
    <EmptyState v-else type="no-permission" text="无权限访问此页面" />
  </div>
</template>

<script setup lang="ts">
import EmptyState from '@/components/business/EmptyState/EmptyState.vue'
import { unwrapList } from '@/utils/unwrapList'
import { logger } from '@/utils/logger'

import { ref, computed, onMounted } from 'vue'
import { useRouterSafe } from '@/composables/useRouterSafe'
import { useUserStore } from '@/stores/user'
import { isAdminUser } from '@/utils/roleAccess'
import { get } from '@/api/request'
import { getErrorMessage } from '@/utils/getErrorMessage'
import {
  UserFilled,
  Files,
  Document,
  Setting,
  Monitor,
  Lock,
  EditPen,
  Cpu,
  Bell,
  CircleCheck,
  DataAnalysis,
  Key,
} from '@element-plus/icons-vue'

const { pushSafe } = useRouterSafe()
const userStore = useUserStore()
// M47：管理员判定统一走 roleAccess.isAdminUser()（normalizeRole + is_superuser），
// 与路由守卫 / v-permission 指令同口径。
const isAdmin = computed(() => isAdminUser(userStore.currentUser))

const currentDate = new Date().toLocaleDateString('zh-CN', {
  year: 'numeric',
  month: 'long',
  day: 'numeric',
  weekday: 'long',
})

const adminStats = ref([
  { label: '用户总数', value: 0, icon: UserFilled, trend: '', trendClass: 'stable' },
  // 「今日活跃」取审计统计的 active_users（真实指标）；接口失败时回落 '--' 而非 0，
  // 避免把"取不到"伪装成"今天没人活跃"。
  { label: '今日活跃', value: '--', icon: CircleCheck, trend: '', trendClass: 'stable' },
  { label: '数据记录', value: 0, icon: DataAnalysis, trend: '', trendClass: 'stable' },
  {
    label: '系统运行',
    value: '--',
    icon: Cpu,
    trend: '',
    trendClass: 'stable',
  },
])

const systemStatus = ref<any[]>([])

const recentLogins = ref<any[]>([])

const auditLogs = ref<any[]>([])

const quickActions = [
  { icon: UserFilled, label: '用户管理', path: '/system/users' },
  { icon: Key, label: '角色权限', path: '/system/roles' },
  { icon: Files, label: '数据备份', path: '/system/backup' },
  { icon: Document, label: '操作审计', path: '/system/audit' },
  { icon: Setting, label: '系统配置', path: '/system/config' },
  { icon: DataAnalysis, label: '数据总览', path: '/data-management' },
]

const pendingItems = ref<any[]>([])

const storageUsed = ref(0)
const storageTotal = ref(1)
const dbSize = ref(0)
const backupSize = ref(0)
const logSize = ref(0)
const storageError = ref(false)
/** 五个数据面板是否已加载完成（用于区分"加载中"与"确实为空"） */
const panelsLoaded = ref(false)
/** 各面板的加载失败原因：失败时把"暂无数据"换成真实原因，不静默伪装成空 */
const panelError = ref<Record<string, string>>({})

const storagePercent = computed(() => Math.round((storageUsed.value / storageTotal.value) * 100))

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  return `${(bytes / 1024 / 1024 / 1024).toFixed(1)} GB`
}

/** 把任意错误对象转成一行可读文本（用于面板内联错误提示，不弹全局消息） */
function errText(e: unknown, fallback: string): string {
  return getErrorMessage(e, fallback)
}

/** 从响应中取数组（兼容裸数组 / {items} / envelope 展开后的两种形态） */
function pickItems(res: any): any[] {
  return unwrapList(res).items
}

/** 从响应中取 payload（envelope 展开后字段已在顶层；未展开时回落到 data） */
function pickData(res: any): any {
  const inner = res?.data
  return inner && typeof inner === 'object' ? inner : (res ?? {})
}

/** 秒级时间戳/ISO 串 → 本地 'YYYY-MM-DD HH:mm'；解析失败返回 '--' */
function fmtTime(value?: string | null): string {
  if (!value) return '--'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '--'
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

/** 概览统计（用户数 / 数据记录 / 系统运行） */
async function loadOverviewStats() {
  try {
    const res: any = await get('/dashboard/stats')
    // /dashboard/stats 返回（backend/app/api/v1/data/data/dashboard.py）：
    //   total_users / total_villages / total_projects / total_schools / total_population /
    //   total_funds(万元) / data_completeness / pending_approvals / trends；无数据时返回 null。
    const data = res?.data ?? res ?? {}

    adminStats.value[0].value = Number(data.total_users) || 0
    // 「数据记录」只累加**记录条数**（村/项目/学校）。此前把 total_funds 也加进来，
    // 而 total_funds = SUM(Fund.amount)，单位是万元，与条数混加属量纲错误。
    adminStats.value[2].value =
      Number(data.total_villages || 0) +
      Number(data.total_projects || 0) +
      Number(data.total_schools || 0)
    if (data.total_villages !== undefined) {
      adminStats.value[3].value = `${data.total_villages} 村 / ${data.total_projects ?? 0} 项目`
    }
  } catch (e) {
    logger.error('加载概览统计失败:', e)
  }
}

/** 「今日活跃」← 审计统计 active_users（真实指标） */
async function loadActiveUsers() {
  try {
    const res: any = await get('/system/audit/stats')
    const data = pickData(res)
    const active = Number(data.active_users)
    adminStats.value[1].value = Number.isFinite(active) ? active : '--'
  } catch (e) {
    // 取不到时保持 '--'：不得回落成 0（那会把"接口失败"显示为"今日无人活跃"）
    logger.error('加载活跃用户数失败:', e)
    adminStats.value[1].value = '--'
  }
}

/**
 * 系统状态 ← GET /system/monitor/snapshot
 * 后端快照字段：cpu_usage / memory_usage / disk_usage / status（healthy|limited|error）
 * 原实现读 /dashboard/stats 的 system_status（后端无此键）→ 面板恒为空。
 */
async function loadSystemStatus() {
  try {
    const res: any = await get('/system/monitor/snapshot')
    const snap = pickData(res)
    const rows: Array<{ name: string; status: string; statusText: string }> = []
    const push = (name: string, pct: unknown) => {
      const v = Number(pct)
      if (!Number.isFinite(v)) return
      rows.push({
        name,
        status: v >= 90 ? 'offline' : 'online',
        statusText: `${v.toFixed(1)}%`,
      })
    }
    push('CPU 使用率', snap.cpu_usage)
    push('内存使用率', snap.memory_usage)
    push('磁盘使用率', snap.disk_usage)
    const overall = snap.status
    if (overall) {
      rows.push({
        name: '采集状态',
        status: overall === 'healthy' ? 'online' : 'offline',
        statusText: overall === 'healthy' ? '正常' : overall === 'limited' ? '受限' : '异常',
      })
    }
    systemStatus.value = rows
  } catch (e) {
    logger.error('加载系统状态失败:', e)
    panelError.value.status = errText(e, '系统状态加载失败')
    systemStatus.value = []
  }
}

/**
 * 存储 ← GET /system/monitor/database-size（库文件）+ GET /system/backup/stats（备份）
 * 原实现读 /dashboard/stats 的 storage（后端无此键）→ 面板恒为 0/1。
 */
async function loadStorage() {
  try {
    const [dbRes, backupRes]: any[] = await Promise.all([
      get('/system/monitor/database-size'),
      get('/system/backup/stats'),
    ])
    const dbData = pickData(dbRes)
    const backupData = pickData(backupRes)
    dbSize.value = Number(dbData.size_bytes) || 0
    backupSize.value = Number(backupData.totalSize) || 0
    // 日志体积后端无端点可查 → 保持 0（面板显示 0 B），不虚构数字
    logSize.value = 0
    await applyDiskUsage()
    storageError.value = false
  } catch (e) {
    logger.error('加载存储信息失败:', e)
    panelError.value.storage = errText(e, '存储信息加载失败')
    storageError.value = true
  }
}

/**
 * 容量口径 ← GET /system-health/disk-space（total_gb / used_percent）。
 * 磁盘端点不可用时退化为「已用 = 库文件 + 备份」，并保证 total ≥ used（百分比不越界）。
 */
async function applyDiskUsage() {
  const used = dbSize.value + backupSize.value
  let totalBytes: number | null = null
  let usedPct: number | null = null
  try {
    const diskRes: any = await get('/system-health/disk-space')
    const disk = pickData(diskRes)
    const totalGb = Number(disk.total_gb)
    const pct = Number(disk.used_percent)
    if (Number.isFinite(totalGb) && totalGb > 0) totalBytes = totalGb * 1024 ** 3
    if (Number.isFinite(pct) && pct >= 0) usedPct = pct
  } catch (e) {
    logger.error('加载磁盘容量失败:', e)
  }
  if (totalBytes === null) {
    storageTotal.value = Math.max(used, 1)
    storageUsed.value = used
    return
  }
  storageTotal.value = totalBytes
  storageUsed.value = usedPct === null ? used : (totalBytes * usedPct) / 100
}

/**
 * 最近登录 ← GET /system/audit/login-attempts（仅取成功的登录尝试）
 * 原实现读 /dashboard/stats 的 recent_logins（后端无此键）→ 面板恒为空。
 */
async function loadRecentLogins() {
  try {
    const res: any = await get('/system/audit/login-attempts', { page: 1, page_size: 10 })
    recentLogins.value = pickItems(res)
      .filter((it: any) => it?.success === true)
      .slice(0, 5)
      .map((it: any) => ({
        id: it.id,
        name: it.username || '未知用户',
        // 头像取原始用户名首字母：name 是中文占位符时不能再取它的首字（否则空
        // 用户名会渲染成「未」）；取不到时回落 'U'（Unknown）。
        avatar: (it.username || '').charAt(0).toUpperCase() || 'U',
        time: fmtTime(it.attemptTime ?? it.attempt_time),
        ip: it.ipAddress ?? it.ip_address ?? '--',
      }))
  } catch (e) {
    logger.error('加载最近登录失败:', e)
    panelError.value.logins = errText(e, '登录记录加载失败')
    recentLogins.value = []
  }
}

/**
 * 审计日志 ← GET /system/audit/logs（page_size=5）
 * 原实现读 /dashboard/stats 的 audit_logs（后端无此键）→ 面板恒为空。
 */
async function loadAuditLogs() {
  try {
    const res: any = await get('/system/audit/logs', { page: 1, page_size: 5 })
    auditLogs.value = pickItems(res)
      .slice(0, 5)
      .map((it: any) => ({
        id: it.id,
        // 级别决定标签配色（info/warning/danger），与后端 level 字段对齐
        type: it.level === 'error' || it.level === 'critical' ? 'danger' : (it.level ?? 'info'),
        action: it.action || '--',
        user: it.username || '系统',
        target: it.resourceType ?? it.resource_type ?? '--',
        time: fmtTime(it.createdAt ?? it.created_at),
      }))
  } catch (e) {
    logger.error('加载审计日志失败:', e)
    panelError.value.audit = errText(e, '审计日志加载失败')
    auditLogs.value = []
  }
}

/**
 * 待处理事项 ← GET /approval/tasks/pending
 * 原实现读 /dashboard/stats 的 pending_items（后端无此键）→ 面板恒为空。
 */
async function loadPendingItems() {
  try {
    const res: any = await get('/approval/tasks/pending', { skip: 0, limit: 5 })
    pendingItems.value = pickItems(res)
      .slice(0, 5)
      .map((it: any) => ({
        id: it.id,
        // 后端 priority 为整数（>0 为高优先级），与 PendingList.vue 的判定一致
        priority: Number(it.priority) > 0 ? 'high' : 'low',
        type: it.entityType ?? it.entity_type ?? '审批',
        description: it.title || '--',
        time: fmtTime(it.createdAt ?? it.created_at),
      }))
  } catch (e) {
    logger.error('加载待处理事项失败:', e)
    panelError.value.pending = errText(e, '待处理事项加载失败')
    pendingItems.value = []
  }
}

/**
 * 加载管理面板数据。
 *
 * 修复（M42）：原实现只调 /dashboard/stats，却去读 system_status / recent_logins /
 * audit_logs / pending_items / storage 五个该端点**从不返回**的键，导致 5 个区域恒为空；
 * 且 adminStats[1]「今日活跃」展示的是 total_population（量纲错位）。
 * 现改为各面板接各自真实端点，逐块独立降级（单块失败不影响其他块）。
 */
async function loadAdminData() {
  panelsLoaded.value = false
  panelError.value = {}
  await Promise.all([
    loadOverviewStats(),
    loadActiveUsers(),
    loadSystemStatus(),
    loadStorage(),
    loadRecentLogins(),
    loadAuditLogs(),
    loadPendingItems(),
  ])
  panelsLoaded.value = true
}

onMounted(() => {
  loadAdminData()
})
</script>

<style lang="scss" scoped>
.admin-dashboard {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.admin-banner {
  background: linear-gradient(
    135deg,
    var(--color-primary-dark-1) 0%,
    var(--color-primary) 50%,
    var(--color-primary-light-1) 100%
  );
  border-radius: 12px;
  padding: 24px 32px;
  color: white;
  display: flex;
  justify-content: space-between;
  align-items: center;
  box-shadow: 0 4px 20px rgba(27, 67, 50, 0.3);
}

.welcome-title {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
}

.welcome-subtitle {
  margin: 4px 0 0;
  opacity: 0.8;
  font-size: 13px;
}

.admin-actions {
  display: flex;
  gap: 10px;
}

.action-btn.gold {
  background: linear-gradient(135deg, var(--color-accent-gold), #c9a227);
  color: var(--color-primary-dark-1);
  border: none;
  padding: 10px 20px;
  border-radius: 8px;
  font-weight: 600;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  transition:
    transform 0.2s,
    box-shadow 0.2s;
}

.action-btn.gold:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(212, 175, 55, 0.4);
}

.admin-stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.admin-stat-card {
  background: white;
  border-radius: 10px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.stat-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.stat-icon {
  font-size: 20px;
  display: inline-flex;
  align-items: center;
}

.stat-label {
  color: var(--color-text-secondary);
  font-size: 13px;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--color-primary-dark-1);
}

.stat-trend {
  font-size: 12px;
  margin-top: 4px;
}

.stat-trend.up {
  color: var(--color-success);
}

.stat-trend.down {
  color: var(--color-danger);
}

.stat-trend.stable {
  color: var(--color-text-secondary);
}

.admin-main-grid {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 20px;
}

.admin-left-col,
.admin-right-col {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.admin-card {
  background: white;
  border-radius: 10px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  overflow: hidden;
}

.card-header {
  padding: 16px 20px;
  border-bottom: 1px solid var(--color-border-lighter);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header h3 {
  margin: 0;
  font-size: 15px;
  color: var(--color-text-primary);
  display: flex;
  align-items: center;
  gap: 6px;
}

.text-btn {
  background: none;
  border: none;
  color: var(--color-primary-light-1);
  cursor: pointer;
  font-size: 13px;
}

.system-status {
  padding: 16px 20px;
}

.status-item {
  display: flex;
  justify-content: space-between;
  padding: 10px 0;
  border-bottom: 1px solid var(--color-border-lighter);
}

.status-item:last-child {
  border-bottom: none;
}

.status-name {
  color: var(--color-text-primary);
}

.status-value {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.status-value.online .status-dot {
  background: #10b981;
}

.status-value.offline .status-dot {
  background: var(--color-danger);
}

.login-list {
  padding: 16px 20px;
}

.login-item {
  display: flex;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid var(--color-border-lighter);
}

.login-item:last-child {
  border-bottom: none;
}

.login-avatar {
  width: 36px;
  height: 36px;
  background: linear-gradient(135deg, var(--color-primary-light-1), var(--color-primary));
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  margin-right: 12px;
}

.login-info {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.login-name {
  font-size: 14px;
  color: var(--color-text-primary);
}

.login-time {
  font-size: 12px;
  color: var(--color-text-placeholder);
}

.login-ip {
  font-size: 12px;
  color: var(--color-text-secondary);
}

.audit-list {
  padding: 16px 20px;
}

.audit-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 0;
  font-size: 13px;
}

.audit-action {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
}

.audit-action.info {
  background: #dbeafe;
  color: #1d4ed8;
}

.audit-action.warning {
  background: #fef3c7;
  color: #d97706;
}

.audit-action.danger {
  background: #fee2e2;
  color: var(--color-danger);
}

.audit-user {
  color: var(--color-primary-light-1);
}

.audit-target {
  flex: 1;
  color: var(--color-text-secondary);
}

.audit-time {
  color: var(--color-text-placeholder);
  font-size: 12px;
}

.quick-actions-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  padding: 16px 20px;
}

.quick-action {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 16px 8px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s;
}

.quick-action:hover {
  background: var(--color-border-lighter);
}

.action-icon {
  font-size: 24px;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.action-label {
  font-size: 12px;
  color: var(--color-text-secondary);
}

.pending-count {
  background: var(--color-danger);
  color: white;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 12px;
}

.pending-list {
  padding: 16px 20px;
}

.pending-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 0;
  border-left: 3px solid transparent;
  padding-left: 12px;
  margin-left: -12px;
}

.pending-item.high {
  border-left-color: var(--color-danger);
}

.pending-item.medium {
  border-left-color: var(--color-warning);
}

.pending-item.low {
  border-left-color: var(--color-primary);
}

.pending-type {
  font-size: 12px;
  color: var(--color-text-secondary);
  background: var(--color-border-lighter);
  padding: 2px 8px;
  border-radius: 4px;
}

.pending-desc {
  flex: 1;
  font-size: 13px;
  color: var(--color-text-primary);
}

.pending-time {
  font-size: 12px;
  color: var(--color-text-placeholder);
}

.storage-info {
  padding: 16px 20px;
}

.storage-bar {
  height: 8px;
  background: var(--color-border-lighter);
  border-radius: 4px;
  overflow: hidden;
}

.storage-used {
  height: 100%;
  background: linear-gradient(90deg, var(--color-primary-light-1), var(--color-primary));
  border-radius: 4px;
}

.storage-text {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-top: 8px;
}

.storage-breakdown {
  padding: 0 20px 16px;
}

.breakdown-item {
  display: flex;
  justify-content: space-between;
  padding: 6px 0;
  font-size: 13px;
}

.breakdown-label {
  color: var(--color-text-secondary);
}

.breakdown-value {
  color: var(--color-text-primary);
  font-weight: 500;
}

@media (max-width: 1200px) {
  .admin-stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .admin-main-grid {
    grid-template-columns: 1fr;
  }
}

.empty-tip {
  text-align: center;
  color: var(--color-text-placeholder);
  font-size: 13px;
  padding: 20px 0;
}

/* 加载失败与"确实为空"必须可区分：失败用告警色 + 真实原因 */
.empty-tip.error-tip {
  color: var(--color-danger);
}

@media (max-width: 768px) {
  .admin-banner {
    flex-direction: column;
    gap: 16px;
  }
  .admin-actions {
    flex-wrap: wrap;
    justify-content: center;
  }
  .admin-stats-grid {
    grid-template-columns: 1fr;
  }
}
</style>
