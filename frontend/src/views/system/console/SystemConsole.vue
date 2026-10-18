<template>
  <div class="system-console" data-testid="system-console">
    <div class="console-header">
      <div class="console-heading">
        <h2 class="console-title" data-testid="system-console-title">{{ boardTitle }}</h2>
        <p class="console-description" data-testid="system-console-description">
          {{ boardDescription }}
        </p>
      </div>
      <el-button
        class="console-back"
        data-testid="system-console-back"
        text
        type="primary"
        @click="goDashboard"
      >
        返回工作台
      </el-button>
    </div>

    <!-- 菜单尚未就绪时只显示骨架，避免把"未加载"误判成"无权限" -->
    <el-skeleton v-if="booting" :rows="6" animated data-testid="system-console-loading" />

    <el-tabs
      v-else-if="renderableTabs.length"
      v-model="currentTab"
      class="console-tabs"
      data-testid="system-console-tabs"
    >
      <el-tab-pane v-for="tab in renderableTabs" :key="tab.key" :label="tab.label" :name="tab.key">
        <!-- 仅渲染当前 Tab 的组件：其余 Tab 的异步模块不会被加载 -->
        <div
          v-if="currentTab === tab.key"
          class="console-pane"
          :data-testid="`system-console-pane-${tab.key}`"
        >
          <component :is="TAB_COMPONENTS[tab.key]" />
        </div>
      </el-tab-pane>
    </el-tabs>

    <el-empty v-else :description="EMPTY_HINT" data-testid="system-console-empty">
      <el-button type="primary" data-testid="system-console-empty-back" @click="goDashboard">
        返回工作台
      </el-button>
    </el-empty>
  </div>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent, onMounted, ref } from 'vue'
import type { Component } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMenuStore } from '@/stores/menu'
import type { MenuEntry, MenuTab } from '@/stores/menu'
import { useRouterSafe } from '@/composables/useRouterSafe'

/**
 * 系统管理聚合页（契约 §4/§5）：
 * 路由 `/system/console/:group`（group ∈ org/security/ops/storage/settings/about），
 * 从后端下发的 v2 菜单 sections 中定位 kind==='console' 的节点，按 tabs 渲染页内切换。
 * 当前 Tab 由 query.tab 决定（默认第一个可渲染 Tab），切换时用 router.replace 同步 query。
 * 复用旧页面组件、旧路由全部保留，聚合页只是新的入口形态。
 */
defineOptions({ name: 'SystemConsole' })

/** 板块兜底标题/说明：后端 console 节点缺失（无权限）或未知 group 时仍能给出可读标题 */
const GROUP_META: Record<string, { label: string; description: string }> = {
  org: {
    label: '组织与权限',
    description: '用户、角色、菜单、权限包与组织架构的集中配置入口。',
  },
  security: {
    label: '安全与审计',
    description: '审计日志、零信任、密钥、数据分级与机器码等安全能力。',
  },
  ops: {
    label: '运维与监控',
    description: '系统总览、健康检查、实时监控、缓存与后台任务的运维入口。',
  },
  storage: {
    label: '备份与存储',
    description: '备份恢复、分片上传、地图瓦片与配置/管控包管理。',
  },
  settings: {
    label: '系统设置',
    description: '国际化、邮件与更新日志等基础系统配置。',
  },
  about: {
    label: '关于与反馈',
    description: '系统信息、意见反馈、帮助中心与管理面板。',
  },
}

/** 无权限 / 未知 group / 无可渲染 Tab 时统一空态文案 */
const EMPTY_HINT = '当前板块不存在、无访问权限或暂无可渲染的页签，请返回工作台。'

/**
 * 契约 §5：Tab key → 旧页面组件。
 * 必须使用 defineAsyncComponent 懒加载：一方面避免进入聚合页时一次性加载全部系统页，
 * 另一方面保证本 .vue 的模块求值不触发任何子 .vue（单执行者/覆盖率合并不变量：
 * 子页仍由其专属测试唯一真实执行）。
 */
