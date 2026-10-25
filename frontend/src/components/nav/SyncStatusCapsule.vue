<template>
  <!-- 单一根元素：多根 + 具名插槽组合会触发 "Codegen node is missing" 编译错误
       （仓库在 ErrorBoundary 上已踩过同类坑），故显式包一层。 -->
  <div class="sync-status">
    <el-tooltip :content="tooltipText" placement="bottom">
      <span
        class="sync-capsule"
        :class="`sync-capsule--${summary.level}`"
        role="button"
        tabindex="0"
        :aria-label="ariaLabel"
        data-testid="sync-capsule"
        @click="openDrawer"
        @keydown.enter.prevent="openDrawer"
        @keydown.space.prevent="openDrawer"
      >
        <span class="sync-capsule__dot" aria-hidden="true" />
        <span class="sync-capsule__text">{{ capsuleText }}</span>
      </span>
    </el-tooltip>

    <el-drawer
      :model-value="drawerVisible"
      title="数据同步台账"
      size="420px"
      data-testid="sync-drawer"
      @update:model-value="onDrawerChange"
    >
      <div class="sync-drawer" data-testid="sync-drawer-body">
        <el-alert
          v-if="error"
          type="warning"
          :closable="false"
          show-icon
          class="sync-drawer__alert"
          :title="`同步日志加载失败：${error}`"
        />

        <div class="sync-drawer__summary" data-testid="sync-drawer-summary">
          最近同步：<strong>{{ summary.relativeLabel }}</strong>
          <span v-if="summary.lastAction">（{{ lastActionText }}）</span>
        </div>

        <el-table
          v-if="drawerRows.length > 0"
          :data="drawerRows"
          border
          size="small"
          data-testid="sync-drawer-table"
        >
          <el-table-column prop="time" label="时间" min-width="150" />
          <el-table-column prop="action" label="动作" width="110" />
          <el-table-column prop="status" label="结果" width="90" />
          <el-table-column prop="message" label="说明" min-width="140" />
        </el-table>

        <el-empty v-else-if="!loading" description="暂无同步记录（尚未导出/导入过数据）" />
      </div>

      <template #footer>
        <el-button size="small" data-testid="sync-drawer-refresh" @click="refresh">刷新</el-button>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
/**
 * 顶栏「同步状态胶囊」+ 台账抽屉（2026-10-25 / ④）
 *
 * 胶囊只显示"最近一次同步距今多久"，颜色分级：正常 / 提醒 / 过期 / 未知；
 * 点击展开最近若干条同步台账（只读 `/data-sync/logs`，不新增后端接口）。
 * 接口失败不弹错（顶栏常驻，弹错会污染每个页面），只在抽屉里说明原因。
 *
 * 展示格式化（动作中文名/时间/占位符）放在 `utils/syncLogFormat` 并在此以计算属性求值：
 * 若写在 el-table 的插槽里，单测 stub 掉表格后插槽不执行 → 函数覆盖率到不了 100%。
 */
import { computed, onMounted } from 'vue'

import { useSyncStatus } from '@/composables/useSyncStatus'
import { actionLabel, toDrawerRows } from '@/utils/syncLogFormat'

const { logs, loading, error, drawerVisible, summary, refresh, openDrawer, closeDrawer } =
  useSyncStatus()

const LEVEL_TEXT: Record<string, string> = {
  ok: '已同步',
  warn: '待同步',
  stale: '久未同步',
  unknown: '未同步',
}

const drawerRows = computed(() => toDrawerRows(logs.value))

const lastActionText = computed(() => actionLabel(summary.value.lastAction))

const capsuleText = computed(() => {
  if (summary.value.level === 'unknown') return LEVEL_TEXT.unknown
  return summary.value.relativeLabel
})

const tooltipText = computed(() => {
  const action = summary.value.lastAction ? actionLabel(summary.value.lastAction) : '同步'
  return `最近一次${action}：${summary.value.relativeLabel}（点击查看台账）`
})

// level 恒为 LEVEL_TEXT 的四个键之一，不写 `|| ''` 兜底（那会留下永不进入的分支）
const ariaLabel = computed(
  () => `数据同步状态：${LEVEL_TEXT[summary.value.level]}，${summary.value.relativeLabel}`
)

function onDrawerChange(value: boolean): void {
  if (value) {
    openDrawer()
    return
  }
  closeDrawer()
}

onMounted(() => {
  // 首屏只拉一次；失败静默（胶囊显示"未同步"，不打扰用户）
  void refresh()
})
</script>

<style scoped lang="scss">
.sync-capsule {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 28px;
  padding: 0 10px;
  margin-right: 8px;
  border-radius: var(--radius-pill);
  border: 1px solid var(--color-card-border);
  background: var(--color-white-90);
  font-size: 12px;
  color: var(--color-text-secondary);
  cursor: pointer;
  user-select: none;

  &:focus-visible {
    outline: 2px solid var(--color-primary);
    outline-offset: 2px;
  }
}

.sync-capsule__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-text-placeholder);
}

.sync-capsule--ok .sync-capsule__dot {
  background: var(--color-success);
}

.sync-capsule--warn .sync-capsule__dot {
  background: var(--color-warning);
}

.sync-capsule--stale .sync-capsule__dot {
  background: var(--color-danger);
}

.sync-drawer__alert {
  margin-bottom: 12px;
}

.sync-drawer__summary {
  margin-bottom: 12px;
  font-size: 13px;
  color: var(--color-text-secondary);
}
</style>
