<template>
  <div class="my-applications">
    <div class="page-header">
      <h2 class="page-title">我的申请</h2>
      <p class="page-desc">查看自己提交的审批申请及状态</p>
    </div>

    <!-- 筛选 -->
    <el-card class="filter-card">
      <el-form :inline="true" :model="filters">
        <el-form-item label="状态">
          <el-select v-model="filters.status" clearable placeholder="全部" style="width: 140px">
            <el-option label="待审批" value="pending" />
            <el-option label="已通过" value="approved" />
            <el-option label="已驳回" value="rejected" />
          </el-select>
        </el-form-item>
        <el-form-item label="时间范围">
          <el-date-picker
            v-model="filters.dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始"
            end-placeholder="结束"
            value-format="YYYY-MM-DD"
            style="width: 260px"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadData">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 统计卡片 -->
    <div class="stats-row">
      <el-card class="stat-card"
        ><div class="stat-num">{{ stats.total }}</div>
        <div class="stat-label">总申请</div></el-card
      >
      <el-card class="stat-card stat-pending"
        ><div class="stat-num">{{ stats.pending }}</div>
        <div class="stat-label">待审批</div></el-card
      >
      <el-card class="stat-card stat-approved"
        ><div class="stat-num">{{ stats.approved }}</div>
        <div class="stat-label">已通过</div></el-card
      >
      <el-card class="stat-card stat-rejected"
        ><div class="stat-num">{{ stats.rejected }}</div>
        <div class="stat-label">已驳回</div></el-card
      >
    </div>

    <!-- 申请列表 -->
    <el-card>
      <el-table v-loading="loading" :data="applications" stripe>
        <el-table-column prop="title" label="申请标题" min-width="200" />
        <el-table-column prop="type" label="类型" width="120">
          <template #default="{ row }">
            <el-tag size="small">
              {{ formatEntityType(row.type || row.entity_type) || '通用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">{{
              statusLabel(row.status)
            }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="提交时间" width="170">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column prop="reviewer_name" label="审批人" width="120" />
        <el-table-column prop="opinion" label="审批意见" min-width="200" show-overflow-tooltip />
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'pending'"
              link
              type="warning"
              size="small"
              @click="handleWithdraw(row)"
              >撤回</el-button
            >
            <el-button
              v-if="row.status === 'rejected'"
              link
              type="primary"
              size="small"
              @click="handleResubmit(row)"
              >重新提交</el-button
            >
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getMyTasks, formatEntityType, type ApprovalTask } from '@/api/approval'
import { post } from '@/api/request'

const loading = ref(false)
const applications = ref<ApprovalTask[]>([])
const filters = reactive({ status: '', dateRange: null as any })

const stats = computed(() => {
  const list = applications.value
  return {
    total: list.length,
    pending: list.filter((a) => a.status === 'pending').length,
    approved: list.filter((a) => a.status === 'approved').length,
    rejected: list.filter((a) => a.status === 'rejected').length,
  }
})

const statusLabel = (s: string) =>
  ({
    pending: '待审批',
    approved: '已通过',
    rejected: '已驳回',
    withdrawn: '已撤回',
  })[s] || s
const statusTagType = (
  s: string
): 'success' | 'warning' | 'danger' | 'info' | 'primary' | undefined =>
  (
    ({
      pending: 'warning',
      approved: 'success',
      rejected: 'danger',
      withdrawn: 'info',
    }) as Record<string, 'success' | 'warning' | 'danger' | 'info' | 'primary'>
  )[s] || 'info'
const formatDate = (d: string) => (d ? new Date(d).toLocaleString('zh-CN') : '-')

async function loadData() {
  loading.value = true
  try {
    const params: Record<string, any> = {}
    if (filters.status) params.status = filters.status
    if (filters.dateRange?.length === 2) {
      params.date_from = filters.dateRange[0]
      params.date_to = filters.dateRange[1]
    }
    // 使用「我的申请」任务接口：后端按当前用户过滤提交记录，id 即任务ID
    const result = await getMyTasks({ ...params, skip: 0, limit: 500 })
    applications.value = result.items
  } catch {
    applications.value = []
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  filters.status = ''
  filters.dateRange = null
  loadData()
}

async function handleWithdraw(row: any) {
  try {
    await ElMessageBox.confirm(
      `确认撤回「${row.title || '该申请'}」？撤回后审批流程将终止。`,
      '撤回申请',
      { type: 'warning' }
    )
    await post(`/approval/tasks/${row.id}/withdraw`)
    ElMessage.success('已撤回')
    loadData()
  } catch {
    // 用户取消
  }
}

async function handleResubmit(row: any) {
  try {
    await ElMessageBox.confirm(`确认重新提交「${row.title || '该申请'}」？`, '重新提交')
    await post(`/approval/tasks/${row.id}/resubmit`)
    ElMessage.success('已重新提交')
    loadData() // 重新加载数据
  } catch {
    // 用户取消
  }
}

onMounted(loadData)
</script>

<style scoped>
.my-applications {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.page-header {
  margin-bottom: 0;
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
.filter-card {
  padding: 0;
}
.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}
.stat-card {
  text-align: center;
  padding: 16px;
}
.stat-num {
  font-size: 28px;
  font-weight: 700;
  color: var(--color-primary-dark-1);
}
.stat-label {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin-top: 4px;
}
.stat-pending .stat-num {
  color: var(--color-warning);
}
.stat-approved .stat-num {
  color: var(--color-success);
}
.stat-rejected .stat-num {
  color: var(--color-danger);
}
</style>
