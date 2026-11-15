<template>
  <!--
    首次登录操作指引：
    - 非模态、无遮罩，页面保持可操作；
    - 仅提示 + 上一步/下一步/跳过/关闭，不产生任何需要用户回答的交互；
    - 完成后写 localStorage，按用户维度只展示一次。
  -->
  <aside
    v-if="visible"
    class="first-use-guide"
    :style="cardStyle"
    role="complementary"
    aria-label="首次使用操作指引"
    aria-live="polite"
  >
    <div class="guide-head">
      <span class="guide-step">第 {{ index + 1 }} / {{ steps.length }} 步</span>
      <button type="button" class="guide-close" aria-label="关闭指引" @click="finish">×</button>
    </div>

    <h3 class="guide-title">{{ currentStep.title }}</h3>
    <p class="guide-body">{{ currentStep.body }}</p>

    <div class="guide-dots" aria-hidden="true">
      <span
        v-for="(step, i) in steps"
        :key="step.key"
        class="guide-dot"
        :class="{ active: i === index }"
      ></span>
    </div>

    <div class="guide-actions">
      <button type="button" class="guide-btn guide-btn-text" @click="finish">跳过指引</button>
      <button v-if="index > 0" type="button" class="guide-btn guide-btn-text" @click="goPrev">
        上一步
      </button>
      <button type="button" class="guide-btn guide-btn-primary" @click="goNext">
        {{ isLast ? '完成' : '下一步' }}
      </button>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { FIRST_USE_GUIDE_PENDING_KEY, firstUseGuideDoneKey, useAuthStore } from '@/stores/auth'

type Placement = 'right' | 'bottom' | 'top' | 'center'

interface GuideStep {
  key: string
  title: string
  body: string
  target: string
  placement: Placement
}

/**
 * 步骤顺序固定：先认识工作台 → 再认识导航 → 再找常用操作 → 最后找帮助。
 * target 对应页面上的 data-guide 锚点；目标不存在时自动居中展示，不报错。
 */
const steps: GuideStep[] = [
  {
    key: 'welcome',
    title: '欢迎使用工作台',
    body: '这里汇总你权限范围内的数据概览和最新动态。可以先用几秒钟熟悉整体布局。',
    target: '[data-guide="dashboard-header"]',
    placement: 'bottom',
  },
  {
    key: 'navigation',
    title: '从左侧菜单开始',
    body: '左侧菜单按账号权限自动显示。点击「工作台」随时回到这里，其他模块从这里进入。',
    target: '[data-guide="sidebar"]',
    placement: 'right',
  },
  {
    key: 'quick-actions',
    title: '常用操作入口',
    body: '快捷入口把新建项目、新增帮扶村、资金申请等高频操作放在一起，减少来回找菜单。',
    target: '[data-guide="dashboard-quick-actions"]',
    placement: 'top',
  },
  {
    key: 'help',
    title: '遇到问题看帮助中心',
    body: '帮助中心提供登录、用户管理、机器码、备份恢复等操作说明；本指引可随时跳过或关闭。',
    target: '[data-guide="help-menu"]',
    placement: 'right',
  },
]

const authStore = useAuthStore()
const visible = ref(false)
const index = ref(0)
const cardStyle = ref<Record<string, string>>({})
let highlighted: HTMLElement | null = null

const currentStep = computed(() => steps[index.value])
const isLast = computed(() => index.value === steps.length - 1)

function clearHighlight() {
  highlighted?.classList.remove('first-use-guide-target')
  highlighted = null
}

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), Math.max(min, max))
}

