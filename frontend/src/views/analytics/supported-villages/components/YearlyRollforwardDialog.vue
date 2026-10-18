<template>
  <div class="yearly-rollforward-dialog">
    <div v-if="loading" class="rollforward-loading">正在加载 {{ fromYear }} 年数据…</div>

    <el-alert
      v-else-if="loadError"
      class="rollforward-error"
      type="error"
      :closable="false"
      show-icon
      :title="loadError"
    />

    <template v-else-if="hasPreviousData">
      <div class="rollforward-toolbar">
        <el-checkbox :model-value="allSelected" @change="handleToggleAll"
          >全选可沿用板块</el-checkbox
        >
        <span class="select-summary">
          已选 {{ selectedKeys.length }} / {{ selectableSections.length }} 个板块，可沿用
          {{ selectedCopyableCount }} 项字段
        </span>
      </div>

      <div class="section-list">
        <div
          v-for="section in sections"
          :key="section.key"
          class="section-item"
          :class="{ 'section-item-disabled': !section.hasPreviousData }"
        >
          <el-checkbox
            :model-value="selectedKeys.includes(section.key)"
            :disabled="!section.hasPreviousData"
            @change="handleSectionChange(section.key, $event)"
          >
            {{ section.title }}
          </el-checkbox>
          <span v-if="section.hasPreviousData" class="section-counts">
            可沿用 {{ section.copyableCount }} · 保留 {{ section.keptCount }} · 需重填
            {{ section.blankCount }}
          </span>
          <span v-else class="section-counts section-no-data">无上年数据</span>
        </div>
      </div>

      <div v-if="selectedSections.length" class="diff-panel">
        <h4 class="diff-title">逐字段差异（沿用 / 保留本年度 / 需重填）</h4>
        <div v-for="section in selectedSections" :key="section.key" class="diff-section">
          <div class="diff-section-title">{{ section.title }}</div>
          <div
            v-for="field in section.fields"
            :key="field.field"
            class="diff-row"
            :class="'status-' + field.status"
          >
            <span class="diff-label">{{ field.label }}</span>
            <span class="diff-previous">上年：{{ formatValue(field.previousValue) }}</span>
            <span class="diff-current">本年度：{{ formatValue(field.currentValue) }}</span>
            <el-tag size="small" :type="statusTagType(field.status)">
              {{ statusLabel(field.status) }}
            </el-tag>
          </div>
        </div>
      </div>

      <div class="mode-panel">
        <span class="mode-label">写入方式：</span>
        <el-radio-group v-model="overwrite">
          <el-radio :value="false">只填空字段（推荐，不覆盖本年度已有值）</el-radio>
          <el-radio :value="true">覆盖本年度已有值</el-radio>
        </el-radio-group>
      </div>

      <el-alert class="impact-tip" type="warning" :closable="false" show-icon :title="impactText" />
    </template>

    <el-alert
      v-else
      class="rollforward-empty"
      type="info"
      :closable="false"
      show-icon
      :title="emptyMessage"
    />

    <div class="dialog-actions">
      <el-button class="btn-cancel" @click="handleClose">取消</el-button>
      <el-button
        class="btn-submit"
        type="primary"
        :loading="submitting"
        :disabled="!canSubmit"
        @click="handleSubmit"
      >
        确认沿用
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { logger } from '@/utils/logger'
import { getErrorMessage } from '@/utils/getErrorMessage'
import {
  getYearlyPrefill,
  rollforwardYearlyData,
  type YearlyPrefillResult,
  type YearlyPrefillSection,
} from '@/api/supportedVillage'

const props = defineProps<{
  villageId: number
  year: number
}>()

const emit = defineEmits<{
  close: []
  applied: []
}>()

const fromYear = computed(() => props.year - 1)
const loading = ref(false)
const submitting = ref(false)
const loadError = ref('')
const prefill = ref<YearlyPrefillResult | null>(null)
const selectedKeys = ref<string[]>([])
const overwrite = ref(false)

const STATUS_LABELS: Record<string, string> = {
  copy: '可沿用',
  keep: '保留本年度',
  blank: '需重填',
}
const STATUS_TAG_TYPES: Record<string, 'success' | 'info' | 'warning'> = {
  copy: 'success',
  keep: 'info',
  blank: 'warning',
}

function statusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status
}

function statusTagType(status: string): 'success' | 'info' | 'warning' {
  return STATUS_TAG_TYPES[status] ?? 'info'
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—'
  if (Array.isArray(value)) return `${value.length} 项`
  if (typeof value === 'boolean') return value ? '是' : '否'
  return String(value)
}

