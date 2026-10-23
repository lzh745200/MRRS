<template>
  <el-card class="self-check-card">
    <template #header>
      <div class="self-check-header">
        <span class="self-check-title">
          <el-icon><CircleCheck /></el-icon> 系统自检
        </span>
        <div class="self-check-actions">
          <el-tag v-if="summaryTag" :type="summaryTag.type" size="small">{{
            summaryTag.label
          }}</el-tag>
          <el-button link type="primary" :loading="loading" @click="runCheck">重新检查</el-button>
        </div>
      </div>
    </template>

    <div v-if="!report" class="self-check-hint">点击「重新检查」执行配置一致性体检</div>

    <template v-else>
      <div class="self-check-summary">
        共 {{ report.summary.check_count }} 项，异常 {{ report.summary.error_count }} 项， 提醒
        {{ report.summary.warn_count }} 项（生成于 {{ generatedAt }}）
      </div>
      <ul class="self-check-list">
        <li v-for="item in report.checks" :key="item.name" class="self-check-item">
          <el-tag :type="levelTagType(item.level)" size="small">{{
            levelLabel(item.level)
          }}</el-tag>
          <span class="self-check-name">{{ item.name }}</span>
          <span class="self-check-detail">{{ item.detail }}</span>
        </li>
      </ul>
    </template>
  </el-card>
</template>

<script setup lang="ts">
/**
 * 系统自检卡片（P3）。
 *
 * 把"这台机器能不能正常开工"压成一次可读结论：单位码 / 组织层级 /
 * 账号状态 / PII 密钥 / 介质导入近况。只读，不改任何配置。
 */
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { CircleCheck } from '@element-plus/icons-vue'

import { getSelfCheck, type SelfCheckReport } from '@/api/selfCheck'

const report = ref<SelfCheckReport | null>(null)
const loading = ref(false)

const LEVEL_LABELS: Record<string, string> = {
  ok: '正常',
  warn: '提醒',
  error: '异常',
}

const LEVEL_TAGS: Record<string, 'success' | 'warning' | 'danger'> = {
  ok: 'success',
  warn: 'warning',
  error: 'danger',
}

function levelLabel(level: string): string {
  return LEVEL_LABELS[level] || level
}

function levelTagType(level: string): 'success' | 'warning' | 'danger' {
  return LEVEL_TAGS[level] || 'warning'
}

const summaryTag = computed(() => {
  if (!report.value) return null
  const status = report.value.status
  const label = LEVEL_LABELS[status] || status
  const type = LEVEL_TAGS[status] || 'warning'
  return { label, type }
})

const generatedAt = computed(() => {
  const raw = report.value?.generated_at
  if (!raw) return '-'
  return raw.replace('T', ' ').slice(0, 19)
})

async function runCheck(): Promise<void> {
  loading.value = true
  try {
    report.value = await getSelfCheck()
  } catch {
    ElMessage.error('自检失败，请稍后重试')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  runCheck()
})

defineExpose({ runCheck, levelLabel, levelTagType, report })
</script>

<style scoped>
.self-check-card {
  margin-bottom: 16px;
}

.self-check-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.self-check-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
}

.self-check-actions {
  display: inline-flex;
  align-items: center;
  gap: 12px;
}

.self-check-hint {
  color: var(--color-text-secondary);
  font-size: 13px;
}

.self-check-summary {
  margin-bottom: 12px;
  color: var(--color-text-secondary);
  font-size: 13px;
}

.self-check-list {
  margin: 0;
  padding: 0;
  list-style: none;
}

.self-check-item {
  display: flex;
  align-items: baseline;
  gap: 10px;
  padding: 6px 0;
  border-bottom: 1px solid var(--color-card-border);
}

.self-check-item:last-child {
  border-bottom: none;
}

.self-check-name {
  min-width: 96px;
  font-weight: 500;
}

.self-check-detail {
  color: var(--color-text-secondary);
  font-size: 13px;
}
</style>
