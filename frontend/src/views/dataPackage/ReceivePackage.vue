<template>
  <div class="receive-package">
    <el-card class="page-header">
      <div class="header-content">
        <div style="display: flex; justify-content: space-between; align-items: center">
          <div>
            <h2>接收下级数据包</h2>
            <p class="description">接收并处理下级单位上报的数据包</p>
          </div>
          <el-button type="primary" @click="showLocalImport = true">
            <el-icon><Folder /></el-icon> 从本地文件导入
          </el-button>
        </div>
      </div>
    </el-card>

    <!-- 本地文件导入对话框 -->
    <el-dialog
      v-model="showLocalImport"
      title="从本地导入数据包"
      width="550px"
      destroy-on-close
      @close="clearLocalImport"
    >
      <template v-if="localImportStep === 0">
        <el-alert
          title="选择通过U盘等方式拷贝过来的上报数据包ZIP文件"
          type="info"
          show-icon
          :closable="false"
          style="margin-bottom: 16px"
        />
        <el-upload
          ref="localUploadRef"
          :auto-upload="false"
          :limit="1"
          accept=".zip"
          :on-change="handleLocalFileChange"
          drag
        >
          <el-icon style="font-size: 36px; color: var(--color-info)"><UploadFilled /></el-icon>
          <div style="margin-top: 8px">拖放或点击选择数据包ZIP文件</div>
        </el-upload>
      </template>

      <template v-if="localImportStep === 1">
        <el-descriptions title="数据包信息" :column="1" border size="small">
          <el-descriptions-item label="文件名">{{ localImportInfo.fileName }}</el-descriptions-item>
          <el-descriptions-item label="包编号">{{
            localImportInfo.packageId || '-'
          }}</el-descriptions-item>
        </el-descriptions>
      </template>

      <template v-if="localImportStep === 2">
        <el-result icon="success" title="导入成功" sub-title="数据包已成功导入，请在列表中查看" />
      </template>

      <template #footer>
        <el-button @click="closeLocalImport">
          {{ localImportStep === 2 ? '关闭' : '取消' }}
        </el-button>
        <el-button
          v-if="localImportStep === 1"
          type="primary"
          :loading="localImporting"
          @click="confirmLocalImport"
        >
          确认导入
        </el-button>
      </template>
    </el-dialog>

    <!-- 筛选条件 -->
    <el-card class="filter-card">
      <el-form :inline="true" :model="filters">
        <el-form-item label="上报单位">
          <el-select
            v-model="filters.sourceOrgId"
            placeholder="选择单位"
            clearable
            filterable
            style="width: 200px"
          >
            <el-option
              v-for="org in subordinateOrgs"
              :key="org.id"
              :label="org.name"
              :value="org.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部状态" clearable style="width: 150px">
            <el-option label="待接收" value="pending" />
            <el-option label="已接收" value="received" />
            <el-option label="已拒绝" value="rejected" />
          </el-select>
        </el-form-item>
        <el-form-item label="上报时间">
          <el-date-picker
            v-model="filters.dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            style="width: 260px"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadReports">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 数据列表 -->
    <el-card>
      <el-table v-loading="loading" :data="reports" stripe>
        <el-table-column label="上报单位" min-width="150">
          <template #default="{ row }">
            {{ row.source_org_name || row.title || `单位#${row.source_org_id}` }}
          </template>
        </el-table-column>
        <el-table-column label="数据包编码" width="200">
          <template #default="{ row }">
            {{ row.package_code || row.report_code || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="数据类型" width="150">
          <template #default="{ row }">
            <template v-if="parseDataTypes(row.data_types).length">
              <el-tag
                v-for="type in parseDataTypes(row.data_types)"
                :key="type"
                size="small"
                style="margin-right: 4px"
              >
                {{ getDataTypeLabel(type) }}
              </el-tag>
            </template>
            <span v-else style="color: #999">-</span>
          </template>
        </el-table-column>
        <el-table-column label="记录数" width="100">
          <template #default="{ row }">
            {{ row.record_count ?? '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">
              {{ getStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="上报时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.submitted_at || row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="handlePreview(row as DataReport)">
              预览
            </el-button>
            <template v-if="row.status === 'pending' || row.status === 'submitted'">
              <el-button link type="success" size="small" @click="handleReceive(row as DataReport)">
                接收
              </el-button>
              <el-button link type="danger" size="small" @click="handleReject(row as DataReport)">
                拒绝
              </el-button>
            </template>
            <el-button link type="primary" size="small" @click="handleDownload(row as DataReport)">
              下载
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!loading && reports.length === 0" description="暂无数据包" />

      <div v-if="total > 0" class="pagination">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          @size-change="loadReports"
          @current-change="loadReports"
        />
      </div>
    </el-card>

    <!-- 预览对话框 -->
    <el-dialog v-model="showPreviewDialog" title="数据预览" width="900px" destroy-on-close>
      <div v-if="previewData.length" class="preview-content">
        <el-descriptions :column="2" border class="preview-info">
          <el-descriptions-item label="上报单位">{{
            currentReport?.source_org_name || currentReport?.title || '-'
          }}</el-descriptions-item>
          <el-descriptions-item label="数据包编码">{{
            currentReport?.package_code || currentReport?.report_code || '-'
          }}</el-descriptions-item>
          <el-descriptions-item label="记录总数">{{
            currentReport?.record_count ?? '-'
          }}</el-descriptions-item>
          <el-descriptions-item label="上报时间">{{
            formatDate(currentReport?.submitted_at || currentReport?.created_at)
          }}</el-descriptions-item>
        </el-descriptions>

        <el-tabs style="margin-top: 20px">
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
                :label="getColumnLabel(col)"
                min-width="120"
              />
            </el-table>
          </el-tab-pane>
        </el-tabs>
      </div>
      <el-empty v-else description="暂无预览数据" />
    </el-dialog>

    <!-- 拒绝对话框 -->
    <el-dialog v-model="showRejectDialog" title="拒绝数据包" width="500px">
      <el-form :model="rejectForm" label-width="80px">
        <el-form-item label="拒绝原因" required>
          <el-input
            v-model="rejectForm.reason"
            type="textarea"
            :rows="4"
            placeholder="请输入拒绝原因"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showRejectDialog = false">取消</el-button>
        <el-button type="danger" :loading="rejecting" @click="confirmReject"> 确认拒绝 </el-button>
      </template>
    </el-dialog>
    <!-- 组件异常回退 -->
    <el-card v-if="componentError" class="error-fallback">
      <el-result icon="warning" title="页面加载异常" :sub-title="componentError">
        <template #extra>
          <el-button type="primary" @click="handleRetry">重试</el-button>
        </template>
      </el-result>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { logger } from '@/utils/logger'

import { ref, reactive, computed, onMounted, onErrorCaptured } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled, Folder } from '@element-plus/icons-vue'
import { useDataReportStore } from '@/stores/dataReport'
import { useOrganizationStore } from '@/stores/organization'
import type { DataReport, DataPackagePreviewData } from '@/types/organization'
import { post } from '@/api/request'

const reportStore = useDataReportStore()
const orgStore = useOrganizationStore()

// 错误边界
const componentError = ref('')
onErrorCaptured((err: Error) => {
  logger.error('[ReceivePackage] 组件异常:', err)
  componentError.value = err?.message || '未知错误，请重试'
  return false
})
function handleRetry() {
  componentError.value = ''
  loadReports()
}

// 状态
const loading = ref(false)
const showPreviewDialog = ref(false)
const showRejectDialog = ref(false)
const rejecting = ref(false)
const currentReport = ref<DataReport | null>(null)
const previewData = ref<DataPackagePreviewData[]>([])

const filters = reactive({
  sourceOrgId: null as number | null,
  status: '',
  dateRange: null as [Date, Date] | null,
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
})

const rejectForm = reactive({
  reason: '',
})

// 计算属性
const reports = computed(() => reportStore.receivedReports)
const total = computed(() => reportStore.receivedTotal)
const subordinateOrgs = computed(() => orgStore.subordinateOrganizations)

// 标签映射
const statusLabels: Record<string, string> = {
  pending: '待接收',
  received: '已接收',
  rejected: '已拒绝',
  submitted: '已提交',
}

const statusTypes: Record<string, 'info' | 'primary' | 'success' | 'warning' | 'danger'> = {
  pending: 'warning',
  received: 'success',
  rejected: 'danger',
  submitted: 'info',
}

const dataTypeLabels: Record<string, string> = {
  villages: '村庄数据',
  projects: '项目数据',
  funds: '资金数据',
  schools: '学校数据',
}

const columnLabels: Record<string, string> = {
  id: '编号',
  name: '名称',
  code: '编码',
  status: '状态',
  created_at: '创建时间',
  updated_at: '更新时间',
}

// 方法
async function loadReports() {
  loading.value = true
  try {
    await reportStore.fetchReceivedReports({
      page: pagination.page,
      page_size: pagination.pageSize,
      source_org_id: filters.sourceOrgId || undefined,
      status: filters.status || undefined,
      start_date: filters.dateRange?.[0]?.toISOString(),
      end_date: filters.dateRange?.[1]?.toISOString(),
    })
  } catch (error) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  filters.sourceOrgId = null
  filters.status = ''
  filters.dateRange = null
  pagination.page = 1
  loadReports()
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

function getColumnLabel(col: string): string {
  return columnLabels[col] || col
}

function parseDataTypes(types: string | string[]): string[] {
  if (Array.isArray(types)) return types
  try {
    return JSON.parse(types)
  } catch {
    return []
  }
}

function formatDate(dateStr?: string): string {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

async function handlePreview(report: DataReport) {
  currentReport.value = report
  try {
    const data = await reportStore.previewReport(report.id)
    // 兼容不同 API 返回格式
    previewData.value = Array.isArray(data) ? data : (data as any)?.data || []
    showPreviewDialog.value = true
  } catch (error) {
    logger.error('[ReceivePackage] 预览失败:', error)
    ElMessage.error('加载预览数据失败')
  }
}

async function handleReceive(report: DataReport) {
  const orgName = report.source_org_name || report.title || `单位#${report.source_org_id}`
  try {
    await ElMessageBox.confirm(`确定要接收来自"${orgName}"的数据包吗？`, '确认接收', {
      type: 'info',
    })
    await reportStore.receiveReport(report.id)
    ElMessage.success('接收成功')
    pagination.page = 1 // 重置到第1页，确保新建/编辑后的数据可见
    loadReports()
  } catch (error: any) {
    if (error !== 'cancel' && error?.toString?.() !== 'cancel') {
      ElMessage.error(error?.message || '接收失败')
    }
  }
}

function handleReject(report: DataReport) {
  currentReport.value = report
  rejectForm.reason = ''
  showRejectDialog.value = true
}

async function confirmReject() {
  if (!rejectForm.reason.trim()) {
    ElMessage.warning('请输入拒绝原因')
    return
  }

  rejecting.value = true
  try {
    await reportStore.rejectReport(currentReport.value!.id, rejectForm.reason)
    ElMessage.success('已拒绝该数据包')
    showRejectDialog.value = false
    pagination.page = 1 // 重置到第1页，确保新建/编辑后的数据可见
    loadReports()
  } catch (error) {
    ElMessage.error((error as Error).message || '操作失败')
  } finally {
    rejecting.value = false
  }
}

async function handleDownload(report: DataReport) {
  try {
    await reportStore.downloadReport(report.id)
    ElMessage.success('下载已开始')
  } catch (error) {
    ElMessage.error('下载失败')
  }
}

// ========== 本地文件导入 ==========
const showLocalImport = ref(false)
const localImportStep = ref(0)
const localImporting = ref(false)
const localUploadRef = ref<any>(null)
const localImportInfo = reactive({ fileName: '', packageId: '' })

async function handleLocalFileChange(file: any) {
  const raw = file?.raw || file
  if (!raw) return
  const formData = new FormData()
  formData.append('file', raw)
  try {
    const data = await post('/data-packages/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    if (data?.errors?.length) {
      ElMessage.error(`数据包验证失败: ${data.errors[0]}`)
      return
    }
    localImportInfo.fileName = raw.name
    localImportInfo.packageId = String(data?.package_id || '')
    localImportStep.value = 1
  } catch {
    ElMessage.error('数据包上传失败，请检查文件格式')
  }
}

async function confirmLocalImport() {
  if (!localImportInfo.packageId) return
  localImporting.value = true
  try {
    await post(`/data-packages/${localImportInfo.packageId}/confirm`, {
      package_id: Number(localImportInfo.packageId),
      confirm: true,
    })
    localImportStep.value = 2
    ElMessage.success('数据包导入成功')
    pagination.page = 1 // 重置到第1页，确保新建/编辑后的数据可见
    loadReports()
  } catch {
    ElMessage.error('导入确认失败')
  } finally {
    localImporting.value = false
  }
}

function clearLocalImport() {
  localImportStep.value = 0
  localImportInfo.fileName = ''
  localImportInfo.packageId = ''
  localUploadRef.value?.clearFiles?.()
}

function closeLocalImport() {
  clearLocalImport()
  showLocalImport.value = false
}

// 生命周期
onMounted(() => {
  loadReports()
  orgStore.fetchSubordinateOrganizations().catch((err) => {
    logger.error('[ReceivePackage] 加载组织失败', err)
  })
})
</script>

<style scoped lang="scss">
.receive-package {
  padding: 20px;

  .page-header {
    margin-bottom: 20px;

    .header-content {
      h2 {
        margin: 0 0 8px 0;
      }

      .description {
        margin: 0;
        color: #666;
        font-size: 14px;
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
    .preview-info {
      margin-bottom: 16px;
    }
  }
}
</style>
