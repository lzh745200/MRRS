<template>
  <div class="layout-container">
    <!-- WCAG 2.1: 跳过导航链接 -->
    <a href="#main-content" class="skip-link">跳到主内容</a>

    <!-- ============================================================ -->
    <!-- 侧边栏 — 完全由后端菜单 v2 data 驱动（工作台固定第一）           -->
    <!-- ============================================================ -->
    <el-aside
      :width="
        isCollapsed
          ? 'var(--layout-sidebar-collapsed-width, 68px)'
          : 'var(--layout-sidebar-width, 240px)'
      "
      class="layout-aside"
      role="navigation"
      aria-label="主导航"
    >
      <!-- Logo 区域 -->
      <div class="aside-header">
        <img src="/images/badges/badge.png" class="app-logo" alt="系统标识" />
        <transition name="fade-title">
          <span v-show="!isCollapsed" class="app-title">帮扶管理信息系统</span>
        </transition>
      </div>

      <!-- 导航菜单 — 数据驱动：工作台固定第一 → 收藏 → 最近访问 → 后端板块 -->
      <el-scrollbar class="aside-scrollbar">
        <el-menu
          :default-active="route.path"
          :collapse="isCollapsed"
          router
          class="aside-menu"
          background-color="transparent"
          text-color="rgba(255,255,255,0.78)"
          active-text-color="#d4af37"
          :style="{
            '--el-menu-text-color': 'rgba(255,255,255,0.85)',
            '--el-menu-hover-text-color': '#ffffff',
            '--el-menu-active-color': '#d4af37',
            '--el-menu-bg-color': 'transparent',
            '--el-menu-hover-bg-color': 'rgba(255,255,255,0.08)',
          }"
        >
          <!-- ════ 工作台：固定第一（后端 sections 不含 dashboard） ════ -->
          <el-menu-item index="/dashboard" class="menu-item-dashboard">
            <el-icon><HomeFilled /></el-icon>
            <template #title>
              <span class="menu-title-text">工作台</span>
            </template>
          </el-menu-item>

          <!-- ════ 收藏（有数据时才显示） ════ -->
          <template v-if="visibleFavorites.length">
            <div v-show="!isCollapsed" class="menu-section-label">
              <span>收藏</span>
            </div>
            <el-menu-item
              v-for="entry in visibleFavorites"
              :key="`fav-${entry.key}`"
              :index="entry.path"
            >
              <el-icon><StarFilled /></el-icon>
              <template #title>
                <span class="menu-title-text">{{ entry.label }}</span>
              </template>
            </el-menu-item>
          </template>

          <!-- ════ 最近访问（有数据时才显示，已收藏项去重） ════ -->
          <template v-if="visibleRecents.length">
            <div v-show="!isCollapsed" class="menu-section-label">
              <span>最近访问</span>
            </div>
            <el-menu-item
              v-for="entry in visibleRecents"
              :key="`recent-${entry.key}`"
              :index="entry.path"
            >
              <el-icon><Clock /></el-icon>
              <template #title>
                <span class="menu-title-text">{{ entry.label }}</span>
              </template>
            </el-menu-item>
          </template>

          <!-- ════ 后端下发的板块（page / group / console 三种渲染） ════ -->
          <!-- 板块标题：W22 折叠/记忆；W23 当前板块金色竖条 + 收起态悬停/聚焦浮层 -->
          <template v-for="section in sidebarSections" :key="section.key">
            <div
              v-show="!isCollapsed"
              class="section-head"
              @mouseenter="showSectionFlyout(section.key, $event)"
              @mouseleave="hideSectionFlyout"
            >
              <button
                type="button"
                class="menu-section-label menu-section-toggle"
                :class="{ 'is-current': currentSectionKey === section.key }"
                :aria-expanded="isSectionExpanded(section.key)"
                @click="toggleSection(section.key)"
                @focus="showSectionFlyout(section.key, $event)"
              >
                <span>{{ section.label }}</span>
                <el-icon
                  class="section-toggle-icon"
                  :class="{ 'is-expanded': isSectionExpanded(section.key) }"
                >
                  <ArrowDown />
                </el-icon>
              </button>

              <!-- 收起态浮层：hover/键盘聚焦板块标题时浮出该板块子项（fixed 定位不被侧栏裁剪） -->
              <div
                v-if="flyoutSection && flyoutSection.key === section.key"
                class="section-flyout"
                :style="{ top: `${flyoutTop}px` }"
                data-test="section-flyout"
              >
                <div class="section-flyout-title">{{ section.label }}</div>
                <template v-for="item in section.items" :key="`flyout-${item.key}`">
                  <div v-if="item.kind === 'group'" class="section-flyout-group">
                    <div class="section-flyout-group-title">{{ item.label }}</div>
                    <button
                      v-for="child in item.children"
                      :key="`flyout-${child.key}`"
                      type="button"
                      class="section-flyout-item"
                      @click="goFlyoutPath(child.path)"
                    >
                      <span>{{ child.label }}</span>
                    </button>
                  </div>
                  <button
                    v-else
                    type="button"
                    class="section-flyout-item"
                    @click="goFlyoutPath(item.path)"
                  >
                    <el-icon><component :is="resolveMenuIcon(item.icon)" /></el-icon>
                    <span>{{ item.label }}</span>
                  </button>
                </template>
              </div>
            </div>
            <template v-for="item in section.items" :key="item.key">
              <!-- page：普通页面直链 -->
              <el-menu-item
                v-if="item.kind === 'page'"
                v-show="isSectionExpanded(section.key)"
                :index="item.path"
              >
                <el-icon><component :is="resolveMenuIcon(item.icon)" /></el-icon>
                <template #title>
                  <span class="menu-title-text">{{ item.label }}</span>
                </template>
              </el-menu-item>
              <!-- group：可折叠分组 -->
              <el-sub-menu
                v-else-if="item.kind === 'group'"
                v-show="isSectionExpanded(section.key)"
                :index="`group-${item.key}`"
                popper-class="aside-popper"
              >
                <template #title>
                  <el-icon><component :is="resolveMenuIcon(item.icon)" /></el-icon>
                  <span class="menu-title-text">{{ item.label }}</span>
                </template>
                <el-menu-item v-for="child in item.children" :key="child.key" :index="child.path">
                  <span>{{ child.label }}</span>
                </el-menu-item>
              </el-sub-menu>
              <!-- console：系统管理聚合页（页内 Tab 切换） -->
              <el-menu-item
                v-else
                v-show="isSectionExpanded(section.key)"
                :index="item.path"
                class="menu-item-console"
              >
                <el-icon><component :is="resolveMenuIcon(item.icon)" /></el-icon>
                <template #title>
                  <span class="menu-title-text">{{ item.label }}</span>
                </template>
              </el-menu-item>
            </template>
          </template>
        </el-menu>
      </el-scrollbar>
    </el-aside>

    <!-- ============================================================ -->
    <!-- 主内容区                                                       -->
    <!-- ============================================================ -->
    <el-container class="layout-main">
      <el-header class="layout-header">
        <div class="header-left">
          <el-button
            class="collapse-btn"
            :icon="isCollapsed ? Expand : Fold"
            text
            @click="isCollapsed = !isCollapsed"
          />
          <el-breadcrumb separator="">
            <el-breadcrumb-item :to="{ path: '/' }">
              <el-icon class="breadcrumb-home"><HomeFilled /></el-icon>
            </el-breadcrumb-item>
            <el-breadcrumb-item v-if="breadcrumb.sectionLabel">
              <span class="breadcrumb-section">{{ breadcrumb.sectionLabel }}</span>
            </el-breadcrumb-item>
            <el-breadcrumb-item v-if="breadcrumb.pageLabel">
              <span class="breadcrumb-current">{{ breadcrumb.pageLabel }}</span>
            </el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="header-right">
          <!-- ④ 同步状态胶囊：离线+介质传输下用户最关心"多久没对账"，原来埋在系统管理里 -->
          <SyncStatusCapsule />

          <!-- 菜单搜索（Ctrl+K） -->
          <el-tooltip content="菜单搜索 (Ctrl+K)" placement="bottom">
            <span
              class="theme-trigger menu-search-trigger"
              role="button"
              tabindex="0"
              aria-label="菜单搜索"
              @click="openMenuSearch"
            >
              <el-icon><Search /></el-icon>
            </span>
          </el-tooltip>

          <!-- 消息中心铃铛（未读角标） -->
          <el-tooltip content="消息中心" placement="bottom">
            <span class="theme-trigger message-bell" role="button" tabindex="0" @click="goMessages">
              <el-badge
                :value="unreadCount"
                :hidden="unreadCount === 0"
                :max="99"
                class="bell-badge"
              >
                <el-icon><Bell /></el-icon>
              </el-badge>
            </span>
          </el-tooltip>

          <!-- 主题切换器 -->
          <el-dropdown trigger="click" class="theme-switcher" @command="handleThemeChange">
            <span class="theme-trigger" role="button" tabindex="0" aria-label="切换外观主题">
              <el-icon><Brush /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item v-for="t in headerThemeOptions" :key="t.value" :command="t.value">
                  <el-icon class="theme-check">
                    <Check v-if="configStore.theme === t.value" />
                  </el-icon>
                  {{ t.label }}
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>

          <el-dropdown trigger="click" @command="handleCommand">
            <span class="user-info">
              <el-avatar :size="30" class="header-avatar">
                <el-icon><User /></el-icon>
              </el-avatar>
              <span class="username">{{ username }}</span>
              <el-icon class="dropdown-arrow"><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="appearance">
                  <el-icon><Setting /></el-icon> 外观设置
                </el-dropdown-item>
                <el-dropdown-item command="profile">
                  <el-icon><User /></el-icon> 个人中心
                </el-dropdown-item>
                <el-dropdown-item command="change-password">
                  <el-icon><Lock /></el-icon> 修改密码
                </el-dropdown-item>
                <el-dropdown-item divided command="logout">
                  <el-icon><SwitchButton /></el-icon> 退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main id="main-content" class="layout-content" role="main" aria-label="主内容区">
        <router-view v-slot="{ Component }">
          <!-- 注意：此处曾用 <transition name="fade" mode="out-in"> 包裹，但其子组件
               ErrorBoundary 根节点是 display:contents（无盒模型），opacity 过渡不产生
               transitionend，out-in 模式下旧节点永不完成离场 → 客户端路由切换后主内容区
               永久空白。淡入淡出为纯装饰，移除以根治；不要再加回 transition 包装。 -->
          <CommonErrorBoundary :key="route.path">
            <component :is="Component" v-if="Component" />
          </CommonErrorBoundary>
        </router-view>
      </el-main>

      <el-footer class="layout-footer" height="28px">
        <span>帮扶管理信息系统 v{{ systemVersion }}</span>
      </el-footer>
    </el-container>
    <!-- 移动端底部导航 -->
    <MobileBottomNav />
    <!-- 菜单搜索（Ctrl+K） -->
    <MenuSearchDialog v-model="menuSearchVisible" />
    <!-- 外观设置（W23）：W1 外观面板（主题 + 字号/密度/对比/简化） -->
    <el-dialog
      v-model="appearanceVisible"
      append-to-body
      title="外观设置"
      width="480px"
      class="appearance-dialog"
    >
      <AppearanceSettings />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, onUnmounted, watch } from 'vue'
