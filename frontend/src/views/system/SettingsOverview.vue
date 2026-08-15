<template>
  <div class="settings-overview-page">
    <!-- 页头 -->
    <div class="page-header">
      <div>
        <h2 class="page-title">系统设置总览</h2>
        <p class="page-desc">掌握系统健康状态，快速进入各项设置功能</p>
      </div>
      <div class="header-right">
        <span v-if="lastUpdated" class="last-updated">
          <el-icon><Clock /></el-icon> 更新于 {{ lastUpdated }}
        </span>
        <el-button
          :icon="Refresh"
          :loading="loading"
          size="small"
          type="primary"
          @click="refreshAll"
        >
          刷新
        </el-button>
      </div>
    </div>

    <!-- 系统健康状态 -->
    <el-card class="section-card">
      <template #header>
        <div class="card-header">
          <span class="header-title">
            <el-icon><Odometer /></el-icon> 系统健康状态
          </span>
          <el-tag :type="overallTagType" size="small" effect="dark">{{ overallText }}</el-tag>
        </div>
      </template>
      <el-row v-loading="loading" :gutter="16" class="health-row">
        <el-col
          v-for="card in healthCards"
          :key="card.key"
          :xs="12"
          :sm="8"
          :md="6"
          :lg="4"
          class="health-col"
        >
          <div class="status-card" :class="'level-' + card.level">
            <div class="status-card-top">
              <span class="status-dot" :class="'dot-' + card.level" />
              <span class="status-label">{{ card.label }}</span>
            </div>
            <div class="status-value">{{ card.value }}</div>
            <div class="status-detail">{{ card.detail }}</div>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <!-- 快捷导航 -->
    <el-card class="section-card">
      <template #header>
        <div class="card-header">
          <span class="header-title">
            <el-icon><Grid /></el-icon> 快捷导航
          </span>
        </div>
      </template>
      <el-row :gutter="20">
        <el-col v-for="group in navGroups" :key="group.title" :xs="12" :sm="12" :md="6">
          <div class="nav-group">
            <div class="nav-group-title">{{ group.title }}</div>
            <el-card
              v-for="item in group.items"
              :key="item.path"
              class="nav-item"
              shadow="never"
              @click="goTo(item.path)"
            >
              <el-icon :size="18" class="nav-icon"><component :is="item.icon" /></el-icon>
              <span class="nav-item-label">{{ item.label }}</span>
              <el-icon class="nav-arrow"><ArrowRight /></el-icon>
            </el-card>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <!-- 最近审计日志 -->
    <el-card class="section-card">
      <template #header>
        <div class="card-header">
          <span class="header-title">
            <el-icon><Document /></el-icon> 最近审计日志
          </span>
          <el-button link type="primary" @click="goTo('/system/audit')">查看全部</el-button>
        </div>
      </template>
      <el-table v-loading="auditLoading" :data="auditLogs" stripe size="small">
        <el-table-column label="时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="用户" width="120">
          <template #default="{ row }">{{ row.username || '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-tag :type="actionTagType(row.action)" size="small">{{ row.action || '-' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="资源" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.resource_type || '-' }}
            <span v-if="row.resource_id" class="resource-id">#{{ row.resource_id }}</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 版本信息 -->
    <div class="version-footer">
      <span class="version-name">帮扶管理信息系统 v{{ systemVersion }}</span>
      <span v-if="buildInfoText" class="version-build">{{ buildInfoText }}</span>
      <span class="version-copyright">内部系统 · 未经授权禁止外传</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import type { Component } from 'vue'
import { useRouterSafe } from '@/composables/useRouterSafe'
import {
  Refresh,
  Clock,
  Odometer,
  Grid,
  ArrowRight,
  Document,
  User,
  Menu,
  Stamp,
  FolderChecked,
  Lock,
  Key,
  Monitor,
  Box,
  Timer,
  Cpu,
  Setting,
  Message,
  Flag,
  Tickets,
} from '@element-plus/icons-vue'
import { get } from '@/api/request'
import { getBackupStats } from '@/api/backup'
import { getSecretsStatus } from '@/api/secrets'
import { SYSTEM_VERSION } from '@/config/constants'

const systemVersion = SYSTEM_VERSION

