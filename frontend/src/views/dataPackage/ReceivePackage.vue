<template>
  <div class="receive-package">
    <el-card class="page-header">
      <div class="header-content">
        <div style="display: flex; justify-content: space-between; align-items: center">
          <div>
            <h2>接收下级数据包</h2>
            <p class="description">接收并处理下级单位上报的数据包</p>
          </div>
          <el-button v-if="isAdmin" type="primary" @click="showLocalImport = true">
            <el-icon><Folder /></el-icon> 从本地文件导入
          </el-button>
        </div>
      </div>
    </el-card>

    <!-- 非管理员体验层提示（后端对导入/确认已强制 403） -->
    <el-alert v-if="!isAdmin" type="warning" show-icon :closable="false" class="admin-only-alert"
      >仅管理员可接收数据包</el-alert
    >

    <el-tabs v-model="activeTab" class="receive-tabs" @tab-change="handleTabChange">
      <el-tab-pane label="上报列表" name="reports">
        <!-- 本地文件导入对话框 -->
        <el-dialog
          v-model="showLocalImport"
          title="从本地导入数据包"
          :width="DIALOG_SM"
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
              <el-descriptions-item label="文件名">{{
                localImportInfo.fileName
              }}</el-descriptions-item>
              <el-descriptions-item label="包编号">{{
                localImportInfo.packageId || '-'
              }}</el-descriptions-item>
            </el-descriptions>
          </template>

          <template v-if="localImportStep === 2">
            <el-result
              icon="success"
              title="导入成功"
              sub-title="数据包已成功导入，请在列表中查看"
            />
          </template>

          <template #footer>
            <el-button @click="closeLocalImport">
              {{ localImportStep === 2 ? '关闭' : '取消' }}
            </el-button>
            <el-button
              v-if="localImportStep === 1 && isAdmin"
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
              <el-select
                v-model="filters.status"
                placeholder="全部状态"
                clearable
                style="width: 150px"
              >
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
                <el-button
                  link
                  type="primary"
                  size="small"
                  @click="handlePreview(row as DataReport)"
                >
                  预览
                </el-button>
                <template
                  v-if="isAdmin && (row.status === 'pending' || row.status === 'submitted')"
                >
                  <el-button
                    link
                    type="success"
                    size="small"
                    @click="handleReceive(row as DataReport)"
                  >
                    接收
                  </el-button>
                  <el-button
                    link
                    type="danger"
                    size="small"
                    @click="handleReject(row as DataReport)"
                  >
                    拒绝
                  </el-button>
                </template>
                <el-button
                  link
                  type="primary"
                  size="small"
                  @click="handleDownload(row as DataReport)"
                >
                  下载
                </el-button>
              </template>
            </el-table-column>
          </el-table>

          <EmptyState v-if="!loading && reports.length === 0" text="暂无数据包" />

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
      </el-tab-pane>

      <!-- 接收记录（仅管理员） -->
      <el-tab-pane v-if="isAdmin" label="接收记录" name="received">
        <el-card>
          <el-table v-loading="receivedLoading" :data="receivedItems" stripe>
            <el-table-column label="包编号" width="180">
              <template #default="{ row }">{{ row.package_code || '-' }}</template>
            </el-table-column>
            <el-table-column label="来源组织" min-width="140">
              <template #default="{ row }">{{ row.org_name || row.org_code || '-' }}</template>
            </el-table-column>
            <el-table-column label="上报人" width="110">
              <template #default="{ row }">{{ row.exported_by_name || '-' }}</template>
            </el-table-column>
            <el-table-column label="文件名" min-width="170">
              <template #default="{ row }">{{ row.file_name || '-' }}</template>
            </el-table-column>
            <el-table-column label="大小" width="90">
              <template #default="{ row }">{{ formatFileSize(row.file_size) }}</template>
            </el-table-column>
            <el-table-column label="记录数" width="90" align="center">
              <template #default="{ row }">{{ row.record_count ?? '-' }}</template>
            </el-table-column>
            <el-table-column label="校验结果" min-width="180">
              <template #default="{ row }">
                <span v-if="row._vs">
                  通过{{ row._vs.ok }}
                  <span class="vs-corrected">纠正{{ row._vs.corrected }}</span>
                  <span class="vs-rejected">拒绝{{ row._vs.rejected }}</span>
                </span>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="getStatusType(row.status)">{{ getStatusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="接收时间" width="170">
              <template #default="{ row }">{{
                formatDate(row.imported_at || row.created_at)
              }}</template>
            </el-table-column>
            <el-table-column label="操作" width="140" fixed="right">
              <template #default="{ row }">
                <el-button
                  v-if="row.status === 'validated'"
                  link
                  type="primary"
                  size="small"
                  @click="previewReceived(row)"
                >
                  预览
                </el-button>
                <el-button link type="primary" size="small" @click="handleReceivedDownload(row)">
                  下载
                </el-button>
              </template>
            </el-table-column>
          </el-table>

          <EmptyState v-if="!receivedLoading && receivedItems.length === 0" text="暂无接收记录" />

          <div v-if="receivedTotal > 0" class="pagination">
            <el-pagination
              v-model:current-page="receivedPagination.page"
              v-model:page-size="receivedPagination.pageSize"
              :total="receivedTotal"
              :page-sizes="[10, 20, 50]"
              layout="total, sizes, prev, pager, next"
              @size-change="loadReceived"
              @current-change="loadReceived"
            />
          </div>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- 预览对话框 -->
    <el-dialog v-model="showPreviewDialog" title="数据预览" :width="DIALOG_LG" destroy-on-close>
      <!-- 字段级校验报告（import 响应 validation.warnings / 接收记录 validation_summary） -->
      <div v-if="validationWarnings.length" class="validation-report">
        <h4>字段校验报告</h4>
        <div
          v-for="(line, i) in validationWarnings"
          :key="i"
          class="vr-line"
          :class="`vr-${classifyWarningLine(line)}`"
        >
          {{ line }}
        </div>
      </div>
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
      <EmptyState v-else text="暂无预览数据" />
    </el-dialog>

    <!-- 拒绝对话框 -->
    <el-dialog v-model="showRejectDialog" title="拒绝数据包" :width="DIALOG_SM">
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
import { DIALOG_SM, DIALOG_LG } from '@/config/dialog'
import EmptyState from '@/components/business/EmptyState/EmptyState.vue'
import { logger } from '@/utils/logger'