import { SYSTEM_VERSION as systemVersion } from '@/config/constants'
import { ElNotification } from 'element-plus'
import { useAutoLock as useAutoLockModule } from '@/composables/useAutoLock'
import { useRoute } from 'vue-router'
import { useRouterSafe } from '@/composables/useRouterSafe'
import { useKeyboardShortcuts, type Shortcut } from '@/composables/useKeyboardShortcuts'
import { useAuthStore } from '@/stores/auth'
import { useMenuStore, type MenuEntry, type MenuKind } from '@/stores/menu'
import { useMenuFavorites } from '@/composables/useMenuFavorites'
import { useRecentMenus } from '@/composables/useRecentMenus'
import { resolveMenuIcon } from '@/components/nav/menuIcons'
import { useConfigStore, THEME_OPTIONS } from '@/stores/config'
import { cancelAllRequests, freezeRequests } from '@/api/request'
import MobileBottomNav from '@/components/layout/MobileBottomNav.vue'
import MenuSearchDialog from '@/components/nav/MenuSearchDialog.vue'
import SyncStatusCapsule from '@/components/nav/SyncStatusCapsule.vue'
import AppearanceSettings from '@/components/settings/AppearanceSettings.vue'
import {
  HomeFilled,
  Expand,
  Fold,
  User,
  Bell,
  ArrowDown,
  Lock,
  SwitchButton,
  Brush,
  Check,
  StarFilled,
  Clock,
  Search,
  Setting,
} from '@element-plus/icons-vue'