const TAB_COMPONENTS: Record<string, Component> = {
  'users-orgs': defineAsyncComponent(() => import('@/views/system/UserManagement.vue')),
  roles: defineAsyncComponent(() => import('@/views/system/Role.vue')),
  menus: defineAsyncComponent(() => import('@/views/system/Menu.vue')),
  'system-permission-packs': defineAsyncComponent(
    () => import('@/views/system/PermissionPacks.vue')
  ),
  organizations: defineAsyncComponent(() => import('@/views/organization/List.vue')),
  audit: defineAsyncComponent(() => import('@/views/system/AuditManagement.vue')),
  'zero-trust': defineAsyncComponent(() => import('@/views/system/ZeroTrust.vue')),
  secrets: defineAsyncComponent(() => import('@/views/system/SecretsManagement.vue')),
  'data-tier': defineAsyncComponent(() => import('@/views/system/DataTier.vue')),
  encryption: defineAsyncComponent(() => import('@/views/system/EncryptionSettings.vue')),
  'machine-code': defineAsyncComponent(() => import('@/views/admin/MachineCodeManagement.vue')),
  'system-overview': defineAsyncComponent(() => import('@/views/system/SettingsOverview.vue')),
  'health-check': defineAsyncComponent(() => import('@/views/system/HealthCheck.vue')),
  monitor: defineAsyncComponent(() => import('@/views/system/MonitoringDashboard.vue')),
  cache: defineAsyncComponent(() => import('@/views/system/CacheManagement.vue')),
  tasks: defineAsyncComponent(() => import('@/views/system/TaskManager.vue')),
  environment: defineAsyncComponent(() => import('@/views/system/EnvCheck.vue')),
  'error-reports': defineAsyncComponent(() => import('@/views/system/ErrorReports.vue')),
  backup: defineAsyncComponent(() => import('@/views/system/BackupManagement.vue')),
  'chunked-upload': defineAsyncComponent(() => import('@/views/system/ChunkedUploadManager.vue')),
  'map-tiles': defineAsyncComponent(() => import('@/views/system/MapTileManager.vue')),
  'control-package': defineAsyncComponent(() => import('@/views/system/ControlPackage.vue')),
  'config-package': defineAsyncComponent(() => import('@/views/system/ConfigPackage.vue')),
  i18n: defineAsyncComponent(() => import('@/views/system/I18nManagement.vue')),
  email: defineAsyncComponent(() => import('@/views/system/EmailSettings.vue')),
  'update-logs': defineAsyncComponent(() => import('@/views/system/UpdateLogs.vue')),
  about: defineAsyncComponent(() => import('@/views/system/About.vue')),
  feedback: defineAsyncComponent(() => import('@/views/system/Feedback.vue')),
  help: defineAsyncComponent(() => import('@/views/help/HelpCenter.vue')),
  'admin-dashboard': defineAsyncComponent(() => import('@/views/admin/AdminDashboard.vue')),
}

const route = useRoute()
const router = useRouter()
const menuStore = useMenuStore()
const { pushSafe } = useRouterSafe()

/** 当前板块分组（org/security/ops/storage/settings/about） */
const group = computed(() => String(route.params.group))

/** 后端 console 节点声明的聚合页路由 */
const consolePath = computed(() => `/system/console/${group.value}`)

/** 从 v2 sections 中定位当前板块的 console 节点（未下发 = 无权限或未知 group） */
const consoleNode = computed<MenuEntry | null>(() => {
  for (const section of menuStore.sections) {
    for (const item of section.items) {
      if (item.kind === 'console' && item.path === consolePath.value) {
        return item
      }
    }
  }
  return null
})

/**
 * 可见且可渲染的 Tab：
 * 后端已按权限裁剪 tabs；前端再用 canAccessMenu（含 tabs.key 与超管旁路）兜底，
 * 并剔除前端无组件映射的未知 key，避免渲染空白页。
 */
const renderableTabs = computed<MenuTab[]>(() =>
  (consoleNode.value?.tabs ?? []).filter(
    (tab) => Boolean(TAB_COMPONENTS[tab.key]) && menuStore.canAccessMenu(tab.key)
  )
)

/** 板块标题：优先后端菜单节点 label，其次静态板块元数据，未知 group 用兜底文案 */
const boardTitle = computed(
  () => consoleNode.value?.label || GROUP_META[group.value]?.label || '未知板块'
)

/** 板块说明：静态元数据（后端 schema 不含 description 字段） */
const boardDescription = computed(
  () => GROUP_META[group.value]?.description || '该板块不存在或已下线，请从左侧菜单重新选择。'
)

/**
 * 当前 Tab：query.tab 是唯一来源，非法/缺失时回退首个可渲染 Tab。
 * setter 通过 router.replace 同步 query —— 页内切换不新增历史记录，
 * 同时保证刷新/复制链接后仍停留在同一 Tab。
 */
const currentTab = computed<string>({
  get() {
    const keys = renderableTabs.value.map((tab) => tab.key)
    const queryTab = (route.query.tab as string | undefined) || ''
    return keys.includes(queryTab) ? queryTab : keys[0]
  },
  set(key: string) {
    void router.replace({ path: route.path, query: { ...route.query, tab: key } })
  },
})

/** 菜单未加载完成时显示骨架，避免把"未加载"误判成"无权限" */
const booting = ref(!menuStore.loaded)

onMounted(async () => {
  // 深链/刷新场景：layout 的 fetchMenus 可能尚未完成，这里按共享 inflight 兜底一次
  if (!menuStore.loaded && !menuStore.loading) {
    try {
      await menuStore.fetchMenus()
    } catch {
      // 菜单加载失败不阻断页面：空态提示用户，真实权限仍由后端接口兜底
    }
  }
  booting.value = false
})

function goDashboard() {
  pushSafe('/dashboard')
}
</script>

<style scoped lang="scss">
.system-console {
  padding: 20px;

  .console-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 16px;
  }

  .console-title {
    margin: 0 0 6px;
    font-size: 20px;
    color: var(--color-text-primary);
  }

  .console-description {
    margin: 0;
    font-size: 13px;
    color: var(--color-text-secondary);
  }

  .console-back {
    flex-shrink: 0;
  }

  .console-tabs {
    min-height: 200px;
  }

  .console-pane {
    padding-top: 4px;
  }
}
</style>
