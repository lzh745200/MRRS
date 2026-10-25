<template>
  <div class="ocr-suggest" data-testid="ocr-suggest">
    <div class="ocr-suggest__head">
      <el-upload :show-file-list="false" :http-request="onUpload" accept="image/*">
        <el-button size="small" :loading="loading" data-testid="ocr-upload-btn">
          识别凭证图片
        </el-button>
      </el-upload>
      <span v-if="engineHint" class="ocr-suggest__engine" data-testid="ocr-engine">
        引擎：{{ engineHint }}
      </span>
      <el-button
        v-if="adoptable.length > 1"
        size="small"
        type="primary"
        plain
        data-testid="ocr-adopt-all"
        @click="adoptAll"
      >
        全部采纳
      </el-button>
    </div>

    <el-alert
      v-if="error"
      type="warning"
      :closable="false"
      show-icon
      class="ocr-suggest__alert"
      data-testid="ocr-error"
      :title="error"
    />

    <div v-if="suggestions.length > 0" class="ocr-suggest__list" data-testid="ocr-list">
      <div
        v-for="item in suggestions"
        :key="item.key"
        class="ocr-suggest__row"
        :class="`ocr-suggest__row--${item.level}`"
        :data-testid="`ocr-row-${item.key}`"
      >
        <span class="ocr-suggest__label">{{ item.label }}</span>
        <span class="ocr-suggest__current">{{ item.current || '（空）' }}</span>
        <span class="ocr-suggest__arrow">→</span>
        <span class="ocr-suggest__recognized">{{ item.recognized }}</span>
        <el-tag size="small" :type="tagType(item.level)">{{ levelText(item.level) }}</el-tag>
        <span v-if="item.same" class="ocr-suggest__same">与当前值相同</span>
        <el-button
          v-else
          size="small"
          type="primary"
          link
          :data-testid="`ocr-adopt-${item.key}`"
          @click="adopt(item)"
        >
          采纳
        </el-button>
        <el-button
          size="small"
          link
          :data-testid="`ocr-ignore-${item.key}`"
          @click="ignore(item.key)"
        >
          忽略
        </el-button>
      </div>
    </div>

    <div v-else-if="!loading && !error" class="ocr-suggest__empty" data-testid="ocr-empty">
      选择凭证图片后可自动识别金额与日期，逐字段确认后写入表单。
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * 经费凭证 OCR「字段级建议」（2026-10-25 / ⑤）
 *
 * 后端 `/funds/ocr-voucher` 早就存在，但**前端零调用** —— 现场等于"识别完还要自己抄"。
 * 本组件把它接成逐字段建议：识别 → 显示「当前值 → 识别值 + 置信度」→ 用户逐条采纳/忽略。
 *
 * 为什么不一次性覆盖表单：覆盖错了更麻烦，且用户不知道改了哪几个字段；
 * 逐条确认把控制权留在人手上，符合"审计留痕"场景的使用习惯。
 */
import { computed, ref } from 'vue'

import { fundApi } from '@/api/funds'
import {
  DEFAULT_OCR_TARGETS,
  buildOcrSuggestions,
  type OcrFieldSuggestion,
  type OcrFieldTarget,
  type OcrRawResult,
  type OcrSuggestionLevel,
} from '@/utils/ocrSuggestion'

const props = withDefaults(
  defineProps<{
    /** 表单当前值（展示"将会覆盖成什么"） */
    current?: Record<string, string>
    /** 字段映射，默认金额 + 划转日期 */
    targets?: OcrFieldTarget[]
  }>(),
  {
    current: () => ({}),
    targets: () => DEFAULT_OCR_TARGETS,
  }
)

const emit = defineEmits<{
  (e: 'apply', payload: { key: string; value: string }): void
  (e: 'apply-all', payload: Record<string, string>): void
}>()

const loading = ref(false)
const error = ref('')
const engineHint = ref('')
const suggestions = ref<OcrFieldSuggestion[]>([])

/** 尚未采纳的建议里，"与当前值不同"的都可一键采纳 */
const adoptable = computed(() => suggestions.value.filter((item) => !item.same))

const LEVEL_TEXT: Record<OcrSuggestionLevel, string> = {
  high: '高置信',
  medium: '需核对',
  low: '低置信',
}

const TAG_TYPE: Record<OcrSuggestionLevel, 'success' | 'warning' | 'danger'> = {
  high: 'success',
  medium: 'warning',
  low: 'danger',
}

function levelText(level: OcrSuggestionLevel): string {
  return LEVEL_TEXT[level]
}

function tagType(level: OcrSuggestionLevel): 'success' | 'warning' | 'danger' {
  return TAG_TYPE[level]
}

/** el-upload 的 http-request：接管上传，走 OCR 接口（不落盘）。 */
async function onUpload(options: { file: File }): Promise<void> {
  const file = options?.file
  if (!file) return
  loading.value = true
  error.value = ''
  suggestions.value = []
  try {
    const result = (await fundApi.ocrVoucher(file)) as OcrRawResult
    engineHint.value = result?.engine || ''
    suggestions.value = buildOcrSuggestions(result || {}, props.current, props.targets)
    if (suggestions.value.length === 0) {
      error.value = '未能识别出金额或日期，请手工录入'
    }
  } catch (e) {
    // 503 = 引擎不可用（ARM64 侧会降级），提示手工录入而不阻断业务
    error.value = describeError(e)
  } finally {
    loading.value = false
  }
}

/** 把后端 503 / 其他错误翻译成用户能懂的话。 */
function describeError(error: unknown): string {
  const box = (error ?? {}) as Record<string, unknown>
  const status = box.status ?? (box.response as Record<string, unknown> | undefined)?.status
  if (status === 503) return '识别引擎不可用（当前平台不支持），请手工录入'
  const detail = box.detail ?? box.message
  if (typeof detail === 'string' && detail.trim()) return detail
  return '识别失败，请重试或手工录入'
}

function adopt(item: OcrFieldSuggestion): void {
  emit('apply', { key: item.key, value: item.recognized })
  ignore(item.key)
}

function adoptAll(): void {
  const payload: Record<string, string> = {}
  for (const item of adoptable.value) payload[item.key] = item.recognized
  if (Object.keys(payload).length === 0) return
  emit('apply-all', payload)
  suggestions.value = []
}

function ignore(key: string): void {
  suggestions.value = suggestions.value.filter((item) => item.key !== key)
}
</script>

<style scoped lang="scss">
.ocr-suggest__head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.ocr-suggest__engine {
  font-size: 12px;
  color: var(--color-text-secondary);
}

.ocr-suggest__alert {
  margin-bottom: 8px;
}

.ocr-suggest__list {
  border: 1px solid var(--color-card-border);
  border-radius: var(--radius-control);
  padding: 8px 12px;
}

.ocr-suggest__row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  font-size: 13px;

  & + & {
    border-top: 1px dashed var(--color-card-border);
  }
}

.ocr-suggest__label {
  min-width: 72px;
  color: var(--color-text-secondary);
}

.ocr-suggest__current {
  color: var(--color-text-placeholder);
}

.ocr-suggest__recognized {
  font-weight: 600;
  color: var(--color-text-primary);
}

.ocr-suggest__same {
  font-size: 12px;
  color: var(--color-text-placeholder);
}

.ocr-suggest__empty {
  font-size: 13px;
  color: var(--color-text-placeholder);
}
</style>
