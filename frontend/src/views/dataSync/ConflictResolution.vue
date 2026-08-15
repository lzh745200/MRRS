<template>
  <div class="conflict-resolution">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>数据冲突解决</span>
          <el-button type="primary" @click="resolveAll">批量解决</el-button>
        </div>
      </template>

      <el-alert
        v-if="conflicts.length === 0"
        title="暂无冲突"
        type="success"
        :closable="false"
        show-icon
      />

      <div v-else class="conflicts-list">
        <el-collapse v-model="activeNames">
          <el-collapse-item v-for="(conflict, index) in conflicts" :key="conflict.id" :name="index">
            <template #title>
              <div class="conflict-title">
                <el-tag :type="getConflictTypeTag(conflict.conflict_type || '')">
                  {{ getConflictTypeLabel(conflict.conflict_type || '') }}
                </el-tag>
                <span class="table-name">{{ conflict.table_name }}</span>
                <span class="record-id">记录ID: {{ conflict.record_id }}</span>
              </div>
            </template>

            <div class="conflict-content">
              <el-row :gutter="20">
                <el-col :span="12">
                  <div class="data-panel">
                    <h4>导入数据</h4>
                    <el-descriptions :column="1" border>
                      <el-descriptions-item
                        v-for="(value, key) in conflict.remote_data"
                        :key="key"
                        :label="key"
                      >
                        {{ value }}
                      </el-descriptions-item>
                    </el-descriptions>
                  </div>
                </el-col>
              </el-row>

              <div class="conflict-actions">
                <el-radio-group v-model="conflict.resolution">
                  <el-radio value="keep_local">保留本地数据</el-radio>
                  <el-radio value="use_import">使用导入数据</el-radio>
                  <el-radio value="merge">合并数据</el-radio>
                </el-radio-group>
                <el-button type="primary" size="small" @click="resolveConflict(conflict)">
                  解决此冲突
                </el-button>
              </div>
            </div>
          </el-collapse-item>
        </el-collapse>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useRouterSafe } from '@/composables/useRouterSafe'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getConflicts,
  resolveConflict as resolveConflictApi,
  type ConflictDetail,
} from '@/api/dataSync'

interface Conflict extends ConflictDetail {
  remote_data: Record<string, any>
  resolution?: 'keep_local' | 'use_import' | 'merge'
  conflict_type?: string
  table_name?: string
  record_id?: string | number
}

const route = useRoute()
const { pushSafe } = useRouterSafe()
const conflicts = ref<Conflict[]>([])
const activeNames = ref<number[]>([])
const loading = ref(false)

const getConflictTypeTag = (type: string): 'info' | 'warning' | 'danger' => {
  const tags: Record<string, 'info' | 'warning' | 'danger'> = {
    update: 'warning',
    delete: 'danger',
    insert: 'info',
  }
  return tags[type] || 'info'
}

const getConflictTypeLabel = (type: string) => {
  const labels: Record<string, string> = {
    update: '更新冲突',
    delete: '删除冲突',
    insert: '插入冲突',
  }
  return labels[type] || type
}

const loadConflicts = async () => {
  try {
    loading.value = true
    const syncLogId = route.query.syncLogId as string
    if (!syncLogId) {
      ElMessage.warning('缺少同步日志ID')
      return
    }

    const response = await getConflicts(parseInt(syncLogId))
    if (response.success) {
      const conflictList = Array.isArray(response.data)
        ? response.data
        : response.data?.items || response.data?.data || []
      conflicts.value = conflictList.map((c: any) => ({
        ...c,
        remote_data: c.import_data ?? c.remote_data,
        resolution: 'keep_local' as const,
      }))
      // 默认展开第一个冲突
      if (conflicts.value.length > 0) {
        activeNames.value = [0]
      }
    }
  } catch (error: any) {
    ElMessage.error(error.message || '加载冲突数据失败')
  } finally {
    loading.value = false
  }
}

const resolveConflict = async (conflict: Conflict) => {
  if (!conflict.resolution) {
    ElMessage.warning('请选择解决方案')
    return
  }

  try {
    await resolveConflictApi({
      conflict_id: Number(conflict.id),
      resolution: conflict.resolution,
    })
    ElMessage.success('冲突已解决')
    // 从列表中移除已解决的冲突
    conflicts.value = conflicts.value.filter((c) => c.id !== conflict.id)
  } catch (error: any) {
    ElMessage.error(error.message || '解决冲突失败')
  }
}

const resolveAll = async () => {
  if (conflicts.value.length === 0) {
    ElMessage.info('没有需要解决的冲突')
    return
  }

  try {
    await ElMessageBox.confirm(`确定要批量解决 ${conflicts.value.length} 个冲突吗？`, '批量解决', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })

    for (const conflict of conflicts.value) {
      await resolveConflictApi({
        conflict_id: Number(conflict.id),
        resolution: conflict.resolution || 'keep_local',
      })
    }

    ElMessage.success('所有冲突已解决')
    conflicts.value = []
    pushSafe({ name: 'DataSyncImport' })
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '批量解决失败')
    }
  }
}

onMounted(() => {
  loadConflicts()
})
</script>

<style scoped lang="scss">
.conflict-resolution {
  padding: 20px;

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .conflicts-list {
    margin-top: 20px;
  }

  .conflict-title {
    display: flex;
    align-items: center;
    gap: 12px;
    flex: 1;

    .table-name {
      font-weight: 500;
    }

    .record-id {
      color: var(--color-info);
      font-size: 14px;
    }
  }

  .conflict-content {
    padding: 20px 0;

    .data-panel {
      h4 {
        margin-bottom: 12px;
        color: #303133;
      }
    }

    .conflict-actions {
      margin-top: 20px;
      padding-top: 20px;
      border-top: 1px solid #ebeef5;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
  }
}
</style>
