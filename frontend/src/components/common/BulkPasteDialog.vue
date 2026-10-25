<template>
  <el-dialog
    :model-value="visible"
    :title="title"
    width="720px"
    class="bulk-paste"
    data-testid="bulk-paste-dialog"
    @update:model-value="onVisibleChange"
  >
    <div class="bulk-paste__hint" data-testid="bulk-paste-hint">
      {{ hintText }}
    </div>

    <!-- 目标列：让用户一眼看到"粘几列、每列是什么"，避免错位（错位比缺行更难发现） -->
    <div class="bulk-paste__columns" data-testid="bulk-paste-columns">
      <el-tag v-for="(col, index) in columns" :key="col.key" size="small" class="bulk-paste__col">
        {{ index + 1 }}. {{ col.label
        }}<span v-if="col.required" class="bulk-paste__required">*</span>
      </el-tag>
    </div>

    <el-input
      v-model="rawText"
      type="textarea"
      :rows="6"
      resize="vertical"
      data-testid="bulk-paste-input"
      placeholder="从 Excel / WPS 复制整块数据后粘贴到这里（制表符分列、换行分行）"
    />

    <el-alert
      v-if="exceededMessage"
      class="bulk-paste__alert"
      type="error"
      :closable="false"
      show-icon
      data-testid="bulk-paste-exceeded"
      :title="exceededMessage"
    />

    <el-alert
      v-else-if="mismatchRow > 0"
      class="bulk-paste__alert"
      type="warning"
      :closable="false"
      show-icon
      data-testid="bulk-paste-mismatch"
      :title="`第 ${mismatchRow} 行列数与目标列（${columns.length} 列）不一致，请检查后再确认`"
    />

    <div v-if="rows.length > 0" class="bulk-paste__summary" data-testid="bulk-paste-summary">
      已解析 <strong>{{ rows.length }}</strong> 行 × <strong>{{ rows[0].length }}</strong> 列
      <span v-if="normalizedRows.length > PREVIEW_ROWS"
        >（下表仅预览前 {{ PREVIEW_ROWS }} 行）</span
      >
    </div>

    <el-table
      v-if="previewMatrix.length > 0"
      :data="previewMatrix"
      border
      size="small"
      max-height="240"
      data-testid="bulk-paste-preview"
    >
      <el-table-column type="index" label="#" width="72" align="center" />
      <el-table-column
        v-for="(col, index) in columns"
        :key="col.key"
        :label="col.label"
        min-width="120"
      >
        <template #default="{ row }">
          <span :class="{ 'bulk-paste__empty': row.cells[index].empty }">
            {{ row.cells[index].text }}
          </span>
        </template>
      </el-table-column>
    </el-table>

    <template #footer>
      <el-button data-testid="bulk-paste-cancel" @click="onCancel">取消</el-button>
      <el-button
        type="primary"
        :disabled="!canConfirm"
        data-testid="bulk-paste-confirm"
        @click="onConfirm"
      >
        确认填入
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
/**
 * 批量粘贴弹窗（2026-10-25 / ③ 录入效率包）
 *
 * 现场数据多数先在 Excel/WPS 里整理好，逐条手敲是最费时的一步。本组件只做三件事：
 * 1. 收下剪贴板文本（`parsePastedTable` 负责所有边界）；
 * 2. **把将要填入的内容原样展示**（列含义 + 前 N 行预览 + 空单元格显式标 `—`）；
 * 3. 列数一致、未超限才允许确认 —— 不做任何"自动补空/自动对齐"，因为错位比缺行更难发现。
 *
 * 只 emit 数据，不直接改业务状态：调用方拿到 `rows` 后自行决定是"填入当前表单"
 * 还是"批量新增"，避免组件与业务耦合。
 */
import { computed, ref, watch } from 'vue'

import { parsePastedTable } from '@/utils/parsePastedTable'

export interface BulkPasteColumn {
  /** 业务字段名（调用方据此映射） */
  key: string
  /** 表头显示名 */
  label: string
  /** 必填列（仅用于表头标注，校验仍由调用方表单负责） */
  required?: boolean
}

