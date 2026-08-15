<template>
  <div class="data-management">
    <!-- 页面标题 -->
    <el-card class="header-card">
      <template #header>
        <div class="card-header">
          <span class="title">数据管理中心</span>
          <span class="subtitle">集中管理数据导入、导出和备份功能</span>
        </div>
      </template>

      <!-- 数据统计概览 -->
      <el-row :gutter="20">
        <el-col :span="6">
          <el-statistic title="帮扶村总数" :value="stats.villageCount" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="本月导入" :value="stats.monthlyImports" suffix="次" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="本月导出" :value="stats.monthlyExports" suffix="次" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="备份数量" :value="stats.backupCount" />
        </el-col>
      </el-row>
    </el-card>

    <!-- 功能模块选项卡 -->
    <el-tabs v-model="activeTab" type="border-card" class="main-tabs">
      <!-- 数据导入 -->
      <el-tab-pane label="数据导入" name="import">
        <ImportSection @import-complete="handleImportComplete" />
      </el-tab-pane>

      <!-- 数据导出 -->
      <el-tab-pane label="数据导出" name="export">
        <ExportSection @export-complete="handleExportComplete" />
      </el-tab-pane>

      <!-- 数据备份（已整合至系统管理 → 备份管理，此处跳转避免功能重复） -->
      <el-tab-pane label="数据备份" name="backup">
        <el-card shadow="never" class="redirect-card">
          <el-empty description="备份与恢复功能已整合至「系统管理 → 备份管理」">
            <el-button type="primary" @click="goBackupManagement">前往备份管理</el-button>
          </el-empty>
        </el-card>
      </el-tab-pane>

      <!-- 数据质量 -->
      <el-tab-pane label="数据质量" name="quality">
        <QualitySection :stats="qualityStats" />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { logger } from '@/utils/logger'
import { getErrorMessage } from '@/utils/getErrorMessage'

import { ref, onMounted, defineAsyncComponent } from 'vue'
import { ElMessage } from 'element-plus'
import { get, apiRequest } from '@/api/request'
import { useRouterSafe } from '@/composables/useRouterSafe'

const { pushSafe } = useRouterSafe()

// 异步加载子组件
const ImportSection = defineAsyncComponent(() => import('./components/ImportSection.vue'))
const ExportSection = defineAsyncComponent(() => import('./components/ExportSection.vue'))
const QualitySection = defineAsyncComponent(() => import('./components/QualitySection.vue'))

// 备份管理已整合至系统管理，跳转避免重复
function goBackupManagement() {
  pushSafe('/system/backup')
}

// 状态
const activeTab = ref('import')
const stats = ref({
  villageCount: 0,
  monthlyImports: 0,
  monthlyExports: 0,
  backupCount: 0,
})

const qualityStats = ref({
  totalRecords: 0,
  validRecords: 0,
  invalidRecords: 0,
  completenessRate: 0,
  lastCheckTime: '',
})
// 加载统计数据
async function loadStats() {
  try {
    // 帮扶村总数来自 /dashboard/stats 聚合统计
    const res = await get('/dashboard/stats')
    const data = res?.data ?? res ?? {}
    const villageCount = Number(data.total_villages ?? data.villageCount ?? 0) || 0

    // 本月导入/导出/备份数分别从各自真实端点统计（后端 /dashboard/stats 不返回这些字段）
    const now = new Date()
    const monthPrefix = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
    let monthlyImports = 0
    let monthlyExports = 0
    let backupCount = 0
    try {
      // 注意: /import/history 与 /audit/exports 的 page_size 上限为 100，
      // 传 200 会触发 422 导致统计恒为 0
      const hist: any = await get('/import/history', { page: 1, page_size: 100 })
      const items = hist?.items || hist?.data?.items || (Array.isArray(hist?.data) ? hist.data : [])
      monthlyImports = (Array.isArray(items) ? items : []).filter((r: any) =>
        String(r.createdAt || r.created_at || '').startsWith(monthPrefix)
      ).length
    } catch {
      /* 统计失败保持 0 */
    }
    try {
      const exp: any = await get('/audit/exports', { page: 1, page_size: 100 })
      const items = exp?.items || exp?.data?.items || (Array.isArray(exp?.data) ? exp.data : [])
      monthlyExports = (Array.isArray(items) ? items : []).filter((r: any) =>
        String(r.createdAt || r.created_at || '').startsWith(monthPrefix)
      ).length
    } catch {
      /* 统计失败保持 0 */
    }
    try {
      const bk: any = await get('/system/backup', { page: 1, page_size: 1000 })
      const items = bk?.items || bk?.data?.items || (Array.isArray(bk?.data) ? bk.data : [])
      backupCount = Array.isArray(items) ? items.length : Number(bk?.total ?? 0) || 0
    } catch {
      /* 统计失败保持 0 */
    }

    stats.value = {
      villageCount,
      monthlyImports,
      monthlyExports,
      backupCount,
    }
    // 加载帮扶村数据用于质量统计
    const villageRes = await apiRequest({
      method: 'GET',
      url: '/supported-villages',
      params: { page: 1, page_size: 200 },
    })
    const villages = villageRes.data?.items || []
    const totalRecords = villages.length
    const validRecords = villages.filter(
      (v: any) => v.department && v.village_name && v.county
    ).length
    qualityStats.value = {
      totalRecords,
      validRecords,
      invalidRecords: totalRecords - validRecords,
      completenessRate:
        totalRecords > 0 ? Math.round((validRecords / totalRecords) * 10000) / 100 : 0,
      lastCheckTime: new Date().toLocaleString('zh-CN'),
    }
  } catch (error) {
    logger.error('加载统计数据失败:', error)
    ElMessage.error(getErrorMessage(error, '加载统计数据失败，请稍后重试'))
  }
}

// 事件处理
function handleImportComplete() {
  loadStats()
  ElMessage.success('数据导入完成')
}

function handleExportComplete() {
  loadStats()
  ElMessage.success('数据导出完成')
}

onMounted(() => {
  loadStats()
})
</script>

<style scoped lang="scss">
.data-management {
  padding: 20px;
}

.header-card {
  margin-bottom: 20px;

  .card-header {
    .title {
      font-size: 20px;
      font-weight: 600;
      color: #1b4332;
    }

    .subtitle {
      margin-left: 12px;
      font-size: 14px;
      color: var(--color-info);
    }
  }
}

.main-tabs {
  :deep(.el-tabs__content) {
    padding: 20px;
    min-height: 500px;
  }
}
</style>