/** 侧栏普通链接（page / group children / 聚合页共用） */
interface SidebarLink {
  key: string
  label: string
  path: string
  icon?: string
}

/** 侧栏一级入口：page 直链 / group 可折叠 / console 聚合页 */
interface SidebarItem {
  key: string
  label: string
  icon?: string
  kind: MenuKind
  path: string
  children: SidebarLink[]
}

/** 侧栏板块 */
interface SidebarSection {
  key: string
  label: string
  items: SidebarItem[]
}

const route = useRoute()
const { pushSafe } = useRouterSafe()
const authStore = useAuthStore()
const menuStore = useMenuStore()
const configStore = useConfigStore()
const { favorites } = useMenuFavorites()
const { recentMenus: recents } = useRecentMenus()

// ── 侧栏数据驱动：后端菜单 v2 → 渲染模型（保证模板零防御分支） ──
function toSidebarLink(entry: MenuEntry): SidebarLink {
  return {
    key: entry.key,
    label: entry.label,
    path: entry.path as string,
    icon: entry.icon,
  }
}

function toSidebarItem(entry: MenuEntry): SidebarItem {
  const children = entry.kind === 'group' ? (entry.children as MenuEntry[]).map(toSidebarLink) : []
  return {
    key: entry.key,
    label: entry.label,
    icon: entry.icon,
    kind: entry.kind,
    path: entry.kind === 'group' ? '' : (entry.path as string),
    children,
  }
}

const sidebarSections = computed<SidebarSection[]>(() =>
  menuStore.sections.map((section) => ({
    key: section.key,
    label: section.label,
    items: section.items.map(toSidebarItem),
  }))
)

// ── 当前路由匹配（W23）：面包屑「板块 › 页面」+ 当前板块自动展开 ──
/** 路径命中：精确相等或位于其子路径（详情页归入列表入口） */
function matchMenuPath(current: string, target: string): boolean {
  return current === target || current.startsWith(`${target}/`)
}

/** 当前路由所属板块 key（工作台等未入板块的页面返回 null） */
function sectionKeyForPath(path: string): string | null {
  for (const section of sidebarSections.value) {
    for (const item of section.items) {
      const hit =
        item.kind === 'group'
          ? item.children.some((child) => matchMenuPath(path, child.path))
          : matchMenuPath(path, item.path)
      if (hit) return section.key
    }
  }
  return null
}

const currentSectionKey = computed<string | null>(() => sectionKeyForPath(route.path))

interface BreadcrumbInfo {
  sectionLabel: string
  pageLabel: string
}

/**
 * 面包屑（W23）：工作台固定「工作台」；其它页面「板块 › 页面」，无匹配时回退 meta.title。
 *
 * v1.15.0 收口：按**最长路径优先**匹配（原实现按遍历顺序，`/rural-works/list` 会先命中
 * 父级 `/rural-works` 的「工作首页」；详情页 `/households/:id` 同理需要更长前缀优先）。
 */
const breadcrumb = computed<BreadcrumbInfo>(() => {
  if (route.path === '/dashboard') return { sectionLabel: '', pageLabel: '工作台' }
  let best: { sectionLabel: string; pageLabel: string; pathLen: number } | null = null
  for (const section of sidebarSections.value) {
    for (const item of section.items) {
      const entries = item.kind === 'group' ? item.children : [item]
      for (const entry of entries) {
        if (!matchMenuPath(route.path, entry.path)) continue
        if (!best || entry.path.length > best.pathLen) {
          best = { sectionLabel: section.label, pageLabel: entry.label, pathLen: entry.path.length }
        }
      }
    }
  }
  if (best) return { sectionLabel: best.sectionLabel, pageLabel: best.pageLabel }
  return { sectionLabel: '', pageLabel: (route.meta?.title as string) || '' }
})

// ── 七大板块折叠（W22）：默认折叠，点击标题展开/收起，状态记忆到 localStorage ──
const EXPANDED_SECTIONS_KEY = 'nav:expanded-sections'

function readExpandedSections(): Set<string> {
  try {
    const raw = safeGetItem(EXPANDED_SECTIONS_KEY, 'local')
    if (!raw) return new Set()
    const parsed: unknown = JSON.parse(raw)
    if (!Array.isArray(parsed)) return new Set()
    return new Set(parsed.filter((key): key is string => typeof key === 'string'))
  } catch {
    return new Set()
  }
}