import { ref, reactive, computed, onMounted, onErrorCaptured } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled, Folder } from '@element-plus/icons-vue'
import { useDataReportStore } from '@/stores/dataReport'
import { useOrganizationStore } from '@/stores/organization'
import { useAuthStore } from '@/stores/auth'
import type { DataReport, DataPackagePreviewData } from '@/types/organization'
import { get, post } from '@/api/request'
import { downloadDataPackage, previewDataPackage } from '@/api/dataPackage'

const reportStore = useDataReportStore()
const orgStore = useOrganizationStore()
const authStore = useAuthStore()

// 仅管理员可接收/导入数据包（后端已 403，前端做体验层）
const isAdmin = computed(() => authStore.isAdmin)

// 页签：reports=上报列表，received=接收记录（仅管理员可见）
const activeTab = ref('reports')

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
  validated: '已校验',
  imported: '已导入',
}

const statusTypes: Record<string, 'info' | 'primary' | 'success' | 'warning' | 'danger'> = {
  pending: 'warning',
  received: 'success',
  rejected: 'danger',
  submitted: 'info',
  validated: 'primary',
  imported: 'success',
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

// ========== 接收记录（仅管理员） ==========
const receivedLoading = ref(false)
const receivedItems = ref<any[]>([])
const receivedTotal = ref(0)
const receivedPagination = reactive({ page: 1, pageSize: 20 })

/** 解析 manifest.validation_summary（字段校验 warnings 列表）为 ok/corrected/rejected 计数 */
function parseValidationSummary(
  vs: unknown
): { ok: number; corrected: number; rejected: number } | null {
  if (!Array.isArray(vs)) return null
  let ok = 0
  let corrected = 0
  let rejected = 0
  let found = false
  for (const line of vs) {
    const m = /通过(\d+)条\/纠正(\d+)条\/拒绝(\d+)条/.exec(String(line))
    if (m) {
      found = true
      ok += Number(m[1])
      corrected += Number(m[2])
      rejected += Number(m[3])
    }
  }
  return found ? { ok, corrected, rejected } : null
}

/** 字段校验报告行分类：rejected 红标原因 / corrected 已自动纠正 / summary 计数摘要 */
function classifyWarningLine(line: string): 'rejected' | 'corrected' | 'summary' {
  if (line.includes('校验未通过')) return 'rejected'
  if (line.includes('已自动纠正')) return 'corrected'
  return 'summary'
}

function formatFileSize(size: unknown): string {
  const num = Number(size)
  if (!num || isNaN(num)) return '-'
  if (num < 1024) return `${num}B`
  if (num < 1024 * 1024) return `${(num / 1024).toFixed(1)}KB`
  return `${(num / 1024 / 1024).toFixed(2)}MB`
}

async function loadReceived() {
  if (!isAdmin.value) return
  receivedLoading.value = true
  try {
    const res = await get('/data-packages/received', {
      page: receivedPagination.page,
      page_size: receivedPagination.pageSize,
    })
    const items = res?.items || res?.data?.items || []
    receivedItems.value = items.map((it: any) => ({
      ...it,
      _vs: parseValidationSummary(it.validation_summary),
    }))
    receivedTotal.value = res?.total ?? res?.data?.total ?? items.length
  } catch {
    ElMessage.error('加载接收记录失败')
    receivedItems.value = []
    receivedTotal.value = 0
  } finally {
    receivedLoading.value = false
  }
}

function handleTabChange(name: string | number) {
  if (name === 'received') loadReceived()
}

// 字段级校验报告（import 响应 validation.warnings 或接收记录 validation_summary）
const validationWarnings = ref<string[]>([])

/** 接收记录预览（仅已校验包可预览），同时展示字段级校验报告 */
async function previewReceived(row: any) {
  try {
    const data = await previewDataPackage(row.id)
    previewData.value = Array.isArray(data) ? data : (data as any)?.data || []
    currentReport.value = {
      source_org_name: row.org_name,
      package_code: row.package_code,
      record_count: row.record_count,
      created_at: row.imported_at || row.created_at,
    } as unknown as DataReport
    validationWarnings.value = Array.isArray(row.validation_summary) ? row.validation_summary : []
    showPreviewDialog.value = true
  } catch (error) {
    logger.error('[ReceivePackage] 接收记录预览失败:', error)
    ElMessage.error('加载预览数据失败')
  }
}

async function handleReceivedDownload(row: any) {
  try {
    const blob = await downloadDataPackage(row.id)
    const url = URL.createObjectURL(new Blob([blob]))
    const link = document.createElement('a')
    link.href = url
    link.download = row.file_name || `${row.package_code || 'package'}.zip`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
    ElMessage.success('下载已开始')
  } catch {
    ElMessage.error('下载失败')
  }
}

async function handlePreview(report: DataReport) {
  currentReport.value = report
  validationWarnings.value = [] // 列表预览无校验报告上下文
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
    // 字段级校验报告（各类型 ok/corrected/rejected 计数 + 前 5 条明细），随包带入预览对话框
    validationWarnings.value = data?.validation?.warnings ?? data?.warnings ?? []
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
        color: var(--color-text-secondary);
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

  .admin-only-alert {
    margin-bottom: 16px;
  }

  .receive-tabs {
    margin-bottom: 0;
  }

  .vs-corrected {
    color: var(--color-warning-dark);
    margin-left: 4px;
  }

  .vs-rejected {
    color: var(--color-danger);
    margin-left: 4px;
  }

  .validation-report {
    margin-bottom: 16px;
    padding: 12px;
    border: 1px solid var(--color-border, var(--color-border-light));
    border-radius: 4px;

    h4 {
      margin: 0 0 8px;
      color: var(--color-primary-dark-1);
    }

    .vr-line {
      font-size: 13px;
      line-height: 1.8;
    }

    .vr-summary {
      color: var(--color-text-secondary);
    }

    .vr-corrected {
      color: var(--color-warning-dark);
    }

    .vr-rejected {
      color: var(--color-danger);
    }
  }
}
</style>
