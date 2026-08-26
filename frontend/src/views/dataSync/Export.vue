<template>
  <div class="data-sync-export">
    <el-card class="page-header">
      <div class="header-content">
        <h2>数据导出</h2>
        <p class="description">导出数据包用于多台电脑间的数据同步和备份</p>
      </div>
    </el-card>

    <!-- 导出配置 -->
    <el-card class="export-config">
      <h3 class="section-title">导出配置</h3>
      <el-form :model="exportForm" label-width="120px">
        <el-form-item label="导出类型">
          <el-radio-group v-model="exportForm.exportType">
            <el-radio value="full">完整导出</el-radio>
            <el-radio value="selective">选择性导出</el-radio>
            <el-radio value="incremental">增量导出（旧版）</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item v-if="exportForm.exportType === 'incremental'" label="起始时间">
          <el-date-picker
            v-model="exportForm.since"
            type="datetime"
            placeholder="选择起始时间"
            style="width: 100%"
            :clearable="true"
          />
          <div class="form-tip">留空则导出所有数据</div>
        </el-form-item>

        <el-form-item v-if="exportForm.exportType !== 'full'" label="导出模块">
          <el-checkbox-group v-model="exportForm.modules">
            <el-checkbox value="supported_villages">帮扶村</el-checkbox>
            <el-checkbox value="village_populations">人口数据</el-checkbox>
            <el-checkbox value="village_incomes">收入数据</el-checkbox>
            <el-checkbox value="organizations">组织</el-checkbox>
            <el-checkbox value="policies">政策</el-checkbox>
            <el-checkbox value="force_investments">专项投入</el-checkbox>
            <el-checkbox value="industry_supports">产业帮扶</el-checkbox>
            <el-checkbox value="infrastructure_improvements">基础设施</el-checkbox>
            <el-checkbox value="party_building_supports">党建帮扶</el-checkbox>
            <el-checkbox value="medical_supports">医疗帮扶</el-checkbox>
            <el-checkbox value="consumption_supports">消费帮扶</el-checkbox>
            <el-checkbox value="employment_supports">就业帮扶</el-checkbox>
            <el-checkbox value="education_supports">教育帮扶</el-checkbox>
          </el-checkbox-group>
          <div class="form-tip">
            <el-button type="text" size="small" @click="selectAllModules">全选</el-button>
            <el-button type="text" size="small" @click="clearModules">清空</el-button>
          </div>
        </el-form-item>

        <el-form-item v-if="exportForm.exportType === 'incremental'" label="包含上传文件">
          <el-switch v-model="exportForm.includeFiles" />
          <div class="form-tip">包含上传的图片、文档等文件(会增加数据包大小)</div>
        </el-form-item>

        <el-form-item label="加密保护">
          <el-switch v-model="exportForm.encrypted" />
          <div class="form-tip">启用加密后，导出的数据包将使用密码保护（推荐）</div>
        </el-form-item>

        <el-form-item v-if="exportForm.encrypted" label="加密密码" required>
          <el-input
            v-model="exportForm.password"
            type="password"
            placeholder="至少 8 位"
            show-password
          />
        </el-form-item>

        <el-form-item v-if="exportForm.encrypted" label="确认密码" required>
          <el-input
            v-model="exportForm.confirmPassword"
            type="password"
            placeholder="再次输入密码"
            show-password
          />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="exporting" @click="handleExport">
            开始导出
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 导出结果 -->
    <el-card v-if="exportResult" class="export-result">
      <h3 class="section-title">导出结果</h3>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="数据包名称">
          {{ exportResult.package_name }}
        </el-descriptions-item>
        <el-descriptions-item label="记录数">
          {{ exportResult.total_records ?? 0 }}
        </el-descriptions-item>
        <el-descriptions-item label="导出时间">
          {{ exportResult.exported_at ? formatDate(exportResult.exported_at) : '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="数据包大小">
          {{ formatSize(exportResult.size || 0) }}
        </el-descriptions-item>
      </el-descriptions>
      <div class="result-actions">
        <el-button
          type="primary"
          :loading="downloading"
          @click="handleDownloadByName(exportResult.package_name)"
        >
          <el-icon style="margin-right: 4px"><Download /></el-icon>重新下载数据包
        </el-button>
      </div>
    </el-card>

    <!-- 导出历史 -->
    <el-card class="export-history">
      <h3 class="section-title">导出历史</h3>
      <el-table v-loading="loadingHistory" :data="exportHistory" style="width: 100%">
        <template #empty>
          <EmptyState text="暂无导出记录" />
        </template>
        <el-table-column prop="package_name" label="数据包名称" />
        <el-table-column prop="total_records" label="记录数" width="100" />
        <el-table-column label="大小" width="120">
          <template #default="{ row }">
            {{ formatSize(row.size) }}
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="导出时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column prop="user_name" label="操作人" width="120" />
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" size="small" @click="handleDownload(row)"> 下载 </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import EmptyState from '@/components/business/EmptyState/EmptyState.vue'
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Download } from '@element-plus/icons-vue'
import { logger } from '@/utils/logger'
import {
  exportData,
  exportEncryptedData,
  downloadExportPackage,
  getSyncLogs,
  type ExportEncryptedParams,
} from '@/api/dataSync'

const exportForm = ref({
  exportType: 'full' as 'full' | 'selective' | 'incremental',
  since: null as Date | null,
  modules: [] as string[],
  includeFiles: false,
  encrypted: true,
  password: '',
  confirmPassword: '',
})

const exporting = ref(false)
const downloading = ref(false)
const loadingHistory = ref(false)
const exportHistory = ref<any[]>([])
const exportResult = ref<{
  package_name: string
  total_records?: number
  exported_at?: string
  size?: number
} | null>(null)

const allModules = [
  'supported_villages',
  'village_populations',
  'village_incomes',
  'organizations',
  'policies',
  'force_investments',
  'industry_supports',
  'infrastructure_improvements',
  'party_building_supports',
  'medical_supports',
  'consumption_supports',
  'employment_supports',
  'education_supports',
]

const selectAllModules = () => {
  exportForm.value.modules = [...allModules]
}

const clearModules = () => {
  exportForm.value.modules = []
}

const handleExport = async () => {
  // 验证
  if (exportForm.value.exportType !== 'full' && exportForm.value.modules.length === 0) {
    ElMessage.warning('请至少选择一个导出模块')
    return
  }

  if (exportForm.value.encrypted) {
    if (!exportForm.value.password) {
      ElMessage.warning('请输入加密密码')
      return
    }
    if (exportForm.value.password.length < 8) {
      ElMessage.warning('密码长度至少为 8 位')
      return
    }
    if (exportForm.value.password !== exportForm.value.confirmPassword) {
      ElMessage.warning('两次输入的密码不一致')
      return
    }
  }

  exporting.value = true
  try {
    let response

    if (exportForm.value.encrypted) {
      // 加密导出
      const params: ExportEncryptedParams = {
        export_type: (exportForm.value.exportType === 'full' ? 'full' : 'selective') as
          | 'full'
          | 'selective',
        modules: exportForm.value.exportType === 'full' ? undefined : exportForm.value.modules,
        password: exportForm.value.password,
        since: exportForm.value.since?.toISOString() ?? undefined,
      }
      response = await exportEncryptedData(params)
    } else {
      // 旧版增量导出（无加密）
      const params = {
        since: exportForm.value.since?.toISOString(),
        modules: exportForm.value.modules,
        include_files: exportForm.value.includeFiles,
      }
      response = await exportData(params)
    }

    // post() 已自动解包，后端裸返回 {success, package_name, total_records, ...}
    const result = response?.data ?? response
    if (result?.success) {
      exportResult.value = {
        package_name: result.package_name,
        total_records: result.total_records ?? 0,
        exported_at: result.exported_at,
        size: result.size ?? 0,
      }
      ElMessage.success(`导出成功! 共 ${exportResult.value.total_records} 条记录`)
      // 自动下载
      if (result.package_name) {
        await handleDownloadByName(result.package_name)
      }
      // 刷新历史
      await loadExportHistory()
      // 清空密码
      exportForm.value.password = ''
      exportForm.value.confirmPassword = ''
    } else if (result?.message) {
      ElMessage.warning(result.message)
    }
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || error.message || '导出失败')
  } finally {
    exporting.value = false
  }
}