const expandedSections = ref<Set<string>>(readExpandedSections())

/** 板块是否展开（默认折叠） */
function isSectionExpanded(key: string): boolean {
  return expandedSections.value.has(key)
}

function persistExpandedSections(): void {
  safeSetItem(EXPANDED_SECTIONS_KEY, JSON.stringify([...expandedSections.value]), 'local')
}

/** 点击板块标题：展开/收起并持久化 */
function toggleSection(key: string): void {
  const next = new Set(expandedSections.value)
  if (next.has(key)) {
    next.delete(key)
  } else {
    next.add(key)
  }
  expandedSections.value = next
  flyoutSectionKey.value = null
  persistExpandedSections()
}

/** 当前板块自动展开并保持（W23） */
function ensureSectionExpanded(key: string): void {
  if (expandedSections.value.has(key)) return
  const next = new Set(expandedSections.value)
  next.add(key)
  expandedSections.value = next
  persistExpandedSections()
}

watch(
  currentSectionKey,
  (key) => {
    if (key) ensureSectionExpanded(key)
  },
  { immediate: true }
)

// ── 板块收起态浮层（W23）：hover / 键盘聚焦标题时浮出本板块子项 ──
const flyoutSectionKey = ref<string | null>(null)
const flyoutTop = ref(0)

/** 当前浮层板块（key 只可能来自已渲染板块，直接断言为非空） */
const flyoutSection = computed<SidebarSection | null>(() => {
  const key = flyoutSectionKey.value
  if (!key) return null
  return sidebarSections.value.find((section) => section.key === key) as SidebarSection
})

/** 显示浮层：仅板块收起时生效（展开态已有内联子项） */
function showSectionFlyout(key: string, event: Event): void {
  if (isSectionExpanded(key)) return
  flyoutSectionKey.value = key
  // 事件派发期间 currentTarget 必为该板块标题/包裹层
  const target = event.currentTarget as HTMLElement
  flyoutTop.value = Math.round(target.getBoundingClientRect().top)
}

function hideSectionFlyout(): void {
  flyoutSectionKey.value = null
}

/** 浮层子项跳转：先关闭浮层再导航 */
function goFlyoutPath(path: string): void {
  hideSectionFlyout()
  pushSafe(path)
}

// ── 收藏 / 最近访问（localStorage；仅展示当前用户仍可访问的入口） ──
const visibleFavorites = computed(() =>
  favorites.value.filter((entry) => menuStore.canAccessMenu(entry.key))
)
const favoriteKeys = computed(() => new Set(visibleFavorites.value.map((entry) => entry.key)))
const visibleRecents = computed(() =>
  recents.value.filter(
    (entry) => menuStore.canAccessMenu(entry.key) && !favoriteKeys.value.has(entry.key)
  )
)

// ── 菜单搜索弹窗（Ctrl+K） ──
const menuSearchVisible = ref(false)

function openMenuSearch(): void {
  menuSearchVisible.value = true
}

// ── 外观设置（W23）：W1 AppearanceSettings 落盘前为内联占位入口 ──
const appearanceVisible = ref(false)

function openAppearanceSettings(): void {
  appearanceVisible.value = true
}

// ── 消息中心未读角标 ──
const unreadCount = ref(0)

function goMessages() {
  pushSafe('/message')
}

async function loadUnreadCount() {
  try {
    const { getUnreadCount } = await import('@/api/message')
    const res: any = await getUnreadCount()
    const d = res?.data ?? res
    unreadCount.value = Number(d?.total ?? d?.count ?? 0) || 0
    // Electron 托盘角标与未读数联动（浏览器/麒麟模式无 electronAPI，可选链静默跳过）
    window.electronAPI?.updateTrayUnread?.(unreadCount.value)
    // T037：锁屏归来摘要——近 30 分钟内锁定过且有未读增量时弹一次
    if (authStore.isAuthenticated && consumeLockDigest(unreadCount.value)) {
      ElNotification({
        title: '欢迎回来',
        message: `您有 ${unreadCount.value} 条未读消息`,
        type: 'info',
        duration: 6000,
        onClick: () => pushSafe('/message'),
      })
    }
  } catch {
    /* 轮询失败静默 */
  }
}

// 未读数轮询定时器句柄必须放在 setup 作用域：
// 原实现把 onBeforeUnmount 注册在 onMounted 回调内部（此时无活动实例，
// 钩子不生效）且 timer 为回调局部变量 → 布局销毁后定时器仍在轮询，永久泄漏。
let unreadTimer: number | null = null

onMounted(() => {
  loadUnreadCount()
  // 每 60 秒轮询未读数（单机版无 WebSocket）
  unreadTimer = window.setInterval(loadUnreadCount, 60000)
})

onBeforeUnmount(() => {
  // 挂载即创建定时器，卸载时无条件清理（clearInterval(undefined) 为安全空操作）
  window.clearInterval(unreadTimer as number)
  unreadTimer = null
})

// ── 主题切换 ──
// 顶栏仅开放日常/现场主题；dark-bigscreen 为汇报大屏专用（大屏页强制启用），不在顶栏切换
const HEADER_THEME_VALUES = ['default', 'outdoor']
const headerThemeOptions = THEME_OPTIONS.filter((t) => HEADER_THEME_VALUES.includes(t.value))

function handleThemeChange(command: string) {
  configStore.setTheme(command)
}

// 挂载时加载用户可见菜单（若未加载）
onMounted(async () => {
  if (!menuStore.loaded) {
    await menuStore.fetchMenus()
  }
})

const isCollapsed = ref(false)

