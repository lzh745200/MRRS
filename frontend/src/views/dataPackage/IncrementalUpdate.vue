<template>
  <div class="incremental-update">
    <el-alert
      title="该功能正在开发中"
      description="增量更新功能的后端接口尚未实现，当前页面操作暂不可用。如有紧急需求请联系开发团队。"
      type="warning"
      :closable="false"
      show-icon
      style="margin-bottom: 16px"
    />
    <el-card>
      <template #header>
        <div class="card-header">
          <span>增量更新管理</span>
        </div>
      </template>

      <el-tabs v-model="activeTab">
        <!-- 导出增量包 -->
        <el-tab-pane label="导出增量包" name="export">
          <el-form :model="exportForm" label-width="120px">
            <el-form-item label="基础数据包">
              <el-select
                v-model="exportForm.base_package_id"
                placeholder="选择基础数据包"
                style="width: 100%"
              >
                <el-option
                  v-for="pkg in packageList"
                  :key="pkg.id"
                  :label="`${pkg.package_code} - ${pkg.description || '无描述'}`"
                  :value="pkg.id"
                />
              </el-select>
            </el-form-item>

            <el-form-item label="数据类型">
              <el-checkbox-group v-model="exportForm.data_types">
                <el-checkbox :value="DATA_TYPES.VILLAGES">{{
                  DATA_TYPE_LABELS[DATA_TYPES.VILLAGES]
                }}</el-checkbox>
                <el-checkbox :value="DATA_TYPES.PROJECTS">{{
                  DATA_TYPE_LABELS[DATA_TYPES.PROJECTS]
                }}</el-checkbox>
                <el-checkbox :value="DATA_TYPES.FUNDS">{{
                  DATA_TYPE_LABELS[DATA_TYPES.FUNDS]
                }}</el-checkbox>
                <el-checkbox :value="DATA_TYPES.SCHOOLS">{{
                  DATA_TYPE_LABELS[DATA_TYPES.SCHOOLS]
                }}</el-checkbox>
              </el-checkbox-group>
            </el-form-item>

            <el-form-item label="描述">
              <el-input
                v-model="exportForm.description"
                type="textarea"
                :rows="3"
                placeholder="请输入增量包描述"
              />
            </el-form-item>

            <el-form-item>
              <el-button type="primary" disabled @click="handleDetectChanges"> 检测变更 </el-button>
              <el-button type="success" disabled @click="handleExport"> 导出增量包 </el-button>
            </el-form-item>
          </el-form>

          <!-- 变更摘要 -->
          <el-card v-if="changesSummary" style="margin-top: 20px">
            <template #header>
              <span>变更摘要</span>
            </template>

            <el-descriptions :column="3" border>
              <el-descriptions-item label="新增记录">
                <el-tag type="success">{{ changesSummary.total_added }}</el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="修改记录">
                <el-tag type="warning">{{ changesSummary.total_modified }}</el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="删除记录">
                <el-tag type="danger">{{ changesSummary.total_deleted }}</el-tag>
              </el-descriptions-item>
            </el-descriptions>

            <el-divider>按数据类型统计</el-divider>

            <el-table :data="changesByType" style="width: 100%">
              <el-table-column prop="type" label="数据类型" />
              <el-table-column prop="added" label="新增" />
              <el-table-column prop="modified" label="修改" />
              <el-table-column prop="deleted" label="删除" />
              <el-table-column prop="total" label="总计" />
            </el-table>
          </el-card>
        </el-tab-pane>

        <!-- 导入增量包 -->
        <el-tab-pane label="导入增量包" name="import">
          <el-form :model="importForm" label-width="120px">
            <el-form-item label="增量数据包">
              <el-select
                v-model="importForm.package_id"
                placeholder="选择增量数据包"
                style="width: 100%"
                @change="handlePackageChange"
              >
                <el-option
                  v-for="pkg in incrementalPackages"
                  :key="pkg.id"
                  :label="`${pkg.package_code} - ${pkg.description || '无描述'}`"
                  :value="pkg.id"
                />
              </el-select>
            </el-form-item>

            <el-form-item label="应用变更">
              <el-switch v-model="importForm.apply_changes" />
              <span style="margin-left: 10px; color: var(--color-text-placeholder)">
                关闭时仅预览，不实际导入
              </span>
            </el-form-item>

            <el-form-item>
              <el-button type="primary" disabled @click="handleImport">
                {{ importForm.apply_changes ? '导入增量包' : '预览变更' }}
              </el-button>
            </el-form-item>
          </el-form>

          <!-- 导入结果 -->
          <el-card v-if="importResult" style="margin-top: 20px">
            <template #header>
              <span>{{ importResult.preview_only ? '预览结果' : '导入结果' }}</span>
            </template>

            <el-alert
              v-if="importResult.preview_only"
              title="这是预览模式，数据未实际导入"
              type="info"
              :closable="false"
              style="margin-bottom: 20px"
            />

            <el-descriptions v-if="importResult.stats" :column="3" border>
              <el-descriptions-item label="新增">
                {{ importResult.stats.added }}
              </el-descriptions-item>
              <el-descriptions-item label="修改">
                {{ importResult.stats.modified }}
              </el-descriptions-item>
              <el-descriptions-item label="删除">
                {{ importResult.stats.deleted }}
              </el-descriptions-item>
            </el-descriptions>

            <el-descriptions v-if="importResult.summary" :column="3" border>
              <el-descriptions-item label="新增">
                {{ importResult.summary.total_added }}
              </el-descriptions-item>
              <el-descriptions-item label="修改">
                {{ importResult.summary.total_modified }}
              </el-descriptions-item>
              <el-descriptions-item label="删除">
                {{ importResult.summary.total_deleted }}
              </el-descriptions-item>
            </el-descriptions>
          </el-card>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { get, post } from '@/api/request'
