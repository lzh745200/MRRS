<template>
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
          <button class="action-btn gold" @click="pushSafe('/data-management/backup')">
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
  <el-empty v-else description="无权限访问此页面" />
</template>

<script setup lang="ts">
import { logger } from '@/utils/logger'

import { ref, computed, onMounted } from 'vue'
import { useRouterSafe } from '@/composables/useRouterSafe'
import { useUserStore } from '@/stores/user'
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
  const role = userStore.currentUser?.role
  return role === 'super_admin' || role === 'admin'
})

const currentDate = new Date().toLocaleDateString('zh-CN', {
  year: 'numeric',
  month: 'long',
  day: 'numeric',
  weekday: 'long',
})

const adminStats = ref([
  { label: '用户总数', value: 0, icon: UserFilled, trend: '', trendClass: 'stable' },
  { label: '今日活跃', value: 0, icon: CircleCheck, trend: '', trendClass: 'stable' },
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
  { icon: Files, label: '数据备份', path: '/data-management/backup' },
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
    const res = await get('/dashboard/stats')
    const data = res.data?.data || res.data || {}

    adminStats.value[0].value = data.total_users || 0
    adminStats.value[1].value = data.active_today || 0
    adminStats.value[2].value = data.total_records || 0
    if (data.uptime) {
      adminStats.value[3].value = data.uptime
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

<style scoped>
.admin-dashboard {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.admin-banner {
  background: linear-gradient(135deg, #1b4332 0%, #2d6a4f 50%, #40916c 100%);
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
  background: linear-gradient(135deg, #d4af37, #c9a227);
  color: #1b4332;
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
  color: #64748b;
  font-size: 13px;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: #1b4332;
}

.stat-trend {
  font-size: 12px;
  margin-top: 4px;
}

.stat-trend.up {
  color: #10b981;
}

.stat-trend.down {
  color: #ef4444;
}

.stat-trend.stable {
  color: #6b7280;
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
  border-bottom: 1px solid #f1f5f9;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header h3 {
  margin: 0;
  font-size: 15px;
  color: #1e293b;
  display: flex;
  align-items: center;
  gap: 6px;
}

.text-btn {
  background: none;
  border: none;
  color: #40916c;
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
  border-bottom: 1px solid #f8fafc;
}

.status-item:last-child {
  border-bottom: none;
}

.status-name {
  color: #334155;
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
  border-bottom: 1px solid #f8fafc;
}

.login-item:last-child {
  border-bottom: none;
}

.login-avatar {
  width: 36px;
  height: 36px;
  background: linear-gradient(135deg, #40916c, #2d6a4f);
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
  color: #1e293b;
}

.login-time {
  font-size: 12px;
  color: #94a3b8;
}

.login-ip {
  font-size: 12px;
  color: #64748b;
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
  color: #dc2626;
}

.audit-user {
  color: #40916c;
}

.audit-target {
  flex: 1;
  color: #64748b;
}

.audit-time {
  color: #94a3b8;
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
  background: #f1f5f9;
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
  color: #475569;
}

.pending-count {
  background: #f56c6c;
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
  border-left-color: #f56c6c;
}

.pending-item.medium {
  border-left-color: #e6a23c;
}

.pending-item.low {
  border-left-color: #409eff;
}

.pending-type {
  font-size: 12px;
  color: #64748b;
  background: #f1f5f9;
  padding: 2px 8px;
  border-radius: 4px;
}

.pending-desc {
  flex: 1;
  font-size: 13px;
  color: #1e293b;
}

.pending-time {
  font-size: 12px;
  color: #94a3b8;
}

.storage-info {
  padding: 16px 20px;
}

.storage-bar {
  height: 8px;
  background: #f1f5f9;
  border-radius: 4px;
  overflow: hidden;
}

.storage-used {
  height: 100%;
  background: linear-gradient(90deg, #40916c, #2d6a4f);
  border-radius: 4px;
}

.storage-text {
  font-size: 12px;
  color: #64748b;
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
  color: #64748b;
}

.breakdown-value {
  color: #1e293b;
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
  color: #94a3b8;
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