// ── 窄屏（< 768px）自动收起侧边栏 ──
// 只在进入窄屏时强制压窄为 68px；回到宽屏时不改写用户的折叠偏好
const narrowMq = window.matchMedia('(max-width: 767px)')
function handleNarrowChange(e: MediaQueryListEvent | MediaQueryList) {
  if (e.matches) {
    isCollapsed.value = true
  }
}
onMounted(() => {
  handleNarrowChange(narrowMq)
  narrowMq.addEventListener('change', handleNarrowChange)
})
onUnmounted(() => {
  narrowMq.removeEventListener('change', handleNarrowChange)
})

// ── 自动锁屏（单机共用电脑，无操作 N 分钟回登录页）──
// markLockNow：锁屏打点（供解锁后的摘要判定）；consumeLockDigest：摘要消费
import { consumeLockDigest, markLockNow } from '@/utils/lockDigest'
import { safeGetItem, safeSetItem } from '@/utils/safeStorage'
// 锁屏只结束当前会话；不调用 logout()（否则会清除"记住登录"持久凭据，
// 导致下次开机免登录失效 —— 修复 2026-08-15）
useAutoLockModule({
  onLock: () => {
    authStore.lockSession()
    // 打锁屏时间戳：解锁回来后的首次未读轮询据此弹「欢迎回来」摘要
    // （consumeLockDigest 只认近 30 分钟内的打点，自定义 onLock 覆盖了
    //  useAutoLock 默认实现，此处不调用则摘要永不触发）。
    markLockNow()
    // 携带当前路由：解锁重新登录后恢复到锁屏前页面
    const _rp =
      route.fullPath && route.fullPath !== '/login'
        ? `?redirect=${encodeURIComponent(route.fullPath)}`
        : ''
    window.location.href = `/login${_rp}`
  },
})

const username = computed(() => authStore.user?.username || authStore.user?.full_name || '管理员')

// ── 全局快捷键 ──
const globalShortcuts: Shortcut[] = [
  {
    key: 'k',
    ctrl: true,
    handler: openMenuSearch,
    description: '菜单搜索',
    group: '导航',
    disabledInInput: false,
  },
  {
    key: 'h',
    ctrl: true,
    handler: () => pushSafe('/'),
    description: '返回首页/工作台',
    group: '导航',
  },
  {
    key: 'd',
    ctrl: true,
    handler: () => pushSafe('/data-analysis'),
    description: '数据分析',
    group: '导航',
  },
  {
    key: 'v',
    ctrl: true,
    handler: () => pushSafe('/supported-villages'),
    description: '帮扶村管理',
    group: '导航',
  },
  {
    key: 'f',
    ctrl: true,
    handler: () => pushSafe('/funds'),
    description: '经费管理',
    group: '导航',
  },
  {
    key: 'p',
    ctrl: true,
    handler: () => pushSafe('/projects'),
    description: '项目管理',
    group: '导航',
  },
  {
    key: 's',
    ctrl: true,
    handler: () => pushSafe('/schools'),
    description: '学校管理',
    group: '导航',
  },
  {
    key: 'm',
    ctrl: true,
    handler: () => pushSafe('/data-analysis/map'),
    description: '地图看板',
    group: '导航',
  },
  {
    key: 'b',
    ctrl: true,
    shift: true,
    handler: () => pushSafe('/system/backup'),
    description: '备份管理',
    group: '系统',
  },
  {
    key: 'u',
    ctrl: true,
    shift: true,
    handler: () => pushSafe('/system/users'),
    description: '用户管理',
    group: '系统',
  },
  {
    key: '?',
    shift: true,
    handler: () => {
      showShortcutHelp.value = !showShortcutHelp.value
    },
    description: '显示/隐藏快捷键帮助',
    group: '帮助',
    disabledInInput: false,
  },
]

const showShortcutHelp = ref(false)
useKeyboardShortcuts(globalShortcuts)

function handleCommand(command: string) {
  switch (command) {
    case 'appearance':
      openAppearanceSettings()
      break
    case 'profile':
      pushSafe('/profile')
      break
    case 'change-password':
      pushSafe('/change-password')
      break
    case 'logout':
      // 冻结请求 + 取消 pending，防止 router.push 异步跳转期间组件发请求触发 401
      freezeRequests()
      cancelAllRequests()
      authStore.logout()
      // 硬跳转（避免 Vue Router 异步跳转期间组件继续渲染发请求）
      window.location.href = '/login'
      break
  }
}
</script>

<style lang="scss" scoped>
/* ===================================================================
   布局容器
   =================================================================== */