// ── 类型定义 ──
type StatusLevel = 'green' | 'yellow' | 'red' | 'gray'

interface HealthCard {
  key: string
  label: string
  value: string
  detail: string
  level: StatusLevel
}

interface NavItem {
  label: string
  path: string
  icon: Component
}

interface NavGroup {
  title: string
  items: NavItem[]
}

/** /system/health 响应（拦截器会将 data 内字段提升到顶层） */
interface HealthOverview {
  code?: number
  status?: string
  uptime_seconds?: number
  platform?: string
  python_version?: string
  cpu_count?: number
}

/** /system/monitor/snapshot 响应 */
interface SnapshotData {
  cpu_usage?: number
  memory_usage?: number
  memory_used_mb?: number
  memory_total_mb?: number
  disk_usage?: number
  disk_used_gb?: number
  disk_total_gb?: number
}

/** /system/health/full 响应（构建信息、数据库与备份统计） */
interface HealthFullData {
  app_version?: string
  build_git_hash?: string
  build_time?: string
  db_size_mb?: number
  db_integrity_ok?: boolean
  total_backups?: number
}

interface AuditLogRow {
  id: number
  username?: string
  action?: string
  resource_type?: string
  resource_id?: string
  created_at?: string
}

interface AuditLogListResponse {
  items?: AuditLogRow[]
  total?: number
}

// ── 状态 ──
const { pushSafe } = useRouterSafe()
const loading = ref(false)
const auditLoading = ref(false)
const lastUpdated = ref('')

const health = ref<HealthOverview | null>(null)
const snapshot = ref<SnapshotData | null>(null)
const healthFull = ref<HealthFullData | null>(null)
const backupLast = ref('')
const backupCount = ref(0)
const backupUnknown = ref(true)
const secretsOk = ref(false)
const secretsNeedRotation = ref(false)
const secretsUnknown = ref(true)
const auditLogs = ref<AuditLogRow[]>([])

// ── 快捷导航配置 ──
const navGroups: NavGroup[] = [
  {
    title: '用户权限',
    items: [
      { label: '用户管理', path: '/system/users', icon: User },
      { label: '菜单管理', path: '/system/menus', icon: Menu },
      { label: '用户权限', path: '/system/user-permissions', icon: Stamp },
    ],
  },
  {
    title: '数据安全',
    items: [
      { label: '审计日志', path: '/system/audit', icon: Document },
      { label: '数据备份', path: '/system/backup', icon: FolderChecked },
      { label: '加密设置', path: '/system/encryption', icon: Lock },
      { label: '密钥管理', path: '/system/secrets', icon: Key },
    ],
  },
  {
    title: '运维监控',
    items: [
      { label: '系统监控', path: '/system/monitoring', icon: Monitor },
      { label: '缓存管理', path: '/system/cache', icon: Box },
      { label: '任务管理', path: '/system/tasks', icon: Timer },
      { label: '运行环境', path: '/system/environment', icon: Cpu },
    ],
  },
  {
    title: '配置管理',
    items: [
      { label: '系统配置', path: '/system/config', icon: Setting },
      { label: '邮件设置', path: '/system/email', icon: Message },
      { label: '国际化', path: '/system/i18n', icon: Flag },
      { label: '更新日志', path: '/system/update-logs', icon: Tickets },
    ],
  },
]

// ── 工具函数 ──
function pad(n: number): string {
  return String(n).padStart(2, '0')
}

