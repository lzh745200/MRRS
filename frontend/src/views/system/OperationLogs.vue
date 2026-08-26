<template>
  <div class="operation-logs">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>操作日志</span>
          <el-button size="small" :loading="exporting" @click="handleExport">导出Excel</el-button>
        </div>
      </template>

      <!-- 过滤栏 -->
      <div class="filter-bar">
        <el-input
          v-model="filters.keyword"
          placeholder="搜索操作内容"
          clearable
          style="width: 200px"
          @clear="loadLogs"
          @keyup.enter="loadLogs"
        />
        <el-select
          v-model="filters.module"
          placeholder="模块"
          clearable
          style="width: 140px"
          @change="loadLogs"
        >
          <el-option label="帮扶村" value="supported_village" />
          <el-option label="项目" value="project" />
          <el-option label="资金" value="fund" />
          <el-option label="学校" value="school" />
          <el-option label="组织" value="organization" />
          <el-option label="用户" value="user" />
          <el-option label="审批" value="approval" />
        </el-select>
        <el-date-picker
          v-model="filters.dateRange"
          type="daterange"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          value-format="YYYY-MM-DD"
          style="width: 240px"
          @change="loadLogs"
        />
        <el-button type="primary" @click="loadLogs">查询</el-button>
      </div>

      <!-- 时间线 -->
      <el-timeline v-if="groupedLogs.length > 0" v-loading="loading">
        <el-timeline-item
          v-for="group in groupedLogs"
          :key="group.date"
          :timestamp="group.date"
          placement="top"
        >
          <div v-for="log in group.items" :key="log.id" class="log-item">
            <el-tag size="small" :type="actionType(log.action)" class="log-action">{{
              log.action
            }}</el-tag>
            <span class="log-module">{{ log.module }}</span>
            <span class="log-content">{{ log.content }}</span>
            <span class="log-user">{{ log.username || '系统' }}</span>
            <span class="log-time">{{ formatTime(log.createdAt) }}</span>
          </div>
        </el-timeline-item>
      </el-timeline>
      <EmptyState v-else-if="!loading" text="暂无操作日志" :size="80" />

      <el-pagination
        v-if="total > pageSize"
        :current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        style="margin-top: 16px; justify-content: flex-end"
        @current-change="handlePageChange"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import EmptyState from '@/components/business/EmptyState/EmptyState.vue'
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { get, apiRequest } from '@/api/request'
import { downloadBlobAsFile } from '@/api/helpers/blobDownload'
import { logger } from '@/utils/logger'

interface WorkLog {
  id: number
  module: string
  action: string
  content: string
  username: string
  createdAt: string
}

interface LogGroup {
  date: string
  items: WorkLog[]
}

const logs = ref<WorkLog[]>([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(50)
const total = ref(0)

const filters = ref({
  keyword: '',
  module: '',
  dateRange: null as [string, string] | null,
})

const groupedLogs = computed<LogGroup[]>(() => {
  const groups: Record<string, WorkLog[]> = {}
  for (const log of logs.value) {
    const date = (log.createdAt || '').slice(0, 10)
    if (!groups[date]) groups[date] = []
    groups[date].push(log)
  }
  return Object.entries(groups)
    .sort(([a], [b]) => b.localeCompare(a))
    .map(([date, items]) => ({ date, items }))
})

function actionType(action: string): 'success' | 'warning' | 'danger' | 'info' | 'primary' {
  if (action.includes('创建') || action.includes('create')) return 'success'
  if (action.includes('删除') || action.includes('delete')) return 'danger'
  if (action.includes('更新') || action.includes('update')) return 'warning'
  if (action.includes('导入') || action.includes('import')) return 'primary'
  return 'info'
}

function formatTime(t: string) {
  return t ? t.slice(11, 19) : ''
}

async function loadLogs() {
  loading.value = true
  try {
    // 操作日志数据源为审计日志 /audit/logs（字段 action/resourceType/username/createdAt）
    const params: Record<string, unknown> = { page: page.value, page_size: pageSize.value }
    if (filters.value.module) params.resource_type = filters.value.module
    if (filters.value.dateRange) {
      params.start_date = filters.value.dateRange[0]
      params.end_date = filters.value.dateRange[1]
    }
    const res: any = await get('/audit/logs', params)
    const data = res?.data ?? res
    const items = data?.items ?? (Array.isArray(data) ? data : [])
    const kw = filters.value.keyword.trim().toLowerCase()
    logs.value = (Array.isArray(items) ? items : [])
      .filter(
        (log: any) =>
          !kw ||
          String(log.action || '')
            .toLowerCase()
            .includes(kw)
      )
      .map((log: any) => ({
        id: log.id,
        module: log.resourceType || log.resource_type || '',
        action: log.action || '',
        content: log.requestPath || log.request_path || log.errorMessage || '',
        username: log.username || '',
        createdAt: log.createdAt || log.created_at || '',
      }))
    total.value = Number(data?.total ?? logs.value.length) || logs.value.length
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载日志失败')
  } finally {
    loading.value = false
  }
}

function handlePageChange(p: number) {
  page.value = p
  loadLogs()
}

const exporting = ref(false)

async function handleExport() {
  exporting.value = true
  try {
    await downloadBlobAsFile(
      () =>
        apiRequest({
          method: 'GET',
          url: '/audit/logs/export',
          params: {
            format: 'excel',
            start_date: filters.value.dateRange?.[0] || undefined,
            end_date: filters.value.dateRange?.[1] || undefined,
          },
          responseType: 'blob',
        }),
      { fallbackFileName: `操作日志_${new Date().toISOString().slice(0, 10)}.xlsx` }
    )
    ElMessage.success('导出成功')
  } catch (e) {
    logger.error('导出失败:', e)
    ElMessage.error('导出失败，请稍后重试')
  } finally {
    exporting.value = false
  }
}

onMounted(loadLogs)
</script>

<style scoped>
.operation-logs {
  padding: 20px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.filter-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}
.log-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  border-bottom: 1px solid var(--color-bg-hover);
  font-size: 13px;
}
.log-module {
  color: var(--color-info);
  min-width: 60px;
}
.log-content {
  flex: 1;
  color: var(--color-text-primary);
}
.log-user {
  color: var(--color-primary);
  min-width: 60px;
}
.log-time {
  color: var(--color-text-placeholder, #c0c4cc);
  font-size: 12px;
}
</style>