const sections = computed<YearlyPrefillSection[]>(() => prefill.value?.sections ?? [])
const hasPreviousData = computed(() => Boolean(prefill.value?.hasPreviousData))
const selectableSections = computed(() =>
  sections.value.filter((section) => section.hasPreviousData)
)
const selectedSections = computed(() =>
  selectableSections.value.filter((section) => selectedKeys.value.includes(section.key))
)
const selectedCopyableCount = computed(() =>
  selectedSections.value.reduce((sum, section) => sum + section.copyableCount, 0)
)
const selectedKeptCount = computed(() =>
  selectedSections.value.reduce((sum, section) => sum + section.keptCount, 0)
)
const allSelected = computed(() => {
  const total = selectableSections.value.length
  return total > 0 ? selectedKeys.value.length === total : false
})
const canSubmit = computed(
  () => selectedKeys.value.length > 0 && !loading.value && !submitting.value
)
const impactText = computed(() => {
  if (overwrite.value) {
    return `将用 ${fromYear.value} 年数据覆盖所选 ${selectedKeys.value.length} 个板块中已有值的字段（影响本年度已填数据，请确认）`
  }
  return `将沿用 ${selectedCopyableCount.value} 项字段到 ${props.year} 年；本年度已有 ${selectedKeptCount.value} 项非空值将保留不覆盖`
})
const emptyMessage = computed(
  () => prefill.value?.message || `${fromYear.value} 年没有可沿用的年度数据，请手工填写`
)

async function loadPrefill() {
  loading.value = true
  loadError.value = ''
  try {
    const data = await getYearlyPrefill(props.villageId, props.year)
    prefill.value = data
    const list: YearlyPrefillSection[] = data?.sections ?? []
    selectedKeys.value = list
      .filter((section) => section.hasPreviousData)
      .map((section) => section.key)
  } catch (e) {
    logger.error('加载上年数据预览失败:', e)
    loadError.value = getErrorMessage(e, '加载上年数据失败，请稍后重试')
  } finally {
    loading.value = false
  }
}

function handleToggleAll(checked: boolean | string | number) {
  selectedKeys.value = checked ? selectableSections.value.map((section) => section.key) : []
}

function handleToggleSection(key: string, checked: boolean | string | number) {
  if (checked) {
    if (!selectedKeys.value.includes(key)) {
      selectedKeys.value = [...selectedKeys.value, key]
    }
  } else {
    selectedKeys.value = selectedKeys.value.filter((item) => item !== key)
  }
}

// 模板内联箭头参数无显式类型会被 vue-tsc 判为隐式 any（TS7006）：
// 改为具名函数 + $event 传参，参数类型在此显式声明。
function handleSectionChange(key: string, checked: boolean | string | number) {
  handleToggleSection(key, checked)
}

async function handleSubmit() {
  if (!canSubmit.value) {
    ElMessage.warning('请先选择要沿用的板块')
    return
  }
  try {
    await ElMessageBox.confirm(impactText.value, '确认从上年复制', {
      confirmButtonText: '确认沿用',
      cancelButtonText: '取消',
      type: overwrite.value ? 'warning' : 'info',
    })
  } catch {
    return
  }
  submitting.value = true
  try {
    const result = await rollforwardYearlyData(props.villageId, props.year, {
      sectionKeys: [...selectedKeys.value],
      overwrite: overwrite.value,
    })
    const applied = result?.appliedFields ?? 0
    const sectionCount = result?.appliedSections?.length ?? 0
    ElMessage.success(
      applied > 0
        ? `已从 ${fromYear.value} 年沿用 ${applied} 项字段（${sectionCount} 个板块）`
        : `未做修改：${fromYear.value} 年无可沿用的有效字段或本年度已填写`
    )
    emit('applied')
    emit('close')
  } catch (e) {
    logger.error('批量沿用上年数据失败:', e)
    ElMessage.error(getErrorMessage(e, '沿用失败，请稍后重试'))
  } finally {
    submitting.value = false
  }
}

function handleClose() {
  emit('close')
}

onMounted(loadPrefill)
</script>

<style scoped>
.yearly-rollforward-dialog {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.rollforward-loading {
  padding: 24px 0;
  text-align: center;
  color: var(--color-text-secondary);
}

.rollforward-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.select-summary {
  color: var(--color-text-secondary);
  font-size: 13px;
}

.section-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 220px;
  overflow-y: auto;
  padding: 8px 12px;
  background: var(--color-bg-page);
  border-radius: 6px;
}

.section-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.section-item-disabled {
  opacity: 0.6;
}

.section-counts {
  color: var(--color-text-secondary);
  font-size: 12px;
}

.section-no-data {
  color: var(--color-text-placeholder, var(--color-text-disabled));
}

.diff-panel {
  border: 1px solid var(--color-bg-hover);
  border-radius: 6px;
  padding: 8px 12px;
  max-height: 280px;
  overflow-y: auto;
}

.diff-title {
  margin: 0 0 8px;
  font-size: 14px;
  font-weight: 600;
}

.diff-section-title {
  margin: 8px 0 4px;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-primary-dark-1);
}

.diff-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 2px 0;
  font-size: 12px;
}

.diff-label {
  min-width: 120px;
}

.diff-previous,
.diff-current {
  color: var(--color-text-secondary);
  min-width: 110px;
}

.status-copy .diff-label {
  color: var(--color-success);
}

.status-keep .diff-label {
  color: var(--color-info);
}

.status-blank .diff-label {
  color: var(--color-warning);
}

.mode-panel {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.mode-label {
  font-size: 13px;
  color: var(--color-text-secondary);
}

.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding-top: 8px;
  border-top: 1px solid var(--color-bg-hover);
}
</style>
