<template>
  <div class="layout-container">
    <!-- WCAG 2.1: 跳过导航链接 -->
    <a href="#main-content" class="skip-link">跳到主内容</a>

    <!-- ============================================================ -->
    <!-- 侧边栏 — 帮扶管理信息主题，精美分层导航                         -->
    <!-- ============================================================ -->
    <el-aside
      :width="isCollapsed ? '68px' : '240px'"
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

      <!-- 导航菜单 — 每项带独立 v-if 权限守卫 -->
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
          <!-- ════ 首页 ════ -->
          <el-menu-item index="/dashboard" class="menu-item-dashboard">
            <el-icon><HomeFilled /></el-icon>
            <template #title>
              <span class="menu-title-text">工作台</span>
            </template>
          </el-menu-item>

          <!-- ════ 核心业务 ════ -->
          <div
            v-show="!isCollapsed"
            v-if="
              menuStore.canAccessMenu('villages') ||
              menuStore.canAccessMenu('projects') ||
              menuStore.canAccessMenu('schools') ||
              menuStore.canAccessMenu('policies') ||
              menuStore.canAccessMenu('funds-admin') ||
              menuStore.canAccessMenu('funds-user')
            "
            class="menu-section-label"
          >
            <span>核心业务</span>
          </div>

          <!-- 帮扶村管理：单入口，年度概览/数据录入选为页内tab -->
          <el-menu-item v-if="menuStore.canAccessMenu('villages')" index="/supported-villages">
            <el-icon><Location /></el-icon>
            <template #title>
              <span class="menu-title-text">帮扶村管理</span>
            </template>
          </el-menu-item>

          <!-- 帮扶项目：单入口，项目管控/导入为页内tab -->
          <el-menu-item v-if="menuStore.canAccessMenu('projects')" index="/projects">
            <el-icon><Folder /></el-icon>
            <template #title>
              <span class="menu-title-text">帮扶项目</span>
            </template>
          </el-menu-item>

          <!-- 帮扶学校：单入口，学校分析为页内tab -->
          <el-menu-item v-if="menuStore.canAccessMenu('schools')" index="/schools">
            <el-icon><School /></el-icon>
            <template #title>
              <span class="menu-title-text">帮扶学校</span>
            </template>
          </el-menu-item>

          <!-- 经费管理：多子项保留el-sub-menu，位置移到帮扶学校之后 -->
          <el-sub-menu
            v-if="menuStore.canAccessMenu('funds-admin') || menuStore.canAccessMenu('funds-user')"
            index="fund-group"
            popper-class="aside-popper"
          >
            <template #title>
              <el-icon><Money /></el-icon>
              <span class="menu-title-text">经费管理</span>
            </template>
            <el-menu-item index="/funds"><span>经费总览</span></el-menu-item>
            <el-menu-item index="/funds/budget"><span>预算管理</span></el-menu-item>
            <el-menu-item index="/funds/user"><span>经费申请</span></el-menu-item>
            <el-menu-item index="/funds/contract"><span>合同管理</span></el-menu-item>
            <el-menu-item index="/funds/transfer"><span>转账凭证</span></el-menu-item>
            <el-menu-item index="/funds/anomaly"><span>异常监控</span></el-menu-item>
            <el-menu-item index="/funds/lifecycle"><span>资金周期</span></el-menu-item>
            <el-menu-item index="/funds/settlement"><span>决算结算</span></el-menu-item>
            <el-menu-item index="/funds/analysis"><span>经费分析</span></el-menu-item>
            <el-menu-item index="/funds/report"><span>经费报表</span></el-menu-item>
          </el-sub-menu>

          <el-menu-item v-if="menuStore.canAccessMenu('policies')" index="/policies">
            <el-icon><Document /></el-icon>
            <template #title>
              <span class="menu-title-text">帮扶政策</span>
            </template>
          </el-menu-item>

          <!-- ════ 乡村振兴 ════ -->
          <div
            v-show="!isCollapsed"
            v-if="menuStore.canAccessMenu('rural-works')"
            class="menu-section-label"
          >
            <span>乡村振兴</span>
          </div>

          <el-sub-menu
            v-if="menuStore.canAccessMenu('rural-works')"
            index="rural-group"
            popper-class="aside-popper"
          >
            <template #title>
              <el-icon><Stamp /></el-icon>
              <span class="menu-title-text">乡村振兴</span>
            </template>
            <el-menu-item index="/rural-works"><span>工作首页</span></el-menu-item>
            <el-menu-item index="/rural-works/list"><span>工作列表</span></el-menu-item>
          </el-sub-menu>

          <!-- ════ 工作流 ════ -->
          <div
            v-show="!isCollapsed"
            v-if="menuStore.canAccessMenu('approval') || menuStore.canAccessMenu('work-analysis')"
            class="menu-section-label"
          >
            <span>工作流</span>
          </div>

          <el-sub-menu
            v-if="menuStore.canAccessMenu('approval')"
            index="approval-group"
            popper-class="aside-popper"
          >
            <template #title>
              <el-icon><Checked /></el-icon>
              <span class="menu-title-text">审批管理</span>
            </template>
            <el-menu-item index="/approval"><span>审批概览</span></el-menu-item>
            <el-menu-item index="/approval/pending"><span>待审批</span></el-menu-item>
            <el-menu-item index="/approval/my"><span>我的申请</span></el-menu-item>
            <el-menu-item index="/approval/history"><span>审批历史</span></el-menu-item>
          </el-sub-menu>

          <el-menu-item v-if="menuStore.canAccessMenu('work-analysis')" index="/work-calendar">
            <el-icon><Calendar /></el-icon>
            <template #title>
              <span class="menu-title-text">工作日历</span>
            </template>
          </el-menu-item>

          <el-menu-item v-if="menuStore.canAccessMenu('todos')" index="/todos">
            <el-icon><Select /></el-icon>
            <template #title>
              <span class="menu-title-text">待办事项</span>
            </template>
          </el-menu-item>

          <!-- ════ 数据分析 ════ -->
          <div
            v-show="!isCollapsed"
            v-if="
              menuStore.canAccessMenu('data') ||
              menuStore.canAccessMenu('data-overview') ||
              menuStore.canAccessMenu('report-templates') ||
              menuStore.canAccessMenu('report-export') ||
              menuStore.canAccessMenu('analytics') ||
              menuStore.canAccessMenu('analytics-dashboard') ||
              menuStore.canAccessMenu('analytics-map')
            "
            class="menu-section-label"
          >
            <span>数据分析</span>
          </div>

          <el-sub-menu
            v-if="menuStore.canAccessMenu('data') || menuStore.canAccessMenu('data-overview')"
            index="data-group"
            popper-class="aside-popper"
          >
            <template #title>
              <el-icon><DataAnalysis /></el-icon>
              <span class="menu-title-text">数据分析</span>
            </template>
            <el-menu-item index="/data-analysis"><span>分析首页</span></el-menu-item>
            <el-menu-item index="/data-analysis/dashboard"><span>分析仪表板</span></el-menu-item>
            <el-menu-item index="/data-analysis/map"><span>地图可视化</span></el-menu-item>
            <el-menu-item index="/report/templates"><span>报表模板</span></el-menu-item>
            <el-menu-item index="/export/report"><span>报表导出</span></el-menu-item>
            <el-menu-item index="/data-analysis/assessment"><span>成效评估</span></el-menu-item>
            <el-menu-item index="/effectiveness"><span>帮扶成效</span></el-menu-item>
          </el-sub-menu>

          <!-- ════ 数据管理 ════ -->
          <div
            v-show="!isCollapsed"
            v-if="
              menuStore.canAccessMenu('data') ||
              menuStore.canAccessMenu('data-overview') ||
              menuStore.canAccessMenu('user-backup') ||
              menuStore.canAccessMenu('data-quality') ||
              menuStore.canAccessMenu('data-logs') ||
              menuStore.canAccessMenu('data-package-report') ||
              menuStore.canAccessMenu('data-package-receive')
            "
            class="menu-section-label"
          >
            <span>数据管理</span>
          </div>

          <el-sub-menu
            v-if="menuStore.canAccessMenu('data') || menuStore.canAccessMenu('data-overview')"
            index="datasync-group"
            popper-class="aside-popper"
          >
            <template #title>
              <el-icon><Connection /></el-icon>
              <span class="menu-title-text">数据管理</span>
            </template>
            <el-menu-item index="/data-management"><span>数据概览</span></el-menu-item>
            <!-- 数据备份/操作日志入口已统一收归至系统管理 → 审计管理/备份管理 -->
            <el-menu-item index="/data-sync/export"><span>数据导出</span></el-menu-item>
            <el-menu-item index="/data-sync/import"><span>数据导入</span></el-menu-item>
            <el-menu-item index="/data-package"><span>数据包与批量导入</span></el-menu-item>
            <!-- 批量导入已整合至数据包管理 -->
            <el-menu-item v-if="menuStore.canAccessMenu('data-verify')" index="/data-verify"
              ><span>数据校验</span></el-menu-item
            >
          </el-sub-menu>

          <!-- ════ 系统 ════ -->
          <div
            v-show="!isCollapsed"
            v-if="menuStore.canAccessMenu('system')"
            class="menu-section-label"
          >
            <span>系统管理</span>
          </div>

          <el-menu-item v-if="menuStore.canAccessMenu('users-orgs')" index="/organization">
            <el-icon><OfficeBuilding /></el-icon>
            <template #title>
              <span class="menu-title-text">组织机构</span>
            </template>
          </el-menu-item>

          <el-sub-menu
            v-if="menuStore.canAccessMenu('system')"
            index="system-group"
            popper-class="aside-popper"
          >
            <template #title>
              <el-icon><Setting /></el-icon>
              <span class="menu-title-text">系统管理</span>
            </template>
            <el-menu-item v-if="authStore.isAdmin" index="/admin/machine-code/management"
              ><span>机器码与通行码</span></el-menu-item
            >
            <el-menu-item v-if="menuStore.canAccessMenu('users-orgs')" index="/system/users"
              ><span>用户与角色</span></el-menu-item
            >
            <el-menu-item v-if="menuStore.canAccessMenu('audit')" index="/system/audit"
              ><span>审计管理</span></el-menu-item
            >
            <el-menu-item v-if="menuStore.canAccessMenu('backup')" index="/system/backup"
              ><span>备份管理</span></el-menu-item
            >
            <el-menu-item v-if="menuStore.canAccessMenu('system-config')" index="/system/config"
              ><span>系统配置</span></el-menu-item
            >
            <el-menu-item v-if="menuStore.canAccessMenu('monitor')" index="/system/monitoring"
              ><span>系统监控</span></el-menu-item
            >
            <el-menu-item v-if="menuStore.canAccessMenu('help')" index="/help"
              ><span>帮助文档</span></el-menu-item
            >
          </el-sub-menu>

          <el-menu-item v-if="menuStore.canAccessMenu('messages')" index="/message">
            <el-icon><Message /></el-icon>
            <template #title>
              <span class="menu-title-text">消息中心</span>
            </template>
          </el-menu-item>
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
            <el-breadcrumb-item v-if="currentRoute">
              <span class="breadcrumb-current">{{ currentRoute }}</span>
            </el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="header-right">
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
        <span>帮扶管理信息系统 v1.5.0</span>
      </el-footer>
    </el-container>
    <!-- 移动端底部导航 -->
    <MobileBottomNav />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, onUnmounted } from 'vue'
