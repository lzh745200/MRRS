<template>
  <div class="info-row">
    <!-- 左侧：近期动态 -->
    <div class="timeline-section">
      <h3 class="section-title">近期动态</h3>
      <div class="timeline-list">
        <div v-if="loading" class="tl-state">加载中...</div>
        <div v-else-if="error && activities.length === 0" class="tl-state tl-state--error">
          <span>数据加载失败，请稍后重试</span>
          <el-button size="small" type="primary" @click="loadActivities">重试</el-button>
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
          <div v-if="activities.length === 0" class="tl-empty">暂无动态</div>
        </template>
      </div>
    </div>

    <!-- 快捷入口已整合至上方"快捷入口"卡片中 -->
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { EditPen, Close } from '@element-plus/icons-vue'
import { put, del, apiRequest } from '@/api/request'
import { logger } from '@/utils/logger'

const activities = ref<any[]>([])
const loading = ref(true)
const error = ref(false)
const retried = ref(false)
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

function formatTime(t: string): string {
  if (!t) return ''
  const d = new Date(t)
  if (isNaN(d.getTime())) return t.slice(0, 10)
  return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours()}:${String(d.getMinutes()).padStart(2, '0')}`
}

async function loadActivities() {
  loading.value = true
  error.value = false
  try {
    const res = await apiRequest({
      method: 'GET',
      url: '/dashboard/recent-activities',
      params: { limit: 10 },
    })
    const data = (res as any)?.data?.items || (res as any)?.items || []
    activities.value = (Array.isArray(data) ? data : []).slice(0, 10)
  } catch (e) {
    logger.error('近期动态加载失败', e)
    error.value = true
    activities.value = []
    // 后端可能仍在冷启动: 2 秒后自动重试一次,避免首次打开即报错
    if (!retried.value) {
      retried.value = true
      setTimeout(() => {
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
</script>

<style scoped lang="scss">
.info-row {
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
  @media (max-width: 768px) {
    grid-template-columns: 1fr;
  }
}

.timeline-section {
  background: var(--color-bg-card);
  border-radius: 12px;
  padding: 20px 24px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.section-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 0 0 16px 0;
  display: flex;
  align-items: center;
  gap: 8px;
  &::before {
    content: '';
    display: inline-block;
    width: 4px;
    height: 16px;
    border-radius: 2px;
    background: linear-gradient(180deg, #1e4d8c, var(--color-primary));
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
  font-size: 11px;
  color: var(--color-text-placeholder);
  font-family: 'DIN Alternate', monospace;
  white-space: nowrap;
  min-width: 50px;
}
.tl-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-primary);
  flex-shrink: 0;
}
.tl-text {
  font-size: 13px;
  color: var(--color-text-secondary);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tl-target {
  font-size: 12px;
  color: var(--color-text-placeholder);
  margin-left: 4px;
}
.tl-edit-btn,
.tl-delete-btn {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 12px;
  padding: 2px 6px;
  opacity: 0;
  transition: opacity 0.15s;
  color: var(--color-text-placeholder);
  border-radius: 4px;
  display: inline-flex;
  align-items: center;
}
.timeline-item:hover .tl-edit-btn,
.timeline-item:hover .tl-delete-btn {
  opacity: 1;
}
.tl-edit-btn:hover {
  color: var(--color-primary);
  background: var(----color-bg-hover);
}
.tl-delete-btn:hover {
  color: var(--color-danger);
  background: #fef2f2;
}
.tl-edit-input {
  font-size: 12px;
  padding: 2px 6px;
  border: 1px solid #d1d5db;
  border-radius: 4px;
  width: 80px;
}
.tl-save-btn,
.tl-cancel-btn {
  font-size: 11px;
  border: none;
  border-radius: 4px;
  padding: 2px 8px;
  cursor: pointer;
}
.tl-save-btn {
  background: var(--color-primary);
  color: var(--color-text-inverse);
}
.tl-cancel-btn {
  background: #e5e7eb;
  color: #374151;
}
.tl-empty {
  text-align: center;
  color: var(--color-text-placeholder);
  font-size: 13px;
  padding: 20px 0;
}
.tl-state {
  text-align: center;
  color: $color-text-secondary;
  font-size: 13px;
  padding: 20px 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: $spacing-sm;
}
</style>
