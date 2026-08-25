<template>
  <div
    class="skeleton"
    :class="[`skeleton--${variant}`, `skeleton--${animation}`, { 'skeleton--loading': loading }]"
    :style="skeletonStyle"
    role="status"
    :aria-busy="loading"
    aria-label="加载中"
  >
    <!-- 列表布局 -->
    <template v-if="variant === 'list'">
      <div v-for="i in rows" :key="i" class="skeleton__list-item">
        <div v-if="avatar" class="skeleton__avatar" :style="avatarStyle"></div>
        <div class="skeleton__content">
          <div class="skeleton__title"></div>
          <div class="skeleton__text"></div>
        </div>
      </div>
    </template>

    <!-- 卡片布局 -->
    <template v-else-if="variant === 'card'">
      <div class="skeleton__card">
        <div v-if="image" class="skeleton__image"></div>
        <div class="skeleton__card-content">
          <div class="skeleton__title"></div>
          <div class="skeleton__text"></div>
          <div class="skeleton__text skeleton__text--short"></div>
        </div>
      </div>
    </template>

    <!-- 表单布局 -->
    <template v-else-if="variant === 'form'">
      <div v-for="i in rows" :key="i" class="skeleton__form-item">
        <div class="skeleton__label"></div>
        <div class="skeleton__input"></div>
      </div>
    </template>

    <!-- 表格布局 -->
    <template v-else-if="variant === 'table'">
      <div class="skeleton__table">
        <div class="skeleton__table-header">
          <div v-for="i in columns" :key="i" class="skeleton__table-cell"></div>
        </div>
        <div v-for="row in rows" :key="row" class="skeleton__table-row">
          <div v-for="col in columns" :key="col" class="skeleton__table-cell"></div>
        </div>
      </div>
    </template>

    <!-- 文本布局 -->
    <template v-else-if="variant === 'text'">
      <div
        v-for="i in rows"
        :key="i"
        class="skeleton__text-line"
        :style="{ width: getLineWidth(i) }"
      ></div>
    </template>

    <!-- 圆形布局 -->
    <template v-else-if="variant === 'circle'">
      <div class="skeleton__circle" :style="circleStyle"></div>
    </template>

    <!-- 矩形布局（默认） -->
    <template v-else>
      <div class="skeleton__rect" :style="rectStyle"></div>
    </template>

    <!-- 插槽内容 -->
    <slot v-if="!loading"></slot>
  </div>
</template>

<script setup lang="ts">
import { computed, type CSSProperties } from 'vue'

// Props 定义
export interface SkeletonProps {
  /** 是否加载中 */
  loading?: boolean
  /** 变体类型 */
  variant?: 'rect' | 'circle' | 'text' | 'list' | 'card' | 'form' | 'table'
  /** 动画类型 */
  animation?: 'pulse' | 'wave' | 'none'
  /** 宽度 */
  width?: string | number
  /** 高度 */
  height?: string | number
  /** 行数（用于列表、表单、文本） */
  rows?: number
  /** 列数（用于表格） */
  columns?: number
  /** 是否显示头像（用于列表） */
  avatar?: boolean
  /** 头像大小 */
  avatarSize?: string | number
  /** 是否显示图片（用于卡片） */
  image?: boolean
  /** 圆角 */
  borderRadius?: string | number
}

const props = withDefaults(defineProps<SkeletonProps>(), {
  loading: true,
  variant: 'rect',
  animation: 'pulse',
  rows: 3,
  columns: 4,
  avatar: false,
  avatarSize: 40,
  image: true,
  borderRadius: 4,
})

// 计算样式
const skeletonStyle = computed<CSSProperties>(() => ({
  '--skeleton-border-radius':
    typeof props.borderRadius === 'number' ? `${props.borderRadius}px` : props.borderRadius,
}))

const rectStyle = computed<CSSProperties>(() => ({
  width: typeof props.width === 'number' ? `${props.width}px` : props.width || '100%',
  height: typeof props.height === 'number' ? `${props.height}px` : props.height || '20px',
}))

