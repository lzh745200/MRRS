<template>
  <div class="map-tile-manager">
    <el-card class="page-header">
      <div class="header-content">
        <h2>地图瓦片管理</h2>
        <p class="description">管理离线地图瓦片缓存</p>
      </div>
    </el-card>

    <!-- 瓦片状态 -->
    <el-card class="tile-status">
      <h3 class="section-title">瓦片状态</h3>
      <el-descriptions :column="3" border>
        <el-descriptions-item label="总瓦片数">
          {{ coverage.total_tiles }}
        </el-descriptions-item>
        <el-descriptions-item label="占用空间">
          {{ coverage.total_size_mb }} MB
        </el-descriptions-item>
        <el-descriptions-item label="缩放级别">
          {{ Object.keys(coverage.zoom_levels).length }}
        </el-descriptions-item>
      </el-descriptions>

      <div v-if="Object.keys(coverage.zoom_levels).length > 0" class="zoom-levels">
        <h4>各级别瓦片数量</h4>
        <el-table :data="zoomLevelData" style="width: 100%">
          <el-table-column prop="level" label="缩放级别" width="120" />
          <el-table-column prop="count" label="瓦片数量" />
          <el-table-column label="操作" width="150">
            <template #default="{ row }">
              <el-button type="danger" size="small" @click="handleClearLevel(row.level)">
                清理
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div class="actions">
        <el-button type="primary" @click="loadStatus">刷新状态</el-button>
        <el-button type="danger" @click="handleClearAll">清理所有瓦片</el-button>
      </div>
    </el-card>

    <!-- 下载瓦片 -->
    <el-card class="tile-download">
      <h3 class="section-title">下载瓦片</h3>
      <el-alert title="注意" type="warning" :closable="false" style="margin-bottom: 20px">
        下载瓦片需要网络连接,大范围下载可能需要较长时间
      </el-alert>

      <el-form :model="downloadForm" label-width="120px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="最小纬度">
              <el-input-number
                v-model="downloadForm.min_lat"
                :min="-90"
                :max="90"
                :precision="4"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="最大纬度">
              <el-input-number
                v-model="downloadForm.max_lat"
                :min="-90"
                :max="90"
                :precision="4"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="最小经度">
              <el-input-number
                v-model="downloadForm.min_lon"
                :min="-180"
                :max="180"
                :precision="4"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="最大经度">
              <el-input-number
                v-model="downloadForm.max_lon"
                :min="-180"
                :max="180"
                :precision="4"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="最小缩放">
              <el-input-number
                v-model="downloadForm.min_zoom"
                :min="0"
                :max="18"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="最大缩放">
              <el-input-number
                v-model="downloadForm.max_zoom"
                :min="0"
                :max="18"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item>
          <el-button type="primary" :loading="downloading" @click="handleDownload">
            开始下载
          </el-button>
          <el-button @click="usePresetRegion('guizhou')"> 使用贵州省预设 </el-button>
          <el-button @click="usePresetRegion('bijie')"> 使用毕节市预设 </el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getMapStatus, downloadTiles, clearTiles } from '@/api/offlineMap'

interface MapCoverage {
  total_tiles: number
  total_size_mb: number
  zoom_levels: Record<string, number>
}

const coverage = ref<MapCoverage>({
  total_tiles: 0,
  total_size_mb: 0,
  zoom_levels: {},
})

const downloadForm = ref({
  min_lat: 24.5,
  max_lat: 29.2,
  min_lon: 103.6,
  max_lon: 109.5,
  min_zoom: 4,
  max_zoom: 12,
})

const downloading = ref(false)

const zoomLevelData = computed(() => {
  return Object.entries(coverage.value.zoom_levels)
    .map(([level, count]) => ({
      level: parseInt(level),
      count,
    }))
    .sort((a, b) => a.level - b.level)
})

const loadStatus = async () => {
  try {
    const response = await getMapStatus()
    if (response.success) {
      /* c8 ignore next */ // 防御性代码：success=true 时后端必带 data；缺 data 模板 Object.keys(zoom_levels) 会抛错
      coverage.value = response.data || {}
    }
  } catch (error: any) {
    ElMessage.error(error.message || '加载状态失败')
  }
}

const handleDownload = async () => {
  try {
    await ElMessageBox.confirm('下载瓦片可能需要较长时间,确定要继续吗?', '确认下载', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })

    downloading.value = true
    const response = await downloadTiles(downloadForm.value)

    if (response.success) {
      ElMessage.success(
        `下载完成! 成功 ${response.data.downloaded} 个, 失败 ${response.data.failed} 个`
      )
      await loadStatus()
    }
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '下载失败')
    }
  } finally {
    downloading.value = false
  }
}

const handleClearLevel = async (level: number) => {
  try {
    await ElMessageBox.confirm(`确定要清理缩放级别 ${level} 的所有瓦片吗?`, '确认清理', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })

    const response = await clearTiles()
    if (response.success) {
      ElMessage.success(`已清理 ${response.data.deleted_count} 个瓦片`)
      await loadStatus()
    }
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '清理失败')
    }
  }
}

const handleClearAll = async () => {
  try {
    await ElMessageBox.confirm('确定要清理所有瓦片吗?', '确认清理', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })

    const response = await clearTiles()
    if (response.success) {
      ElMessage.success(`已清理 ${response.data.deleted_count} 个瓦片`)
      await loadStatus()
    }
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '清理失败')
    }
  }
}

const usePresetRegion = (region: string) => {
  if (region === 'guizhou') {
    // 贵州省
    downloadForm.value = {
      min_lat: 24.5,
      max_lat: 29.2,
      min_lon: 103.6,
      max_lon: 109.5,
      min_zoom: 4,
      max_zoom: 8,
    }
  } else if (region === 'bijie') {
    // 毕节市
    downloadForm.value = {
      min_lat: 26.5,
      max_lat: 27.9,
      min_lon: 105.3,
      max_lon: 106.8,
      min_zoom: 9,
      max_zoom: 12,
    }
  }
}

onMounted(() => {
  loadStatus()
})
</script>

<style scoped lang="scss">
.map-tile-manager {
  padding: 20px;
}

.page-header {
  margin-bottom: 20px;

  .header-content {
    h2 {
      margin: 0 0 8px 0;
      font-size: 24px;
      color: #303133;
    }

    .description {
      margin: 0;
      color: var(--color-info);
      font-size: 14px;
    }
  }
}

.tile-status,
.tile-download {
  margin-bottom: 20px;
}

.section-title {
  margin: 0 0 20px 0;
  font-size: 18px;
  color: #303133;
  border-bottom: 2px solid var(--color-primary);
  padding-bottom: 10px;
}

.zoom-levels {
  margin-top: 20px;

  h4 {
    margin: 0 0 10px 0;
    font-size: 16px;
    color: #303133;
  }
}

.actions {
  margin-top: 20px;
  display: flex;
  gap: 10px;
}
</style>
