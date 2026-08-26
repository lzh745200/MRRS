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
            <button class="action-btn gold" @click="pushSafe('/system/users-orgs')">
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
                <div v-if="systemStatus.length === 0" class="empty-tip">加载中...</div>
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
                <div v-if="recentLogins.length === 0" class="empty-tip">暂无登录记录</div>
                <div v-for="login in recentLogins" :key="login.id" class="login-item">
                  <div class="login-avatar">
                    {{ (login.name || '').charAt(0) || 'U' }}
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
                <div v-if="auditLogs.length === 0" class="empty-tip">暂无审计记录</div>
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
                <div v-if="pendingItems.length === 0" class="empty-tip">暂无待处理事项</div>
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
                <div class="storage-bar">
                  <div class="storage-used" :style="{ width: storagePercent + '%' }"></div>
                </div>
                <div class="storage-text">
                  已使用 {{ formatSize(storageUsed) }} /
                  {{ formatSize(storageTotal) }}
                </div>
              </div>
              <div class="storage-breakdown">
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
import { logger } from '@/utils/logger'

import { ref, computed, onMounted } from 'vue'
import { useRouterSafe } from '@/composables/useRouterSafe'
import { useUserStore } from '@/stores/user'
import { ADMIN_ROLES, normalizeRole } from '@/utils/roleAccess'
import { get } from '@/api/request'
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
const isAdmin = computed(() => {
  const role = normalizeRole(userStore.currentUser?.role)
  return ADMIN_ROLES.includes(role)
})

const currentDate = new Date().toLocaleDateString('zh-CN', {
  year: 'numeric',
  month: 'long',
  day: 'numeric',
  weekday: 'long',
})

const adminStats = ref([
  { label: '用户总数', value: 0, icon: UserFilled, trend: '', trendClass: 'stable' },
  { label: '覆盖人口', value: 0, icon: CircleCheck, trend: '', trendClass: 'stable' },
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
  { icon: UserFilled, label: '用户管理', path: '/system/users-orgs' },
  { icon: Key, label: '角色权限', path: '/system/roles' },
  { icon: Files, label: '数据备份', path: '/system/backup' },
  { icon: Document, label: '操作审计', path: '/system/audit' },
  { icon: Setting, label: '系统配置', path: '/system/config' },
  { icon: DataAnalysis, label: '数据总览', path: '/data-management/overview' },
]

const pendingItems = ref<any[]>([])

const storageUsed = ref(0)
const storageTotal = ref(1)
const dbSize = ref(0)
const backupSize = ref(0)
const logSize = ref(0)

const storagePercent = computed(() => Math.round((storageUsed.value / storageTotal.value) * 100))

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  return `${(bytes / 1024 / 1024 / 1024).toFixed(1)} GB`
}

async function loadAdminData() {
  try {
    const res: any = await get('/dashboard/stats')
    // 后端返回 {code, data:{total_users,total_villages,total_projects,total_funds,...}, message}
    // 无数据时返回 null
    const data = res?.data ?? res ?? {}

    adminStats.value[0].value = Number(data.total_users) || 0
    // 今日活跃后端未提供 → 用覆盖人口展示（卡片文案保持不变会误导，改用有数据支撑的字段）
    adminStats.value[1].value = Number(data.total_population) || 0
    adminStats.value[2].value =
      Number(data.total_villages || 0) +
      Number(data.total_projects || 0) +
      Number(data.total_funds || 0) +
      Number(data.total_schools || 0)
    if (data.total_villages !== undefined) {
      adminStats.value[3].value = `${data.total_villages} 村 / ${data.total_projects ?? 0} 项目`
    }

    if (data.system_status && Array.isArray(data.system_status)) {
      systemStatus.value = data.system_status
    }
    if (data.recent_logins && Array.isArray(data.recent_logins)) {
      recentLogins.value = data.recent_logins
    }
    if (data.audit_logs && Array.isArray(data.audit_logs)) {
      auditLogs.value = data.audit_logs
    }
    if (data.pending_items && Array.isArray(data.pending_items)) {
      pendingItems.value = data.pending_items
    }
    if (data.storage) {
      storageUsed.value = data.storage.used || 0
      storageTotal.value = data.storage.total || 1
      dbSize.value = data.storage.db || 0
      backupSize.value = data.storage.backup || 0
      logSize.value = data.storage.log || 0
    }
  } catch (e) {
    logger.error('加载管理数据失败:', e)
  }
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
  background: #ef4444;
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
