<template>
  <div class="dashboard-home dashboard-modern">
    <PageHeader :title="welcomeTitle" :subtitle="formattedDate" :level="1">
      <template #title>
        欢迎回来，<span class="welcome-name">{{ displayName }}</span>
      </template>
      <template #extra>
        <HeaderActions
          :is-admin="isAdmin"
          :backing-up="backingUp"
          @toggle-layout="showLayoutEditor = !showLayoutEditor"
          @backup="handleBackup"
        />
      </template>
    </PageHeader>

    <!-- 自定义布局面板 -->
    <transition name="slide">
      <div v-if="showLayoutEditor" class="layout-editor app-card">
        <div class="layout-header">
          <span class="layout-title">
            <el-icon><Setting /></el-icon> 自定义布局
          </span>
          <span v-if="layoutSaved" class="layout-saved"
            ><el-icon><Select /></el-icon> 已保存</span
          >
          <el-select v-model="layoutPreset" @change="applyPreset">
            <el-option label="默认布局" value="default" />
            <el-option label="紧凑模式" value="compact" />
            <el-option label="展开全部" value="expand" />
            <el-option label="管理员模板" value="role_admin" />
            <el-option label="管理模板" value="role_officer" />
            <el-option label="访客模板" value="role_viewer" />
          </el-select>
          <el-button text @click="resetLayout">恢复默认</el-button>
          <el-button type="primary" @click="showLayoutEditor = false">完成</el-button>
        </div>
        <p class="layout-hint">拖拽排序 · 开关控制可见性</p>
        <div class="layout-sections">
          <div
            v-for="section in layoutSections"
            :key="section.key"
            class="layout-item"
            :class="{ 'drag-over': dragOverKey === section.key }"
            draggable="true"
            @dragstart="onDragStart($event, section.key)"
            @dragover.prevent="onDragOver(section.key)"
            @dragleave="onDragLeave"
            @drop="onDrop($event, section.key)"
            @dragend="onDragEnd"
          >
            <el-icon class="drag-handle"><Rank /></el-icon>
            <span>{{ section.label }}</span>
            <el-switch v-model="section.visible" @change="onToggle" />
          </div>
        </div>
      </div>
    </transition>

    <!-- KPI 统计卡网格 -->
    <section v-if="visible.kpi" class="dashboard-section kpi-strip app-card">
      <div class="section-head">
        <h2 class="section-title">数据概览</h2>
        <div class="kpi-toolbar">
          <span class="auto-refresh-hint">
            <el-icon><Refresh /></el-icon>
            数据每 60 秒自动刷新
          </span>
          <el-tooltip content="刷新数据" placement="top">
            <el-button data-test="btn-refresh-kpi" circle :icon="Refresh" @click="refreshKpiData" />
          </el-tooltip>
        </div>
      </div>
      <KpiCards :key="kpiRefreshKey" />
    </section>

    <!-- 待办清单 -->
    <TodoListPanel v-if="visible.todos" class="dashboard-section" />

    <!-- 图表区（项目进度 / 经费概览 两列） -->
    <ChartRow v-if="visible.charts" class="dashboard-section chart-panel" />

    <!-- 快捷入口 / 近期动态 -->
    <div class="bottom-row">
      <section v-if="visible.quickActions" class="dashboard-section quick-panel app-card">
        <div class="section-head">
          <h2 class="section-title">快捷入口</h2>
          <el-button
            text
            class="layout-toggle"
            data-testid="dashboard-layout-toggle"
            @click="showLayoutEditor = !showLayoutEditor"
          >
            <el-icon><Setting /></el-icon>
          </el-button>
        </div>
        <div class="shortcut-strip">
          <span class="shortcut-label">常用操作</span>
          <el-button
            v-if="isAdmin"
            type="primary"
            plain
            :icon="Plus"
            @click="pushSafe('/projects/create')"
          >
            新建项目
          </el-button>
          <el-button
            v-if="isAdmin"
            type="success"
            plain
            :icon="House"
            @click="pushSafe('/supported-villages')"
          >
            新增帮扶村
          </el-button>
          <el-button type="warning" plain :icon="Money" @click="pushSafe('/funds/user')">
            资金申请
          </el-button>
          <el-button type="info" plain :icon="EditPen" @click="pushSafe('/data-package/report')">
            数据上报
          </el-button>
        </div>
        <QuickActions
          :is-manager="isManager"
          :is-admin="isAdmin"
          :backing-up="backingUp"
          @backup="handleBackup"
          @restore="handleRestore"
        />
      </section>

      <InfoRow v-if="visible.info" class="dashboard-section info-panel" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive, watch, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Setting,
  Rank,
  Select,
  Refresh,
  Plus,
  House,
  Money,
  EditPen,
} from '@element-plus/icons-vue'
import PageHeader from '@/components/common/PageHeader.vue'
import HeaderActions from './components/HeaderActions.vue'
import KpiCards from './KpiCards.vue'
import TodoListPanel from './components/TodoListPanel.vue'
import QuickActions from './components/QuickActions.vue'
import ChartRow from './ChartRow.vue'
import InfoRow from './InfoRow.vue'
import { useUserStore } from '@/stores/user'
import { useAuthStore } from '@/stores/auth'
import { createBackup } from '@/api/backup'
import { useRouterSafe } from '@/composables/useRouterSafe'
import { isAdminUser } from '@/utils/roleAccess'
import { format } from '@/utils'