/** 计算提示卡位置；目标不存在时居中，保证任何权限/路由下都能展示。 */
function updatePosition() {
  clearHighlight()
  const step = currentStep.value
  const candidates = Array.from(document.querySelectorAll<HTMLElement>(step.target))
  const target = candidates.find((el) => el.offsetParent !== null) || candidates[0] || null

  if (!target) {
    cardStyle.value = {
      left: '50%',
      top: '50%',
      transform: 'translate(-50%, -50%)',
    }
    return
  }

  highlighted = target
  target.classList.add('first-use-guide-target')
  const rect = target.getBoundingClientRect()
  const cardWidth = 340
  const margin = 16
  const viewportWidth = window.innerWidth || 1280
  const viewportHeight = window.innerHeight || 800
  let left = rect.left
  let top = rect.bottom + margin

  if (step.placement === 'right') {
    left = rect.right + margin
    top = rect.top + 16
  } else if (step.placement === 'top') {
    left = rect.left
    top = rect.top - 220
  }

  cardStyle.value = {
    left: `${clamp(left, margin, viewportWidth - cardWidth - margin)}px`,
    top: `${clamp(top, margin, viewportHeight - 220)}px`,
    transform: 'none',
  }
}

function persistDone() {
  const user = authStore.user
  try {
    if (user?.id != null) {
      localStorage.setItem(firstUseGuideDoneKey(user.id), 'done')
    }
    sessionStorage.removeItem(FIRST_USE_GUIDE_PENDING_KEY)
  } catch {
    /* 隐私模式/配额异常：关闭动作仍应生效 */
  }
  clearHighlight()
  visible.value = false
}

function finish() {
  persistDone()
}

async function moveTo(nextIndex: number) {
  if (nextIndex < 0 || nextIndex >= steps.length) return
  index.value = nextIndex
  await nextTick()
  updatePosition()
}

const goPrev = () => moveTo(index.value - 1)
const goNext = () => {
  if (isLast.value) {
    finish()
    return
  }
  void moveTo(index.value + 1)
}

onMounted(async () => {
  const user = authStore.user
  if (!user?.id) return
  try {
    if (sessionStorage.getItem(FIRST_USE_GUIDE_PENDING_KEY) !== String(user.id)) return
    if (localStorage.getItem(firstUseGuideDoneKey(user.id)) === 'done') {
      sessionStorage.removeItem(FIRST_USE_GUIDE_PENDING_KEY)
      return
    }
    visible.value = true
    await nextTick()
    updatePosition()
    window.addEventListener('resize', updatePosition)
    window.addEventListener('scroll', updatePosition, true)
  } catch {
    /* 存储不可用时不展示，不影响正常使用 */
  }
})

onBeforeUnmount(() => {
  clearHighlight()
  window.removeEventListener('resize', updatePosition)
  window.removeEventListener('scroll', updatePosition, true)
})
</script>

<style scoped>
.first-use-guide {
  position: fixed;
  z-index: 2500;
  width: 340px;
  max-width: calc(100vw - 32px);
  padding: 18px;
  box-sizing: border-box;
  border: 1px solid var(--el-color-primary-light-5);
  border-radius: 12px;
  background: var(--el-bg-color-overlay);
  box-shadow: var(--shadow-pop);
  color: var(--el-text-color-primary);
}

.guide-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.guide-step {
  color: var(--el-color-primary);
  font-size: 12px;
  font-weight: 600;
}

.guide-close {
  width: 24px;
  height: 24px;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--el-text-color-secondary);
  font-size: 20px;
  line-height: 1;
  cursor: pointer;
}

.guide-title {
  margin: 8px 0 6px;
  font-size: 16px;
  font-weight: 700;
}

.guide-body {
  margin: 0;
  color: var(--el-text-color-regular);
  font-size: 13px;
  line-height: 1.7;
}

.guide-dots {
  display: flex;
  gap: 6px;
  margin: 14px 0 12px;
}

.guide-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--el-border-color);
}

.guide-dot.active {
  width: 18px;
  border-radius: 999px;
  background: var(--el-color-primary);
}

.guide-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
}

.guide-btn {
  padding: 6px 10px;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
}

.guide-btn-text {
  border: 0;
  background: transparent;
  color: var(--el-text-color-secondary);
}

.guide-btn-primary {
  border: 1px solid var(--el-color-primary);
  background: var(--el-color-primary);
  color: var(--el-color-white);
}

:global(.first-use-guide-target) {
  outline: 3px solid var(--el-color-primary);
  outline-offset: 3px;
  border-radius: 8px;
  box-shadow: var(--shadow-pop);
}
</style>
