<template>
  <div class="data-package-list">
    <el-card class="page-header">
      <div class="header-content">
        <h2>数据包管理</h2>
        <div class="header-actions">
          <el-button type="primary" @click="showExportDialog = true">
            <el-icon><Upload /></el-icon>
            导出数据
          </el-button>
          <el-button @click="showImportDialog = true">
            <el-icon><Download /></el-icon>
            导入数据
          </el-button>
          <el-button type="warning" @click="showEncryptedExportDialog = true">
            <el-icon><Lock /></el-icon>
            加密导出
          </el-button>
          <el-button type="warning" plain @click="showEncryptedImportDialog = true">
            <el-icon><Key /></el-icon>
            加密导入
          </el-button>
        </div>
      </div>
    </el-card>

    <!-- Filters -->
    <el-card class="filter-card">
      <el-form :inline="true" :model="filters">
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部状态" clearable style="width: 150px">
            <el-option label="待处理" value="pending" />
            <el-option label="已验证" value="validated" />
            <el-option label="已导入" value="imported" />
            <el-option label="失败" value="failed" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadPackages">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- Package List -->
    <el-card>
      <el-table v-loading="loading" :data="packages" stripe>
        <el-table-column prop="package_code" label="包编码" width="200" />
        <el-table-column prop="file_name" label="文件名" min-width="150" />
        <el-table-column prop="file_size" label="大小" width="100">
          <template #default="{ row }">
            {{ formatFileSize(row.file_size) }}
          </template>
        </el-table-column>
        <el-table-column prop="record_count" label="记录数" width="100" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">
              {{ getStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="handlePreview(row as DataPackage)">
              预览
            </el-button>
            <el-button
              v-if="row.status === 'validated'"
              link
              type="success"
              size="small"
              @click="handleConfirmImport(row as DataPackage)"
            >
              确认导入
            </el-button>
            <el-button link type="primary" size="small" @click="handleDownload(row as DataPackage)">
              下载
            </el-button>
            <el-button link type="danger" size="small" @click="handleDelete(row as DataPackage)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          @size-change="loadPackages"
          @current-change="loadPackages"
        />
      </div>
    </el-card>

    <!-- Export Dialog -->
    <ExportDialog
      v-model="showExportDialog"
      :org-id="currentOrgId"
      @success="handleExportSuccess"
    />

    <!-- Import Dialog -->
    <ImportDialog
      v-model="showImportDialog"
      :org-id="currentOrgId"
      @success="handleImportSuccess"
    />

    <!-- Encrypted Export Dialog -->
    <ExportEncryptedDialog
      v-model="showEncryptedExportDialog"
      :org-id="currentOrgId"
      @success="handleExportSuccess"
    />

    <!-- Encrypted Import Dialog -->
    <ImportEncryptedDialog
      v-model="showEncryptedImportDialog"
      :org-id="currentOrgId"
      @success="handleImportSuccess"
    />

    <!-- Preview Dialog -->
    <el-dialog v-model="showPreviewDialog" title="数据预览" width="960px">
      <div v-if="previewData.length" class="preview-content">
        <el-tabs>
          <el-tab-pane
            v-for="preview in previewData"
            :key="preview.data_type"
            :label="`${getDataTypeLabel(preview.data_type)} (${preview.total})`"
          >
            <el-table :data="preview.sample" size="small" max-height="400">
              <el-table-column
                v-for="col in preview.columns"
                :key="col"
                :prop="col"
                :label="col"
                min-width="120"
              />
            </el-table>
          </el-tab-pane>
        </el-tabs>
      </div>
      <el-empty v-else description="暂无预览数据" />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { Upload, Download, Lock, Key } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { logger } from '@/utils/logger'
import ExportDialog from '@/components/dataPackage/ExportDialog.vue'
import ImportDialog from '@/components/dataPackage/ImportDialog.vue'
import ExportEncryptedDialog from '@/components/dataPackage/ExportEncryptedDialog.vue'
import ImportEncryptedDialog from '@/components/dataPackage/ImportEncryptedDialog.vue'
import { useDataPackageStore } from '@/stores/dataPackage'
import { useOrganizationStore } from '@/stores/organization'
import type { DataPackage, DataPackagePreviewData } from '@/types/organization'

const packageStore = useDataPackageStore()
const orgStore = useOrganizationStore()

// State
const showExportDialog = ref(false)
const showImportDialog = ref(false)
const showEncryptedExportDialog = ref(false)
const showEncryptedImportDialog = ref(false)
const showPreviewDialog = ref(false)
const previewData = ref<DataPackagePreviewData[]>([])

const filters = reactive({
  status: '',
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
})

// Computed
const packages = computed(() => packageStore.packages)
const loading = computed(() => packageStore.loading)
const total = computed(() => packageStore.total)
const currentOrgId = computed(() => orgStore.current?.id)

const statusLabels: Record<string, string> = {
  pending: '待处理',
  validated: '已验证',
  imported: '已导入',
  failed: '失败',
  cancelled: '已取消',
}

const statusTypes: Record<string, 'info' | 'primary' | 'success' | 'warning' | 'danger'> = {
  pending: 'warning',
  validated: 'success',
  imported: 'primary',
  failed: 'danger',
  cancelled: 'info',
}

const dataTypeLabels: Record<string, string> = {
  villages: '村庄数据',
  projects: '项目数据',
  funds: '资金数据',
  schools: '学校数据',
}

// Methods
async function loadPackages() {
  try {
    await packageStore.fetchPackages({
      page: pagination.page,
      page_size: pagination.pageSize,
      status: filters.status || undefined,
    })
  } catch (error) {
    ElMessage.error('加载数据包列表失败')
  }
}

function resetFilters() {
  filters.status = ''
  pagination.page = 1
  loadPackages()
}

function getStatusLabel(status: string): string {
  return statusLabels[status] || status
}

function getStatusType(status: string): 'success' | 'info' | 'warning' | 'danger' | 'primary' {
  return statusTypes[status] || 'info'
}

function getDataTypeLabel(type: string): string {
  return dataTypeLabels[type] || type
}

function formatFileSize(bytes?: number): string {
  if (!bytes) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(2) + ' MB'
}

function formatDate(dateStr?: string): string {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

async function handlePreview(pkg: DataPackage) {
  try {
    previewData.value = await packageStore.previewPackage(pkg.id)
    showPreviewDialog.value = true
  } catch (error) {
    ElMessage.error('加载预览数据失败')
  }
}

async function handleConfirmImport(pkg: DataPackage) {
  try {
    await ElMessageBox.confirm('确定要导入此数据包吗？', '确认导入', {
      type: 'warning',
    })
    await packageStore.confirmImport(pkg.id)
    ElMessage.success('导入成功')
    pagination.page = 1 // 重置到第1页，确保新建/编辑后的数据可见
    loadPackages()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error((error as Error).message || '导入失败')
    }
  }
}

async function handleDownload(pkg: DataPackage) {
  try {
    await packageStore.downloadPackage(pkg.id)
  } catch (error) {
    ElMessage.error('下载失败')
  }
}

async function handleDelete(pkg: DataPackage) {
  try {
    await ElMessageBox.confirm('确定要删除此数据包吗？', '删除确认', {
      type: 'warning',
    })
    await packageStore.deletePackage(pkg.id)
    ElMessage.success('删除成功')
    pagination.page = 1 // 重置到第1页，确保新建/编辑后的数据可见
    loadPackages()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error((error as Error).message || '删除失败')
    }
  }
}

function handleExportSuccess() {
  pagination.page = 1 // 重置到第1页，确保新建/编辑后的数据可见
  loadPackages()
}

function handleImportSuccess() {
  showImportDialog.value = false
  pagination.page = 1 // 重置到第1页，确保新建/编辑后的数据可见
  loadPackages()
}

// Lifecycle
onMounted(() => {
  loadPackages()
  orgStore.fetchMyOrganization().catch((err) => {
    logger.error('[DataPackage/List] 加载组织失败', err)
  })
})
</script>

<style scoped lang="scss">
.data-package-list {
  padding: 20px;

  .page-header {
    margin-bottom: 20px;

    .header-content {
      display: flex;
      justify-content: space-between;
      align-items: center;

      h2 {
        margin: 0;
      }

      .header-actions {
        display: flex;
        gap: 12px;
      }
    }
  }

  .filter-card {
    margin-bottom: 20px;
  }

  .pagination {
    margin-top: 20px;
    display: flex;
    justify-content: flex-end;
  }

  .preview-content {
    max-height: 500px;
    overflow: auto;
  }
}
</style>
