<template>
  <nav v-if="isMobile" class="mobile-nav">
    <button
      v-for="item in navItems"
      :key="item.path"
      class="nav-btn"
      :class="{ active: isActive(item.path) }"
      @click="navigate(item.path)"
    >
      <el-icon class="nav-icon" :size="20">
        <component :is="item.icon" />
      </el-icon>
      <span class="nav-label">{{ item.label }}</span>
      <!-- /* c8 ignore next -- badge 恒为空字符串，v-if 真分支不可达 */ -->
      <span v-if="item.badge" class="nav-badge">{{ item.badge }}</span>
    </button>
  </nav>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useRouterSafe } from '@/composables/useRouterSafe'
import { HomeFilled, Grid, Money, Message, User } from '@element-plus/icons-vue'

const route = useRoute()
const { pushSafe } = useRouterSafe()

const windowWidth = ref(window.innerWidth)
const isMobile = computed(() => windowWidth.value < 768)

const navItems = [
  { path: '/dashboard', label: '首页', icon: HomeFilled },
  { path: '/supported-villages', label: '帮扶村', icon: Grid },
  { path: '/funds', label: '经费', icon: Money },
  { path: '/message', label: '消息', icon: Message, badge: '' },
  { path: '/profile', label: '我的', icon: User },
]

function isActive(path: string) {
  return route.path === path || route.path.startsWith(path + '/')
}

function navigate(path: string) {
  pushSafe(path)
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
  background: #fff;
  border-top: 1px solid #e4e7ed;
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
.nav-badge {
  position: absolute;
  top: 0;
  right: 4px;
  min-width: 16px;
  height: 16px;
  border-radius: 8px;
  background: var(--color-danger);
  color: #fff;
  font-size: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 4px;
}
</style>