const { pushSafe } = useRouterSafe()
const backingUp = ref(false)

const showLayoutEditor = ref(false)
const userStore = useUserStore()
const authStore = useAuthStore()
// M47：管理员判定统一走 roleAccess.isAdminUser()（读 AuthStorage 并 normalizeRole），
// 不再硬编码原始 role —— 存量旧角色 manager/approval_leader 归一化后即 admin，
// 原实现会把他们误判为非管理员（隐藏备份/恢复入口），与路由守卫口径不一致。
// userStore 仍在使用（布局持久化/用户信息），保留引用。
// 显式传入 store 中的响应式用户档案：既保持对 currentUser 的响应式依赖
//（store 变化时重新计算），也让测试替身走同一条判定路径。
const isAdmin = computed(() => isAdminUser(userStore.currentUser))
const isManager = computed(() => isAdmin.value)

// 页头欢迎语与日期副标题：页头骨架走共享 PageHeader 标准件（#title / #extra 插槽）
const displayName = computed(
  () => authStore.user?.full_name || authStore.user?.username || '管理员'
)
const welcomeTitle = computed(() => `欢迎回来，${displayName.value}`)
const formattedDate = computed(() => format.formatCnDate(new Date()))

// 布局持久化
const STORAGE_KEY = 'dashboard_layout_v2'
const defaults = [
  { key: 'kpi', label: '数据概览', visible: true },
  { key: 'todos', label: '待办清单', visible: true },
  { key: 'charts', label: '数据趋势', visible: true },
  { key: 'quickActions', label: '快捷入口', visible: true },
  { key: 'info', label: '最新动态', visible: true },
]
const layoutSections = reactive<{ key: string; label: string; visible: boolean }[]>([])

function loadLayout() {
  const VALID_KEYS = new Set(['kpi', 'todos', 'charts', 'quickActions', 'info'])
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw)
      if (
        Array.isArray(parsed) &&
        parsed.every((s: any) => s?.key && VALID_KEYS.has(s.key) && typeof s.visible === 'boolean')
      ) {
        layoutSections.splice(0, 99, ...parsed)
        return
      }
    }
  } catch {
    /* ignore */
  }
  layoutSections.splice(0, 99, ...defaults.map((s) => ({ ...s })))
}
function saveLayout() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify([...layoutSections]))
}
function resetLayout() {
  layoutSections.splice(0, 99, ...defaults.map((s) => ({ ...s })))
  saveLayout()
  ElMessage.success('已恢复默认布局')
}
const visible = computed(() => {
  const m: Record<string, boolean> = {}
  layoutSections.forEach((s) => (m[s.key] = s.visible))
  return m
})
watch(layoutSections, saveLayout, { deep: true })
onMounted(loadLayout)

// ── KPI 数据自动刷新（每 60 秒）+ 手动刷新 ──
const kpiRefreshKey = ref(0)
let kpiRefreshTimer: ReturnType<typeof setInterval> | null = null
// 「已保存」提示的复位定时器：卸载时一并清理，避免销毁后仍写 ref
let layoutSavedTimer: ReturnType<typeof setTimeout> | undefined

function refreshKpiData() {
  // 页签隐藏时不刷新，避免无效请求
  if (document.hidden) return
  // 通过变更 key 触发 KpiCards 重新挂载，复用其内部的数据加载逻辑
  kpiRefreshKey.value++
}

onMounted(() => {
  kpiRefreshTimer = setInterval(refreshKpiData, 60 * 1000)
})

onUnmounted(() => {
  if (kpiRefreshTimer) {
    clearInterval(kpiRefreshTimer)
    kpiRefreshTimer = null
  }
  clearTimeout(layoutSavedTimer) // undefined 为安全空操作
})

// 拖拽排序
let dragKey = ''
function onDragStart(_e: DragEvent, key: string) {
  dragKey = key
}
function onDrop(_e: DragEvent, targetKey: string) {
  if (!dragKey || dragKey === targetKey) return
  const from = layoutSections.findIndex((s) => s.key === dragKey)
  const to = layoutSections.findIndex((s) => s.key === targetKey)
  if (from >= 0 && to >= 0) {
    const [item] = layoutSections.splice(from, 1)
    layoutSections.splice(to, 0, item)
    saveLayout()
  }
}

const layoutSaved = ref(false)
const layoutPreset = ref('default')
const dragOverKey = ref('')

function onDragOver(key: string) {
  dragOverKey.value = key
}
function onDragLeave() {
  dragOverKey.value = ''
}
function onDragEnd() {
  dragOverKey.value = ''
  layoutSaved.value = false
  saveLayout()
  layoutSaved.value = true
}
function onToggle() {
  layoutSaved.value = false
  saveLayout()
  layoutSaved.value = true
}

