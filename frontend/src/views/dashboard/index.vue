<template>
  <div class="dashboard-home dashboard-modern">
    <PageHeader @toggle-layout="showLayoutEditor = !showLayoutEditor" />

    <!-- 自定义布局面板 -->
    <transition name="slide">
      <div v-if="showLayoutEditor" class="layout-editor">
        <div class="layout-header">
          <span class="layout-title">
            <el-icon><Setting /></el-icon> 自定义布局
          </span>
          <span v-if="layoutSaved" class="layout-saved"
            ><el-icon><Select /></el-icon> 已保存</span
          >
          <el-select v-model="layoutPreset" size="small" style="width: 140px" @change="applyPreset">
            <el-option label="默认布局" value="default" />
            <el-option label="紧凑模式" value="compact" />
            <el-option label="展开全部" value="expand" />
            <el-option label="管理员模板" value="role_admin" />
            <el-option label="管理模板" value="role_officer" />
            <el-option label="访客模板" value="role_viewer" />
          </el-select>
          <el-button size="small" text @click="resetLayout">恢复默认</el-button>
          <el-button size="small" type="primary" @click="showLayoutEditor = false">完成</el-button>
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
            <el-switch v-model="section.visible" size="small" @change="onToggle" />
          </div>
        </div>
      </div>
    </transition>

    <!-- KPI 统计横条 -->
    <div v-if="visible.kpi" class="kpi-strip">
      <div class="kpi-toolbar">
        <span class="auto-refresh-hint">
          <el-icon><Refresh /></el-icon>
          数据每 60 秒自动刷新
        </span>
        <el-tooltip content="刷新数据" placement="top">
          <el-button
            data-test="btn-refresh-kpi"
            size="small"
            circle
            :icon="Refresh"
            @click="refreshKpiData"
          />
        </el-tooltip>
      </div>
      <KpiCards :key="kpiRefreshKey" />
    </div>

    <!-- 常用快捷操作（按角色权限显示） -->
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

    <!-- 中部：图表 + 快捷入口 -->
    <div class="middle-row">
      <div v-if="visible.charts" class="chart-panel">
        <div class="panel-header">
          <el-icon><TrendCharts /></el-icon>
          <span>数据趋势</span>
        </div>
        <ChartRow />
      </div>
      <div v-if="visible.quickActions" class="quick-panel">
        <div class="panel-header">
          <el-icon><Grid /></el-icon>
          <span>快捷入口</span>
          <el-button size="small" text @click="showLayoutEditor = !showLayoutEditor">
            <el-icon><Setting /></el-icon>
          </el-button>
        </div>
        <QuickActions
          :is-manager="isManager"
          :is-admin="isAdmin"
          :backing-up="backingUp"
          @backup="handleBackup"
          @restore="handleRestore"
        />
      </div>
    </div>

    <!-- 最新动态（全宽） -->
    <div v-if="visible.info" class="info-panel">
      <div class="panel-header">
        <el-icon><Clock /></el-icon>
        <span>最新动态</span>
      </div>
      <InfoRow />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive, watch, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Setting,
  Rank,
  TrendCharts,
  Grid,
  Clock,
  Select,
  Refresh,
  Plus,
  House,
  Money,
  EditPen,
} from '@element-plus/icons-vue'
import PageHeader from './PageHeader.vue'
import KpiCards from './KpiCards.vue'
import QuickActions from './components/QuickActions.vue'
import ChartRow from './ChartRow.vue'
import InfoRow from './InfoRow.vue'
import { useUserStore } from '@/stores/user'
import { createBackup } from '@/api/backup'
import { useRouterSafe } from '@/composables/useRouterSafe'

const { pushSafe } = useRouterSafe()
const backingUp = ref(false)

const showLayoutEditor = ref(false)
const userStore = useUserStore()
const isAdmin = computed(
  () =>
    ['admin', 'super_admin'].includes(userStore.currentUser?.role || '') ||
    !!userStore.currentUser?.is_superuser
)
const isManager = computed(() => isAdmin.value)

// 布局持久化
const STORAGE_KEY = 'dashboard_layout_v2'
const defaults = [
  { key: 'kpi', label: '数据概览', visible: true },
  { key: 'charts', label: '数据趋势', visible: true },
  { key: 'quickActions', label: '快捷入口', visible: true },
  { key: 'info', label: '最新动态', visible: true },
]
const layoutSections = reactive<{ key: string; label: string; visible: boolean }[]>([])

function loadLayout() {
  const VALID_KEYS = new Set(['kpi', 'charts', 'quickActions', 'info'])
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
  setTimeout(() => (layoutSaved.value = false), 2000)
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
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  max-width: 1440px;
  margin: 0 auto;
}

.kpi-strip {
  /* KpiCards 内部自行管理 5 列布局 */
}

.kpi-toolbar {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  margin-bottom: 10px;
}

.auto-refresh-hint {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #909399;

  .el-icon {
    font-size: 13px;
  }
}

.shortcut-strip {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  padding: 12px 20px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}

.shortcut-label {
  font-size: 14px;
  font-weight: 700;
  color: #1b4332;
  margin-right: 4px;
}

.middle-row {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 20px;
  align-items: start;
  @media (max-width: 960px) {
    grid-template-columns: 1fr;
  }
}

.chart-panel,
.quick-panel,
.info-panel {
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
  overflow: hidden;
}

.panel-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 14px 20px;
  font-size: 15px;
  font-weight: 700;
  color: #1b4332;
  background: linear-gradient(135deg, #f0f4f3, #fff);
  border-bottom: 1px solid #e2e8e4;

  .el-button {
    margin-left: auto;
  }
}

// 布局编辑器
.layout-editor {
  background: #fff;
  border: 2px solid var(--el-color-primary);
  border-radius: 12px;
  padding: 16px 20px;
}
.layout-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid #ebeef5;
}
.layout-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
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
  background: #f5f7fa;
  border-radius: 8px;
  min-width: 160px;
  cursor: grab;
  user-select: none;
  &:active {
    cursor: grabbing;
  }
}
.layout-saved {
  font-size: 12px;
  color: var(--color-success);
  margin-right: 8px;
  display: inline-flex;
  align-items: center;
}

.layout-saved .el-icon {
  margin-right: 4px;
}
.layout-hint {
  font-size: 12px;
  color: #909399;
  margin: 0 0 10px;
  padding-left: 2px;
}
.drag-over {
  background: var(--el-color-primary-light-9) !important;
  border-color: var(--el-color-primary) !important;
  transform: scale(1.03);
}
.drag-handle {
  color: #909399;
}

.slide-enter-active,
.slide-leave-active {
  transition: all 0.25s ease;
}
.slide-enter-from,
.slide-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}
</style>
