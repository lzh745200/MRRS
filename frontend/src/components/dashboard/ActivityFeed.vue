<template>
  <div v-show="visible" class="section-card">
    <div class="section-header">
      <h3>
        <el-icon><Clock /></el-icon> 近期动态
      </h3>
      <button class="text-btn" @click="showForm = !showForm">
        {{ showForm ? '取消' : '+ 添加动态' }}
      </button>
    </div>
    <div class="section-body">
      <!-- 添加动态表单 -->
      <div v-if="showForm" class="activity-add-form">
        <div class="activity-form-row">
          <select v-model="newActivity.type" class="activity-select">
            <option value="project">项目动态</option>
            <option value="fund">资金动态</option>
            <option value="village">帮扶村动态</option>
            <option value="system">系统通知</option>
          </select>
        </div>
        <div class="activity-form-row">
          <el-input
            v-model="newActivity.content"
            type="textarea"
            :rows="2"
            placeholder="请输入动态内容"
          />
        </div>
        <div class="activity-form-actions">
          <el-button size="small" type="primary" @click="addActivity">发布</el-button>
          <el-button size="small" @click="resetForm">重置</el-button>
        </div>
      </div>

      <!-- 动态列表 -->
      <div v-if="activities.length === 0" class="empty-state">
        <el-empty description="暂无动态" :image-size="60" />
      </div>
      <div v-else class="activity-list">
        <div v-for="activity in activities" :key="activity.id" class="activity-item">
          <div class="activity-icon" :class="'icon-' + activity.type">
            <el-icon><component :is="getTypeIcon(activity.type)" /></el-icon>
          </div>
          <div class="activity-content">
            <p class="activity-text">{{ activity.content }}</p>
            <span class="activity-time">{{ activity.time }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { Document, Money, House, Setting, Location, Clock } from '@element-plus/icons-vue'

interface Activity {
  id: number | string
  type: string
  content: string
  time: string
}

withDefaults(
  defineProps<{
    visible?: boolean
    activities?: Activity[]
  }>(),
  {
    visible: true,
    activities: () => [],
  }
)

const emit = defineEmits<{
  (e: 'add', activity: Omit<Activity, 'id' | 'time'>): void
}>()

const showForm = ref(false)
const newActivity = reactive({
  type: 'project',
  content: '',
})

function getTypeIcon(type: string): any {
  const icons: Record<string, any> = {
    project: Document,
    fund: Money,
    village: House,
    system: Setting,
  }
  return icons[type] || Location
}

function addActivity() {
  if (!newActivity.content.trim()) {
    ElMessage.warning('请输入动态内容')
    return
  }
  emit('add', { type: newActivity.type, content: newActivity.content })
  resetForm()
  showForm.value = false
}

function resetForm() {
  newActivity.type = 'project'
  newActivity.content = ''
}
</script>

<style scoped>
.section-card {
  background: var(--color-bg-card);
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.section-header h3 {
  margin: 0;
  font-size: 16px;
}
.text-btn {
  background: none;
  border: none;
  color: var(--color-primary);
  cursor: pointer;
  font-size: 13px;
}
.activity-add-form {
  margin-bottom: 16px;
  padding: 12px;
  background: #fafafa;
  border-radius: 8px;
}
.activity-form-row {
  margin-bottom: 8px;
}
.activity-select {
  width: 100%;
  padding: 6px 8px;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  font-size: 14px;
}
.activity-form-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
.activity-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.activity-item {
  display: flex;
  gap: 12px;
  padding: 8px;
  border-radius: 6px;
  transition: background 0.2s;
}
.activity-item:hover {
  background: var(--color-bg-hover);
}
.activity-icon {
  font-size: 20px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
}

.section-header h3 .el-icon {
  vertical-align: middle;
  margin-right: 4px;
}
.activity-content {
  flex: 1;
  min-width: 0;
}
.activity-text {
  margin: 0;
  font-size: 14px;
  color: var(--color-text-primary);
}
.activity-time {
  font-size: 12px;
  color: var(--color-info);
}
.empty-state {
  padding: 20px 0;
}
</style>
