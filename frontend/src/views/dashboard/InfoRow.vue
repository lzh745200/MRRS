<template>
  <div class="info-row">
    <!-- 左侧：近期动态 -->
    <div class="timeline-section app-card">
      <h3 class="section-title">近期动态</h3>
      <div class="timeline-list">
        <div v-if="loading" class="tl-state app-loading" data-testid="info-loading">加载中...</div>
        <div
          v-else-if="error && activities.length === 0"
          class="tl-state tl-state--error app-error"
          data-testid="info-error"
        >
          <span>数据加载失败，请稍后重试</span>
          <el-button type="primary" @click="loadActivities">重试</el-button>
        </div>
        <template v-else>
          <div v-for="item in activities" :key="item.id" class="timeline-item">
            <span class="tl-time">{{ formatTime(item.time || item.created_at) }}</span>
            <span class="tl-dot" />
            <template v-if="editingId === item.id">
              <input v-model="editForm.action" class="tl-edit-input" placeholder="操作" />
              <input v-model="editForm.target" class="tl-edit-input" placeholder="目标" />
              <button class="tl-save-btn" @click="saveEdit(item.id)">保存</button>
              <button class="tl-cancel-btn" @click="editingId = null">取消</button>
            </template>
            <template v-else>
              <span class="tl-text">{{ item.action || item.description || '--' }}</span>
              <span v-if="item.target" class="tl-target">— {{ item.target }}</span>
              <!-- 自定义动态可编辑；系统动态（project_/fund_/approval_ 等）也可删除（隐藏式） -->
              <button
                v-if="String(item.id).startsWith('custom_') || item._custom === true"
                class="tl-edit-btn"
                title="编辑"
                @click="startEdit(item)"
              >
                <el-icon><EditPen /></el-icon>
              </button>
              <button class="tl-delete-btn" title="删除" @click="deleteActivity(item.id)">
                <el-icon><Close /></el-icon>
              </button>
            </template>
          </div>
          <div v-if="activities.length === 0" class="tl-empty app-empty" data-testid="info-empty">
            暂无动态
          </div>
        </template>
      </div>
    </div>

    <!-- 快捷入口已整合至上方"快捷入口"卡片中 -->
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { unwrapList } from '@/utils/unwrapList'
import { ElMessage } from 'element-plus'
import { EditPen, Close } from '@element-plus/icons-vue'
import { put, del, apiRequest } from '@/api/request'
import { logger } from '@/utils/logger'

import { format } from '@/utils'
const activities = ref<any[]>([])
const loading = ref(true)
const error = ref(false)
const retried = ref(false)
// 失败自动重试的定时器句柄：卸载时必须清理，否则销毁后仍会触发一次 loadActivities
let retryTimer: ReturnType<typeof setTimeout> | undefined
const editingId = ref<string | null>(null)
const editForm = ref({ action: '', target: '' })

function startEdit(item: any) {
  editingId.value = item.id
  editForm.value = { action: item.action || '', target: item.target || '' }
}

async function saveEdit(id: string) {
  try {
    await put(`/dashboard/recent-activities/${id}`, editForm.value)
    const idx = activities.value.findIndex((a) => a.id === id)
    if (idx >= 0) {
      activities.value[idx].action = editForm.value.action
      activities.value[idx].target = editForm.value.target
    }
    editingId.value = null
  } catch {
    ElMessage.error('保存失败，请重试')
  }
}

async function deleteActivity(id: string) {
  try {
    await del(`/dashboard/recent-activities/${id}`)
    activities.value = activities.value.filter((a) => a.id !== id)
  } catch {
    ElMessage.error('删除失败，请重试')
  }
}

const formatTime = (t?: string | null): string => format.formatShortDateTime(t)

async function loadActivities() {
  loading.value = true
  error.value = false
  try {
    const res = await apiRequest({
      method: 'GET',
      url: '/dashboard/recent-activities',
      params: { limit: 10 },
    })
    const data = unwrapList(res).items
    activities.value = (Array.isArray(data) ? data : []).slice(0, 10)
  } catch (e) {
    logger.error('近期动态加载失败', e)
    error.value = true
    activities.value = []
    // 后端可能仍在冷启动: 2 秒后自动重试一次,避免首次打开即报错
    if (!retried.value) {
      retried.value = true
      retryTimer = setTimeout(() => {
        if (error.value) loadActivities()
      }, 2000)
    }
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadActivities()
})

onUnmounted(() => {
  clearTimeout(retryTimer) // undefined 为安全空操作，无需分支
})
</script>

<style scoped lang="scss">
.info-row {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--spacing-md, 16px);
}

.timeline-section {
  background: var(--color-bg-card);
  border: 1px solid var(--color-card-border, var(--color-border-light));
  border-radius: var(--radius-card, 8px);
  padding: var(--spacing-lg, 20px);
  box-shadow: var(--shadow-card);
  min-width: 0;
}

.section-title {
  font-size: var(--text-lg, 16px);
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 0 0 var(--spacing-md, 16px) 0;
  display: flex;
  align-items: center;
  gap: 8px;

  &::before {
    content: '';
    display: inline-block;
    width: 4px;
    height: 16px;
    border-radius: 2px;
    background: var(--color-primary);
  }
}

.timeline-list {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.timeline-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px solid var(--color-border-lighter);

  &:last-child {
    border-bottom: none;
  }
}

.tl-time {
  font-size: var(--text-xs, 12px);
  color: var(--color-text-placeholder);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  min-width: 50px;
}

.tl-dot {
  width: 6px;
  height: 6px;
  border-radius: var(--radius-pill, 999px);
  background: var(--color-primary);
  flex-shrink: 0;
}

.tl-text {
  font-size: var(--text-sm, 13px);
  color: var(--color-text-secondary);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tl-target {
  font-size: var(--text-xs, 12px);
  color: var(--color-text-placeholder);
  margin-left: 4px;
}

.tl-edit-btn,
.tl-delete-btn {
  background: none;
  border: none;
  cursor: pointer;
  font-size: var(--text-xs, 12px);
  padding: 2px 6px;
  opacity: 0;
  transition: opacity var(--transition-fast, 0.2s);
  color: var(--color-text-placeholder);
  border-radius: var(--radius-control, 6px);
  display: inline-flex;
  align-items: center;
}

.timeline-item:hover .tl-edit-btn,
.timeline-item:hover .tl-delete-btn {
  opacity: 1;
}

.tl-edit-btn:hover {
  color: var(--color-primary);
  background: var(--color-bg-hover);
}

.tl-delete-btn:hover {
  color: var(--color-danger);
  background: var(--color-danger-lightest);
}

.tl-edit-input {
  font-size: var(--text-xs, 12px);
  padding: 2px 6px;
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-control, 6px);
  width: 80px;
  background: var(--color-bg-card);
  color: var(--color-text-primary);
}

.tl-save-btn,
.tl-cancel-btn {
  font-size: var(--text-xs, 12px);
  border: none;
  border-radius: var(--radius-control, 6px);
  padding: 2px 8px;
  cursor: pointer;
}

.tl-save-btn {
  background: var(--color-primary);
  color: var(--color-text-inverse);
}

.tl-cancel-btn {
  background: var(--color-bg-hover);
  color: var(--color-text-primary);
}

.tl-empty {
  text-align: center;
  color: var(--color-text-placeholder);
  font-size: var(--text-sm, 13px);
  padding: var(--spacing-lg, 20px) 0;
}

.tl-state {
  text-align: center;
  color: var(--color-text-secondary);
  font-size: var(--text-sm, 13px);
  padding: var(--spacing-lg, 20px) 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--spacing-sm, 12px);
}
</style>
