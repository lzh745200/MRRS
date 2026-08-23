<template>
  <el-dialog
    :model-value="visible"
    title="变更历史"
    width="680px"
    @update:model-value="$emit('update:visible', $event)"
  >
    <el-empty v-if="!history?.length" description="暂无变更记录" />
    <el-timeline v-else>
      <el-timeline-item
        v-for="(item, i) in history"
        :key="i"
        :timestamp="item.time"
        :type="item.changes?.length ? 'primary' : undefined"
      >
        <div>{{ item.action }} by {{ item.user }}</div>
        <div v-if="item.changes?.length" class="change-fields">
          <div v-for="(c, j) in item.changes" :key="j" class="change-field-row">
            <span class="cf-name">{{ c.field }}</span>
            <span class="cf-old">{{ formatValue(c.old_value) }}</span>
            <span class="cf-arrow">→</span>
            <span class="cf-new">{{ formatValue(c.new_value) }}</span>
          </div>
        </div>
      </el-timeline-item>
    </el-timeline>
  </el-dialog>
</template>

<script setup lang="ts">
export interface ChangeRecord {
  time: string
  action: string
  user: string
  changes?: { field: string; old_value: any; new_value: any }[]
}

defineProps<{
  visible: boolean
  history?: ChangeRecord[]
}>()
defineEmits<{ (e: 'update:visible', v: boolean): void }>()

function formatValue(v: unknown): string {
  if (v === null || v === undefined || v === '') return '（空）'
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}
</script>

<style scoped lang="scss">
.change-fields {
  margin-top: 6px;
  padding: 8px 12px;
  background: var(--color-bg-hover);
  border-radius: var(--border-radius-sm);
}

.change-field-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-size: 12px;
  line-height: 1.8;
  word-break: break-all;
}

.cf-name {
  color: $color-text-secondary;
  min-width: 96px;
}

.cf-old {
  color: $color-danger;
  text-decoration: line-through;
}

.cf-arrow {
  color: $color-text-placeholder;
}

.cf-new {
  color: $color-success;
}
</style>