.layout-container {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

/* ===================================================================
   侧边栏 — 深色主题
   =================================================================== */
.layout-aside {
  background: var(--sidebar-bg);
  transition: width 0.28s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  border-right: 1px solid color-mix(in srgb, var(--color-text-inverse) 8%, transparent);
}

/* ── Logo 区域 ── */
.aside-header {
  height: 64px;
  display: flex;
  align-items: center;
  padding: 0 16px;
  border-bottom: 1px solid color-mix(in srgb, var(--color-text-inverse) 8%, transparent);
  gap: 0;
  flex-shrink: 0;
}

.app-logo {
  width: 36px;
  height: 36px;
  flex-shrink: 0;
  border-radius: 50%;
  object-fit: cover;
  background: var(--color-primary-900, var(--color-primary-dark-2));
  filter: drop-shadow(0 2px 4px var(--color-black-30));
}

.app-title {
  color: var(--color-accent-gold);
  /* R35（方案 C）：品牌名单行 20px/800，与板块标题（18px）形成正确层级 */
  font-size: var(--text-xl, 20px);
  font-weight: 800;
  white-space: nowrap;
  letter-spacing: 1px;
  margin-left: 12px;
  line-height: 1.2;
  text-shadow: 0 1px 3px var(--color-black-40);
}

.fade-title-enter-active,
.fade-title-leave-active {
  transition: opacity 0.2s ease;
}
.fade-title-enter-from,
.fade-title-leave-to {
  opacity: 0;
}

/* ── 滚动区域 ── */
.aside-scrollbar {
  flex: 1;
  overflow: hidden;
}

.aside-scrollbar :deep(.el-scrollbar__wrap) {
  overflow-x: hidden;
}

.aside-scrollbar :deep(.el-scrollbar__thumb) {
  background-color: var(--color-white-12);
  border-radius: 3px;
}
.aside-scrollbar :deep(.el-scrollbar__thumb:hover) {
  background-color: var(--color-white-22);
}

/* ── 菜单根：强制亮色文字（覆盖 Element Plus 默认暗色）── */
.aside-menu {
  border-right: none !important;
  padding: 8px 0;

  /* 直接设置 Element Plus CSS 变量，从根源解决黑色文字 */
  --el-menu-text-color: var(--color-white-82) !important;
  --el-menu-hover-text-color: var(--color-text-inverse) !important;
  --el-menu-active-color: $badge-gold !important;
  --el-menu-bg-color: transparent !important;
  --el-menu-hover-bg-color: var(--color-white-8) !important;
}

/* ── 菜单分区标签 ── */
.menu-section-label {
  padding: 16px 20px 6px 20px;
  font-size: 11px;
  font-weight: 600;
  color: var(--color-white-45);
  letter-spacing: 0.06em;
  user-select: none;
  pointer-events: none;
}

/* ── 七大板块标题（W22）：放大加粗 + 可点击展开/收起 ── */
.menu-section-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  box-sizing: border-box;
  width: calc(100% - 16px);
  margin: 10px 8px 4px;
  padding: 10px 12px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--color-text-inverse);
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-align: left;
  cursor: pointer;
  pointer-events: auto;
  opacity: 0.85;
  transition:
    background-color 0.22s ease,
    opacity 0.22s ease;
}

.menu-section-toggle:hover,
.menu-section-toggle:focus-visible {
  opacity: 1;
  background: color-mix(in srgb, currentColor 9%, transparent);
}

.section-toggle-icon {
  font-size: 14px;
  transition: transform 0.22s ease;
}

.section-toggle-icon.is-expanded {
  transform: rotate(180deg);
}

/* ── W23：板块标题包裹层 + 当前板块金色竖条 ── */
.section-head {
  position: relative;
}

.menu-section-toggle {
  position: relative;
  min-height: 40px;
}

.menu-section-toggle.is-current::before {
  content: '';
  position: absolute;
  left: 2px;
  top: 50%;
  width: 3px;
  height: 22px;
  border-radius: var(--radius-sm, 2px);
  background: var(--color-accent-gold);
  transform: translateY(-50%);
}

.menu-section-toggle.is-current {
  color: var(--color-accent-gold);
  opacity: 1;
}

/* ── W23：板块收起态浮层（hover / 键盘聚焦标题显示） ── */
.section-flyout {
  position: fixed;
  left: calc(var(--layout-sidebar-width, 240px) + 8px);
  z-index: 3000;
  min-width: 200px;
  max-height: 60vh;
  overflow-y: auto;
  padding: var(--spacing-sm, 8px);
  border: 1px solid var(--color-border-dark);
  border-radius: var(--radius-lg, 8px);
  background: var(--color-primary-dark-1);
  box-shadow: var(--shadow-md, 0 4px 12px transparent);
}

.section-flyout-title {
  padding: 6px 10px;
  color: var(--color-accent-gold);
  font-size: var(--text-sm, 13px);
  font-weight: 700;
  letter-spacing: 0.04em;
}

.section-flyout-group-title {
  padding: 8px 10px 4px;
  color: var(--color-text-inverse);
  font-size: var(--text-xs, 12px);
  opacity: 0.65;
}

.section-flyout-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 10px;
  border: none;
  border-radius: var(--radius-control, 6px);
  background: transparent;
  color: var(--color-text-inverse);
  font-size: var(--text-sm, 13px);
  text-align: left;
  cursor: pointer;
  transition:
    background-color 0.18s ease,
    color 0.18s ease;
}

.section-flyout-item:hover,
.section-flyout-item:focus-visible {
  background: color-mix(in srgb, currentColor 12%, transparent);
  color: var(--color-accent-gold);
}

/* ===================================================================
   菜单项 — 全局精调（强制覆盖所有状态文字颜色）
   =================================================================== */

/* 无条件强制：所有菜单文字必须为亮色 */
.aside-menu :deep(.el-menu-item),
.aside-menu :deep(.el-sub-menu__title),
.aside-menu :deep(.el-menu-item) *,
.aside-menu :deep(.el-sub-menu__title) * {
  color: var(--color-white-82) !important;
}

/* 取消 Element Plus 默认左侧栏 — 改用自定义 ::before 指示器 */
.aside-menu :deep(.el-menu-item),
.aside-menu :deep(.el-sub-menu__title) {
  height: 44px;
  line-height: 44px;
  margin: 2px 8px;
  border-radius: 8px;
  padding: 0 12px !important;
  font-size: 14px;
  transition:
    background-color 0.22s ease,
    color 0.22s ease,
    padding 0.28s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  background-color: transparent !important;
}

/* Hover 态 — 柔和亮起 */
.aside-menu :deep(.el-menu-item:hover),
.aside-menu :deep(.el-sub-menu__title:hover),
.aside-menu :deep(.el-menu-item:hover) *,
.aside-menu :deep(.el-sub-menu__title:hover) * {
  background-color: var(--color-white-7) !important;
  color: var(--color-text-inverse) !important;
}

