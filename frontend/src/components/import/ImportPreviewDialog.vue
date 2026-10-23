<template>
  <el-dialog
    :model-value="visible"
    :title="title"
    width="640px"
    class="import-preview"
    @update:model-value="onVisibleChange"
  >
    <!-- 包基本信息 -->
    <el-descriptions :column="2" border class="import-preview__info">
      <el-descriptions-item v-for="item in infoItems" :key="item.label" :label="item.label">
        {{ item.value }}
      </el-descriptions-item>
    </el-descriptions>

    <!-- 重复导入告警（同一校验和已导入过） -->
    <el-alert
      v-if="hasDuplicate"
      class="import-preview__duplicate"
      type="warning"
      :closable="false"
      show-icon
      :title="duplicateTitle"
    />

    <!-- 差异对比：包内 vs 本机 -->
    <el-table :data="diff" border class="import-preview__diff">
      <el-table-column prop="label" label="类别" width="180" />
      <el-table-column prop="incoming" label="包内" width="120" align="right" />
      <el-table-column prop="local" label="本机" width="120" align="right" />
      <el-table-column label="说明">
        <template #default="{ row }">
          <el-tag :type="row.conflict ? 'danger' : 'info'" size="small">
            {{ row.conflict ? '存在冲突' : '无冲突' }}
          </el-tag>
        </template>
      </el-table-column>
    </el-table>

    <!-- 冲突策略：默认逐条比对（最安全） -->
    <div class="import-preview__strategy">
      <span class="import-preview__strategy-label">冲突处理：</span>
      <el-radio-group :model-value="strategy" @update:model-value="onStrategyChange">
        <el-radio v-for="opt in STRATEGY_OPTIONS" :key="opt.value" :value="opt.value">
          {{ opt.label }}
        </el-radio>
      </el-radio-group>
    </div>

    <template #footer>
      <el-button @click="onCancel">取消</el-button>
      <el-button type="primary" :disabled="hasDuplicate && !allowForce" @click="onConfirm">
        确认导入
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
/**
 * 介质数据包导入前「差异确认」弹窗（P2）。
 *
 * 用途：导入任何介质包（数据包 / 授权包 / 配置包 / 管控包）之前，把
 * 「包信息 + 与本机的差异 + 重复导入告警 + 冲突策略」一屏摊开，确认后才落库。
 * 这是纯展示组件：不发请求、不解析包，由调用方准备数据、处理 confirm。
 */
import { computed } from 'vue'

/** 冲突处理策略：以包为准 / 以本机为准 / 逐条比对（默认，最安全） */
export type ConflictStrategy = 'package' | 'local' | 'compare'

export interface DiffRow {
  label: string
  incoming: number | string
  local: number | string
  conflict?: boolean
}

export interface ImportPackageInfo {
  /** 包类型（数据包 / 授权包 / 配置包 / 管控包） */
  type?: string
  /** 来源单位行政区划代码 */
  sourceOrgCode?: string
  /** 整包校验和（SHA256 前 12 位即可） */
  checksum?: string
  /** 记录数 */
  recordCount?: number
  /** 文件名 */
  fileName?: string
}

export interface DuplicateInfo {
  createdAt?: string
  username?: string
}

const props = withDefaults(
  defineProps<{
    visible: boolean
    title?: string
    info?: ImportPackageInfo
    diff?: DiffRow[]
    duplicate?: DuplicateInfo | null
    strategy?: ConflictStrategy
    /** 已确认重复导入时是否允许继续（由调用方传入 force 决策） */
    allowForce?: boolean
  }>(),
  {
    title: '导入前确认',
    info: () => ({}),
    diff: () => [],
    duplicate: null,
    strategy: 'compare',
    allowForce: false,
  }
)

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'update:strategy', value: ConflictStrategy): void
  (e: 'confirm'): void
  (e: 'cancel'): void
}>()

const STRATEGY_OPTIONS: { value: ConflictStrategy; label: string }[] = [
  { value: 'compare', label: '逐条比对（推荐）' },
  { value: 'package', label: '以包为准' },
  { value: 'local', label: '以本机为准' },
]

const hasDuplicate = computed(() => Boolean(props.duplicate))

const duplicateTitle = computed(() => {
  const when = props.duplicate?.createdAt || '未知时间'
  const who = props.duplicate?.username || '未知操作人'
  return '该数据包已于 ' + when + ' 由 ' + who + ' 导入过，请确认是否重复导入'
})

const infoItems = computed(() => {
  const info = props.info
  return [
    { label: '包类型', value: info.type || '—' },
    { label: '来源单位码', value: info.sourceOrgCode || '—' },
    { label: '校验和', value: info.checksum ? info.checksum.slice(0, 12) : '—' },
    { label: '记录数', value: info.recordCount === undefined ? '—' : String(info.recordCount) },
    { label: '文件名', value: info.fileName || '—' },
  ]
})

function onVisibleChange(value: boolean): void {
  emit('update:visible', value)
}

function onStrategyChange(value: unknown): void {
  emit('update:strategy', value as ConflictStrategy)
}

function onConfirm(): void {
  emit('confirm')
}

function onCancel(): void {
  emit('cancel')
}

defineExpose({ hasDuplicate, duplicateTitle, infoItems, STRATEGY_OPTIONS, onVisibleChange })
</script>

<style scoped>
.import-preview__info {
  margin-bottom: 12px;
}

.import-preview__duplicate {
  margin-bottom: 12px;
}

.import-preview__diff {
  margin-bottom: 12px;
}

.import-preview__strategy {
  display: flex;
  align-items: center;
  gap: 8px;
}

.import-preview__strategy-label {
  color: var(--color-text-secondary);
  font-size: 13px;
}
</style>
