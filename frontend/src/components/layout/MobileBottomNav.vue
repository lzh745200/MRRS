<template>
  <nav v-if="isMobile" class="mobile-nav">
    <button
      v-for="item in navItems"
      :key="item.key"
      type="button"
      class="nav-btn"
      :class="{ active: isActive(item.path) }"
      @click="handleNav(item)"
    >
      <el-icon class="nav-icon" :size="20">
        <component :is="item.icon" />
      </el-icon>
      <span class="nav-label">{{ item.label }}</span>
    </button>

    <!-- 「更多」抽屉：完整数据驱动菜单 + 页内搜索 -->
    <el-drawer
      v-model="drawerVisible"
      title="全部菜单"
      direction="btt"
      size="70%"
      class="mobile-menu-drawer"
    >
      <el-input
        v-model="keyword"
        class="mobile-menu-search"
        placeholder="搜索菜单名称 / key / 路径"
        clearable
      />
      <div class="mobile-menu-list">
        <button
          v-for="entry in filteredEntries"
          :key="entry.key"
          type="button"
          class="mobile-menu-item"
          @click="navigateEntry(entry)"
        >
          <el-icon class="mobile-menu-item-icon">
            <component :is="resolveMenuIcon(entry.icon)" />
          </el-icon>
          <span class="mobile-menu-item-label">{{ entry.label }}</span>
          <span class="mobile-menu-item-section">{{ entry.sectionLabel }}</span>
        </button>
        <el-empty v-if="!filteredEntries.length" description="未找到匹配的菜单" :image-size="60" />
      </div>
    </el-drawer>
  </nav>
</template>

<script setup lang="ts">
/**
 * 移动端底部导航（< 768px）
 *
 * 数据驱动：工作台固定第一 → 后端 sections 前 3 个入口 → 「更多」抽屉。
 * 「更多」抽屉展示 menuStore.flatEntries 全量条目并支持页内搜索，
 * 点击任一入口后写入「最近访问」（localStorage，上限 8）。
 */
import { computed, onMounted, onUnmounted, ref, type Component } from 'vue'
import { useRoute } from 'vue-router'
import { useRouterSafe } from '@/composables/useRouterSafe'
import { useMenuStore, type FlatMenuEntry } from '@/stores/menu'
import { useRecentMenus } from '@/composables/useRecentMenus'
import { resolveMenuIcon } from '@/components/nav/menuIcons'
import { HomeFilled, MoreFilled } from '@element-plus/icons-vue'

/** 底部导航按钮 */
interface MobileNavItem {
  key: string
  label: string
  path: string
  icon: Component
  action: 'navigate' | 'more'
}

const route = useRoute()
const { pushSafe } = useRouterSafe()
const menuStore = useMenuStore()
const { recordMenu } = useRecentMenus()

const windowWidth = ref(window.innerWidth)
const isMobile = computed(() => windowWidth.value < 768)

/** 工作台固定第一 + sections 前 3 个入口 + 「更多」 */
const navItems = computed<MobileNavItem[]>(() => {
  const primary = menuStore.flatEntries.filter((entry) => entry.key !== 'dashboard').slice(0, 3)
  return [
    {
      key: 'dashboard',
      label: '工作台',
      path: '/dashboard',
      icon: HomeFilled,
      action: 'navigate',
    },
    ...primary.map((entry) => ({
      key: entry.key,
      label: entry.label,
      path: entry.path,
      icon: resolveMenuIcon(entry.icon),
      action: 'navigate' as const,
    })),
    {
      key: 'more',
      label: '更多',
      path: '',
      icon: MoreFilled,
      action: 'more',
    },
  ]
})

const drawerVisible = ref(false)
const keyword = ref('')

/** label / key / path 大小写不敏感子串匹配 */
function matchEntry(entry: FlatMenuEntry, query: string): boolean {
  return (
    entry.label.toLowerCase().includes(query) ||
    entry.key.toLowerCase().includes(query) ||
    entry.path.toLowerCase().includes(query)
  )
}

/** 抽屉内菜单列表（关键词为空时展示全部） */
const filteredEntries = computed(() => {
  const query = keyword.value.trim().toLowerCase()
  if (!query) return menuStore.flatEntries
  return menuStore.flatEntries.filter((entry) => matchEntry(entry, query))
})

function isActive(path: string) {
  // 「更多」按钮无 path（path === ''），不参与高亮判定
  if (!path) return false
  return route.path === path || route.path.startsWith(path + '/')
}

/** 记录最近访问并跳转 */
function navigateEntry(entry: FlatMenuEntry) {
  recordMenu({ key: entry.key, label: entry.label, path: entry.path, icon: entry.icon })
  drawerVisible.value = false
  pushSafe(entry.path)
}

/** 底部按钮：普通入口直接跳转，「更多」打开抽屉 */
function handleNav(item: MobileNavItem) {
  if (item.action === 'more') {
    drawerVisible.value = true
    return
  }
  pushSafe(item.path)
}

function onResize() {
  windowWidth.value = window.innerWidth
}
onMounted(() => window.addEventListener('resize', onResize))
onUnmounted(() => window.removeEventListener('resize', onResize))
</script>

<style scoped>
.mobile-nav {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 999;
  display: flex;
  justify-content: space-around;
  align-items: center;
  height: 56px;
  background: var(--color-bg-card);
  border-top: 1px solid var(--color-border-light);
  padding-bottom: env(safe-area-inset-bottom);
}
.nav-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  background: none;
  border: none;
  padding: 4px 12px;
  cursor: pointer;
  color: var(--color-info);
  transition: color 0.2s;
  position: relative;
}
.nav-btn.active {
  color: #1a3c2a;
  font-weight: 600;
}
.nav-icon {
  font-size: 20px;
}
.nav-label {
  font-size: 11px;
}

/* ── 「更多」抽屉 ── */
.mobile-menu-search {
  margin-bottom: var(--spacing-sm, 8px);
}

.mobile-menu-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  max-height: 52vh;
  overflow-y: auto;
}

.mobile-menu-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 10px 8px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--color-text-primary);
  font-size: 14px;
  text-align: left;
  cursor: pointer;
}

.mobile-menu-item:hover {
  background: var(--color-bg-hover);
}

.mobile-menu-item-icon {
  flex-shrink: 0;
  color: var(--color-primary);
}

.mobile-menu-item-label {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mobile-menu-item-section {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--color-text-placeholder);
}
</style>
