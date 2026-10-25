<template>
  <div
    ref="containerRef"
    class="virtual-list"
    :style="{ height: normalizedHeight }"
    data-testid="virtual-list"
    @scroll="onScroll"
  >
    <div class="virtual-list__spacer" :style="{ height: `${window.totalHeight}px` }">
      <div class="virtual-list__window" :style="{ transform: `translateY(${window.offsetTop}px)` }">
        <div
          v-for="(item, i) in visibleItems"
          :key="window.start + i"
          class="virtual-list__item"
          :style="{ height: `${itemHeight}px` }"
          data-testid="virtual-list-item"
        >
          <slot :item="item" :index="window.start + i" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * 通用虚拟列表（2026-10-26 / ⑥ 表格性能）
 *
 * 为什么自己做：项目里 `el-table` 有 1300+ 处使用，但 Element Plus 的表格**不做虚拟滚动**，
 * 上千行时渲染开销与内存都会失控（离线单机没有服务端兜底）。这里给"长列表型"页面
 * 一个低风险替代：**只渲染可视区 + 缓冲行**，DOM 行数恒定，与数据总量无关。
 *
 * 边界处理全部下沉到 `utils/virtualWindow.ts` 的纯函数（有穷举测试），
 * 组件本身只负责"测量视口高度 + 监听滚动 + 渲染窗口"。
 *
 * 用法（行高固定）：
 *   <VirtualList :items="logs" :item-height="96" height="480px" v-slot="{ item }">
 *     <LogCard :log="item" />
 *   </VirtualList>
 */
import { computed, onMounted, ref } from 'vue'

import { computeWindow, sliceWindow } from '@/utils/virtualWindow'

const props = withDefaults(
  defineProps<{
    items: readonly unknown[]
    /** 固定行高（px）；虚拟滚动要求行高一致，否则窗口计算会错位 */
    itemHeight?: number
    /** 容器高度（CSS 值或数字 px） */
    height?: string | number
    /** 上下预渲染行数 */
    buffer?: number
    /** 覆盖视口高度（单测用；运行时不传则由容器实测） */
    viewportHeight?: number
  }>(),
  {
    itemHeight: 40,
    height: 400,
    buffer: 3,
    viewportHeight: 0,
  }
)

const containerRef = ref<HTMLDivElement>()
const scrollTop = ref(0)
const measuredHeight = ref(0)

const normalizedHeight = computed(() =>
  typeof props.height === 'number' ? `${props.height}px` : props.height
)

const viewport = computed(() => props.viewportHeight || measuredHeight.value)

const window = computed(() =>
  computeWindow({
    scrollTop: scrollTop.value,
    viewportHeight: viewport.value,
    itemHeight: props.itemHeight,
    total: props.items.length,
    buffer: props.buffer,
  })
)

const visibleItems = computed(() => sliceWindow(props.items, window.value))

function onScroll(event: Event): void {
  // 滚动事件的目标恒为容器自身（jsdom 下 scrollTop 恒 0，真实浏览器给数字）
  scrollTop.value = (event.target as HTMLElement).scrollTop || 0
}

onMounted(() => {
  // 视口高度只在挂载时测一次：容器高度由 props 固定，不需要监听窗口 resize
  // mounted 之后容器必然存在；clientHeight 在 jsdom 为 0，真实浏览器为实际高度
  measuredHeight.value = (containerRef.value as HTMLDivElement).clientHeight
})
</script>

<style scoped lang="scss">
.virtual-list {
  overflow-y: auto;
  position: relative;
}

.virtual-list__spacer {
  position: relative;
  width: 100%;
}

.virtual-list__window {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  will-change: transform;
}

.virtual-list__item {
  box-sizing: border-box;
  overflow: hidden;
}
</style>