import { useAutoLock as useAutoLockModule } from '@/composables/useAutoLock'
import { useRoute } from 'vue-router'
import { useRouterSafe } from '@/composables/useRouterSafe'
import { useKeyboardShortcuts, type Shortcut } from '@/composables/useKeyboardShortcuts'
import { useAuthStore } from '@/stores/auth'
import { useMenuStore } from '@/stores/menu'
import { useConfigStore, THEME_OPTIONS } from '@/stores/config'
import { cancelAllRequests, freezeRequests } from '@/api/request'
import MobileBottomNav from '@/components/layout/MobileBottomNav.vue'
import {
  HomeFilled,
  Folder,
  Money,
  Location,
  DataAnalysis,
  Setting,
  Expand,
  Fold,
  User,
  School,
  Document,
  Stamp,
  Checked,
  Connection,
  OfficeBuilding,
  Message,
  Bell,
  Calendar,
  ArrowDown,
  Lock,
  SwitchButton,
  Select,
  Brush,
  Check,
} from '@element-plus/icons-vue'

const route = useRoute()
const { pushSafe } = useRouterSafe()
const authStore = useAuthStore()
const menuStore = useMenuStore()
const configStore = useConfigStore()

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
    ;(window as any).electronAPI?.updateTrayUnread?.(unreadCount.value)
  } catch {
    /* 轮询失败静默 */
  }
}