const circleStyle = computed<CSSProperties>(() => {
  const size = typeof props.width === 'number' ? `${props.width}px` : props.width || '40px'
  return {
    width: size,
    height: size,
  }
})

const avatarStyle = computed<CSSProperties>(() => {
  const size = typeof props.avatarSize === 'number' ? `${props.avatarSize}px` : props.avatarSize
  return {
    width: size,
    height: size,
  }
})

// 获取文本行宽度（最后一行较短）
function getLineWidth(index: number): string {
  if (index === props.rows) {
    return '60%'
  }
  return '100%'
}
</script>

<style lang="scss" scoped>
.skeleton {
  --skeleton-bg: #e0e0e0;
  --skeleton-highlight: #f5f5f5;
  --skeleton-border-radius: 4px;

  &--loading {
    pointer-events: none;
  }

  // 动画
  &--pulse {
    .skeleton__rect,
    .skeleton__circle,
    .skeleton__text-line,
    .skeleton__avatar,
    .skeleton__title,
    .skeleton__text,
    .skeleton__label,
    .skeleton__input,
    .skeleton__image,
    .skeleton__table-cell {
      animation: skeleton-pulse 1.5s ease-in-out infinite;
    }
  }

  &--wave {
    .skeleton__rect,
    .skeleton__circle,
    .skeleton__text-line,
    .skeleton__avatar,
    .skeleton__title,
    .skeleton__text,
    .skeleton__label,
    .skeleton__input,
    .skeleton__image,
    .skeleton__table-cell {
      background: linear-gradient(
        90deg,
        var(--skeleton-bg) 25%,
        var(--skeleton-highlight) 50%,
        var(--skeleton-bg) 75%
      );
      background-size: 200% 100%;
      animation: skeleton-wave 1.5s ease-in-out infinite;
    }
  }

  // 基础元素
  &__rect,
  &__circle,
  &__text-line,
  &__avatar,
  &__title,
  &__text,
  &__label,
  &__input,
  &__image,
  &__table-cell {
    background-color: var(--skeleton-bg);
    border-radius: var(--skeleton-border-radius);
  }

  &__circle {
    border-radius: 50%;
  }

  // 列表布局
  &__list-item {
    display: flex;
    align-items: flex-start;
    padding: 12px 0;

    &:not(:last-child) {
      border-bottom: 1px solid var(--color-bg-hover);
    }
  }

  &__avatar {
    flex-shrink: 0;
    border-radius: 50%;
    margin-right: 12px;
  }

  &__content {
    flex: 1;
    min-width: 0;
  }

  &__title {
    height: 16px;
    width: 40%;
    margin-bottom: 8px;
  }

  &__text {
    height: 14px;
    width: 100%;

    &--short {
      width: 60%;
      margin-top: 8px;
    }
  }

  // 卡片布局
  &__card {
    border-radius: 8px;
    overflow: hidden;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  }

  &__image {
    height: 200px;
    border-radius: 0;
  }

  &__card-content {
    padding: 16px;
  }

  // 表单布局
  &__form-item {
    margin-bottom: 20px;
  }

  &__label {
    height: 14px;
    width: 80px;
    margin-bottom: 8px;
  }

  &__input {
    height: 32px;
    width: 100%;
  }

  // 表格布局
  &__table {
    width: 100%;
    border: 1px solid var(--color-bg-hover);
    border-radius: 4px;
    overflow: hidden;
  }

  &__table-header {
    display: flex;
    background-color: #fafafa;
    border-bottom: 1px solid var(--color-bg-hover);

    .skeleton__table-cell {
      height: 20px;
      margin: 12px 8px;
    }
  }

  &__table-row {
    display: flex;
    border-bottom: 1px solid var(--color-bg-hover);

    &:last-child {
      border-bottom: none;
    }

    .skeleton__table-cell {
      height: 16px;
      margin: 16px 8px;
    }
  }

  &__table-cell {
    flex: 1;
  }

  // 文本布局
  &__text-line {
    height: 14px;
    margin-bottom: 12px;

    &:last-child {
      margin-bottom: 0;
    }
  }
}

// 动画关键帧
@keyframes skeleton-pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.4;
  }
}

@keyframes skeleton-wave {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}
</style>