/* Active 态 — 金色文字 + 左侧金色指示条 + 微妙背景 */
.aside-menu :deep(.el-menu-item.is-active),
.aside-menu :deep(.el-menu-item.is-active) * {
  background: linear-gradient(
    90deg,
    rgba(212, 175, 55, 0.16) 0%,
    rgba(212, 175, 55, 0.04) 100%
  ) !important;
  color: $badge-gold !important;
  font-weight: 600;
  box-shadow: inset 3px 0 0 $badge-gold;
}

/* 子菜单打开的父级 — 文字高亮 */
.aside-menu :deep(.el-sub-menu.is-active > .el-sub-menu__title),
.aside-menu :deep(.el-sub-menu.is-active > .el-sub-menu__title) * {
  color: $badge-gold !important;
  font-weight: 600;
}

/* ── 图标 ── */
.aside-menu :deep(.el-menu-item .el-icon),
.aside-menu :deep(.el-sub-menu__title .el-icon) {
  font-size: 18px;
  width: 20px;
  margin-right: 8px;
  flex-shrink: 0;
  transition: color 0.22s ease;
}

/* 子菜单箭头 */
.aside-menu :deep(.el-sub-menu__icon-arrow) {
  color: var(--color-white-35);
  transition: color 0.22s ease;
  right: 14px;
}
.aside-menu :deep(.el-sub-menu__title:hover .el-sub-menu__icon-arrow) {
  color: var(--color-white-70);
}

/* ── 子菜单（内联展开）样式 ── */
.aside-menu :deep(.el-menu--inline) {
  background: var(--color-white-3) !important;
  border-radius: 0 0 8px 8px;
  margin: 0 8px;
  padding: 4px 0;
}

.aside-menu :deep(.el-menu--inline .el-menu-item) {
  height: 38px;
  line-height: 38px;
  padding-left: 52px !important;
  font-size: 13px;
  border-radius: 6px;
  margin: 1px 4px;
  color: var(--color-white-72) !important;
  background-color: transparent !important;
}

.aside-menu :deep(.el-menu--inline .el-menu-item) *,
.aside-menu :deep(.el-menu--inline .el-menu-item span) {
  color: var(--color-white-72) !important;
}

.aside-menu :deep(.el-menu--inline .el-menu-item:hover),
.aside-menu :deep(.el-menu--inline .el-menu-item:hover) * {
  color: var(--color-text-inverse) !important;
  background-color: var(--color-white-5) !important;
}

.aside-menu :deep(.el-menu--inline .el-menu-item.is-active),
.aside-menu :deep(.el-menu--inline .el-menu-item.is-active) * {
  color: $badge-gold !important;
  background: var(--color-gold-a10) !important;
  box-shadow: inset 3px 0 0 $badge-gold;
}

/* ── 工作台（Dashboard）特化 — 顶部间距 + 视觉突出 ── */
/* R35（方案 C）：工作台保留 Home 图标，提升为「板块级入口」——
   与七大板块标题同构（18px/700、同样的外边距/内边距/圆角），消除字号与图标层级倒挂 */
.menu-item-dashboard {
  height: auto !important;
  line-height: 1.4 !important;
  margin: 10px 8px 4px !important;
  padding: 10px 12px !important;
  border-radius: 8px !important;
  font-size: 18px !important;
  font-weight: 700 !important;
  letter-spacing: 0.04em;
}
.menu-item-dashboard :deep(.el-icon) {
  color: $badge-gold;
  font-size: 16px !important;
  margin-right: 10px !important;
}
.menu-item-dashboard :deep(.menu-title-text) {
  font-size: 18px !important;
  font-weight: 700 !important;
}

/* ===================================================================
   弹出子菜单 (popper) — 深色主题
   =================================================================== */
:deep(.aside-popper) {
  background: #1d3d2a !important;
  border: 1px solid var(--color-white-10) !important;
  border-radius: 10px !important;
  box-shadow: 0 8px 30px var(--color-black-40) !important;
  padding: 6px 0 !important;

  /* 弹出菜单 CSS 变量覆盖 */
  --el-menu-text-color: var(--color-white-85) !important;
  --el-menu-hover-text-color: var(--color-text-inverse) !important;
  --el-menu-active-color: $badge-gold !important;
  --el-menu-bg-color: transparent !important;
  --el-menu-hover-bg-color: var(--color-white-8) !important;
}

:deep(.aside-popper .el-menu--popup) {
  background: transparent !important;
}

/* 弹出菜单每一项 —— 强制白色 */
:deep(.aside-popper .el-menu-item),
:deep(.aside-popper .el-menu-item) *,
:deep(.aside-popper .el-menu-item span) {
  color: var(--color-white-85) !important;
  height: 40px;
  line-height: 40px;
  font-size: 13px;
  border-radius: 6px;
  margin: 2px 6px;
  padding: 0 14px !important;
  background-color: transparent !important;
}

:deep(.aside-popper .el-menu-item:hover),
:deep(.aside-popper .el-menu-item:hover) * {
  background-color: var(--color-white-7) !important;
  color: var(--color-text-inverse) !important;
}

/* ===================================================================
   顶栏
   =================================================================== */
.layout-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.layout-header {
  height: 50px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--spacing-lg);
  background: var(--sidebar-bg);
  border-bottom: 1px solid color-mix(in srgb, var(--color-accent-gold) 25%, transparent);
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 14px;
}

.collapse-btn {
  font-size: 20px;
  color: var(--color-text-inverse) !important;
  opacity: 0.72;
  transition:
    color 0.2s ease,
    opacity 0.2s ease;
}
.collapse-btn:hover {
  color: var(--color-accent-gold) !important;
  opacity: 1;
  background: transparent !important;
}