onMounted(() => {
  loadUnreadCount()
  // 每 60 秒轮询未读数（单机版无 WebSocket）
  const timer = window.setInterval(loadUnreadCount, 60000)
  onBeforeUnmount(() => window.clearInterval(timer))
})

// ── 主题切换 ──
// 顶栏仅开放已完成适配的主题；dark/military 待全站硬编码 Token 化后开放（见 UI 设计方案 §3）
const HEADER_THEME_VALUES = ['default', 'light', 'outdoor', 'high-contrast']
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
// 锁屏只结束当前会话；不调用 logout()（否则会清除"记住登录"持久凭据，
// 导致下次开机免登录失效 —— 修复 2026-08-15）
useAutoLockModule({
  onLock: () => {
    authStore.lockSession()
    // 携带当前路由：解锁重新登录后恢复到锁屏前页面
    const _rp =
      route.fullPath && route.fullPath !== '/login'
        ? `?redirect=${encodeURIComponent(route.fullPath)}`
        : ''
    window.location.href = `/login${_rp}`
  },
})

const username = computed(() => authStore.user?.username || authStore.user?.full_name || '管理员')
const currentRoute = computed(() => (route.meta?.title as string) || '')

// ── 全局快捷键 ──
const globalShortcuts: Shortcut[] = [
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

<style scoped>
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
  background: linear-gradient(180deg, #132818 0%, #1d3d2a 40%, #1d3d2a 100%);
  transition: width 0.28s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  border-right: 1px solid rgba(255, 255, 255, 0.08);
}

/* ── Logo 区域 ── */
.aside-header {
  height: 60px;
  display: flex;
  align-items: center;
  padding: 0 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  gap: 0;
  flex-shrink: 0;
}

.app-logo {
  width: 34px;
  height: 34px;
  flex-shrink: 0;
  border-radius: 50%;
  object-fit: cover;
  background: #132818;
  filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.3));
}

