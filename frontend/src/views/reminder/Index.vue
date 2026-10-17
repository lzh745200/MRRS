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

    <div class="stats-row">
      <el-tag type="danger">待处理 {{ stats.pending }}</el-tag>
      <el-tag type="success">已处理 {{ stats.handled }}</el-tag>
      <el-tag type="info">已忽略 {{ stats.ignored }}</el-tag>
      <el-tag type="warning">已延期 {{ stats.snoozed }}</el-tag>
    </div>

    <el-card v-loading="loading">
      <template #header>
        <span>{{ headerText }}（{{ total }}）</span>
        <el-tag v-if="unread > 0" type="danger">未读 {{ unread }}</el-tag>
      </template>

      <div class="filters">
        <el-button
          v-for="f in filterOptions"
          :key="f.value"
          size="small"
          :type="filter === f.value ? 'primary' : 'default'"
          class="filter-btn"
          @click="filter = f.value"
        >
          {{ f.label }}
        </el-button>
      </div>

      <EmptyState v-if="!visibleItems.length" text="暂无提醒，一切正常" />
      <div v-else class="reminder-list">
        <div
          v-for="r in visibleItems"
          :key="r.id"
          class="reminder-item"
          :class="{ 'is-done': !isOpen(r) }"
        >
          <el-tag :type="tagType(r.type)" class="rtype">{{ typeLabel(r.type) }}</el-tag>
          <div class="rbody">
            <div class="rtitle">
              <span v-if="!r.is_read" class="dot" />
              {{ r.title }}
              <el-tag v-if="stateLabel(r)" size="small" :type="stateTagType(r)" class="state-tag">
                {{ stateLabel(r) }}
              </el-tag>
            </div>
            <div class="rcontent">{{ r.content }}</div>
            <div v-if="r.note" class="rnote">备注：{{ r.note }}</div>
            <div v-if="r.snooze_until" class="rsnooze">延期至 {{ formatTime(r.snooze_until) }}</div>
          </div>
          <span class="rtime">{{ formatTime(r.created_at) }}</span>
          <div class="ractions">
            <el-button v-if="jumpRoute(r)" link type="primary" class="act-go" @click="goTo(r)">
              前往处理
            </el-button>
            <template v-if="isOpen(r)">
              <el-button link type="primary" class="act-handle" @click="handleItem(r)">
                处理
              </el-button>
              <el-button link class="act-snooze" @click="snoozeItem(r)">延期</el-button>
              <el-button link type="info" class="act-ignore" @click="ignoreItem(r)">
                忽略
              </el-button>
            </template>
            <el-button v-else link class="act-reopen" @click="reopenItem(r)"> 重新打开 </el-button>
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import EmptyState from '@/components/business/EmptyState/EmptyState.vue'
import { computed, ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { RefreshRight } from '@element-plus/icons-vue'
import { useRouterSafe } from '@/composables/useRouterSafe'
import {
  getReminders,
  triggerReminderScan,
  handleReminder,
  ignoreReminder,
  snoozeReminder,
  reopenReminder,
  type ReminderItem,
  type ReminderStats,
} from '@/api/reminders'

import { format } from '@/utils'

type FilterKey = 'open' | 'handled' | 'ignored' | 'all'

const { pushSafe } = useRouterSafe()

const FILTER_LABELS: Record<FilterKey, string> = {
  open: '待处理',
  handled: '已处理',
  ignored: '已忽略',
  all: '全部',
}

const filterOptions = (Object.keys(FILTER_LABELS) as FilterKey[]).map((value) => ({
  value,
  label: FILTER_LABELS[value],
}))

const loading = ref(false)
const scanning = ref(false)
const items = ref<ReminderItem[]>([])
const total = ref(0)
const unread = ref(0)
const filter = ref<FilterKey>('open')
const stats = ref<ReminderStats>({ pending: 0, handled: 0, ignored: 0, snoozed: 0, total: 0 })

/** 列表为空或后端未返回 stats 时的本地兜底统计（口径与后端 summarize_reminders 一致） */
function localStats(list: ReminderItem[]): ReminderStats {
  let pending = 0
  let handled = 0
  let ignored = 0
  let snoozed = 0
  const now = Date.now()
  for (const r of list) {
    const state = r.state ?? 'open'
    if (state === 'handled') handled += 1
    else if (state === 'ignored') ignored += 1
    else pending += 1
    if (state === 'open' && r.snooze_until && Date.parse(r.snooze_until) > now) snoozed += 1
  }
  return { pending, handled, ignored, snoozed, total: list.length }
}

const visibleItems = computed(() => {
  if (filter.value === 'all') return items.value
  return items.value.filter((r) => (r.state ?? 'open') === filter.value)
})

const headerText = computed(() => FILTER_LABELS[filter.value])

async function load() {
  loading.value = true
  try {
    const res = await getReminders(true)
    items.value = res?.items ?? []
    total.value = res?.total ?? 0
    unread.value = res?.unread ?? 0
    stats.value = res?.stats ?? localStats(items.value)
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
    approval_approaching: '审批临期',
    deadline_warning: '项目到期',
    budget_warning: '预算预警',
    backup_reminder: '备份提醒',
    package_reminder: '数据包',
  }
  return map[type] ?? type
}

/** 是否仍待处理（open 或缺省） */
function isOpen(r: ReminderItem): boolean {
  const state = r.state ?? 'open'
  return state !== 'handled' && state !== 'ignored'
}

/** 状态角标文案；待处理且未延期时返回空串（不展示角标） */
function stateLabel(r: ReminderItem): string {
  const state = r.state ?? 'open'
  if (state === 'handled') return '已处理'
  if (state === 'ignored') return '已忽略'
  if (r.snooze_until && Date.parse(r.snooze_until) > Date.now()) return '已延期'
  return ''
}

function stateTagType(r: ReminderItem): 'success' | 'info' | 'warning' {
  const state = r.state ?? 'open'
  if (state === 'handled') return 'success'
  if (state === 'ignored') return 'info'
  return 'warning'
}

/** 提醒对应的业务页面；无法定位时返回 null（不展示"前往处理"） */
function jumpRoute(r: ReminderItem): string | null {
  const id = r.entity_id
  switch (r.type) {
    case 'approval_overtime':
    case 'approval_approaching':
      return '/approval/pending'
    case 'deadline_warning':
      return id ? `/projects/${id}` : null
    case 'budget_warning':
      return id ? `/funds/${id}` : null
    case 'backup_reminder':
      return '/system/backup'
    case 'package_reminder':
      return '/data-package'
    default:
      return null
  }
}

function goTo(r: ReminderItem) {
  const route = jumpRoute(r)
  if (route) pushSafe(route, '提醒处理')
}

async function runAction(action: () => Promise<unknown>, successText: string) {
  try {
    await action()
    ElMessage.success(successText)
    await load()
  } catch {
    ElMessage.error('操作失败，请稍后重试')
  }
}

async function handleItem(r: ReminderItem) {
  await runAction(() => handleReminder(r.id), '已标记处理')
}

async function ignoreItem(r: ReminderItem) {
  let reason = ''
  try {
    const { value } = await ElMessageBox.prompt('忽略原因（可选）', '忽略提醒', {
      inputValue: '',
      confirmButtonText: '确定忽略',
      cancelButtonText: '取消',
    })
    reason = value ?? ''
  } catch {
    return
  }
  await runAction(() => ignoreReminder(r.id, reason), '已忽略该提醒')
}

async function snoozeItem(r: ReminderItem) {
  let days = 7
  try {
    const { value } = await ElMessageBox.prompt('延期天数（1-90）', '延期提醒', {
      inputValue: '7',
      confirmButtonText: '确定',
      cancelButtonText: '取消',
    })
    const parsed = Number(value)
    if (!Number.isInteger(parsed) || parsed < 1 || parsed > 90) {
      ElMessage.error('延期天数须为 1-90 的整数')
      return
    }
    days = parsed
  } catch {
    return
  }
  await runAction(() => snoozeReminder(r.id, days), `已延期 ${days} 天`)
}

async function reopenItem(r: ReminderItem) {
  await runAction(() => reopenReminder(r.id), '已重新打开')
}

const formatTime = (t?: string | null): string => format.formatShortDateTimePadded(t)

onMounted(load)
</script>

<style lang="scss" scoped>
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
.stats-row {
  display: flex;
  gap: 8px;
  margin-bottom: 14px;
}
.filters {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
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
.reminder-item.is-done {
  opacity: 0.75;
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
.rnote {
  color: var(--el-text-color-secondary);
  font-size: 12px;
  margin-top: 2px;
}
.rsnooze {
  color: var(--el-color-warning);
  font-size: 12px;
  margin-top: 2px;
}
.rtime {
  color: var(--el-text-color-placeholder);
  font-size: 12px;
  flex-shrink: 0;
}
.ractions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}
</style>
