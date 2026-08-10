<template>
  <div v-show="visible" class="section-card">
    <div class="section-header">
      <h3>
        <el-icon><DataAnalysis /></el-icon> 项目进度
      </h3>
      <button class="text-btn" @click="$emit('viewAll')">查看全部</button>
    </div>
    <div class="section-body">
      <div v-if="projects.length === 0" class="empty-state">
        <el-empty description="暂无项目数据" :image-size="60" />
      </div>
      <div v-else class="progress-list">
        <div v-for="project in displayProjects" :key="project.id" class="progress-item">
          <div class="progress-info">
            <span class="project-name">{{ project.name }}</span>
            <span class="project-status" :class="project.statusClass">
              {{ project.statusText }}
            </span>
          </div>
          <el-progress
            :percentage="project.progress"
            :status="project.progress >= 100 ? 'success' : undefined"
            :stroke-width="8"
          />
          <div class="progress-meta">
            <span>{{ project.startDate }}</span>
            <span>{{ project.progress }}%</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { DataAnalysis } from '@element-plus/icons-vue'

interface ProjectItem {
  id: number | string
  name: string
  progress: number
  statusClass: string
  statusText: string
  startDate: string
}

const props = withDefaults(
  defineProps<{
    visible?: boolean
    projects?: ProjectItem[]
    maxDisplay?: number
  }>(),
  {
    visible: true,
    projects: () => [],
    maxDisplay: 5,
  }
)

defineEmits<{
  (e: 'viewAll'): void
}>()

const displayProjects = computed(() => props.projects.slice(0, props.maxDisplay))
</script>

<style scoped>
.section-card {
  background: #fff;
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

.section-header h3 .el-icon {
  vertical-align: middle;
  margin-right: 4px;
}
.text-btn {
  background: none;
  border: none;
  color: var(--color-primary);
  cursor: pointer;
  font-size: 13px;
}
.progress-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.progress-item {
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
}
.progress-item:last-child {
  border-bottom: none;
}
.progress-info {
  display: flex;
  justify-content: space-between;
  margin-bottom: 4px;
}
.project-name {
  font-weight: 500;
  font-size: 14px;
}
.project-status {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 4px;
}
.project-status.active {
  background: #ecf5ff;
  color: #409eff;
}
.project-status.completed {
  background: #f0f9eb;
  color: #67c23a;
}
.project-status.delayed {
  background: #fef0f0;
  color: #f56c6c;
}
.progress-meta {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}
.empty-state {
  padding: 20px 0;
}
</style>