.app-title {
  color: #d4af37;
  font-size: 17px;
  font-weight: 700;
  white-space: nowrap;
  letter-spacing: 1.5px;
  margin-left: 10px;
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.4);
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
  background-color: rgba(255, 255, 255, 0.12);
  border-radius: 3px;
}
.aside-scrollbar :deep(.el-scrollbar__thumb:hover) {
  background-color: rgba(255, 255, 255, 0.22);
}

/* ── 菜单根：强制亮色文字（覆盖 Element Plus 默认暗色）── */
.aside-menu {
  border-right: none !important;
  padding: 8px 0;

  /* 直接设置 Element Plus CSS 变量，从根源解决黑色文字 */
  --el-menu-text-color: rgba(255, 255, 255, 0.82) !important;
  --el-menu-hover-text-color: #ffffff !important;
  --el-menu-active-color: #d4af37 !important;
  --el-menu-bg-color: transparent !important;
  --el-menu-hover-bg-color: rgba(255, 255, 255, 0.08) !important;
}

/* ── 菜单分区标签 ── */
.menu-section-label {
  padding: 16px 20px 6px 20px;
  font-size: 11px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.45);
  letter-spacing: 0.06em;
  user-select: none;
  pointer-events: none;
}

/* ===================================================================
   菜单项 — 全局精调（强制覆盖所有状态文字颜色）
   =================================================================== */

