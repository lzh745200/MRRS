<template>
  <div class="batch-page">
    <div class="page-header">
      <div class="header-info">
        <h2 class="page-title">批量操作</h2>
        <p class="page-desc">对帮扶数据进行批量更新、删除、导出和验证</p>
      </div>
    </div>

    <!-- 操作配置 -->
    <div class="config-card">
      <el-form :model="batchForm" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="操作类型">
              <el-select v-model="batchForm.operation" style="width: 100%">
                <el-option label="批量更新" value="update" />
                <el-option label="批量删除" value="delete" />
                <el-option label="批量导出" value="export" />
                <el-option label="批量验证" value="validate" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="目标实体">
              <el-select v-model="batchForm.entity" style="width: 100%">
                <el-option label="帮扶村庄" value="supported_villages" />
                <el-option label="帮扶学校" value="schools" />
                <el-option label="帮扶项目" value="projects" />
                <el-option label="帮扶经费" value="funds" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col v-if="batchForm.operation === 'export'" :span="8">
            <el-form-item label="导出格式">
              <el-select v-model="batchForm.format" style="width: 100%">
                <el-option label="Excel (.xlsx)" value="xlsx" />
                <el-option label="CSV" value="csv" />
                <el-option label="JSON" value="json" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col v-if="batchForm.operation === 'delete'" :span="8">
            <el-form-item label="删除方式">
              <el-select v-model="batchForm.softDelete" style="width: 100%">
                <el-option label="软删除（可恢复）" :value="true" />
                <el-option label="硬删除（不可恢复）" :value="false" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
    </div>

    <!-- ID输入 -->
    <div class="input-card">
      <div class="input-header">
        <h3>选择目标条目</h3>
        <span class="input-hint">输入ID（每行一个，或用逗号分隔）</span>
      </div>
      <el-input
        v-model="idInput"
        type="textarea"
        :rows="6"
        placeholder="输入要操作的条目ID，每行一个&#10;例如：&#10;1&#10;2&#10;3&#10;或：1, 2, 3, 4, 5"
      />
      <div class="id-summary">
        <span v-if="parsedIds.length > 0" class="id-count">
          已识别 <strong>{{ parsedIds.length }}</strong> 个ID：
          <el-tag v-for="id in parsedIds.slice(0, 10)" :key="id" size="small" style="margin: 2px">
            {{ id }}
          </el-tag>
          <span v-if="parsedIds.length > 10">... 等{{ parsedIds.length }}项</span>
        </span>
        <span v-else class="id-empty">尚未输入有效ID</span>
      </div>
    </div>

    <!-- 批量更新字段 -->
    <div v-if="batchForm.operation === 'update'" class="input-card">
      <div class="input-header">
        <h3>更新字段（JSON格式）</h3>
        <span class="input-hint">输入要更新的字段和值</span>
      </div>
      <el-input
        v-model="updatesInput"
        type="textarea"
        :rows="4"
        placeholder='例如：{"status": "active", "support_unit": "某某单位"}'
      />
    </div>

    <!-- 操作按钮 -->
    <div class="action-bar">
      <el-button
        v-if="batchForm.operation === 'validate'"
        type="info"
        :loading="inProgress"
        @click="handleValidate"
      >
        <el-icon><Check /></el-icon>验证
      </el-button>
      <el-button
        v-else-if="batchForm.operation === 'update'"
        type="primary"
        :loading="inProgress"
        @click="handleBatchUpdate"
      >
        <el-icon><Edit /></el-icon>批量更新
      </el-button>
      <el-button
        v-else-if="batchForm.operation === 'delete'"
        type="danger"
        :loading="inProgress"
        @click="handleBatchDelete"
      >
        <el-icon><Delete /></el-icon>批量删除
      </el-button>
      <el-button
        v-else-if="batchForm.operation === 'export'"
        type="success"
        :loading="inProgress"
        @click="handleBatchExport"
      >
        <el-icon><Download /></el-icon>批量导出
      </el-button>
      <el-button @click="handleReset">重置</el-button>
    </div>

    <!-- 进度条 -->
    <div v-if="inProgress" class="progress-card">
      <el-progress :percentage="progressPercent" :status="progressStatus" :stroke-width="16" />
      <p class="progress-text">{{ progressText }}</p>
    </div>

    <!-- 结果摘要 -->
    <div v-if="resultSummary" class="result-card">
      <div class="card-header">
        <h3>操作结果</h3>
        <el-tag :type="resultSummary.success ? 'success' : 'danger'">
          {{ resultSummary.success ? '成功' : '失败' }}
        </el-tag>
      </div>
      <div class="card-body">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="操作类型">
            {{ operationLabel(batchForm.operation) }}
          </el-descriptions-item>
          <el-descriptions-item label="目标实体">
            {{ entityLabel(batchForm.entity) }}
          </el-descriptions-item>
          <el-descriptions-item label="处理数量">
            {{ resultSummary.processed ?? resultSummary.total ?? '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="成功数量">
            {{ resultSummary.success_count ?? resultSummary.success ?? '-' }}
          </el-descriptions-item>
          <el-descriptions-item v-if="resultSummary.message" label="消息" :span="2">
            {{ resultSummary.message }}
          </el-descriptions-item>
          <el-descriptions-item v-if="resultSummary.errors?.length" label="错误详情" :span="2">
            <div v-for="(err, i) in resultSummary.errors" :key="i" class="error-item">
              {{ err }}
            </div>
          </el-descriptions-item>
        </el-descriptions>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Check, Edit, Delete, Download } from '@element-plus/icons-vue'
import { batchUpdate, batchDelete, batchExport, validateBatch } from '@/api/batchOperations'

const batchForm = reactive({
  operation: 'update' as string,
  entity: 'supported_villages' as string,
  format: 'xlsx' as string,
  softDelete: true,
})

const idInput = ref('')
const updatesInput = ref('{"status": "active"}')
const inProgress = ref(false)
const progressPercent = ref(0)
const progressStatus = ref<'' | 'success' | 'exception'>('')
const progressText = ref('')
const resultSummary = ref<any>(null)

const parsedIds = computed(() => {
  const text = idInput.value.trim()
  if (!text) return []
  const ids: number[] = []
  // 支持逗号、换行、空格分隔
  const parts = text.split(/[,\n\s]+/)
  for (const part of parts) {
    const num = Number(part.trim())
    if (!isNaN(num) && num > 0) {
      ids.push(num)
    }
  }
  return [...new Set(ids)] // 去重
})

function operationLabel(op: string) {
  const map: Record<string, string> = {
    update: '批量更新',
    delete: '批量删除',
    export: '批量导出',
    validate: '批量验证',
  }
  return map[op] || op
}

function entityLabel(entity: string) {
  const map: Record<string, string> = {
    supported_villages: '帮扶村庄',
    schools: '帮扶学校',
    projects: '帮扶项目',
    funds: '帮扶经费',
  }
  return map[entity] || entity
}

function parseUpdates(): Record<string, any> {
  try {
    return JSON.parse(updatesInput.value)
  } catch {
    ElMessage.error('更新字段JSON格式不正确')
    return {}
  }
}

async function handleValidate() {
  if (parsedIds.value.length === 0) {
    ElMessage.warning('请输入至少一个有效ID')
    return
  }
  inProgress.value = true
  progressPercent.value = 30
  progressText.value = '正在验证...'
  try {
    const response = await validateBatch(batchForm.entity, parsedIds.value)
    const data = response?.data ?? response
    resultSummary.value = {
      success: true,
      processed: parsedIds.value.length,
      message: data?.message ?? '验证完成',
      errors: data?.errors ?? [],
    }
    progressPercent.value = 100
    progressStatus.value = 'success'
    progressText.value = '验证完成'
    ElMessage.success('验证完成')
  } catch {
    progressStatus.value = 'exception'
    progressText.value = '验证失败'
    resultSummary.value = {
      success: false,
      message: '验证失败',
    }
    ElMessage.error('验证失败')
  } finally {
    inProgress.value = false
  }
}

async function handleBatchUpdate() {
  if (parsedIds.value.length === 0) {
    ElMessage.warning('请输入至少一个有效ID')
    return
  }
  const updates = parseUpdates()
  if (!updates || Object.keys(updates).length === 0) return

  try {
    await ElMessageBox.confirm(
      `确定要对${parsedIds.value.length}条${entityLabel(batchForm.entity)}执行批量更新吗？`,
      '确认操作',
      { type: 'warning' }
    )
  } catch {
    return
  }

  inProgress.value = true
  progressPercent.value = 20
  progressText.value = '正在批量更新...'
  try {
    const response = await batchUpdate({
      table_name: batchForm.entity,
      ids: parsedIds.value,
      updates,
    })
    const data = response?.data ?? response
    resultSummary.value = {
      success: true,
      processed: parsedIds.value.length,
      success_count: data?.success_count ?? data?.affected ?? parsedIds.value.length,
      message: data?.message ?? '批量更新完成',
      errors: data?.errors ?? [],
    }
    progressPercent.value = 100
    progressStatus.value = 'success'
    progressText.value = '批量更新完成'
    ElMessage.success('批量更新完成')
  } catch {
    progressStatus.value = 'exception'
    progressText.value = '批量更新失败'
    resultSummary.value = { success: false, message: '批量更新失败' }
    ElMessage.error('批量更新失败')
  } finally {
    inProgress.value = false
  }
}

async function handleBatchDelete() {
  if (parsedIds.value.length === 0) {
    ElMessage.warning('请输入至少一个有效ID')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确定要删除${parsedIds.value.length}条${entityLabel(batchForm.entity)}吗？此操作可能不可恢复！`,
      '危险操作',
      { type: 'error', confirmButtonText: '确认删除' }
    )
  } catch {
    return
  }

  inProgress.value = true
  progressPercent.value = 20
  progressText.value = '正在批量删除...'
  try {
    const response = await batchDelete({
      table_name: batchForm.entity,
      ids: parsedIds.value,
      soft_delete: batchForm.softDelete,
    })
    const data = response?.data ?? response
    resultSummary.value = {
      success: true,
      processed: parsedIds.value.length,
      success_count: data?.success_count ?? data?.deleted ?? parsedIds.value.length,
      message: data?.message ?? '批量删除完成',
      errors: data?.errors ?? [],
    }
    progressPercent.value = 100
    progressStatus.value = 'success'
    progressText.value = '批量删除完成'
    ElMessage.success('批量删除完成')
  } catch {
    progressStatus.value = 'exception'
    progressText.value = '批量删除失败'
    resultSummary.value = { success: false, message: '批量删除失败' }
    ElMessage.error('批量删除失败')
  } finally {
    inProgress.value = false
  }
}

async function handleBatchExport() {
  if (parsedIds.value.length === 0) {
    ElMessage.warning('请输入至少一个有效ID')
    return
  }

  inProgress.value = true
  progressPercent.value = 30
  progressText.value = '正在导出...'
  try {
    const response = await batchExport({
      table_name: batchForm.entity,
      ids: parsedIds.value,
      format: batchForm.format,
    })
    const data = response?.data ?? response
    resultSummary.value = {
      success: true,
      processed: parsedIds.value.length,
      message: data?.message ?? '导出完成',
    }
    progressPercent.value = 100
    progressStatus.value = 'success'
    progressText.value = '导出完成'
    ElMessage.success('导出任务已提交，请留意下载通知')
  } catch {
    progressStatus.value = 'exception'
    progressText.value = '导出失败'
    resultSummary.value = { success: false, message: '导出失败' }
    ElMessage.error('导出失败')
  } finally {
    inProgress.value = false
  }
}

function handleReset() {
  idInput.value = ''
  updatesInput.value = '{"status": "active"}'
  resultSummary.value = null
  progressPercent.value = 0
  progressStatus.value = ''
  progressText.value = ''
}
</script>

<style scoped>
.batch-page {
  padding: 20px;
}

.page-header {
  margin-bottom: 20px;
}

.page-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: var(--color-primary-dark-1);
}

.page-desc {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--color-text-secondary);
}

.config-card {
  background: white;
  border-radius: 8px;
  padding: 20px 20px 4px;
  margin-bottom: 16px;
  border: 1px solid var(--color-border-light);
}

.input-card {
  background: white;
  border-radius: 8px;
  padding: 16px 20px;
  margin-bottom: 16px;
  border: 1px solid var(--color-border-light);
}

.input-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.input-header h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.input-hint {
  font-size: 12px;
  color: var(--color-info);
}

.id-summary {
  margin-top: 8px;
  min-height: 24px;
}

.id-count {
  font-size: 13px;
  color: var(--color-text-regular);
}

.id-empty {
  font-size: 13px;
  color: var(--color-text-placeholder, #c0c4cc);
}

.action-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}

.progress-card {
  background: white;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 20px;
  border: 1px solid var(--color-border-light);
}

.progress-text {
  text-align: center;
  margin-top: 12px;
  color: var(--color-text-regular);
  font-size: 13px;
}

.result-card {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  overflow: hidden;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  background: linear-gradient(135deg, var(--color-primary-dark-1) 0%, var(--color-primary) 100%);
}

.card-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: white;
}

.card-body {
  padding: 24px;
}

.error-item {
  color: var(--color-danger);
  font-size: 13px;
  padding: 2px 0;
}
</style>