import { DATA_TYPES, DATA_TYPE_LABELS } from '@/constants/dataTypes'
import { handleApiError } from '@/utils/errorHandler'
import { AuthStorage } from '@/utils/authStorage'

interface PackageItem {
  id: number | string
  package_code: string
  description: string
  type: string
}

interface ChangesSummary {
  total_added: number
  total_modified: number
  total_deleted: number
  by_type: Record<string, { added: number; modified: number; deleted: number; total: number }>
}

interface ImportResult {
  preview_only: boolean
  stats?: { added: number; modified: number; deleted: number }
  summary?: {
    total_added: number
    total_modified: number
    total_deleted: number
  }
}

const activeTab = ref('export')
const packageList = ref<PackageItem[]>([])
const incrementalPackages = ref<PackageItem[]>([])
const changesSummary = ref<ChangesSummary | null>(null)
const importResult = ref<ImportResult | null>(null)

const exportForm = ref({
  base_package_id: null,
  data_types: [DATA_TYPES.VILLAGES, DATA_TYPES.PROJECTS, DATA_TYPES.FUNDS, DATA_TYPES.SCHOOLS],
  description: '',
})

const importForm = ref({
  package_id: null,
  apply_changes: false,
})

// 获取数据包列表
const fetchPackageList = async () => {
  try {
    const response: any = await get('/data-packages')
    // 后端裸返回 {items, total, ...}（拦截器已解包）
    const items =
      response?.items || response?.data?.items || (Array.isArray(response) ? response : [])
    packageList.value = items.filter((p: PackageItem) => p.type !== 'update')
    incrementalPackages.value = items.filter((p: PackageItem) => p.type === 'update')
  } catch {
    ElMessage.error('获取数据包列表失败')
  }
}

// 检测变更
const handleDetectChanges = async () => {
  if (!exportForm.value.base_package_id) {
    ElMessage.warning('请选择基础数据包')
    return
  }

  if (exportForm.value.data_types.length === 0) {
    ElMessage.warning('请选择数据类型')
    return
  }

  try {
    const response: any = await post('/data-packages/incremental/detect-changes', null, {
      params: {
        org_id: null, // 使用当前用户组织
        data_types: exportForm.value.data_types,
        base_package_id: exportForm.value.base_package_id,
      },
    })

    const result = response?.data ?? response
    if (result && (result.summary || result.changes)) {
      changesSummary.value = result.summary ?? result
      ElMessage.success('变更检测完成')
    } else {
      ElMessage.info('未检测到变更')
    }
  } catch (error: unknown) {
    handleApiError(error, '检测变更失败')
  }
}

// 导出增量包
const handleExport = async () => {
  try {
    const response: any = await post('/data-packages/incremental/export', {
      org_id: null,
      data_types: exportForm.value.data_types,
      base_package_id: exportForm.value.base_package_id,
      description: exportForm.value.description || '增量更新包',
    })

    const result = response?.data ?? response
    if (result && (result.package_id || result.download_url)) {
      ElMessage.success('增量包导出成功')

      // 使用认证请求下载文件（兼容 Electron，避免 window.open 无 token 问题）
      const downloadUrl = result.download_url || result.url
      if (downloadUrl) {
        try {
          const token = AuthStorage.getToken()
          const dlResponse = await fetch(downloadUrl, {
            headers: { Authorization: `Bearer ${token}` },
          })
          if (!dlResponse.ok) throw new Error('Download failed')
          const blob = await dlResponse.blob()
          const blobUrl = URL.createObjectURL(blob)
          const link = document.createElement('a')
          link.href = blobUrl
          link.download = result.filename || '增量更新包.zip'
          link.click()
          setTimeout(() => URL.revokeObjectURL(blobUrl), 1000)
        } catch {
          ElMessage.error('下载增量包失败')
        }
      }

      // 刷新列表
      fetchPackageList()
      changesSummary.value = null
    } else if (result?.message) {
      ElMessage.warning(result.message)
    }
  } catch (error: unknown) {
    handleApiError(error, '导出失败')
  }
}

// 导入增量包
const handleImport = async () => {
  try {
    const response: any = await post('/data-packages/incremental/import', {
      package_id: importForm.value.package_id,
      apply_changes: importForm.value.apply_changes,
    })

    const result = response?.data ?? response
    if (
      result &&
      (result.success === true || result.package_id || result.total_records !== undefined)
    ) {
      importResult.value = result
      ElMessage.success(importForm.value.apply_changes ? '导入成功' : '预览完成')
    } else if (result?.message) {
      ElMessage.warning(result.message)
    }
  } catch (error: unknown) {
    handleApiError(error, '操作失败')
  }
}

// 数据包变更
const handlePackageChange = () => {
  importResult.value = null
}

// 获取按类型统计的变更
const changesByType = computed(() => {
  if (!changesSummary.value?.by_type) return []

  return Object.entries(changesSummary.value.by_type).map(([type, stats]) => ({
    type,
    added: stats.added,
    modified: stats.modified,
    deleted: stats.deleted,
    total: stats.total,
  }))
})

onMounted(() => {
  fetchPackageList()
})
</script>

<style lang="scss" scoped>
.incremental-update {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