function formatDateTime(iso?: string): string {
  if (!iso) return '-'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function formatUptime(sec?: number): string {
  if (sec == null || Number.isNaN(sec)) return '-'
  const days = Math.floor(sec / 86400)
  const hours = Math.floor((sec % 86400) / 3600)
  const mins = Math.floor((sec % 3600) / 60)
  if (days > 0) return `${days} 天 ${hours} 小时`
  if (hours > 0) return `${hours} 小时 ${mins} 分钟`
  return `${mins} 分钟`
}

/** 使用率阈值：<70 正常，70-85 偏高，>85 告警 */
function usageLevel(pct: number): StatusLevel {
  if (pct >= 85) return 'red'
  if (pct >= 70) return 'yellow'
  return 'green'
}

function actionTagType(action?: string): 'success' | 'warning' | 'danger' | 'info' | 'primary' {
  const a = (action || '').toLowerCase()
  if (a.includes('delete') || a.includes('删除')) return 'danger'
  if (a.includes('update') || a.includes('修改') || a.includes('更新')) return 'warning'
  if (a.includes('create') || a.includes('新增') || a.includes('创建')) return 'success'
  if (a.includes('login') || a.includes('登录')) return 'primary'
  return 'info'
}

function goTo(path: string): void {
  pushSafe(path)
}

// ── 健康卡片 ──
const backupDays = computed<number | null>(() => {
  if (!backupLast.value) return null
  const t = new Date(backupLast.value).getTime()
  if (Number.isNaN(t)) return null
  return (Date.now() - t) / 86400000
})

const healthCards = computed<HealthCard[]>(() => {
  // 数据库状态
  let dbCard: HealthCard
  if (!health.value) {
    dbCard = {
      key: 'db',
      label: '数据库状态',
      level: 'gray',
      value: '未知',
      detail: '健康检查获取失败',
    }
  } else {
    const ok = (health.value.status || 'healthy') === 'healthy'
    const sizeMb = healthFull.value?.db_size_mb
    const integrity = healthFull.value?.db_integrity_ok
    dbCard = {
      key: 'db',
      label: '数据库状态',
      level: ok ? 'green' : 'red',
      value: ok ? '运行正常' : '状态异常',
      detail:
        sizeMb != null
          ? `占用 ${sizeMb} MB${integrity === false ? ' · 完整性异常' : ''}`
          : `已运行 ${formatUptime(health.value.uptime_seconds)}`,
    }
  }

  // 磁盘空间
  const disk = snapshot.value?.disk_usage
  let diskCard: HealthCard
  if (disk == null) {
    diskCard = {
      key: 'disk',
      label: '磁盘空间',
      level: 'gray',
      value: '--',
      detail: '监控数据获取失败',
    }
  } else {
    const used = snapshot.value?.disk_used_gb
    const total = snapshot.value?.disk_total_gb
    diskCard = {
      key: 'disk',
      label: '磁盘空间',
      level: usageLevel(disk),
      value: `${disk.toFixed(1)}%`,
      detail:
        used != null && total != null
          ? `已用 ${used.toFixed(1)} / ${total.toFixed(1)} GB`
          : '磁盘使用率',
    }
  }

  // 内存使用
  const mem = snapshot.value?.memory_usage
  let memCard: HealthCard
  if (mem == null) {
    memCard = {
      key: 'memory',
      label: '内存使用',
      level: 'gray',
      value: '--',
      detail: '监控数据获取失败',
    }
  } else {
    const used = snapshot.value?.memory_used_mb
    const total = snapshot.value?.memory_total_mb
    memCard = {
      key: 'memory',
      label: '内存使用',
      level: usageLevel(mem),
      value: `${mem.toFixed(1)}%`,
      detail:
        used != null && total != null
          ? `已用 ${(used / 1024).toFixed(1)} / ${(total / 1024).toFixed(1)} GB`
          : '内存使用率',
    }
  }

  // 备份状态
  let backupCard: HealthCard
  if (backupUnknown.value) {
    backupCard = {
      key: 'backup',
      label: '备份状态',
      level: 'gray',
      value: '未知',
      detail: '备份信息获取失败',
    }
  } else if (backupDays.value != null) {
    const recent = backupDays.value <= 7
    backupCard = {
      key: 'backup',
      label: '备份状态',
      level: recent ? 'green' : 'yellow',
      value: formatDateTime(backupLast.value),
      detail: recent ? `最近备份 · 共 ${backupCount.value} 份` : '备份超过 7 天，建议尽快备份',
    }
  } else if (backupCount.value > 0) {
    backupCard = {
      key: 'backup',
      label: '备份状态',
      level: 'yellow',
      value: `共 ${backupCount.value} 份`,
      detail: '未获取到最近备份时间',
    }
  } else {
    backupCard = {
      key: 'backup',
      label: '备份状态',
      level: 'red',
      value: '暂无备份',
      detail: '建议尽快创建数据备份',
    }
  }

  // 安全状态
  let secCard: HealthCard
  if (secretsUnknown.value) {
    secCard = {
      key: 'security',
      label: '安全状态',
      level: 'gray',
      value: '未知',
      detail: '密钥状态获取失败',
    }
  } else if (secretsNeedRotation.value) {
    secCard = {
      key: 'security',
      label: '安全状态',
      level: 'yellow',
      value: '待轮换',
      detail: '加密密钥即将或已经过期',
    }
  } else if (secretsOk.value) {
    secCard = {
      key: 'security',
      label: '安全状态',
      level: 'green',
      value: '加密已启用',
      detail: '字段加密与零信任防护就绪',
    }
  } else {
    secCard = {
      key: 'security',
      label: '安全状态',
      level: 'red',
      value: '未启用',
      detail: '请前往密钥管理配置加密密钥',
    }
  }

  return [dbCard, diskCard, memCard, backupCard, secCard]
})

const overallTagType = computed<'success' | 'warning' | 'danger' | 'info'>(() => {
  const levels = healthCards.value.map((c) => c.level)
  if (levels.includes('red')) return 'danger'
  if (levels.includes('yellow')) return 'warning'
  if (levels.every((l) => l === 'green')) return 'success'
  return 'info'
})

const overallText = computed(() => {
  const map = {
    success: '整体正常',
    warning: '部分告警',
    danger: '存在异常',
    info: '加载中',
  } as const
  return map[overallTagType.value]
})

const buildInfoText = computed(() => {
  const h = healthFull.value
  if (!h?.build_git_hash && !h?.build_time) return ''
  const parts: string[] = []
  if (h.build_git_hash) parts.push(`构建 ${h.build_git_hash}`)
  if (h.build_time) parts.push(h.build_time)
  return parts.join(' · ')
})

// ── 数据加载 ──
async function fetchHealth(): Promise<void> {
  try {
    health.value = await get<HealthOverview>('/system/health')
  } catch {
    health.value = null
  }
}

async function fetchSnapshot(): Promise<void> {
  try {
    snapshot.value = await get<SnapshotData>('/system/monitor/snapshot')
  } catch {
    snapshot.value = null
  }
}

async function fetchHealthFull(): Promise<void> {
  try {
    healthFull.value = await get<HealthFullData>('/system/health/full')
  } catch {
    healthFull.value = null
  }
}

async function fetchBackup(): Promise<void> {
  try {
    const stats = await getBackupStats()
    backupCount.value =
      stats?.total_backups ?? stats?.totalBackups ?? healthFull.value?.total_backups ?? 0
    backupLast.value = stats?.lastBackup ?? ''
    backupUnknown.value = false
  } catch {
    backupUnknown.value = true
  }
}

async function fetchSecrets(): Promise<void> {
  try {
    const st = await getSecretsStatus()
    secretsOk.value = (st?.active_versions ?? 0) > 0
    secretsNeedRotation.value = !!st?.requires_rotation
    secretsUnknown.value = false
  } catch {
    secretsUnknown.value = true
  }
}

async function fetchAuditLogs(): Promise<void> {
  auditLoading.value = true
  try {
    const res = await get<AuditLogListResponse>('/system/audit/logs', { page: 1, page_size: 5 })
    auditLogs.value = res?.items ?? []
  } catch {
    auditLogs.value = []
  } finally {
    auditLoading.value = false
  }
}

async function refreshAll(): Promise<void> {
  loading.value = true
  await Promise.allSettled([
    fetchHealth(),
    fetchSnapshot(),
    fetchHealthFull(),
    fetchBackup(),
    fetchSecrets(),
    fetchAuditLogs(),
  ])
  lastUpdated.value = new Date().toLocaleTimeString()
  loading.value = false
}

onMounted(() => {
  refreshAll()
})
</script>

<style scoped>
.settings-overview-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 20px;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
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
.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}
.last-updated {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--color-info);
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.header-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
  color: #1b4332;
}

