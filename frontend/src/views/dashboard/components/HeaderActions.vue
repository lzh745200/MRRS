<template>
  <div class="header-actions" data-test="dashboard-header-actions">
    <!-- 全局搜索 -->
    <GlobalSearch class="header-search" />
    <el-button
      data-test="btn-new-project"
      type="primary"
      :icon="Plus"
      @click="pushSafe('/projects/create')"
    >
      新建项目
    </el-button>
    <el-button data-test="btn-analysis" :icon="TrendCharts" @click="pushSafe('/data-analysis')">
      数据分析
    </el-button>
    <el-button
      v-if="isAdmin"
      data-test="btn-backup"
      :icon="Upload"
      :loading="backingUp"
      @click="$emit('backup')"
    >
      {{ backingUp ? '备份中...' : '一键备份' }}
    </el-button>
    <!-- 更多菜单 -->
    <el-dropdown trigger="click" @command="handleMoreCommand">
      <el-button :icon="MoreFilled" />
      <template #dropdown>
        <el-dropdown-menu>
          <el-dropdown-item command="layout">
            <el-icon><Grid /></el-icon> 自定义布局
          </el-dropdown-item>
          <el-dropdown-item command="bigscreen" divided>
            <el-icon><Monitor /></el-icon> 成效大屏
          </el-dropdown-item>
        </el-dropdown-menu>
      </template>
    </el-dropdown>
  </div>
</template>

<script setup lang="ts">
/**
 * 工作台页头操作区（W11-T45：原 views/dashboard/PageHeader.vue 去重后的产物）
 *
 * 页头骨架由共享 standard 件 `@/components/common/PageHeader.vue` 提供
 * （title/subtitle/#extra），本组件只承载工作台专属操作：
 * 全局搜索 + 新建项目 / 数据分析 / 一键备份（管理员）+ 更多菜单。
 *
 * - isAdmin / backingUp 由页面（index.vue）注入，避免在工作台内出现第二处
 *   管理员判定与备份状态来源；
 * - backup 不在本组件内直连 API，向页面 emit，复用页面既有 handleBackup
 *   与 QuickActions 的备份入口，保持同页只有一个备份实现。
 */
import { useRouterSafe } from '@/composables/useRouterSafe'
import { Plus, TrendCharts, Upload, MoreFilled, Grid, Monitor } from '@element-plus/icons-vue'
import GlobalSearch from './GlobalSearch.vue'

defineProps<{
  /** 管理员（页面按 roleAccess.isAdminUser 判定后注入） */
  isAdmin: boolean
  /** 备份进行中（按钮 loading 态） */
  backingUp: boolean
}>()

const emit = defineEmits<{
  (e: 'toggle-layout'): void
  (e: 'backup'): void
}>()

const { pushSafe } = useRouterSafe()

function handleMoreCommand(cmd: string) {
  if (cmd === 'bigscreen') {
    pushSafe('/bigscreen')
    return
  }
  if (cmd === 'layout') {
    emit('toggle-layout')
  }
}
</script>

<style scoped lang="scss">
.header-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.header-search {
  width: 320px;
  flex-shrink: 0;
}

@media (max-width: 768px) {
  .header-search {
    display: none;
  }
}
</style>