function applyPreset(val: string) {
  if (val === 'default') layoutSections.splice(0, 99, ...defaults.map((s) => ({ ...s })))
  else if (val === 'compact') {
    layoutSections.splice(
      0,
      99,
      ...defaults.map((s) => ({
        ...s,
        visible: s.key === 'kpi' || s.key === 'quickActions',
      }))
    )
  } else if (val === 'expand') {
    layoutSections.splice(0, 99, ...defaults.map((s) => ({ ...s, visible: true })))
  } else if (val === 'role_admin') {
    // 管理员模板：全展开，突出系统管理功能
    layoutSections.splice(0, 99, ...defaults.map((s) => ({ ...s, visible: true })))
  } else if (val === 'role_officer') {
    // 管理模板：突出数据趋势和快捷入口，隐藏最新动态
    layoutSections.splice(
      0,
      99,
      ...defaults.map((s) => ({
        ...s,
        visible: s.key !== 'info',
      }))
    )
  } else if (val === 'role_viewer') {
    // 访客模板：仅显示数据概览和最新动态
    layoutSections.splice(
      0,
      99,
      ...defaults.map((s) => ({
        ...s,
        visible: s.key === 'kpi' || s.key === 'info',
      }))
    )
  }
  saveLayout()
  layoutSaved.value = true
  layoutSavedTimer = setTimeout(() => (layoutSaved.value = false), 2000)
}

async function handleBackup() {
  backingUp.value = true
  try {
    await createBackup({ description: '手动备份' })
    ElMessage.success('备份创建成功')
  } catch (e: any) {
    ElMessage.error(e?.message || '备份失败，请前往系统管理→备份管理重试')
  } finally {
    backingUp.value = false
  }
}
function handleRestore() {
  pushSafe('/system/backup')
}
</script>

<style scoped lang="scss">
.dashboard-home {
  padding: var(--spacing-lg, 20px);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg, 20px);
  max-width: 1440px;
  margin: 0 auto;
}

.dashboard-section {
  min-width: 0;
}

.app-card {
  background: var(--color-bg-card);
  border: 1px solid var(--color-card-border, var(--color-border-light));
  border-radius: var(--radius-card, 8px);
  padding: var(--spacing-lg, 20px);
  box-shadow: var(--shadow-card);
}

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-sm, 12px);
  margin-bottom: var(--spacing-sm, 12px);
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

.kpi-strip .section-head {
  margin-bottom: var(--spacing-md, 16px);
}

.welcome-name {
  color: var(--color-accent-gold);
}

.kpi-toolbar {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
}

.auto-refresh-hint {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: var(--text-xs, 12px);
  color: var(--color-text-secondary);

  .el-icon {
    font-size: var(--text-sm, 13px);
  }
}

.bottom-row {
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  gap: var(--spacing-lg, 20px);
  align-items: start;

  @media (max-width: 1200px) {
    grid-template-columns: 1fr;
  }
}

.quick-panel,
.info-panel {
  min-width: 0;
}

.shortcut-strip {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--spacing-sm, 12px);
  padding: var(--spacing-sm, 12px) 0;
  border-bottom: 1px solid var(--color-border-lighter);
  margin-bottom: var(--spacing-sm, 12px);
}

.shortcut-label {
  font-size: var(--text-sm, 13px);
  font-weight: 600;
  color: var(--color-text-primary);
  margin-right: 4px;
}

.layout-toggle {
  margin-left: auto;
}

// 布局编辑器
.layout-editor {
  background: var(--color-bg-card);
  border: 1px solid var(--color-primary);
  border-radius: var(--radius-card, 8px);
  padding: var(--spacing-md, 16px) var(--spacing-lg, 20px);
}

.layout-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm, 12px);
  margin-bottom: var(--spacing-sm, 12px);
  padding-bottom: 10px;
  border-bottom: 1px solid var(--color-border-light);
}

.layout-title {
  font-size: var(--text-md, 14px);
  font-weight: 600;
  color: var(--color-text-primary);
  flex: 1;
  display: flex;
  align-items: center;
  gap: 6px;
}

.layout-sections {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.layout-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  background: var(--color-bg-hover);
  border-radius: var(--radius-control, 6px);
  min-width: 160px;
  cursor: grab;
  user-select: none;

  &:active {
    cursor: grabbing;
  }
}

.layout-saved {
  font-size: var(--text-xs, 12px);
  color: var(--color-success);
  margin-right: 8px;
  display: inline-flex;
  align-items: center;
}

.layout-saved .el-icon {
  margin-right: 4px;
}

.layout-hint {
  font-size: var(--text-xs, 12px);
  color: var(--color-text-secondary);
  margin: 0 0 10px;
  padding-left: 2px;
}

.drag-over {
  background: var(--color-primary-100, var(--color-primary-light-8)) !important;
  border-color: var(--color-primary) !important;
  transform: scale(1.03);
}

.drag-handle {
  color: var(--color-text-secondary);
}

.slide-enter-active,
.slide-leave-active {
  transition: all var(--transition-normal, 0.25s) ease;
}

.slide-enter-from,
.slide-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}
</style>
