<template>
  <div class="approval-center">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>审批中心</span>
          <el-badge :value="pendingCount" :hidden="pendingCount === 0" type="danger">
            <el-tag size="small">待处理</el-tag>
          </el-badge>
        </div>
      </template>

      <el-tabs v-model="activeTab" @tab-change="handleTabChange">
        <el-tab-pane label="待我审批" name="pending">
          <template #label>
            <el-badge :value="pendingCount" :hidden="pendingCount === 0" :max="99">
              <span>待我审批</span>
            </el-badge>
          </template>
        </el-tab-pane>
        <el-tab-pane label="我发起的" name="initiated" />
        <el-tab-pane label="已完成" name="completed" />
      </el-tabs>

      <!-- 批量操作栏 -->
      <div v-if="activeTab === 'pending' && selectedIds.length > 0" class="batch-bar">
        <span>已选 {{ selectedIds.length }} 项</span>
        <el-button size="small" type="success" :loading="batchLoading" @click="handleBatchApprove"
          >批量通过</el-button
        >
        <el-button size="small" type="danger" @click="handleBatchReject">批量驳回</el-button>
      </div>

      <el-table v-loading="loading" :data="tasks" stripe @selection-change="handleSelectionChange">
        <el-table-column v-if="activeTab === 'pending'" type="selection" width="45" />
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="title" label="审批标题" min-width="200" show-overflow-tooltip />
        <el-table-column prop="workflow_name" label="流程" width="140" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{
              statusLabel(row.status)
            }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="提交时间" width="160" show-overflow-tooltip />
        <el-table-column v-if="activeTab === 'pending'" label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button link size="small" type="success" @click="handleApprove(row as ApprovalTask)"
              >通过</el-button
            >
            <el-button link size="small" type="danger" @click="handleReject(row as ApprovalTask)"
              >驳回</el-button
            >
          </template>
        </el-table-column>
      </el-table>

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

<script lang="ts">
// 批量驳回原因必填校验（普通 script 具名导出，便于测试覆盖）
export function batchRejectValidator(v: string): true | string {
  return v && v.trim().length > 0 ? true : '驳回原因不能为空'
}
</script>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { get, post } from '@/api/request'

interface ApprovalTask {
  id: number
  title: string
  workflow_name: string
  status: string
  created_at: string
}

const activeTab = ref('pending')
const tasks = ref<ApprovalTask[]>([])
const loading = ref(false)
const batchLoading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const pendingCount = ref(0)
const selectedIds = ref<number[]>([])

function statusType(status: string): 'success' | 'warning' | 'danger' | 'info' | 'primary' {
  const map: Record<string, 'success' | 'warning' | 'danger' | 'info' | 'primary'> = {
    pending: 'warning',
    approved: 'success',
    rejected: 'danger',
    completed: 'info',
  }
  return map[status] || 'primary'
}

function statusLabel(status: string) {
  const map: Record<string, string> = {
    pending: '待审批',
    approved: '已通过',
    rejected: '已驳回',
    completed: '已完成',
    withdrawn: '已撤回',
  }
  return map[status] || status
}

async function loadTasks() {
  loading.value = true
  try {
    // 后端：/approval/tasks/all（管理员全部）与 /approval/tasks/pending（待审批），
    // 分页参数为 skip/limit
    const url = activeTab.value === 'pending' ? '/approval/tasks/pending' : '/approval/tasks/all'
    const params: Record<string, unknown> = {
      skip: (page.value - 1) * pageSize.value,
      limit: pageSize.value,
    }
    if (activeTab.value === 'completed') {
      params.status = 'completed'
    }
    const res: any = await get(url, params)
    // get() 已解包：items 提升到顶层
    const data = res?.data ?? res
    const list = data?.items || data?.data?.items || (Array.isArray(data) ? data : [])
    tasks.value = Array.isArray(list) ? list : []
    total.value = data?.total ?? tasks.value.length
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载审批任务失败')
  } finally {
    loading.value = false
  }
}

async function loadPendingCount() {
  try {
    const res: any = await get('/approval/tasks/pending', { skip: 0, limit: 1 })
    const data = res?.data ?? res
    pendingCount.value = data?.total ?? 0
  } catch {
    pendingCount.value = 0
  }
}

function handleTabChange() {
  page.value = 1
  selectedIds.value = []
  loadTasks()
}

function handlePageChange(p: number) {
  page.value = p
  loadTasks()
}

function handleSelectionChange(rows: ApprovalTask[]) {
  selectedIds.value = rows.map((r) => r.id)
}

async function handleApprove(row: ApprovalTask) {
  try {
    await ElMessageBox.confirm(`确认通过审批「${row.title}」？`, '审批确认', { type: 'success' })
    await post(`/approval/tasks/${row.id}/approve`, { opinion: '同意' })
    ElMessage.success('审批通过')
    await loadTasks()
    await loadPendingCount()
  } catch {
    // 用户取消
  }
}

async function handleReject(row: ApprovalTask) {
  try {
    const { value } = await ElMessageBox.prompt('请输入驳回原因（必填）', '驳回审批', {
      inputPlaceholder: '驳回原因',
      inputValidator: (v: string) => (v && v.trim().length > 0 ? true : '驳回原因不能为空'),
      type: 'warning',
    })
    await post(`/approval/tasks/${row.id}/reject`, { opinion: value.trim() })
    ElMessage.success('已驳回')
    await loadTasks()
    await loadPendingCount()
  } catch {
    // 用户取消
  }
}

async function handleBatchApprove() {
  try {
    await ElMessageBox.confirm(`确认批量通过 ${selectedIds.value.length} 项审批？`, '批量审批', {
      type: 'success',
    })
    batchLoading.value = true
    await post('/approval/tasks/batch', {
      task_ids: selectedIds.value,
      opinion: '批量通过',
    })
    ElMessage.success('批量审批通过')
    selectedIds.value = []
    await loadTasks()
    await loadPendingCount()
  } catch {
    // 用户取消或失败
  } finally {
    batchLoading.value = false
  }
}

// 批量驳回原因必填校验（具名函数便于测试覆盖）
async function handleBatchReject() {
  try {
    const { value } = await ElMessageBox.prompt('请输入驳回原因（必填）', '批量驳回', {
      inputPlaceholder: '驳回原因',
      inputValidator: batchRejectValidator,
      type: 'warning',
    })
    batchLoading.value = true
    for (const id of selectedIds.value) {
      await post(`/approval/tasks/${id}/reject`, { opinion: value.trim() })
    }
    ElMessage.success('批量驳回完成')
    selectedIds.value = []
    await loadTasks()
    await loadPendingCount()
  } catch {
    // 用户取消或失败
  } finally {
    batchLoading.value = false
  }
}

onMounted(() => {
  loadTasks()
  loadPendingCount()
})
</script>

<style scoped>
.approval-center {
  padding: 20px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.batch-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  padding: 8px 12px;
  background: #f0f9eb;
  border-radius: 4px;
}
</style>
