<template>
  <div class="system-status">
    <!-- 离线/在线指示灯 -->
    <div class="status-item status-indicator" :title="onlineStatusText">
      <span
        class="status-dot"
        :class="{
          'status-dot--online': isOnline,
          'status-dot--offline': !isOnline,
          'status-dot--syncing': isSyncing,
        }"
      ></span>
      <span class="status-label">{{ onlineStatusText }}</span>
    </div>

    <div class="status-divider"></div>

    <!-- 数据同步时间 -->
    <div class="status-item" title="上次数据同步时间">
      <el-icon class="status-icon-sync"><Timer /></el-icon>
      <span class="status-label">同步</span>
      <span class="status-value">{{ formattedSyncTime }}</span>
    </div>

    <div class="status-divider"></div>

    <!-- 数据库文件大小 -->
    <div class="status-item" title="本地数据库文件大小">
      <el-icon class="status-icon-db"><Coin /></el-icon>
      <span class="status-label">数据库</span>
      <span class="status-value data-number data-number--sm">{{ dbSizeText }}</span>
    </div>

    <div class="status-divider"></div>

    <!-- CPU 使用率 -->
    <div class="status-item" title="CPU 使用率">
      <el-icon class="status-icon-cpu"><Monitor /></el-icon>
      <span class="status-label">CPU</span>
      <span class="status-value data-number data-number--sm">{{ cpuPercent }}%</span>
      <div class="status-bar">
        <div
          class="status-bar__fill status-bar__fill--cpu"
          :style="{ width: cpuPercent + '%' }"
          :class="{
            'status-bar__fill--warning': cpuPercent > 70,
            'status-bar__fill--danger': cpuPercent > 90,
          }"
        ></div>
      </div>
    </div>

    <div class="status-divider"></div>

    <!-- 内存使用率 -->
    <div class="status-item" title="内存使用率">
      <el-icon class="status-icon-mem"><Files /></el-icon>
      <span class="status-label">内存</span>
      <span class="status-value data-number data-number--sm">{{ memPercent }}%</span>
      <div class="status-bar">
        <div
          class="status-bar__fill status-bar__fill--mem"
          :style="{ width: memPercent + '%' }"
          :class="{
            'status-bar__fill--warning': memPercent > 70,
            'status-bar__fill--danger': memPercent > 85,
          }"
        ></div>
      </div>
    </div>

    <div class="status-divider"></div>

    <!-- 进程信息 -->
    <div class="status-item" title="后端进程">
      <el-icon class="status-icon-proc"><Cpu /></el-icon>
      <span class="status-label">进程</span>
      <span class="status-value data-number data-number--sm">
        {{ processMemoryMB }}MB / {{ processThreads }}线程
      </span>
    </div>

    <!-- 刷新按钮 -->
    <el-button
      text
      size="small"
      class="refresh-btn"
      :loading="isRefreshing"
      title="刷新系统状态"
      @click="refresh"
    >
      <el-icon><Refresh /></el-icon>
    </el-button>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { Timer, Coin, Monitor, Files, Cpu, Refresh } from '@element-plus/icons-vue'
import { getMonitorSnapshot } from '@/api/systemMonitor'
import type { MonitorSnapshot } from '@/api/systemMonitor'
import { logger } from '@/utils/logger'

// =========================================================================
// Props
// =========================================================================

interface Props {
  /** 轮询间隔（毫秒），默认 30 秒，设为 0 禁用轮询 */
  pollInterval?: number
  /** 是否显示刷新按钮 */
  showRefresh?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  pollInterval: 30000,
  showRefresh: true,
})

// =========================================================================
// 状态
// =========================================================================

const isOnline = ref(true)
const isSyncing = ref(false)
const isRefreshing = ref(false)
const lastSyncTime = ref<Date | null>(null)
const dbSizeBytes = ref<number>(0)
const cpuPercent = ref<number>(0)
const memPercent = ref<number>(0)
const processMemoryMB = ref<number>(0)
const processThreads = ref<number>(0)

let pollTimer: ReturnType<typeof setInterval> | null = null

// =========================================================================
// 计算属性
// =========================================================================

const onlineStatusText = computed(() => {
  if (isSyncing.value) return '同步中'
  return isOnline.value ? '在线' : '离线'
})