/* 面包屑（W23：板块 › 页面） */
.header-left :deep(.el-breadcrumb) {
  font-size: var(--text-sm, 13px);
}
.header-left :deep(.el-breadcrumb__inner) {
  color: var(--color-text-inverse);
  font-weight: 400;
  opacity: 0.66;
  transition: opacity 0.2s;
}
.header-left :deep(.el-breadcrumb__inner.is-link:hover) {
  color: var(--color-accent-gold);
  opacity: 1;
}
.header-left :deep(.el-breadcrumb__separator) {
  color: var(--color-text-inverse);
  opacity: 0.35;
  margin: 0 8px;
}
.breadcrumb-home {
  font-size: 15px;
  vertical-align: -2px;
}
.breadcrumb-section {
  color: var(--color-text-inverse);
  opacity: 0.72;
}
.breadcrumb-current {
  color: var(--color-accent-gold) !important;
  font-weight: 600;
}

/* ── 用户菜单 ── */
.header-right {
  display: flex;
  align-items: center;
  gap: 6px;
}

/* ── 主题切换器 / 顶栏图标（W23：统一 token 视觉） ── */
.theme-switcher {
  outline: none;
}
.theme-trigger {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  cursor: pointer;
  color: var(--color-text-inverse);
  opacity: 0.72;
  font-size: 16px;
  transition:
    background-color 0.22s ease,
    color 0.22s ease,
    opacity 0.22s ease;
}
.theme-trigger:hover,
.theme-trigger:focus-visible {
  background-color: color-mix(in srgb, currentColor 12%, transparent);
  color: var(--color-accent-gold);
  opacity: 1;
}
.theme-check {
  margin-right: 4px;
  color: var(--color-primary);
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 4px 12px 4px 4px;
  border-radius: 24px;
  transition: background-color 0.22s ease;
}
.user-info:hover {
  background-color: color-mix(in srgb, var(--color-text-inverse) 12%, transparent);
}

.header-avatar {
  border: 2px solid color-mix(in srgb, var(--color-accent-gold) 55%, transparent);
}

.username {
  font-size: var(--text-sm, 13px);
  color: var(--color-text-inverse);
  opacity: 0.88;
  font-weight: 500;
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dropdown-arrow {
  font-size: 12px;
  color: var(--color-text-inverse);
  opacity: 0.55;
  transition:
    transform 0.2s ease,
    opacity 0.2s ease;
}
.user-info:hover .dropdown-arrow {
  opacity: 0.85;
}

/* ===================================================================
   主内容区
   =================================================================== */
.layout-content {
  flex: 1;
  overflow: auto;
  background: var(--color-bg-page);
  padding: var(--layout-content-padding, 24px);
}

/* ===================================================================
   底栏
   =================================================================== */
.layout-footer {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--text-xs, 12px);
  color: var(--color-text-inverse);
  opacity: 0.55;
  background: var(--sidebar-bg);
  border-top: 1px solid color-mix(in srgb, var(--color-text-inverse) 6%, transparent);
  flex-shrink: 0;
  letter-spacing: 0.03em;
}

/* ===================================================================
   过渡动画（仅保留标题区 fade-title；主内容区 fade 已移除，见模板注释）
   =================================================================== */

/* ===================================================================
   WCAG 跳过链接
   =================================================================== */
.skip-link {
  position: absolute;
  top: -100px;
  left: 0;
  z-index: 1000;
  padding: 8px 16px;
  background: var(--color-accent-gold);
  color: var(--color-primary-dark-1);
  font-weight: 700;
  border-radius: 0 0 4px 0;
  transition: top 0.2s;
}
.skip-link:focus {
  top: 0;
}

/* ===================================================================
   窄屏响应式（< 768px）
   底部 MobileBottomNav 已覆盖主导航，隐藏侧边栏避免挤压主内容
   =================================================================== */
@media (max-width: 767px) {
  .layout-aside {
    display: none;
  }

  /* MobileBottomNav 固定底部高 56px，为滚动容器留出底部净空，避免遮挡内容 */
  .layout-content {
    padding-bottom: calc(56px + var(--spacing-md));
  }

  .section-flyout {
    display: none;
  }
}
</style>

<!-- 全局非 scoped 样式：彻底消灭 Element Plus 菜单中的黑色文字 -->
<style lang="scss">
/* === 侧边栏菜单：全局强制白色文字 === */
.layout-aside .el-menu-item,
.layout-aside .el-sub-menu__title,
.layout-aside .el-menu-item span,
.layout-aside .el-sub-menu__title span,
.layout-aside .el-menu-item i,
.layout-aside .el-sub-menu__title i {
  color: var(--color-white-85) !important;
}

.layout-aside .el-menu-item:hover,
.layout-aside .el-sub-menu__title:hover,
.layout-aside .el-menu-item:hover span,
.layout-aside .el-sub-menu__title:hover span {
  color: var(--color-text-inverse) !important;
}

.layout-aside .el-menu-item.is-active,
.layout-aside .el-menu-item.is-active span,
.layout-aside .el-sub-menu.is-active > .el-sub-menu__title,
.layout-aside .el-sub-menu.is-active > .el-sub-menu__title span {
  color: $badge-gold !important;
}

/* 内联展开子菜单 */
.layout-aside .el-menu--inline .el-menu-item,
.layout-aside .el-menu--inline .el-menu-item span {
  color: rgba(255, 255, 255, 0.75) !important;
}
.layout-aside .el-menu--inline .el-menu-item:hover,
.layout-aside .el-menu--inline .el-menu-item:hover span {
  color: var(--color-text-inverse) !important;
}
.layout-aside .el-menu--inline .el-menu-item.is-active,
.layout-aside .el-menu--inline .el-menu-item.is-active span {
  color: $badge-gold !important;
}

/* 弹出层子菜单 */
.aside-popper .el-menu-item,
.aside-popper .el-menu-item span {
  color: var(--color-white-85) !important;
}
.aside-popper .el-menu-item:hover,
.aside-popper .el-menu-item:hover span {
  color: var(--color-text-inverse) !important;
}
</style>
