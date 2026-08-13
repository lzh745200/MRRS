<template>
  <div class="export-section">
    <el-row :gutter="20">
      <!-- 左侧：导出配置 -->
      <el-col :span="14">
        <el-card class="export-card">
          <template #header>
            <span>导出配置</span>
          </template>

          <el-form :model="exportForm" label-width="100px">
            <!-- 数据类型 -->
            <el-form-item label="数据类型">
              <el-select
                v-model="exportForm.dataType"
                placeholder="选择数据类型"
                style="width: 100%"
              >
                <el-option label="帮扶村数据" value="villages" />
                <el-option label="年度统计数据" value="yearly_stats" />
                <el-option label="经费投入数据" value="funding" />
                <el-option label="产业帮扶数据" value="industry" />
              </el-select>
            </el-form-item>

            <!-- 导出格式 -->
            <el-form-item label="导出格式">
              <el-radio-group v-model="exportForm.format">
                <el-radio value="xlsx">Excel (.xlsx)</el-radio>
                <el-radio value="csv">CSV (.csv)</el-radio>
              </el-radio-group>
            </el-form-item>

            <!-- 筛选条件 -->
            <el-divider content-position="left">筛选条件（可选）</el-divider>

            <el-form-item label="部门">
              <el-input
                v-model="exportForm.filters.department"
                placeholder="输入部门名称"
                clearable
              />
            </el-form-item>

            <el-form-item label="帮扶单位">
              <el-input
                v-model="exportForm.filters.support_unit"
                placeholder="输入帮扶单位"
                clearable
              />
            </el-form-item>

            <el-form-item label="地区范围">
              <el-select
                v-model="exportForm.filters.region_scope"
                placeholder="选择地区"
                clearable
                style="width: 100%"
              >
                <el-option label="都匀市" value="都匀市" />
                <el-option label="长顺县" value="长顺县" />
                <el-option label="独山县" value="独山县" />
                <el-option label="平塘县" value="平塘县" />
                <el-option label="罗甸县" value="罗甸县" />
                <el-option label="惠水县" value="惠水县" />
                <el-option label="贵定县" value="贵定县" />
                <el-option label="福泉市" value="福泉市" />
                <el-option label="瓮安县" value="瓮安县" />
                <el-option label="三都县" value="三都县" />
                <el-option label="荔波县" value="荔波县" />
                <el-option label="龙里县" value="龙里县" />
              </el-select>
            </el-form-item>

            <el-form-item label="振兴梯队">
              <el-switch v-model="exportForm.filters.is_revitalization_tier" />
            </el-form-item>

            <el-form-item>
              <el-button type="primary" :loading="exporting" @click="handleExport">
                <el-icon><Download /></el-icon>
                开始导出
              </el-button>
              <el-button @click="resetForm">重置</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <!-- 右侧：导出历史 -->
      <el-col :span="10">
        <el-card class="history-card">
          <template #header>
            <div class="card-header">
              <span>导出历史</span>
              <el-button link @click="loadHistory">
                <el-icon><Refresh /></el-icon>
              </el-button>
            </div>
          </template>

          <el-table v-loading="loadingHistory" :data="historyList" max-height="500">
            <el-table-column prop="export_type" label="类型" width="100" />
            <el-table-column label="状态" width="80">
              <template #default="{ row }">
                <el-tag :type="formatExportStatus(row.status).type" size="small">
                  {{ formatExportStatus(row.status).text }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="大小" width="80">
              <template #default="{ row }">
                {{ row.file_size ? formatFileSize(row.file_size) : '-' }}
              </template>
            </el-table-column>
            <el-table-column label="时间" width="100">
              <template #default="{ row }">
                {{ formatTime(row.created_at) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="80">
              <template #default="{ row }">
                <el-button
                  v-if="row.is_downloadable"
                  type="primary"
                  link
                  size="small"
                  @click="handleDownload(row)"
                >
                  下载
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { logger } from '@/utils/logger'

import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Download, Refresh } from '@element-plus/icons-vue'
import {
  exportVillages,
  exportFunds,
  getExportTasks,
  downloadExportFile,
  formatExportStatus as _formatExportStatus,
  formatFileSize,
  type ExportFilterParams,
} from '@/api/export'

// Wrap to return any for template compatibility (template accesses .type and .text)
const formatExportStatus = (status: string): any => _formatExportStatus(status)

const emit = defineEmits<{
  (e: 'export-complete'): void
}>()

// 表单数据
const exportForm = reactive({
  dataType: 'villages',
  format: 'xlsx',
  filters: {
    department: '',
    support_unit: '',
    region_scope: '',
    is_revitalization_tier: false,
  },
})

// 状态
const exporting = ref(false)
const loadingHistory = ref(false)
const historyList = ref<any[]>([])

// 加载导出历史
async function loadHistory() {
  loadingHistory.value = true
  try {
    const res = await getExportTasks({ page: 1, page_size: 10 })
    historyList.value = (res as any)?.data?.items || (res as any)?.items || []
  } catch (error) {
    logger.error('加载导出历史失败:', error)
  } finally {
    loadingHistory.value = false
  }
}

// 执行导出（按数据类型分派到对应导出接口）
async function handleExport() {
  exporting.value = true
  try {
    // 构建筛选参数
    const filters: ExportFilterParams = {
      type: exportForm.dataType,
      format: exportForm.format,
    }
    if (exportForm.filters.department) filters.department = exportForm.filters.department
    if (exportForm.filters.support_unit) filters.support_unit = exportForm.filters.support_unit
    if (exportForm.filters.region_scope) filters.region_scope = exportForm.filters.region_scope
    if (exportForm.filters.is_revitalization_tier)
      filters.is_revitalization_tier = exportForm.filters.is_revitalization_tier

    switch (exportForm.dataType) {
      case 'funding':
        await exportFunds(filters)
        break
      case 'yearly_stats':
        await exportVillages({ ...filters, type: 'yearly_stats' })
        break
      case 'industry':
        await exportVillages({ ...filters, type: 'industry' })
        break
      default:
        await exportVillages(filters)
    }

    // 导出函数已通过 downloadBlobAsFile 触发浏览器下载
    ElMessage.success('导出成功')

    emit('export-complete')
    loadHistory()
  } catch (error) {
    ElMessage.error('导出失败')
  } finally {
    exporting.value = false
  }
}

// 下载文件
async function handleDownload(task: any) {
  try {
    await downloadExportFile(task.task_id)
    ElMessage.success('下载成功')
  } catch (error) {
    ElMessage.error('下载失败')
  }
}

// 重置表单
function resetForm() {
  exportForm.dataType = 'villages'
  exportForm.format = 'xlsx'
  exportForm.filters = {
    department: '',
    support_unit: '',
    region_scope: '',
    is_revitalization_tier: false,
  }
}

// 格式化时间
function formatTime(dateStr: string): string {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return `${date.getMonth() + 1}/${date.getDate()} ${date.getHours()}:${String(date.getMinutes()).padStart(2, '0')}`
}

onMounted(() => {
  loadHistory()
})
</script>

<style scoped lang="scss">
.export-section {
  .export-card,
  .history-card {
    height: 100%;
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
}
</style>
