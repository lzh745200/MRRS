<template>
  <div class="reminder-center">
    <div class="page-header">
      <h2>提醒中心</h2>
      <div class="header-actions">
        <el-button :loading="loading" @click="load">刷新</el-button>
        <el-button type="primary" :loading="scanning" @click="handleScan">
          <el-icon><RefreshRight /></el-icon> 立即扫描
        </el-button>
      </div>
    </div>

    <el-alert
      type="info"
      show-icon
      :closable="false"
      title="系统每 6 小时自动扫描一次：审批超时、项目到期、预算超支等提醒自动生成。"
      class="tip"
    />

    <el-card v-loading="loading">
      <template #header>
        <span>全部提醒（{{ total }}）</span>
        <el-tag v-if="unread > 0" type="danger" size="small">未读 {{ unread }}</el-tag>
      </template>

      <EmptyState v-if="!items.length" text="暂无提醒，一切正常" />
      <div v-else class="reminder-list">
        <div v-for="r in items" :key="r.id" class="reminder-item">
          <el-tag :type="tagType(r.type)" size="small" class="rtype">{{
            typeLabel(r.type)
          }}</el-tag>
          <div class="rbody">
            <div class="rtitle">
              <span v-if="!r.is_read" class="dot" />
              {{ r.title }}
            </div>
            <div class="rcontent">{{ r.content }}</div>
          </div>
          <span class="rtime">{{ formatTime(r.created_at) }}</span>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import EmptyState from '@/components/business/EmptyState/EmptyState.vue'
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { RefreshRight } from '@element-plus/icons-vue'
import { getReminders, triggerReminderScan, type ReminderItem } from '@/api/reminders'

const loading = ref(false)
const scanning = ref(false)
const items = ref<ReminderItem[]>([])
const total = ref(0)
const unread = ref(0)

async function load() {
  loading.value = true
  try {
    const res = await getReminders()
    items.value = res?.items ?? []
    total.value = res?.total ?? 0
    unread.value = res?.unread ?? 0
  } catch {
    ElMessage.error('加载提醒失败')
  } finally {
    loading.value = false
  }
}

async function handleScan() {
  scanning.value = true
  try {
    const res = await triggerReminderScan()
    ElMessage.success(`扫描完成，新增 ${res?.created ?? 0} 条提醒`)
    await load()
  } catch {
    ElMessage.error('扫描失败')
  } finally {
    scanning.value = false
  }
}

function tagType(type: string): 'success' | 'warning' | 'info' | 'danger' {
  const map: Record<string, 'success' | 'warning' | 'info' | 'danger'> = {
    approval_overtime: 'danger',
    deadline_warning: 'warning',
    budget_warning: 'danger',
    backup_reminder: 'info',
    package_reminder: 'info',
  }
  return map[type] ?? 'info'
}

function typeLabel(type: string): string {
  const map: Record<string, string> = {
    approval_overtime: '审批超时',
    deadline_warning: '项目到期',
    budget_warning: '预算预警',
    backup_reminder: '备份提醒',
    package_reminder: '数据包',
  }
  return map[type] ?? type
}

function formatTime(t?: string | null): string {
  if (!t) return ''
  const d = new Date(t)
  if (Number.isNaN(d.getTime())) return t
  return `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

onMounted(load)
</script>

<style scoped>
.reminder-center {
  padding: 20px;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}
.page-header h2 {
  margin: 0;
}
.header-actions {
  display: flex;
  gap: 8px;
}
.tip {
  margin-bottom: 14px;
}
.reminder-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.reminder-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-bg-color);
}
.rtype {
  flex-shrink: 0;
  margin-top: 2px;
}
.rbody {
  flex: 1;
  min-width: 0;
}
.rtitle {
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 6px;
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--el-color-danger);
  display: inline-block;
}
.rcontent {
  color: var(--el-text-color-secondary);
  font-size: 13px;
  margin-top: 2px;
}
.rtime {
  color: var(--el-text-color-placeholder);
  font-size: 12px;
  flex-shrink: 0;
}
</style>
