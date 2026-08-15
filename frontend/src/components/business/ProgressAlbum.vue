<template>
  <div class="progress-album">
    <div v-if="!items || items.length === 0" class="empty-state">
      <el-empty :description="emptyText" />
    </div>
    <el-row v-else :gutter="16">
      <el-col
        v-for="(item, index) in items"
        :key="index"
        :xs="24"
        :sm="colSpan"
        :md="colSpan"
        :lg="colSpan"
      >
        <el-card shadow="hover" class="progress-card">
          <template #header>
            <div class="card-header">
              <span class="title">{{ item.title || item.name }}</span>
              <el-tag :type="getStatusType(item.status)" size="small">
                {{ item.status }}
              </el-tag>
            </div>
          </template>
          <div class="card-body">
            <el-progress
              v-if="item.progress != null"
              :percentage="Math.min(item.progress, 100)"
              :status="item.progress >= 100 ? 'success' : undefined"
              :stroke-width="strokeWidth"
            />
            <p v-if="item.description" class="description">
              {{ item.description }}
            </p>
            <div v-if="item.images && item.images.length" class="images-row">
              <el-image
                v-for="(img, i) in item.images.slice(0, 3)"
                :key="i"
                :src="img"
                fit="cover"
                class="thumb"
              />
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
interface AlbumItem {
  id?: number
  title?: string
  name?: string
  status: string
  progress?: number
  description?: string
  images?: string[]
}

withDefaults(
  defineProps<{
    items: AlbumItem[]
    colSpan?: number
    strokeWidth?: number
    emptyText?: string
  }>(),
  {
    colSpan: 8,
    strokeWidth: 16,
    emptyText: '暂无进度数据',
  }
)

function getStatusType(
  status: string
): 'success' | 'warning' | 'danger' | 'info' | 'primary' | undefined {
  const map: Record<string, 'success' | 'warning' | 'danger' | 'info' | 'primary'> = {
    completed: 'success',
    in_progress: 'warning',
    进行中: 'warning',
    已完成: 'success',
    delayed: 'danger',
    延期: 'danger',
    cancelled: 'info',
    已取消: 'info',
  }
  return map[status] || undefined
}
</script>

<style scoped>
.progress-album {
  width: 100%;
}
.empty-state {
  padding: 40px;
  text-align: center;
}
.progress-card {
  margin-bottom: 16px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.card-header .title {
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.card-body {
  padding: 8px 0;
}
.description {
  margin-top: 8px;
  color: var(--color-info);
  font-size: 13px;
}
.images-row {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}
.thumb {
  width: 80px;
  height: 60px;
  border-radius: 4px;
}
</style>