/* ── 健康状态卡片 ── */
@media (min-width: 1200px) {
  .health-row .health-col {
    flex: 1 1 0;
    max-width: 20%;
  }
}
.status-card {
  position: relative;
  height: 100%;
  padding: 14px 16px;
  background: #ffffff;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  overflow: hidden;
  transition:
    transform 0.25s ease,
    box-shadow 0.25s ease;
  margin-bottom: 4px;
}
.status-card::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: transparent;
}
.status-card.level-green::before {
  background: var(--color-success);
}
.status-card.level-yellow::before {
  background: var(--color-warning);
}
.status-card.level-red::before {
  background: var(--color-danger);
}
.status-card.level-gray::before {
  background: #c0c4cc;
}
.status-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 6px 16px rgba(27, 67, 50, 0.12);
}
.status-card-top {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}
.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex: none;
}
.dot-green {
  background: var(--color-success);
  animation: dot-pulse-green 2.4s infinite;
}
.dot-yellow {
  background: var(--color-warning);
  animation: dot-pulse-yellow 2.4s infinite;
}
.dot-red {
  background: var(--color-danger);
  animation: dot-pulse-red 1.6s infinite;
}
.dot-gray {
  background: #c0c4cc;
}
@keyframes dot-pulse-green {
  0% {
    box-shadow: 0 0 0 0 color-mix(in srgb, var(--color-success) 45%, transparent);
  }
  70% {
    box-shadow: 0 0 0 7px color-mix(in srgb, var(--color-success) 0%, transparent);
  }
  100% {
    box-shadow: 0 0 0 0 color-mix(in srgb, var(--color-success) 0%, transparent);
  }
}
@keyframes dot-pulse-yellow {
  0% {
    box-shadow: 0 0 0 0 color-mix(in srgb, var(--color-warning) 45%, transparent);
  }
  70% {
    box-shadow: 0 0 0 7px color-mix(in srgb, var(--color-warning) 0%, transparent);
  }
  100% {
    box-shadow: 0 0 0 0 color-mix(in srgb, var(--color-warning) 0%, transparent);
  }
}
@keyframes dot-pulse-red {
  0% {
    box-shadow: 0 0 0 0 color-mix(in srgb, var(--color-danger) 50%, transparent);
  }
  70% {
    box-shadow: 0 0 0 7px color-mix(in srgb, var(--color-danger) 0%, transparent);
  }
  100% {
    box-shadow: 0 0 0 0 color-mix(in srgb, var(--color-danger) 0%, transparent);
  }
}
.status-label {
  font-size: 13px;
  color: #606266;
}
.status-value {
  font-size: 20px;
  font-weight: 700;
  color: #1b4332;
  margin-bottom: 4px;
  font-variant-numeric: tabular-nums;
}
.status-detail {
  font-size: 12px;
  color: var(--color-info);
  line-height: 1.5;
}

