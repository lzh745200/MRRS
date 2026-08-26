<template>
  <div class="cache-page">
    <el-row :gutter="20" class="stats-row">
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="缓存键数" :value="stats.item_count ?? 0" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="命中次数" :value="stats.hits ?? 0" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="未命中次数" :value="stats.misses ?? 0" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="命中率(%)" :value="hitRateNum" />
        </el-card>
      </el-col>
    </el-row>

    <el-card>
      <template #header>
        <div class="card-header">
          <span class="title">缓存管理</span>
          <div>
            <el-button :loading="loading" @click="refreshData">刷新</el-button>
            <el-button type="danger" :loading="clearing" @click="clearAllCache">
              清除全部缓存
            </el-button>
          </div>
        </div>
      </template>

      <el-descriptions :column="2" border>
        <el-descriptions-item label="缓存后端">
          {{ stats.backend_type || 'memory' }}
        </el-descriptions-item>
        <el-descriptions-item label="最大容量">
          {{ stats.max_size ?? '-' }} 项
        </el-descriptions-item>
        <el-descriptions-item label="当前键数">
          {{ stats.item_count ?? 0 }}
        </el-descriptions-item>
        <el-descriptions-item label="命中率"> {{ hitRateNum }}% </el-descriptions-item>
        <el-descriptions-item label="总请求数">
          {{ stats.total_requests ?? 0 }}
        </el-descriptions-item>
        <el-descriptions-item label="估算内存">
          {{ formatSize(stats.estimated_size_bytes ?? 0) }}
        </el-descriptions-item>
      </el-descriptions>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { get, post } from '@/api/request'

const loading = ref(false)
const clearing = ref(false)
const stats = ref<Record<string, any>>({
  item_count: 0,
  hits: 0,
  misses: 0,
  total_requests: 0,
  max_size: 0,
  backend_type: 'memory',
  estimated_size_bytes: 0,
})

const hitRate = computed(() => {
  const total = (stats.value.hits || 0) + (stats.value.misses || 0)
  if (total === 0) return 0
  return (stats.value.hits / total) * 100
})

const hitRateNum = computed(() => {
  return parseFloat(hitRate.value.toFixed(1))
})

function formatSize(bytes: number) {
  if (!bytes || bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i]
}

async function refreshData() {
  loading.value = true
  try {
    const res = await get('/system/cache/stats')
    // get() 已自动解包，res 即响应体 { success, data, ...expanded_fields }
    if (res?.success !== false) {
      stats.value = res?.data || res || {}
    }
  } catch {
    ElMessage.error('加载缓存信息失败')
  } finally {
    loading.value = false
  }
}

async function clearAllCache() {
  try {
    await ElMessageBox.confirm('确定清除全部缓存吗？', '警告', {
      type: 'warning',
    })
    clearing.value = true
    const res = await post('/system/cache/clear')
    // post() 已自动解包，res 即响应体 { success, message, data }
    if (res?.success !== false) {
      ElMessage.success(res?.message || '缓存已清除')
    }
    await refreshData()
  } catch (e: any) {
    if (e !== 'cancel') ElMessage.error('清除失败')
  } finally {
    clearing.value = false
  }
}

onMounted(() => refreshData())
</script>

<style lang="scss" scoped>
.cache-page {
  padding: 20px;
}
.stats-row {
  margin-bottom: 20px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.title {
  font-size: 16px;
  font-weight: 600;
}
</style>
