<template>
  <div class="message-center">
    <!-- 页面标题 -->
    <el-card class="header-card">
      <template #header>
        <div class="card-header">
          <span class="title">
            消息中心
            <el-badge v-if="unreadCount > 0" :value="unreadCount" class="unread-badge" />
          </span>
          <div class="actions">
            <el-button :disabled="unreadCount === 0" @click="handleMarkAllRead">
              <el-icon><Check /></el-icon>
              全部已读
            </el-button>
            <el-button type="warning" plain @click="handleClearRead">
              <el-icon><Delete /></el-icon>
              清空已读
            </el-button>
            <el-button
              type="danger"
              :disabled="selectedMessages.length === 0"
              @click="handleBatchDelete"
            >
              <el-icon><Delete /></el-icon>
              删除选中 ({{ selectedMessages.length }})
            </el-button>
            <el-button :loading="loading" @click="loadMessages">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
          </div>
        </div>
      </template>

      <!-- 筛选条件 -->
      <el-form :model="filterForm" inline>
        <el-form-item label="消息类型">
          <el-select
            v-model="filterForm.message_type"
            placeholder="全部"
            clearable
            @change="handleSearch"
          >
            <el-option label="系统通知" value="system" />
            <el-option label="审批通知" value="approval" />
            <el-option label="任务提醒" value="task" />
            <el-option label="备份提醒" value="backup" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select
            v-model="filterForm.is_read"
            placeholder="全部"
            clearable
            @change="handleSearch"
          >
            <el-option label="未读" :value="0" />
            <el-option label="已读" :value="1" />
          </el-select>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 消息列表 -->
    <el-card class="list-card">
      <el-tabs v-model="activeTab">
        <!-- 页签1：消息 -->
        <el-tab-pane label="消息" name="messages">
          <el-table
            ref="tableRef"
            v-loading="loading"
            :data="messages"
            :row-class-name="getRowClassName"
            stripe
            @selection-change="handleSelectionChange"
            @row-click="handleRowClick"
          >
            <el-table-column type="selection" width="55" />
            <el-table-column label="类型" width="120">
              <template #default="{ row }">
                <el-tag :type="formatMessageType(row.message_type).type as any" size="small">
                  {{ formatMessageType(row.message_type).text }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="title" label="标题" min-width="200">
              <template #default="{ row }">
                <div class="message-title">
                  <el-badge v-if="!row.is_read" is-dot class="unread-dot" />
                  <span :class="{ unread: !row.is_read }">{{ row.title }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="content" label="内容" min-width="300" show-overflow-tooltip>
              <template #default="{ row }">
                <span class="message-content">{{ row.content }}</span>
              </template>
            </el-table-column>
            <el-table-column label="时间" width="150">
              <template #default="{ row }">
                {{ formatRelativeTime(row.created_at) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150" fixed="right">
              <template #default="{ row }">
                <el-button-group>
                  <el-button
                    size="small"
                    :disabled="row.is_read"
                    @click.stop="handleMarkRead(row as Message)"
                  >
                    <el-icon><Check /></el-icon>
                  </el-button>
                  <el-button size="small" type="danger" @click.stop="handleDelete(row as Message)">
                    <el-icon><Delete /></el-icon>
                  </el-button>
                  <el-button
                    v-if="row.link"
                    size="small"
                    type="primary"
                    @click.stop="handleGoToLink(row as Message)"
                  >
                    <el-icon><Link /></el-icon>
                  </el-button>
                </el-button-group>
              </template>
            </el-table-column>
          </el-table>

          <!-- 分页 -->
          <el-pagination
            v-if="total > 0"
            v-model:current-page="page"
            v-model:page-size="pageSize"
            class="pagination"
            :total="total"
            :page-sizes="[10, 20, 50]"
            layout="total, sizes, prev, pager, next"
            @size-change="loadMessages"
            @current-change="loadMessages"
          />
        </el-tab-pane>

        <!-- 页签2：系统动态 -->
        <el-tab-pane label="系统动态" name="activities">
          <div v-loading="activitiesLoading" class="activity-pane">
            <el-timeline v-if="recentActivities.length">
              <el-timeline-item
                v-for="act in recentActivities"
                :key="act.id"
                :timestamp="formatDateTime(act.time || act.created_at)"
                placement="top"
                :type="activityType(act.type)"
              >
                <div class="activity-item">
                  <span class="activity-title">{{ act.title }}</span>
                  <div v-if="act.description" class="activity-desc">{{ act.description }}</div>
                </div>
              </el-timeline-item>
            </el-timeline>
            <el-empty v-else description="暂无系统动态" />
            <div class="activity-actions">
              <el-button size="small" :loading="activitiesLoading" @click="loadActivities"
                >刷新动态</el-button
              >
            </div>
          </div>
        </el-tab-pane>

        <!-- 页签3：我的操作 -->
        <el-tab-pane label="我的操作" name="myLogs">
          <div v-loading="logsLoading" class="activity-pane">
            <el-timeline v-if="myLogs.length">
              <el-timeline-item
                v-for="log in myLogs"
                :key="log.id"
                :timestamp="formatDateTime(log.created_at)"
                placement="top"
              >
                <div class="activity-item">
                  <span class="activity-title">{{
                    log.action || log.content || log.description || '--'
                  }}</span>
                  <div v-if="log.entity_name" class="activity-desc">{{ log.entity_name }}</div>
                </div>
              </el-timeline-item>
            </el-timeline>
            <el-empty v-else description="暂无操作记录" />
            <div class="activity-actions">
              <el-button size="small" :loading="logsLoading" @click="loadMyLogs"
                >刷新记录</el-button
              >
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 消息详情对话框 -->
    <el-dialog v-model="detailDialogVisible" :title="currentMessage?.title" width="600px">
      <div v-if="currentMessage" class="message-detail">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="类型">
            <el-tag :type="formatMessageType(currentMessage.message_type).type as any" size="small">
              {{ formatMessageType(currentMessage.message_type).text }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="时间">
            {{ formatDateTime(currentMessage.created_at) }}
          </el-descriptions-item>
          <el-descriptions-item label="内容">
            <div class="detail-content">{{ currentMessage.content }}</div>
          </el-descriptions-item>
        </el-descriptions>

        <div v-if="currentMessage.link" class="detail-link">
          <el-button type="primary" @click="handleGoToLink(currentMessage)">
            <el-icon><Link /></el-icon>
            查看详情
          </el-button>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouterSafe } from '@/composables/useRouterSafe'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Check, Delete, Link } from '@element-plus/icons-vue'
import {
  getMessages,
  markAsRead,
  markAllAsRead,
  clearReadMessages,
  deleteMessages,
  getRecentActivities,
  formatMessageType,
  formatRelativeTime,
  type Message,
  type MessageType,
} from '@/api/message'
import { get } from '@/api/request'
import { logger } from '@/utils/logger'

const { pushSafe } = useRouterSafe()

// ==================== 状态 ====================

const activeTab = ref('messages')
const activitiesLoading = ref(false)
const recentActivities = ref<any[]>([])
const logsLoading = ref(false)
const myLogs = ref<any[]>([])

const loading = ref(false)
const messages = ref<Message[]>([])
const selectedMessages = ref<Message[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const unreadCount = ref(0)

const filterForm = ref({
  message_type: undefined as MessageType | undefined,
  is_read: undefined as number | undefined,
})

// 详情对话框
const detailDialogVisible = ref(false)
const currentMessage = ref<Message | null>(null)

// WebSocket（单机版禁用，消息通过 HTTP 轮询）
// ==================== 方法 ====================

/** 系统动态（后端从审计日志实时映射） */
async function loadActivities() {
  activitiesLoading.value = true
  try {
    const res: any = await getRecentActivities()
    recentActivities.value = Array.isArray(res) ? res : res?.items || res?.data || []
  } catch {
    recentActivities.value = []
  } finally {
    activitiesLoading.value = false
  }
}

/** 我的操作（工作日志：非管理员自动只看到自己的） */
async function loadMyLogs() {
  logsLoading.value = true
  try {
    const res: any = await get('/work-logs', { page: 1, page_size: 20 })
    const payload = res?.data ?? res
    const list = Array.isArray(payload) ? payload : payload?.items || []
    myLogs.value = list
  } catch {
    myLogs.value = []
  } finally {
    logsLoading.value = false
  }
}

function activityType(t?: string): 'primary' | 'success' | 'warning' | 'danger' | 'info' {
  const map: Record<string, 'primary' | 'success' | 'warning' | 'danger' | 'info'> = {
    create: 'success',
    update: 'primary',
    delete: 'danger',
    import: 'warning',
    export: 'info',
    login: 'info',
    backup: 'warning',
  }
  return map[t || ''] || 'info'
}

/**
 * 加载消息列表
 */
async function loadMessages() {
  loading.value = true
  try {
    const response = await getMessages({
      page: page.value,
      page_size: pageSize.value,
      message_type: filterForm.value.message_type,
      is_read:
        filterForm.value.is_read === 1 ? true : filterForm.value.is_read === 0 ? false : undefined,
    })
    messages.value = response?.items ?? []
    total.value = response?.total ?? 0
    // 列表响应不含 unread_count（在 /messages/unread-count 端点），单独获取
    unreadCount.value = response?.unread_count ?? (await loadUnreadCountValue())
  } catch (error) {
    ElMessage.error('加载消息列表失败')
  } finally {
    loading.value = false
  }
}

async function loadUnreadCountValue(): Promise<number> {
  try {
    const { getUnreadCount } = await import('@/api/message')
    const res: any = await getUnreadCount()
    const d = res?.data ?? res
    return Number(d?.total ?? d?.count ?? 0) || 0
  } catch {
    return 0
  }
}

/**
 * 搜索
 */
function handleSearch() {
  page.value = 1
  loadMessages()
}

/**
 * 选择变化
 */
function handleSelectionChange(selection: Message[]) {
  selectedMessages.value = selection
}

/**
 * 行点击
 */
function handleRowClick(row: Message) {
  currentMessage.value = row
  detailDialogVisible.value = true

  // 标记为已读
  if (!row.is_read) {
    handleMarkRead(row)
  }
}

/**
 * 获取行样式
 */
function getRowClassName({ row }: { row: Message }) {
  return row.is_read ? '' : 'unread-row'
}

/**
 * 标记单条已读
 */
async function handleMarkRead(message: Message) {
  try {
    await markAsRead([message.id])
    message.is_read = true
    unreadCount.value = Math.max(0, unreadCount.value - 1)
  } catch {
    // 静默失败
  }
}

/**
 * 全部标记已读
 */
async function handleMarkAllRead() {
  try {
    await markAllAsRead()
    messages.value.forEach((m) => (m.is_read = true))
    unreadCount.value = 0
    ElMessage.success('已标记')
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

async function handleClearRead() {
  try {
    await ElMessageBox.confirm('将删除全部已读消息，不可恢复。确认继续？', '清空已读', {
      type: 'warning',
      confirmButtonText: '确认清空',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    const count = await clearReadMessages()
    ElMessage.success(`已删除 ${count} 条已读消息`)
    await loadMessages()
  } catch (e) {
    logger.error('清空已读失败:', e)
    ElMessage.error('操作失败，请稍后重试')
  }
}

/**
 * 删除单条
 */
async function handleDelete(message: Message) {
  try {
    await ElMessageBox.confirm('确定要删除这条消息吗？', '删除确认', {
      type: 'warning',
    })
    await deleteMessages([message.id])
    ElMessage.success('删除成功')
    page.value = 1 // 重置到第1页，确保删除后的数据列表可见
    loadMessages()
  } catch {
    // 用户取消
  }
}

/**
 * 批量删除
 */
async function handleBatchDelete() {
  if (selectedMessages.value.length === 0) return

  try {
    await ElMessageBox.confirm(
      `确定要删除选中的 ${selectedMessages.value.length} 条消息吗？`,
      '批量删除确认',
      { type: 'warning' }
    )

    const ids = selectedMessages.value.map((m) => m.id)
    await deleteMessages(ids)
    ElMessage.success('删除成功')
    page.value = 1 // 重置到第1页，确保批量删除后的数据列表可见
    loadMessages()
  } catch {
    // 用户取消
  }
}

/**
 * 跳转链接
 */
function handleGoToLink(message: Message) {
  if (message.link) {
    if (message.link.startsWith('http')) {
      window.open(message.link, '_blank')
    } else {
      pushSafe(message.link)
    }
  }
}

/**
 * 格式化日期时间
 */
function formatDateTime(dateStr: string): string {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

/**
 * 初始化WebSocket
 */
function initWebSocket() {
  // 单机版：WebSocket 暂不启用，消息通过 HTTP 轮询获取
}

/**
 * 关闭WebSocket
 */
function closeWebSocket() {
  // 单机版：WebSocket 已禁用，无需清理
}

// ==================== 生命周期 ====================

onMounted(() => {
  loadMessages()
  loadActivities()
  loadMyLogs()
  initWebSocket()
})

onUnmounted(() => {
  closeWebSocket()
})
</script>

<style scoped lang="scss">
.message-center {
  padding: 20px;
}

.header-card {
  margin-bottom: 20px;

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;

    .title {
      font-size: 18px;
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .actions {
      display: flex;
      gap: 10px;
    }
  }
}

.list-card {
  .pagination {
    margin-top: 20px;
    justify-content: flex-end;
  }

  :deep(.unread-row) {
    background-color: var(--color-primary-light-8);
  }
}

.message-title {
  display: flex;
  align-items: center;
  gap: 8px;

  .unread {
    font-weight: 600;
  }

  .unread-dot {
    :deep(.el-badge__content) {
      top: 50%;
      transform: translateY(-50%);
    }
  }
}

.message-content {
  color: #606266;
}

.message-detail {
  .detail-content {
    white-space: pre-wrap;
    line-height: 1.6;
  }

  .detail-link {
    margin-top: 20px;
    text-align: center;
  }
}

.activity-pane {
  min-height: 200px;
  padding: 8px 4px;
}

.activity-item {
  .activity-title {
    font-weight: 600;
    color: #1b4332;
  }

  .activity-desc {
    margin-top: 4px;
    font-size: 13px;
    color: #666;
    line-height: 1.5;
  }
}

.activity-actions {
  margin-top: 16px;
  text-align: right;
}
</style>
