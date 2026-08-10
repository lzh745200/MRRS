<template>
  <div class="approval-overview">
    <div class="page-header">
      <h2 class="page-title">审批概览</h2>
      <p class="page-desc">集中查看待办审批、我的申请与审批历史</p>
    </div>

    <!-- 统计仪表板 -->
    <div class="stats-row">
      <el-card class="stat-card stat-pending">
        <div class="stat-num">{{ stats.pending_count }}</div>
        <div class="stat-label">待我审批</div>
      </el-card>
      <el-card class="stat-card">
        <div class="stat-num">{{ stats.my_pending }}</div>
        <div class="stat-label">我的待办申请</div>
      </el-card>
      <el-card class="stat-card stat-approved">
        <div class="stat-num">{{ stats.approved_count }}</div>
        <div class="stat-label">已通过</div>
      </el-card>
      <el-card class="stat-card stat-rejected">
        <div class="stat-num">{{ stats.rejected_count }}</div>
        <div class="stat-label">已驳回</div>
      </el-card>
      <el-card class="stat-card">
        <div class="stat-num">{{ stats.total_count }}</div>
        <div class="stat-label">审批总任务</div>
      </el-card>
    </div>

    <!-- 快捷入口 -->
    <div class="entry-row">
      <el-card class="entry-card" shadow="hover" @click="pushSafe('/approval/pending')">
        <div class="entry-icon">📥</div>
        <div class="entry-title">待审批任务</div>
        <div class="entry-desc">处理需要您审批的申请</div>
      </el-card>
      <el-card class="entry-card" shadow="hover" @click="pushSafe('/approval/my')">
        <div class="entry-icon">📝</div>
        <div class="entry-title">我的申请</div>
        <div class="entry-desc">查看我提交的审批及其状态</div>
      </el-card>
      <el-card class="entry-card" shadow="hover" @click="pushSafe('/approval/history')">
        <div class="entry-icon">🗂️</div>
        <div class="entry-title">审批历史</div>
        <div class="entry-desc">全部审批记录追溯</div>
      </el-card>
    </div>

    <!-- 待审批任务快捷列表 -->
    <el-card>
      <template #header>
        <div class="card-header">
          <span style="font-weight: 600; color: #1b4332">最新待审批任务</span>
          <el-button text type="primary" @click="pushSafe('/approval/pending')">查看全部</el-button>
        </div>
      </template>
      <el-table v-loading="loading" :data="pendingTasks" stripe empty-text="暂无待审批任务">
        <el-table-column prop="title" label="事项" min-width="220" show-overflow-tooltip />
        <el-table-column label="类型" width="110">
          <template #default="{ row }">
            <el-tag size="small">{{ typeLabel(row.entity_type || row.type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="submitter_name" label="申请人" width="110" />
        <el-table-column label="提交时间" width="170">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="goApprove(row)">审批</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 单机版快捷操作 -->
    <el-card v-if="stats.pending_count > 0">
      <template #header>
        <span style="font-weight: 600; color: #1b4332">单机版快捷操作</span>
      </template>
      <el-form label-width="200px">
        <el-form-item label="一键审批所有待处理">
          <el-button
            type="success"
            :loading="autoApproving"
            :disabled="stats.pending_count === 0"
            @click="handleAutoApproveAll"
          >
            一键通过全部 {{ stats.pending_count }} 个待处理任务
          </el-button>
          <span style="margin-left: 8px; color: #888"
            >适用于单机版快速处理（可稍后在审批历史中追溯）</span
          >
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getOverview, getPendingTasks, batchApprove } from '@/api/approval'
import { useRouterSafe } from '@/composables/useRouterSafe'

const { pushSafe } = useRouterSafe()

const loading = ref(false)
const autoApproving = ref(false)
const pendingTasks = ref<any[]>([])
const stats = reactive({
  pending_count: 0,
  my_pending: 0,
  approved_count: 0,
  rejected_count: 0,
  total_count: 0,
})

const TYPE_LABELS: Record<string, string> = {
  project: '项目',
  fund: '经费',
  village: '帮扶村',
  school: '学校',
  rural_work: '乡村工作',
  policy: '政策',
  other: '其他',
}

function typeLabel(t?: string) {
  return TYPE_LABELS[t || 'other'] || t || '其他'
}

function formatDate(v?: string) {
  if (!v) return '-'
  try {
    return new Date(v).toLocaleString('zh-CN')
  } catch {
    return String(v)
  }
}

async function loadOverview() {
  try {
    const res: any = await getOverview()
    const d = res?.data || res || {}
    stats.pending_count = Number(d.pending_count ?? 0)
    stats.approved_count = Number(d.approved_count ?? 0)
    stats.rejected_count = Number(d.rejected_count ?? 0)
    stats.total_count = Number(d.total_count ?? 0)
    stats.my_pending = Number(d.my_pending ?? d.pending_count ?? 0)
  } catch {
    /* 概览统计失败不阻塞页面 */
  }
}

async function loadPending() {
  loading.value = true
  try {
    const res: any = await getPendingTasks({ limit: 10 })
    pendingTasks.value = Array.isArray(res) ? res : res?.items || res?.data?.items || []
  } catch {
    pendingTasks.value = []
  } finally {
    loading.value = false
  }
}

function goApprove(row: any) {
  if (row?.task_id || row?.id) {
    pushSafe(`/approval/pending?focus=${row.task_id || row.id}`)
  } else {
    pushSafe('/approval/pending')
  }
}

async function handleAutoApproveAll() {
  try {
    await ElMessageBox.confirm(
      `确定一键通过全部 ${stats.pending_count} 个待审批任务吗？\n此操作会批量写入审批意见，请确认内容无误。`,
      '一键审批确认',
      { type: 'warning', confirmButtonText: '确认全部通过', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  autoApproving.value = true
  try {
    const ids = pendingTasks.value.map((t) => t.task_id ?? t.id).filter((id) => id != null)
    if (ids.length) {
      await batchApprove(ids, '单机版一键审批通过')
      ElMessage.success(`已通过 ${ids.length} 个待审批任务`)
    } else {
      ElMessage.info('当前没有可批量审批的任务')
    }
    await Promise.all([loadOverview(), loadPending()])
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '批量审批失败')
  } finally {
    autoApproving.value = false
  }
}

onMounted(() => {
  loadOverview()
  loadPending()
})
</script>

<style scoped>
.approval-overview {
  padding: 20px;
}
.page-header {
  margin-bottom: 18px;
}
.page-title {
  margin: 0 0 6px;
  color: #1b4332;
  font-size: 22px;
}
.page-desc {
  margin: 0;
  color: #6b7280;
  font-size: 13px;
}
.stats-row {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 14px;
  margin-bottom: 18px;
}
.stat-card {
  text-align: center;
}
.stat-card :deep(.el-card__body) {
  padding: 18px 10px;
}
.stat-num {
  font-size: 30px;
  font-weight: 700;
  color: #1b4332;
}
.stat-label {
  margin-top: 6px;
  color: #6b7280;
  font-size: 13px;
}
.stat-pending .stat-num {
  color: #e6a23c;
}
.stat-approved .stat-num {
  color: #67c23a;
}
.stat-rejected .stat-num {
  color: #f56c6c;
}
.entry-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
  margin-bottom: 18px;
}
.entry-card {
  cursor: pointer;
  text-align: center;
  transition: transform 0.15s ease;
}
.entry-card:hover {
  transform: translateY(-2px);
}
.entry-card :deep(.el-card__body) {
  padding: 22px 12px;
}
.entry-icon {
  font-size: 30px;
}
.entry-title {
  margin-top: 8px;
  font-size: 16px;
  font-weight: 600;
  color: #1b4332;
}
.entry-desc {
  margin-top: 4px;
  color: #6b7280;
  font-size: 12px;
}
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
</style>
