<template>
  <div class="update-logs-page">
    <div class="page-header">
      <div>
        <h2 class="page-title">系统更新日志</h2>
        <p class="page-desc">查看系统版本更新历史和变更记录</p>
      </div>
      <div class="header-actions">
        <el-button v-if="isAdmin" type="primary" @click="showAddDialog = true">
          + 添加更新记录
        </el-button>
        <el-button :loading="loading" @click="refreshData">刷新</el-button>
      </div>
    </div>

    <!-- 最新版本高亮卡片 -->
    <el-card v-if="latestLog" class="latest-card">
      <template #header>
        <div class="latest-header">
          <span class="latest-label">最新版本</span>
          <el-tag type="success" size="large">{{ latestLog.version }}</el-tag>
        </div>
      </template>
      <div class="latest-body">
        <p class="latest-desc">{{ latestLog.description }}</p>
        <div class="latest-meta">
          <span>发布时间：{{ formatDate(latestLog.created_at) }}</span>
          <span>操作人：{{ latestLog.updated_by || '系统' }}</span>
        </div>
      </div>
    </el-card>

    <!-- 加载骨架 -->
    <el-skeleton v-if="loading && !logs.length" :rows="5" animated />

    <!-- 更新日志时间线 -->
    <el-card v-else class="timeline-card">
      <template #header>
        <span class="card-title">更新历史</span>
      </template>

      <div v-if="logs.length" class="timeline-wrapper">
        <el-timeline>
          <el-timeline-item
            v-for="log in logs"
            :key="log.id"
            :timestamp="formatDate(log.created_at)"
            placement="top"
            :color="
              log.version === latestLog?.version ? 'var(--color-primary)' : 'var(--color-info)'
            "
          >
            <el-card shadow="hover" class="timeline-item-card">
              <div class="log-header">
                <el-tag
                  :type="log.version === latestLog?.version ? 'primary' : 'info'"
                  size="small"
                >
                  {{ log.version }}
                </el-tag>
                <span class="log-author">{{ log.updated_by || '系统' }}</span>
                <el-button
                  v-if="isAdmin"
                  type="danger"
                  size="small"
                  text
                  @click="handleDelete(log)"
                >
                  删除
                </el-button>
              </div>
              <p class="log-description">{{ log.description }}</p>
            </el-card>
          </el-timeline-item>
        </el-timeline>
      </div>

      <el-empty v-else description="暂无更新记录" />

      <!-- 分页 -->
      <div v-if="total > pageSize" class="pagination-wrapper">
        <el-pagination
          v-model:current-page="currentPage"
          :page-size="pageSize"
          :total="total"
          layout="prev, pager, next"
          @current-change="loadLogs"
        />
      </div>
    </el-card>

    <!-- 添加更新记录对话框 -->
    <el-dialog v-model="showAddDialog" title="添加更新记录" width="480px">
      <el-form :model="newLog" label-width="80px">
        <el-form-item label="版本号" required>
          <el-input v-model="newLog.version" placeholder="如 V1.2.0" />
        </el-form-item>
        <el-form-item label="更新内容" required>
          <el-input
            v-model="newLog.description"
            type="textarea"
            :rows="5"
            placeholder="请描述本次更新的内容"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitLog"> 确定 </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { updateLogsApi, type UpdateLog } from '@/api/updateLogs'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const isAdmin = computed(() => authStore.isAdmin)

const loading = ref(false)
const saving = ref(false)
const logs = ref<UpdateLog[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = 20
const latestLog = ref<UpdateLog | null>(null)

const showAddDialog = ref(false)
const newLog = ref({ version: '', description: '' })

async function loadLogs() {
  loading.value = true
  try {
    const result = await updateLogsApi.listLogs({
      page: currentPage.value,
      page_size: pageSize,
    })
    if (result.success && result.data) {
      logs.value = result.data.items || []
      total.value = result.data.total || 0
    }
  } catch {
    ElMessage.error('加载更新日志失败')
  } finally {
    loading.value = false
  }
}

async function loadLatest() {
  try {
    const result = await updateLogsApi.getLatest()
    if (result.success && result.data) {
      latestLog.value = result.data as UpdateLog
    }
  } catch {
    // 可能没有记录，忽略
  }
}

async function refreshData() {
  await Promise.all([loadLogs(), loadLatest()])
}

async function submitLog() {
  if (!newLog.value.version || !newLog.value.description) {
    ElMessage.warning('请填写版本号和更新内容')
    return
  }
  saving.value = true
  try {
    await updateLogsApi.createLog({
      version: newLog.value.version,
      description: newLog.value.description,
    })
    ElMessage.success('更新日志已添加')
    showAddDialog.value = false
    newLog.value = { version: '', description: '' }
    currentPage.value = 1 // 重置到第1页，确保新建/编辑后的数据可见
    await refreshData()
  } catch (e: any) {
    ElMessage.error(e?.message || '添加失败')
  } finally {
    saving.value = false
  }
}

async function handleDelete(log: UpdateLog) {
  try {
    await ElMessageBox.confirm(`确定要删除版本 ${log.version} 的更新记录吗？`, '确认删除', {
      type: 'warning',
    })
    await updateLogsApi.deleteLog(log.id)
    ElMessage.success('已删除')
    currentPage.value = 1 // 重置到第1页，确保新建/编辑后的数据可见
    await refreshData()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e?.message || '删除失败')
    }
  }
}

function formatDate(dateStr: string) {
  if (!dateStr) return '-'
  try {
    const d = new Date(dateStr)
    return d.toLocaleDateString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    })
    /* c8 ignore start */
  } catch {
    return dateStr.slice(0, 10)
  }
  /* c8 ignore stop */
}

onMounted(() => {
  refreshData()
})
</script>

<style scoped lang="scss">
.update-logs-page {
  padding: 20px;
  max-width: 900px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;

  .page-title {
    margin: 0 0 4px;
    font-size: 20px;
    font-weight: 600;
    color: $military-dark;
  }
  .page-desc {
    margin: 0;
    font-size: 13px;
    color: var(--color-info);
  }
  .header-actions {
    display: flex;
    gap: 8px;
  }
}

.latest-card {
  margin-bottom: 20px;
  border-left: 4px solid var(--color-primary);

  .latest-header {
    display: flex;
    align-items: center;
    gap: 12px;
    .latest-label {
      font-weight: 600;
      color: var(--color-text-primary);
    }
  }
  .latest-body {
    .latest-desc {
      margin: 0 0 12px;
      font-size: 15px;
      color: var(--color-text-primary);
      white-space: pre-wrap;
      line-height: 1.6;
    }
    .latest-meta {
      display: flex;
      gap: 20px;
      font-size: 12px;
      color: var(--color-info);
    }
  }
}

.timeline-card {
  .card-title {
    font-size: 16px;
    font-weight: 600;
  }
}

.timeline-wrapper {
  padding: 10px 0;
}

.timeline-item-card {
  .log-header {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 8px;
    .log-author {
      font-size: 12px;
      color: var(--color-info);
      flex: 1;
    }
  }
  .log-description {
    margin: 0;
    font-size: 14px;
    color: var(--color-text-regular);
    white-space: pre-wrap;
    line-height: 1.6;
  }
}

.pagination-wrapper {
  display: flex;
  justify-content: center;
  margin-top: 20px;
}
</style>