const props = withDefaults(
  defineProps<{
    visible: boolean
    columns: BulkPasteColumn[]
    title?: string
    maxRows?: number
    maxCols?: number
    hint?: string
  }>(),
  {
    title: '批量粘贴',
    maxRows: 500,
    maxCols: 50,
    hint: '',
  }
)

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'confirm', rows: string[][]): void
  (e: 'cancel'): void
}>()

/** 预览最多展示多少行（数据仍全量交给调用方）。 */
const PREVIEW_ROWS = 8

const rawText = ref('')

const parsed = computed(() =>
  parsePastedTable(rawText.value, { maxRows: props.maxRows, maxCols: props.maxCols })
)

const rows = computed(() => parsed.value.rows)

/**
 * 归一化到目标列数：**行尾缺失补空**。
 *
 * Excel 复制时行尾空单元格会被省略（某行第 3 列恰好为空，粘出来只有 2 个字段），
 * 这是常态而不是错位 —— 按"列数不等即报错"会大量误拦真实数据。
 * 真正危险的是**多列**（多选了列/整体错位），那种必须拦下让人工核对。
 */
const normalizedRows = computed(() =>
  rows.value.map((row) => {
    const expected = props.columns.length
    if (row.length >= expected) return row
    return [...row, ...Array.from({ length: expected - row.length }, () => '')]
  })
)

const previewRows = computed(() => normalizedRows.value.slice(0, PREVIEW_ROWS))

/**
 * 预览矩阵：把空单元格渲染成显式 `—`。
 * 放在脚本里而不是模板表达式里，是为了让"空格子判定"可被单测直接覆盖
 * （模板插槽在 el-table 被 stub 时不会执行，判定写在模板里就成了覆盖率黑洞）。
 */
const previewMatrix = computed(() =>
  previewRows.value.map((row) => ({
    cells: row.map((value) => {
      const empty = isEmptyCell(value)
      return { text: empty ? '—' : value, empty }
    }),
  }))
)

/** 仅当某行**列数多于**目标列数时才视为错位。 */
const mismatchRow = computed(() => {
  if (normalizedRows.value.length === 0) return 0
  const index = normalizedRows.value.findIndex((row) => row.length > props.columns.length)
  return index >= 0 ? index + 1 : 0
})

const exceededMessage = computed(() => {
  if (!parsed.value.exceeded) return ''
  return parsed.value.exceededBy === 'rows'
    ? `粘贴行数超过上限（最多 ${props.maxRows} 行），请分批粘贴`
    : `粘贴列数超过上限（最多 ${props.maxCols} 列），请检查是否多选了列`
})

const hintText = computed(
  () =>
    props.hint ||
    '从 Excel / WPS 选中区域后复制，粘贴到下方输入框；制表符分列、换行分行，含制表符的单元格请用英文双引号包裹。'
)

const canConfirm = computed(
  () => rows.value.length > 0 && !parsed.value.exceeded && mismatchRow.value === 0
)

function isEmptyCell(value: string | undefined): boolean {
  return value === undefined || value.trim() === ''
}

function reset() {
  rawText.value = ''
}

function onVisibleChange(value: boolean) {
  if (!value) reset()
  emit('update:visible', value)
}

function onCancel() {
  reset()
  emit('cancel')
  emit('update:visible', false)
}

function onConfirm() {
  if (!canConfirm.value) return
  emit(
    'confirm',
    normalizedRows.value.map((row) => [...row])
  )
  reset()
  emit('update:visible', false)
}

// 关闭状态下重新打开时清空，避免上次残留文本被误当成新数据
watch(
  () => props.visible,
  (visible) => {
    if (!visible) reset()
  }
)
</script>

<style scoped lang="scss">
.bulk-paste__hint {
  margin-bottom: 8px;
  font-size: 13px;
  color: var(--color-text-secondary);
  line-height: 1.5;
}

.bulk-paste__columns {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}

.bulk-paste__required {
  color: var(--color-danger);
  margin-left: 2px;
}

.bulk-paste__alert {
  margin-top: 8px;
}

.bulk-paste__summary {
  margin: 8px 0;
  font-size: 13px;
  color: var(--color-text-secondary);
}

.bulk-paste__empty {
  color: var(--color-text-placeholder);
}
</style>