/* 无条件强制：所有菜单文字必须为亮色 */
.aside-menu :deep(.el-menu-item),
.aside-menu :deep(.el-sub-menu__title),
.aside-menu :deep(.el-menu-item) *,
.aside-menu :deep(.el-sub-menu__title) * {
  color: rgba(255, 255, 255, 0.82) !important;
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
  background-color: rgba(255, 255, 255, 0.07) !important;
  color: #ffffff !important;
}

/* Active 态 — 金色文字 + 左侧金色指示条 + 微妙背景 */
.aside-menu :deep(.el-menu-item.is-active),
.aside-menu :deep(.el-menu-item.is-active) * {
  background: linear-gradient(
    90deg,
    rgba(212, 175, 55, 0.16) 0%,
    rgba(212, 175, 55, 0.04) 100%
  ) !important;
  color: #d4af37 !important;
  font-weight: 600;
  box-shadow: inset 3px 0 0 #d4af37;
}

/* 子菜单打开的父级 — 文字高亮 */
.aside-menu :deep(.el-sub-menu.is-active > .el-sub-menu__title),
.aside-menu :deep(.el-sub-menu.is-active > .el-sub-menu__title) * {
  color: #d4af37 !important;
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
  color: rgba(255, 255, 255, 0.35);
  transition: color 0.22s ease;
  right: 14px;
}
.aside-menu :deep(.el-sub-menu__title:hover .el-sub-menu__icon-arrow) {
  color: rgba(255, 255, 255, 0.7);
}

/* ── 子菜单（内联展开）样式 ── */
.aside-menu :deep(.el-menu--inline) {
  background: rgba(255, 255, 255, 0.03) !important;
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
  color: rgba(255, 255, 255, 0.72) !important;
  background-color: transparent !important;
}

.aside-menu :deep(.el-menu--inline .el-menu-item) *,
.aside-menu :deep(.el-menu--inline .el-menu-item span) {
  color: rgba(255, 255, 255, 0.72) !important;
}

.aside-menu :deep(.el-menu--inline .el-menu-item:hover),
.aside-menu :deep(.el-menu--inline .el-menu-item:hover) * {
  color: #ffffff !important;
  background-color: rgba(255, 255, 255, 0.05) !important;
}

.aside-menu :deep(.el-menu--inline .el-menu-item.is-active),
.aside-menu :deep(.el-menu--inline .el-menu-item.is-active) * {
  color: #d4af37 !important;
  background: rgba(212, 175, 55, 0.1) !important;
  box-shadow: inset 3px 0 0 #d4af37;
}

/* ── 工作台（Dashboard）特化 — 顶部间距 + 视觉突出 ── */
.menu-item-dashboard {
  margin-bottom: 4px !important;
}

.menu-item-dashboard :deep(.el-icon) {
  color: #d4af37;
}

/* ===================================================================
   弹出子菜单 (popper) — 深色主题
   =================================================================== */
:deep(.aside-popper) {
  background: #1d3d2a !important;
  border: 1px solid rgba(255, 255, 255, 0.1) !important;
  border-radius: 10px !important;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.4) !important;
  padding: 6px 0 !important;

  /* 弹出菜单 CSS 变量覆盖 */
  --el-menu-text-color: rgba(255, 255, 255, 0.85) !important;
  --el-menu-hover-text-color: #ffffff !important;
  --el-menu-active-color: #d4af37 !important;
  --el-menu-bg-color: transparent !important;
  --el-menu-hover-bg-color: rgba(255, 255, 255, 0.08) !important;
}

:deep(.aside-popper .el-menu--popup) {
  background: transparent !important;
}