/* ── 快捷导航 ── */
.nav-group {
  margin-bottom: 8px;
}
.nav-group-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: #2d6a4f;
  margin-bottom: 10px;
}
.nav-group-title::before {
  content: '';
  width: 3px;
  height: 14px;
  background: #40916c;
  border-radius: 2px;
}
.nav-item {
  margin-bottom: 10px;
  cursor: pointer;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  transition:
    border-color 0.2s ease,
    transform 0.2s ease,
    box-shadow 0.2s ease;
}
.nav-item:hover {
  border-color: #40916c;
  transform: translateX(4px);
  box-shadow: 0 4px 12px rgba(45, 106, 79, 0.1);
}
.nav-item :deep(.el-card__body) {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
}
.nav-icon {
  color: #2d6a4f;
  flex: none;
}
.nav-item-label {
  flex: 1;
  font-size: 13px;
  color: #303133;
}
.nav-arrow {
  flex: none;
  font-size: 12px;
  color: #c0c4cc;
  transition:
    transform 0.2s ease,
    color 0.2s ease;
}
.nav-item:hover .nav-arrow {
  transform: translateX(3px);
  color: #40916c;
}

/* ── 审计日志 ── */
.resource-id {
  margin-left: 4px;
  font-family: monospace;
  color: var(--color-info);
}

/* ── 版本信息 ── */
.version-footer {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 8px 0 4px;
  text-align: center;
}
.version-name {
  font-size: 13px;
  font-weight: 600;
  color: #2d6a4f;
}
.version-build {
  font-size: 12px;
  font-family: monospace;
  color: var(--color-info);
}
.version-copyright {
  font-size: 12px;
  color: #c0c4cc;
}
</style>