const formattedSyncTime = computed(() => {
  if (!lastSyncTime.value) return '--:--'
  const now = new Date()
  const diff = now.getTime() - lastSyncTime.value.getTime()
  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)

  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes}分钟前`
  if (hours < 24) return `${hours}小时前`

  return lastSyncTime.value.toLocaleDateString('zh-CN', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
})

/** 人性化数据库文件大小显示 */
const dbSizeText = computed(() => {
  const bytes = dbSizeBytes.value
  if (bytes === 0) return '-- MB'
  const mb = bytes / (1024 * 1024)
  if (mb >= 1024) return (mb / 1024).toFixed(2) + ' GB'
  return mb.toFixed(1) + ' MB'
})

// =========================================================================
// 方法
// =========================================================================

const estimateDbSize = async () => {
  try {
    // 尝试从后端获取数据库文件大小
    const { getDatabaseFileSize } = await import('@/api/systemMonitor')
    const res = await getDatabaseFileSize()
    if (res?.data?.size_bytes) {
      dbSizeBytes.value = res.data.size_bytes
    }
  } catch {
    // 降级：使用 fetch 探测或设为 0
    dbSizeBytes.value = 0
  }
}

const fetchSnapshot = async () => {
  try {
    const res = await getMonitorSnapshot()
    if (res?.success && res?.data) {
      const d: MonitorSnapshot = res.data
      isOnline.value = true
      cpuPercent.value = Math.round(d.cpu_usage || 0)
      memPercent.value = Math.round(d.memory_usage || 0)
      processMemoryMB.value = Math.round(d.process_memory_mb || 0)
      processThreads.value = d.process_threads || 0
      lastSyncTime.value = new Date()
    }
  } catch {
    isOnline.value = false
    // 保持上次数据不变，仅标记离线
  }
}

const refresh = async () => {
  isRefreshing.value = true
  isSyncing.value = true
  try {
    await Promise.all([fetchSnapshot(), estimateDbSize()])
    lastSyncTime.value = new Date()
  } catch (error) {
    logger.error('[SystemStatus] 刷新失败:', error)
  } finally {
    isRefreshing.value = false
    isSyncing.value = false
  }
}

// =========================================================================
// 生命周期
// =========================================================================

onMounted(async () => {
  await refresh()

  if (props.pollInterval > 0) {
    pollTimer = setInterval(() => {
      fetchSnapshot()
    }, props.pollInterval)
  }
})

onUnmounted(() => {
  if (pollTimer !== null) {
    clearInterval(pollTimer)
    pollTimer = null
  }
})
</script>

<style scoped lang="scss">
.system-status {
  display: flex;
  align-items: center;
  gap: 0;
  background: var(--dash-bg-card, #ffffff);
  padding: 10px 16px;
  border-radius: var(--dash-radius-card, 12px);
  box-shadow: var(--dash-card-shadow-sm, 0 1px 3px rgba(0, 0, 0, 0.04));
  border: 1px solid #f1f5f9;
  flex-wrap: wrap;
  user-select: none;
  transition: box-shadow 0.25s ease;

  &:hover {
    box-shadow: var(--dash-card-shadow-md, 0 4px 12px rgba(0, 0, 0, 0.06));
  }
}

// ── 状态项 ──
.status-item {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  font-size: 12px;
  white-space: nowrap;
}

// ── 分割线 ──
.status-divider {
  width: 1px;
  height: 20px;
  background: #e2e8f0;
  flex-shrink: 0;
}

// ── 在线指示灯 ──
.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  position: relative;

  &--online {
    background: #22c55e;
    box-shadow: 0 0 6px rgba(34, 197, 94, 0.5);
    animation: status-pulse 2s ease-in-out infinite;
  }

  &--offline {
    background: #ef4444;
    box-shadow: 0 0 6px rgba(239, 68, 68, 0.4);
  }

  &--syncing {
    background: #f59e0b;
    box-shadow: 0 0 6px rgba(245, 158, 11, 0.5);
    animation: status-pulse 0.8s ease-in-out infinite;
  }
}

@keyframes status-pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

// ── 图标颜色 ──
.status-icon-sync {
  color: #3b82f6;
  font-size: 13px;
}
.status-icon-db {
  color: #2d6a4f;
  font-size: 13px;
}
.status-icon-cpu {
  color: #6366f1;
  font-size: 13px;
}
.status-icon-mem {
  color: #8b5cf6;
  font-size: 13px;
}
.status-icon-proc {
  color: #64748b;
  font-size: 13px;
}

// ── 标签/值 ──
.status-label {
  color: #94a3b8;
  font-size: 11px;
  font-weight: 500;
  margin-right: 2px;
}

.status-value {
  color: #475569;
  font-size: 12px;
  font-weight: 600;
}

// ── 微型进度条 ──
.status-bar {
  width: 36px;
  height: 4px;
  background: #f1f5f9;
  border-radius: 2px;
  overflow: hidden;
  margin-left: 4px;
  flex-shrink: 0;

  &__fill {
    height: 100%;
    border-radius: 2px;
    transition: width 0.6s ease;

    &--cpu {
      background: linear-gradient(90deg, #6366f1, #818cf8);
    }

    &--mem {
      background: linear-gradient(90deg, #8b5cf6, #a78bfa);
    }

    &--warning {
      background: linear-gradient(90deg, #f59e0b, #fbbf24);
    }

    &--danger {
      background: linear-gradient(90deg, #ef4444, #f87171);
    }
  }
}

// ── 刷新按钮 ──
.refresh-btn {
  margin-left: auto;
  flex-shrink: 0;
  color: #94a3b8;

  &:hover {
    color: #1e4d8c;
  }
}

// ── 响应式 ──
@media (max-width: 768px) {
  .system-status {
    padding: 8px 12px;
    gap: 4px;
  }

  .status-divider {
    height: 14px;
  }

  .status-item {
    padding: 2px 6px;
    font-size: 11px;
  }

  .status-value {
    font-size: 11px;
  }
}
</style>