const handleDownload = async (row: any) => {
  await handleDownloadByName(row.package_name)
}

const handleDownloadByName = async (packageName: string) => {
  downloading.value = true
  try {
    await downloadExportPackage(packageName)
  } catch (error: any) {
    ElMessage.error(error.message || '下载失败')
  } finally {
    downloading.value = false
  }
}

const loadExportHistory = async () => {
  loadingHistory.value = true
  try {
    const response: any = await getSyncLogs({ action: 'export', page: 1, page_size: 20 })
    // 兼容信封 items / 裸数组
    const list = Array.isArray(response) ? response : response?.items || response?.data?.items || []
    exportHistory.value = Array.isArray(list) ? list : []
  } catch (error) {
    logger.error('加载导出历史失败', error)
  } finally {
    loadingHistory.value = false
  }
}

const formatSize = (bytes: number) => {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(2) + ' MB'
}

const formatDate = (dateStr: string) => {
  return new Date(dateStr).toLocaleString('zh-CN')
}

onMounted(() => {
  loadExportHistory()
  // 默认选择所有模块
  selectAllModules()
})
</script>

<style scoped lang="scss">
.data-sync-export {
  padding: 20px;
}

.page-header {
  margin-bottom: 20px;

  .header-content {
    h2 {
      margin: 0 0 8px 0;
      font-size: 24px;
      color: var(--color-text-primary);
    }

    .description {
      margin: 0;
      color: var(--color-info);
      font-size: 14px;
    }
  }
}

.export-config,
.export-history,
.export-result {
  margin-bottom: 20px;
}

.result-actions {
  margin-top: 16px;
  display: flex;
  gap: 8px;
}

.section-title {
  margin: 0 0 20px 0;
  font-size: 18px;
  color: var(--color-text-primary);
  border-bottom: 2px solid var(--color-primary);
  padding-bottom: 10px;
}

.form-tip {
  margin-top: 5px;
  font-size: 12px;
  color: var(--color-info);
}
</style>
