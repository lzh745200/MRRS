<template>
  <div class="contract-container">
    <el-page-header title="返回" @back="pushSafe('/funds')">
      <template #content><span class="page-title">合同-支付管理</span></template>
    </el-page-header>

    <el-card class="mt-4" shadow="never">
      <div class="toolbar">
        <el-select
          v-model="filters.status"
          placeholder="合同状态"
          clearable
          size="default"
          style="width: 140px"
          @change="loadData"
        >
          <el-option label="草稿" value="draft" />
          <el-option label="执行中" value="active" />
          <el-option label="已完成" value="completed" />
          <el-option label="已终止" value="terminated" />
        </el-select>
        <el-button type="primary" @click="openCreateDialog">新建合同</el-button>
      </div>

      <el-table v-loading="loading" :data="contracts" size="default" class="mt-3">
        <el-table-column prop="contract_no" label="合同编号" width="150" />
        <el-table-column
          prop="contract_name"
          label="合同名称"
          min-width="200"
          show-overflow-tooltip
        />
        <el-table-column prop="party_a" label="甲方" width="150" show-overflow-tooltip />
        <el-table-column prop="party_b" label="乙方" width="150" show-overflow-tooltip />
        <el-table-column prop="contract_amount" label="合同金额" width="120" />
        <el-table-column prop="paid_amount" label="已付金额" width="120" />
        <el-table-column label="付款进度" width="120">
          <template #default="{ row }">
            <el-progress :percentage="row.payment_progress" :stroke-width="8" />
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag
              :type="
                row.status === 'completed'
                  ? 'success'
                  : row.status === 'active'
                    ? 'primary'
                    : row.status === 'terminated'
                      ? 'danger'
                      : 'info'
              "
              size="small"
            >
              {{ row.status_label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" plain @click="showAttachmentDialog(row)"
              >附件</el-button
            >
            <el-button size="small" @click="showPaymentDialog(row)">登记付款</el-button>
            <el-button
              v-if="row.status === 'draft'"
              size="small"
              type="danger"
              @click="handleDeleteContract(row.id)"
              >删除</el-button
            >
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="page"
        class="mt-3"
        background
        layout="total, prev, pager, next"
        :total="total"
        :page-size="pageSize"
        @current-change="loadData"
      />
    </el-card>

    <!-- 新建合同对话框 -->
    <el-dialog v-model="showCreateDialog" title="新建合同" width="600px">
      <el-form
        ref="contractFormRef"
        :model="contractForm"
        :rules="contractRules"
        label-width="100px"
      >
        <el-form-item label="合同编号" prop="contract_no" required
          ><el-input v-model="contractForm.contract_no"
        /></el-form-item>
        <el-form-item label="合同名称" prop="contract_name" required
          ><el-input v-model="contractForm.contract_name"
        /></el-form-item>
        <el-form-item label="甲方" prop="party_a"
          ><el-input v-model="contractForm.party_a"
        /></el-form-item>
        <el-form-item label="乙方" prop="party_b"
          ><el-input v-model="contractForm.party_b"
        /></el-form-item>
        <el-form-item label="合同金额" prop="contract_amount"
          ><el-input-number v-model="contractForm.contract_amount" :min="0" :precision="2"
        /></el-form-item>
        <el-form-item label="签订日期" prop="sign_date"
          ><el-date-picker v-model="contractForm.sign_date" type="date" value-format="YYYY-MM-DD"
        /></el-form-item>
        <el-form-item label="截止日期" prop="deadline"
          ><el-date-picker v-model="contractForm.deadline" type="date" value-format="YYYY-MM-DD"
        /></el-form-item>
        <el-form-item label="备注"
          ><el-input v-model="contractForm.remarks" type="textarea"
        /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" :loading="loading" @click="handleCreateContract">创建</el-button>
      </template>
    </el-dialog>

    <!-- 登记付款对话框 -->
    <el-dialog v-model="paymentDialogVisible" title="登记合同付款" width="500px">
      <el-form :model="paymentForm" label-width="100px">
        <el-form-item label="付款金额" required
          ><el-input-number v-model="paymentForm.amount" :min="0.01" :precision="2"
        /></el-form-item>
        <el-form-item label="付款日期" required
          ><el-date-picker v-model="paymentForm.payment_date" type="date" value-format="YYYY-MM-DD"
        /></el-form-item>
        <el-form-item label="用途"><el-input v-model="paymentForm.purpose" /></el-form-item>
        <el-form-item label="凭证号"><el-input v-model="paymentForm.voucher_no" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="paymentDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="loading" @click="handleCreatePayment">提交</el-button>
      </template>
    </el-dialog>

    <!-- 合同附件对话框 -->
    <el-dialog
      v-model="attachmentDialogVisible"
      :title="`合同附件 - ${currentContractName}`"
      width="600px"
    >
      <el-upload
        :action="uploadAction"
        :headers="uploadHeaders"
        :before-upload="beforeUpload"
        :on-success="handleUploadSuccess"
        :on-error="handleUploadError"
        :show-file-list="false"
        accept=".pdf,.doc,.docx,.jpg,.jpeg,.png"
      >
        <el-button type="primary">上传附件</el-button>
        <template #tip>
          <div style="font-size: 12px; color: #999; margin-top: 8px">
            支持 pdf / doc / docx / 图片，单个不超过 10MB
          </div>
        </template>
      </el-upload>
      <el-table :data="attachmentList" size="small" style="margin-top: 12px" max-height="320">
        <el-table-column prop="file_name" label="文件名" min-width="200" show-overflow-tooltip />
        <el-table-column prop="file_size" label="大小" width="100">
          <template #default="{ row }">
            {{ formatSize(row.file_size) }}
          </template>
        </el-table-column>
        <el-table-column prop="uploaded_by" label="上传人" width="100" />
        <el-table-column prop="created_at" label="上传时间" width="140" />
        <el-table-column label="操作" width="130">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openAttachment(row)"
              >打开</el-button
            >
            <el-button link type="primary" size="small" @click="downloadAttachment(row)"
              >下载</el-button
            >
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="暂无附件" :image-size="60" />
        </template>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { fundLifecycleApi } from '@/api/fundLifecycle'
import { safeRouteParam, useRouterSafe } from '@/composables/useRouterSafe'
import { useUploadHeaders } from '@/composables/useUploadHeaders'
import { AuthStorage } from '@/utils/authStorage'

const { pushSafe } = useRouterSafe()
const route = useRoute()
const projectId = route.query.project_id ? safeRouteParam(route.query.project_id) : undefined

const loading = ref(false)
const contracts = ref<any[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const filters = reactive({ status: '' })
const showCreateDialog = ref(false)
const paymentDialogVisible = ref(false)
const currentContractId = ref(0)

// 附件上传配置
const uploadAction = `${import.meta.env.VITE_API_BASE_URL || '/api/v1'}/files/upload`
const { uploadHeaders, ensureCsrf } = useUploadHeaders()
const attachmentDialogVisible = ref(false)
const currentContractName = ref('')
const attachmentList = ref<any[]>([])

const contractForm = reactive({
  contract_no: '',
  contract_name: '',
  party_a: '',
  party_b: '',
  contract_amount: 0,
  sign_date: '',
  deadline: '',
  remarks: '',
  project_id: projectId,
  fund_id: undefined as number | undefined,
})

const contractFormRef = ref<FormInstance | null>(null)

// 新建合同：每次打开都重置表单，避免残留上次输入
function openCreateDialog() {
  Object.assign(contractForm, {
    contract_no: '',
    contract_name: '',
    party_a: '',
    party_b: '',
    contract_amount: 0,
    sign_date: '',
    deadline: '',
    remarks: '',
    project_id: projectId,
    fund_id: undefined,
  })
  contractFormRef.value?.clearValidate?.()
  showCreateDialog.value = true
}

const contractRules: FormRules = {
  contract_no: [{ required: true, message: '请填写合同编号', trigger: 'blur' }],
  contract_name: [{ required: true, message: '请填写合同名称', trigger: 'blur' }],
  contract_amount: [{ required: true, message: '请填写合同金额', trigger: 'blur' }],
}

const paymentForm = reactive({
  amount: 0,
  payment_date: '',
  purpose: '',
  voucher_no: '',
})

async function loadData() {
  loading.value = true
  try {
    const data = await fundLifecycleApi.listContracts({
      project_id: projectId,
      status: filters.status || undefined,
      page: page.value,
      page_size: pageSize,
    })
    contracts.value = data.items || []
    total.value = data.total || 0
  } catch {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

async function handleCreateContract() {
  if (!contractFormRef.value) return
  try {
    await contractFormRef.value.validate()
  } catch {
    return
  }
  loading.value = true
  try {
    await fundLifecycleApi.createContract(contractForm)
    ElMessage.success('创建成功')
    showCreateDialog.value = false
    page.value = 1 // 重置到第1页，确保新建/编辑后的数据可见
    await loadData()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '创建失败')
  } finally {
    loading.value = false
  }
}

function showPaymentDialog(contract: any) {
  currentContractId.value = contract.id
  paymentForm.amount = 0
  paymentForm.payment_date = ''
  paymentForm.purpose = ''
  paymentForm.voucher_no = ''
  paymentDialogVisible.value = true
}

async function handleCreatePayment() {
  if (!paymentForm.amount || !paymentForm.payment_date) {
    ElMessage.warning('请填写金额和日期')
    return
  }
  loading.value = true
  try {
    await fundLifecycleApi.createContractPayment(currentContractId.value, paymentForm)
    ElMessage.success('付款登记成功')
    paymentDialogVisible.value = false
    page.value = 1 // 重置到第1页，确保新建/编辑后的数据可见
    await loadData()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '登记失败')
  } finally {
    loading.value = false
  }
}

async function handleDeleteContract(id: number) {
  try {
    await ElMessageBox.confirm('确认删除此合同？', '确认')
    await fundLifecycleApi.deleteContract(id)
    ElMessage.success('已删除')
    page.value = 1 // 重置到第1页，确保新建/编辑后的数据可见
    await loadData()
  } catch (e: any) {
    if (e !== 'cancel') ElMessage.error(e?.response?.data?.detail || '删除失败')
  }
}

// ========== 合同附件 ==========
async function reloadContractAttachments() {
  try {
    const res: any = await fundLifecycleApi.listContractAttachments(currentContractId.value)
    attachmentList.value = (res?.items ?? res?.data?.items ?? []).map((a: any) => ({
      ...a,
      file_size: a.file_size ?? a.fileSize ?? '',
    }))
  } catch {
    /* 附件列表加载失败不阻塞 */
  }
}

async function showAttachmentDialog(contract: any) {
  currentContractId.value = contract.id
  currentContractName.value = contract.contract_name || contract.contract_no || ''
  attachmentDialogVisible.value = true
  attachmentList.value = []
  await reloadContractAttachments()
}

async function beforeUpload(file: File) {
  const allowedTypes = [
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'image/jpeg',
    'image/png',
  ]
  if (!allowedTypes.includes(file.type)) {
    ElMessage.error('只能上传 pdf/doc/docx/jpg/png 文件!')
    return false
  }
  if (file.size > 10 * 1024 * 1024) {
    ElMessage.error('文件大小不能超过 10MB!')
    return false
  }
  await ensureCsrf()
  return true
}

async function handleUploadSuccess(response: any) {
  const data = response?.data ?? response
  const url = data?.url
  if (!url) {
    ElMessage.error('上传失败：未获取到文件地址')
    return
  }
  try {
    await fundLifecycleApi.uploadContractAttachment(currentContractId.value, {
      url,
      file_name: data.file_name || '',
    })
    // 登记接口只回 {url, file_name} 不回完整列表，成功后必须重拉附件列表上屏
    await reloadContractAttachments()
    ElMessage.success('附件上传成功')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '附件登记失败，请重试')
  }
}

function handleUploadError() {
  ElMessage.error('上传失败')
}

function formatSize(size: any) {
  const num = Number(size)
  if (!num || isNaN(num)) return ''
  if (num < 1024) return `${num}B`
  if (num < 1024 * 1024) return `${(num / 1024).toFixed(1)}KB`
  return `${(num / 1024 / 1024).toFixed(2)}MB`
}

// 带认证拉取文件 blob（后端 JWT 校验，window.open 无法携带 Authorization 头）
async function fetchAttachmentBlob(row: any): Promise<Blob> {
  const raw = row.url || row.download_url || ''
  // /uploads/ 由后端根路径静态托管（不在 /api/v1 前缀下），直接用相对路径，
  // 拼 /api/v1 前缀会 404；dev 环境由 vite 代理 /uploads → 后端
  const url = raw.startsWith('/uploads/') ? raw : `${import.meta.env.VITE_API_BASE_URL || ''}${raw}`
  const token = AuthStorage.getToken()
  const response = await fetch(url, {
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  })
  if (!response.ok) throw new Error('加载失败')
  return response.blob()
}

// 打开附件（图片/PDF 新窗口预览，其余类型触发下载）
async function openAttachment(row: any) {
  try {
    const blob = await fetchAttachmentBlob(row)
    const objectUrl = URL.createObjectURL(blob)
    window.open(objectUrl, '_blank')
    setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000)
  } catch {
    ElMessage.error('附件打开失败')
  }
}

// 下载附件
async function downloadAttachment(row: any) {
  try {
    const blob = await fetchAttachmentBlob(row)
    const objectUrl = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = objectUrl
    link.download = row.file_name || 'attachment'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(objectUrl)
  } catch {
    ElMessage.error('附件下载失败')
  }
}

onMounted(loadData)
</script>

<style scoped>
.contract-container {
  padding: 20px;
}
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.mt-3 {
  margin-top: 12px;
}
.mt-4 {
  margin-top: 16px;
}
.page-title {
  font-size: 18px;
  font-weight: 600;
}
</style>
