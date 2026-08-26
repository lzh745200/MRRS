<template>
  <div class="audit-management-page">
    <div class="page-header">
      <h2 class="page-title">审计管理</h2>
      <p class="page-desc">系统操作审计追踪，确保数据安全与合规</p>
    </div>

    <!-- 审计统计 -->
    <div class="stats-row">
      <div class="stat-card">
        <div class="stat-value">{{ stats.todayOps }}</div>
        <div class="stat-label">今日操作数</div>
      </div>
      <el-tooltip
        content="审计日志总条数（军规要求长期保留，不做自动清理）。可使用右上角导出功能归档。"
        placement="top"
      >
        <div class="stat-card" style="cursor: help">
          <div class="stat-value">{{ stats.totalOps.toLocaleString() }}</div>
          <div class="stat-label">审计总条数</div>
        </div>
      </el-tooltip>
      <div class="stat-card">
        <div class="stat-value">{{ stats.activeUsers }}</div>
        <div class="stat-label">活跃用户</div>
      </div>
      <div class="stat-card warning">
        <div class="stat-value">{{ stats.warnings }}</div>
        <div class="stat-label">安全警告</div>
      </div>
      <div class="stat-card danger">
        <div class="stat-value">{{ stats.failures }}</div>
        <div class="stat-label">失败操作</div>
      </div>
    </div>

    <el-tabs v-model="activeTab" type="border-card">
      <!-- 操作审计 -->
      <el-tab-pane label="操作审计" name="operations">
        <el-card shadow="never">
          <div class="filter-row">
            <div class="filter-item filter-item-wide">
              <span class="filter-label">操作类型</span>
              <el-select
                v-model="filters.action"
                placeholder="全部"
                clearable
                size="default"
                class="action-select"
              >
                <el-option label="登录" value="login" />
                <el-option label="数据修改" value="data_modify" />
                <el-option label="数据导入" value="data_import" />
                <el-option label="数据导出" value="data_export" />
                <el-option label="备份恢复" value="backup" />
                <el-option label="权限变更" value="permission" />
                <el-option label="创建项目" value="create_project" />
                <el-option label="更新项目" value="update_project" />
                <el-option label="删除项目" value="delete_project" />
                <el-option label="创建组织" value="create_organization" />
                <el-option label="更新组织" value="update_organization" />
                <el-option label="删除组织" value="delete_organization" />
                <el-option label="创建用户" value="create_user" />
                <el-option label="更新用户" value="update_user" />
                <el-option label="删除用户" value="delete_user" />
                <el-option label="系统配置" value="system_config" />
                <el-option label="文件上传" value="file_upload" />
                <el-option label="文件下载" value="file_download" />
              </el-select>
            </div>
            <div class="filter-item">
              <label class="filter-label">用户</label>
              <el-input
                v-model="filters.user"
                placeholder="用户名"
                clearable
                class="filter-input"
              />
            </div>
            <div class="filter-item filter-item-date">
              <label class="filter-label">时间</label>
              <el-date-picker
                v-model="filters.dateRange"
                type="daterange"
                start-placeholder="开始"
                end-placeholder="结束"
                value-format="YYYY-MM-DD"
                class="filter-date-picker"
              />
            </div>
            <div class="filter-item filter-item-btn">
              <el-button type="primary" @click="handleSearch">查询</el-button>
              <el-button @click="handleReset">重置</el-button>
              <el-button :loading="exporting" @click="handleExportExcel">导出Excel</el-button>
            </div>
          </div>

          <el-table v-loading="loading" :data="auditLogs" stripe style="margin-top: 16px">
            <el-table-column type="index" label="#" width="50" />
            <el-table-column prop="timestamp" label="时间" width="170" />
            <el-table-column prop="user" label="用户" width="100" />
            <el-table-column label="操作" width="100">
              <template #default="{ row }">
                <el-tag :type="actionTagType(row.action)" size="small">{{
                  actionName(row.action)
                }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="target" label="操作对象" width="150" />
            <el-table-column prop="detail" label="详情" min-width="200" show-overflow-tooltip />
            <el-table-column label="结果" width="80">
              <template #default="{ row }">
                <el-tag :type="row.success ? 'success' : 'danger'" size="small">{{
                  row.success ? '成功' : '失败'
                }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="ip" label="IP地址" width="130" />
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- 登录日志 -->
      <el-tab-pane label="登录日志" name="login">
        <el-card shadow="never">
          <el-table :data="loginLogs" stripe>
            <el-table-column type="index" label="#" width="50" />
            <el-table-column prop="timestamp" label="时间" width="170" />
            <el-table-column prop="user" label="用户" width="120" />
            <el-table-column label="类型" width="90">
              <template #default="{ row }">
                <el-tag :type="row.type === 'login' ? 'success' : 'info'" size="small">{{
                  row.type === 'login' ? '登录' : '登出'
                }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="ip" label="IP地址" width="130" />
            <el-table-column prop="browser" label="浏览器" min-width="150" />
            <el-table-column label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="row.success ? 'success' : 'danger'" size="small">{{
                  row.success ? '成功' : '失败'
                }}</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <!-- 安全告警 -->
      <el-tab-pane label="安全告警" name="alerts">
        <el-card shadow="never">
          <el-table :data="alerts" stripe>
            <el-table-column type="index" label="#" width="50" />
            <el-table-column prop="timestamp" label="时间" width="170" />
            <el-table-column label="级别" width="90">
              <template #default="{ row }">
                <el-tag
                  :type="
                    row.level === 'high' ? 'danger' : row.level === 'medium' ? 'warning' : 'info'
                  "
                  size="small"
                >
                  {{ getLevelText(row.level) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="type" label="类型" width="140" />
            <el-table-column prop="detail" label="详情" min-width="250" show-overflow-tooltip />
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="row.handled ? 'success' : 'warning'" size="small">{{
                  row.handled ? '已处理' : '待处理'
                }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="80">
              <template #default="{ row }">
                <el-button
                  v-if="!row.handled"
                  type="primary"
                  size="small"
                  link
                  @click="handleAlert(row)"
                  >处理</el-button
                >
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { auditApi } from '@/api/audit'
import { apiRequest } from '@/api/request'
import { downloadBlobAsFile } from '@/api/helpers/blobDownload'
import { logger } from '@/utils/logger'

const activeTab = ref('operations')
const loading = ref(false)
const filters = reactive({
  action: '',
  user: '',
  dateRange: null as string[] | null,
})

const stats = reactive({
  todayOps: 0,
  totalOps: 0,
  activeUsers: 0,
  warnings: 0,
  failures: 0,
})

const actionTagType = (a: string): 'info' | 'primary' | 'success' | 'warning' | 'danger' => {
  const map: Record<string, 'info' | 'primary' | 'success' | 'warning' | 'danger'> = {
    login: 'success',
    data_modify: 'primary',
    data_import: 'info',
    data_export: 'success',
    backup: 'warning',
    permission: 'danger',
    create_project: 'primary',
    update_project: 'primary',
    delete_project: 'danger',
    create_organization: 'primary',
    update_organization: 'primary',
    delete_organization: 'danger',
    create_user: 'primary',
    update_user: 'primary',
    delete_user: 'danger',
    system_config: 'warning',
    file_upload: 'info',
    file_download: 'info',
  }
  return map[a] || 'info'
}
const actionNameMap: Record<string, string> = {
  login: '登录',
  data_modify: '数据修改',
  data_import: '导入',
  data_export: '导出',
  backup: '备份',
  permission: '权限',
  create_project: '创建项目',
  update_project: '更新项目',
  delete_project: '删除项目',
  create_organization: '创建组织',
  update_organization: '更新组织',
  delete_organization: '删除组织',
  create_user: '创建用户',
  update_user: '更新用户',
  delete_user: '删除用户',
  system_config: '系统配置',
  file_upload: '文件上传',
  file_download: '文件下载',
}

// 级别文本映射
const getLevelText = (level: string): string => {
  const levelMap: Record<string, string> = {
    high: '高',
    medium: '中',
    low: '低',
  }
  return levelMap[level] || level
}
const actionName = (a: string) => actionNameMap[a] || a

const auditLogs = ref<any[]>([])
const loginLogs = ref<any[]>([])
const alerts = ref<any[]>([])

/** 加载审计统计 */
async function loadStats() {
  try {
    const data = await auditApi.getStats()
    stats.totalOps = data.total_operations ?? 0 // T049 容量治理：审计总条数可见
    stats.todayOps = data.today_operations ?? data.total_operations ?? 0
    stats.activeUsers = data.active_users ?? 0
    stats.failures = data.failed_operations ?? 0
    stats.warnings = data.warnings ?? 0
  } catch {
    // 统计加载失败不阻断页面
  }
}

/** 加载审计日志 */
async function loadAuditLogs() {
  loading.value = true
  try {
    const params: Record<string, any> = { page: 1, page_size: 50 }
    if (filters.action) params.action = filters.action
    if (filters.user) params.user_id = undefined // 用户名暂不支持
    if (filters.dateRange?.length === 2) {
      params.start_date = filters.dateRange[0]
      params.end_date = filters.dateRange[1]
    }
    const data = await auditApi.getLogs(params)
    auditLogs.value = (data.items || []).map((item: any) => ({
      timestamp: item.created_at || '',
      user: item.username || `用户${item.user_id || ''}`,
      action: item.action || '',
      target: item.resource_type ? `${item.resource_type} #${item.resource_id || ''}` : '',
      detail: item.detail || '',
      success: item.status !== 'failed',
      ip: item.ip_address || '',
    }))
  } catch {
    auditLogs.value = []
  } finally {
    loading.value = false
  }
}

/** 加载登录日志 */
async function loadLoginLogs() {
  try {
    const data = await auditApi.getLoginAttempts({ page: 1, page_size: 50 })
    loginLogs.value = (data.items || []).map((item: any) => ({
      timestamp: item.attempt_time || '',
      user: item.username || '',
      type: item.success ? 'login' : 'login',
      ip: item.ip_address || '',
      browser: item.user_agent || '',
      success: item.success ?? true,
    }))
  } catch {
    loginLogs.value = []
  }
}

/** 加载安全告警 */
async function loadAlerts() {
  try {
    const data = await auditApi.getSecurityEvents({ page: 1, page_size: 50 })
    alerts.value = (data.items || []).map((item: any) => ({
      id: item.id,
      timestamp: item.created_at || '',
      level: item.severity || 'low',
      type: item.event_type || '',
      detail: item.description || '',
      handled: item.resolved ?? false,
    }))
  } catch {
    alerts.value = []
  }
}

const exporting = ref(false)

async function handleExportExcel() {
  exporting.value = true
  try {
    const res = await apiRequest({
      method: 'GET',
      url: '/audit/logs/export',
      params: {
        format: 'excel',
        start_date: filters.dateRange?.[0] || undefined,
        end_date: filters.dateRange?.[1] || undefined,
        action: filters.action || undefined,
      },
      responseType: 'blob',
    })
    await downloadBlobAsFile(res as any, {
      fallbackFileName: `审计日志_${new Date().toISOString().slice(0, 10)}.xlsx`,
    })
    ElMessage.success('导出成功')
  } catch (e) {
    logger.error('审计日志导出失败:', e)
    ElMessage.error('导出失败，请稍后重试')
  } finally {
    exporting.value = false
  }
}

function handleSearch() {
  loadAuditLogs()
}

function handleReset() {
  Object.assign(filters, { action: '', user: '', dateRange: null })
  loadAuditLogs()
}

async function handleAlert(row: any) {
  try {
    await ElMessageBox.prompt('请输入处理说明', '处理告警', {
      confirmButtonText: '确认处理',
      cancelButtonText: '取消',
      inputPlaceholder: '处理备注',
    }).then(async ({ value }: any) => {
      await auditApi.resolveSecurityEvent(row.id, value || '已处理')
      row.handled = true
      ElMessage.success('告警已标记为已处理')
    })
  } catch {
    // 用户取消
  }
}

/** Tab 切换时懒加载数据 */
watch(activeTab, (tab) => {
  if (tab === 'login' && loginLogs.value.length === 0) loadLoginLogs()
  if (tab === 'alerts' && alerts.value.length === 0) loadAlerts()
})

onMounted(() => {
  loadStats()
  loadAuditLogs()
})
</script>

<style>
/* 全局样式 - 确保 filter-item-wide 保持 300px 宽度 */
.audit-management-page .filter-item-wide {
  width: 300px;
  min-width: 300px;
  flex-shrink: 0;
}

.audit-management-page .action-select {
  width: 100%;
}
</style>

<style scoped>
.audit-management-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.page-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--color-primary-dark-1);
  margin: 0 0 4px;
}
.page-desc {
  font-size: 14px;
  color: var(--color-text-secondary);
  margin: 0;
}
.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}
.stat-card {
  background: white;
  padding: 20px;
  border-radius: 8px;
  text-align: center;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}
.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--color-primary-dark-1);
}
.stat-card.warning .stat-value {
  color: var(--color-warning);
}
.stat-card.danger .stat-value {
  color: var(--color-danger);
}
.stat-label {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin-top: 4px;
}

/* 筛选表单布局 */
.filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  align-items: flex-start;
}

.filter-item {
  display: flex;
  flex-direction: column;
  min-width: 160px;
}

.filter-item-wide {
  width: 300px;
  flex-shrink: 0;
}

.filter-item-date {
  min-width: 280px;
}

.filter-item-btn {
  flex-direction: row;
  align-items: center;
  gap: 8px;
  min-width: auto;
}

.filter-label {
  font-size: 14px;
  color: var(--color-text-regular);
  margin-bottom: 8px;
  font-weight: 500;
  display: block;
}

.filter-input,
.filter-date-picker {
  width: 100%;
}
</style>