/* 弹出菜单每一项 —— 强制白色 */
:deep(.aside-popper .el-menu-item),
:deep(.aside-popper .el-menu-item) *,
:deep(.aside-popper .el-menu-item span) {
  color: rgba(255, 255, 255, 0.85) !important;
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
  background-color: rgba(255, 255, 255, 0.07) !important;
  color: #ffffff !important;
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
  padding: 0 20px;
  background: linear-gradient(135deg, #1b4332 0%, #2d6a4f 50%, #1b4332 100%);
  border-bottom: 1px solid rgba(212, 175, 55, 0.25);
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 14px;
}

.collapse-btn {
  font-size: 20px;
  color: rgba(255, 255, 255, 0.7) !important;
  transition: color 0.2s ease;
}
.collapse-btn:hover {
  color: #d4af37 !important;
  background: transparent !important;
}

/* 面包屑 */
.header-left :deep(.el-breadcrumb) {
  font-size: 13px;
}
.header-left :deep(.el-breadcrumb__inner) {
  color: rgba(255, 255, 255, 0.6);
  font-weight: 400;
  transition: color 0.2s;
}
.header-left :deep(.el-breadcrumb__inner.is-link:hover) {
  color: #d4af37;
}
.header-left :deep(.el-breadcrumb__separator) {
  color: rgba(255, 255, 255, 0.3);
  margin: 0 8px;
}
.breadcrumb-home {
  font-size: 15px;
  vertical-align: -2px;
}
.breadcrumb-current {
  color: #d4af37 !important;
  font-weight: 600;
}

/* ── 用户菜单 ── */
.header-right {
  display: flex;
  align-items: center;
  gap: 6px;
}

/* ── 主题切换器 ── */
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
  color: rgba(255, 255, 255, 0.7);
  font-size: 16px;
  transition:
    background-color 0.22s ease,
    color 0.22s ease;
}
.theme-trigger:hover,
.theme-trigger:focus-visible {
  background-color: rgba(255, 255, 255, 0.1);
  color: #d4af37;
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
  background-color: rgba(255, 255, 255, 0.1);
}

.header-avatar {
  border: 2px solid rgba(212, 175, 55, 0.5);
}

.username {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.85);
  font-weight: 500;
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dropdown-arrow {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.4);
  transition: transform 0.2s ease;
}
.user-info:hover .dropdown-arrow {
  color: rgba(255, 255, 255, 0.7);
}

/* ===================================================================
   主内容区
   =================================================================== */
.layout-content {
  flex: 1;
  overflow: auto;
  background: #f0f2f5;
  padding: 20px;
}

/* ===================================================================
   底栏
   =================================================================== */
.layout-footer {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.4);
  background: #152718;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
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
  background: #d4af37;
  color: #1a3c2a;
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
}
</style>

<!-- 全局非 scoped 样式：彻底消灭 Element Plus 菜单中的黑色文字 -->
<style>
/* === 侧边栏菜单：全局强制白色文字 === */
.layout-aside .el-menu-item,
.layout-aside .el-sub-menu__title,
.layout-aside .el-menu-item span,
.layout-aside .el-sub-menu__title span,
.layout-aside .el-menu-item i,
.layout-aside .el-sub-menu__title i {
  color: rgba(255, 255, 255, 0.85) !important;
}

.layout-aside .el-menu-item:hover,
.layout-aside .el-sub-menu__title:hover,
.layout-aside .el-menu-item:hover span,
.layout-aside .el-sub-menu__title:hover span {
  color: #ffffff !important;
}

.layout-aside .el-menu-item.is-active,
.layout-aside .el-menu-item.is-active span,
.layout-aside .el-sub-menu.is-active > .el-sub-menu__title,
.layout-aside .el-sub-menu.is-active > .el-sub-menu__title span {
  color: #d4af37 !important;
}

/* 内联展开子菜单 */
.layout-aside .el-menu--inline .el-menu-item,
.layout-aside .el-menu--inline .el-menu-item span {
  color: rgba(255, 255, 255, 0.75) !important;
}
.layout-aside .el-menu--inline .el-menu-item:hover,
.layout-aside .el-menu--inline .el-menu-item:hover span {
  color: #ffffff !important;
}
.layout-aside .el-menu--inline .el-menu-item.is-active,
.layout-aside .el-menu--inline .el-menu-item.is-active span {
  color: #d4af37 !important;
}

/* 弹出层子菜单 */
.aside-popper .el-menu-item,
.aside-popper .el-menu-item span {
  color: rgba(255, 255, 255, 0.85) !important;
}
.aside-popper .el-menu-item:hover,
.aside-popper .el-menu-item:hover span {
  color: #ffffff !important;
}
</style>
