<template>
  <div class="env-check-page">
    <div class="page-header">
      <h2 class="page-title">运行环境诊断</h2>
      <p class="page-desc">检查系统运行环境，确保依赖完整性和系统健康</p>
    </div>

    <!-- 健康状态总览 -->
    <el-card class="health-card">
      <el-row :gutter="20" align="middle">
        <el-col :span="4">
          <div class="health-gauge" :class="healthClass">
            <span class="gauge-score">{{ healthScore }}</span>
            <span class="gauge-label">健康分</span>
          </div>
        </el-col>
        <el-col :span="20">
          <el-descriptions :column="3" border>
            <el-descriptions-item label="Python 版本">
              <el-tag type="primary" size="large">{{ systemInfo?.python_version || '-' }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="操作系统">
              {{ systemInfo?.platform || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="运行模式">
              <el-tag :type="envModeTagType" size="small">
                {{ systemInfo?.env_mode || '-' }}
              </el-tag>
            </el-descriptions-item>
          </el-descriptions>
        </el-col>
      </el-row>
    </el-card>

    <!-- 依赖状态 -->
    <el-card class="deps-card">
      <template #header>
        <div class="card-header">
          <span>依赖包状态</span>
          <div class="header-info">
            <el-tag type="success" size="small"> 已安装: {{ installedCount }} </el-tag>
            <el-tag
              v-if="missingPackages.length > 0"
              type="danger"
              size="small"
              style="margin-left: 8px"
            >
              缺失: {{ missingPackages.length }}
            </el-tag>
            <el-button
              type="primary"
              :icon="Refresh"
              :loading="checking"
              size="small"
              style="margin-left: 12px"
              @click="runCheck"
            >
              重新检查
            </el-button>
          </div>
        </div>
      </template>

      <el-input
        v-model="pkgFilter"
        placeholder="筛选依赖包..."
        clearable
        :prefix-icon="Search"
        style="width: 300px; margin-bottom: 16px"
      />

      <el-table v-loading="checking" :data="filteredDependencies" stripe max-height="500">
        <el-table-column prop="name" label="包名" min-width="200" sortable />
        <el-table-column label="状态" width="120" align="center">
          <template #default="{ row }">
            <el-icon v-if="row.installed" color="#67c23a" :size="20">
              <SuccessFilled />
            </el-icon>
            <el-icon v-else color="#f56c6c" :size="20">
              <CircleCloseFilled />
            </el-icon>
          </template>
        </el-table-column>
        <el-table-column label="安装状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.installed ? 'success' : 'danger'" size="small">
              {{ row.installed ? '已安装' : '缺失' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="version" label="版本" min-width="150">
          <template #default="{ row }">
            {{ row.version || '-' }}
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 缺失包警告 -->
    <el-card v-if="missingPackages.length > 0" class="warning-card">
      <template #header>
        <div class="card-header">
          <span style="color: #f56c6c">缺失依赖</span>
          <el-tag type="danger">{{ missingPackages.length }} 个包缺失</el-tag>
        </div>
      </template>
      <el-alert
        title="以下依赖包未安装，可能影响系统正常运行"
        type="error"
        :closable="false"
        show-icon
        style="margin-bottom: 12px"
      />
      <div class="missing-list">
        <el-tag v-for="pkg in missingPackages" :key="pkg" type="danger" class="missing-tag">
          {{ pkg }}
        </el-tag>
      </div>
      <div v-if="envData?.fix_command" class="fix-command">
        <p>修复命令：</p>
        <code>{{ envData.fix_command }}</code>
      </div>
    </el-card>

    <!-- 空状态 -->
    <el-empty
      v-if="!checking && !envData && !checkError"
      description="点击重新检查按钮开始环境诊断"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Search, SuccessFilled, CircleCloseFilled } from '@element-plus/icons-vue'
import { envApi } from '@/api/env'
import type { EnvCheckResult, SystemInfo } from '@/api/env'

const checking = ref(false)
const checkError = ref('')
const envData = ref<EnvCheckResult | null>(null)
const pkgFilter = ref('')

const systemInfo = ref<SystemInfo | null>(null)
const missingPackages = ref<string[]>([])

const installedCount = computed(() => {
  if (!envData.value?.packages) return 0
  return Object.keys(envData.value.packages).length - missingPackages.value.length
})

const healthScore = computed(() => {
  if (!envData.value) return '--'
  const total = Object.keys(envData.value.packages).length
  const missing = missingPackages.value.length
  if (total === 0) return 100
  return Math.round(((total - missing) / total) * 100)
})

const healthClass = computed(() => {
  const score = healthScore.value
  if (score === '--') return ''
  if (score >= 90) return 'healthy'
  if (score >= 70) return 'warning'
  return 'danger'
})

const envModeTagType = computed<'success' | 'warning' | 'info'>(() => {
  const mode = systemInfo.value?.env_mode || ''
  if (mode === 'production') return 'success'
  if (mode === 'development') return 'warning'
  return 'info'
})

const filteredDependencies = computed(() => {
  if (!envData.value?.packages) return []
  const entries = Object.entries(envData.value.packages).map(([name, version]) => ({
    name,
    version: version || '-',
    installed: !missingPackages.value.includes(name),
  }))
  if (!pkgFilter.value) return entries
  const kw = pkgFilter.value.toLowerCase()
  return entries.filter((e) => (e.name || '').toLowerCase().includes(kw))
})

async function runCheck() {
  checking.value = true
  checkError.value = ''
  envData.value = null
  try {
    const result = await envApi.check()
    envData.value = result
    systemInfo.value = result.system
    missingPackages.value = result.missing_packages || []
    if (missingPackages.value.length === 0) {
      ElMessage.success('环境检查通过，所有依赖已就绪')
    } else {
      ElMessage.warning(`发现 ${missingPackages.value.length} 个缺失依赖`)
    }
  } catch (err: any) {
    checkError.value = err?.message || '环境检查失败'
    ElMessage.error(checkError.value)
  } finally {
    checking.value = false
  }
}

onMounted(() => {
  runCheck()
})
</script>

<style scoped>
.env-check-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 20px;
}
.page-title {
  font-size: 20px;
  font-weight: 600;
  color: #1b4332;
  margin: 0 0 4px;
}
.page-desc {
  font-size: 14px;
  color: #666;
  margin: 0;
}
.health-gauge {
  width: 100px;
  height: 100px;
  border-radius: 50%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border: 4px solid #e0e0e0;
  margin: 0 auto;
}
.health-gauge.healthy {
  border-color: #67c23a;
  background: #f0f9eb;
}
.health-gauge.warning {
  border-color: #e6a23c;
  background: #fdf6ec;
}
.health-gauge.danger {
  border-color: #f56c6c;
  background: #fef0f0;
}
.gauge-score {
  font-size: 28px;
  font-weight: 700;
  color: #1b4332;
}
.gauge-label {
  font-size: 12px;
  color: #909399;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.header-info {
  display: flex;
  align-items: center;
}
.warning-card {
  border-left: 4px solid #f56c6c;
}
.missing-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}
.missing-tag {
  font-family: monospace;
}
.fix-command {
  background: #f5f7fa;
  padding: 12px;
  border-radius: 4px;
}
.fix-command p {
  margin: 0 0 8px;
  font-weight: 500;
}
.fix-command code {
  display: block;
  padding: 8px;
  background: #303133;
  color: #67c23a;
  border-radius: 4px;
  font-size: 13px;
  overflow-x: auto;
}
.deps-card {
  background: #ffffff;
}
.health-card {
  background: #ffffff;
}
</style>
