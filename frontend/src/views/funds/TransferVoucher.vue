<template>
  <div class="voucher-container">
    <el-page-header title="返回" @back="pushSafe('/funds')">
      <template #content><span class="page-title">资金划转凭证</span></template>
    </el-page-header>

    <el-card class="mt-4" shadow="never">
      <div class="toolbar">
        <div class="filters">
          <el-select
            v-model="filters.status"
            placeholder="凭证状态"
            clearable
            size="default"
            style="width: 140px"
            @change="loadData"
          >
            <el-option label="草稿" value="draft" />
            <el-option label="已提交" value="submitted" />
            <el-option label="已确认" value="confirmed" />
            <el-option label="已拒绝" value="rejected" />
          </el-select>
        </div>
        <el-button type="primary" @click="openCreateDialog">新建凭证</el-button>
      </div>

      <el-table v-loading="loading" :data="vouchers" size="default" class="mt-3">
        <el-table-column prop="voucher_no" label="凭证编号" width="160" />
        <el-table-column prop="direction_label" label="划转方向" width="120" />
        <el-table-column prop="amount" label="金额(万元)" width="120" />
        <el-table-column
          prop="payer_account"
          label="付款账户"
          min-width="150"
          show-overflow-tooltip
        />
        <el-table-column
          prop="payee_account"
          label="收款账户"
          min-width="150"
          show-overflow-tooltip
        />
        <el-table-column prop="transfer_date" label="划转日期" width="120" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag
              :type="
                row.status === 'confirmed'
                  ? 'success'
                  : row.status === 'rejected'
                    ? 'danger'
                    : 'info'
              "
              size="small"
            >
              {{ row.status_label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'draft' || row.status === 'submitted'"
              size="small"
              type="success"
              @click="handleConfirm(row.id)"
              >确认</el-button
            >
            <el-button
              v-if="row.status === 'draft'"
              size="small"
              type="danger"
              @click="handleDelete(row.id)"
              >删除</el-button
            >
            <el-upload
              :show-file-list="false"
              :http-request="(opt: any) => handleVoucherUpload(row.id, opt.file as File)"
              accept=".pdf,.jpg,.jpeg,.png"
            >
              <el-button size="small" type="primary" link :loading="uploadingId === row.id"
                >凭证上传</el-button
              >
            </el-upload>
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

    <!-- 新建对话框 -->
    <el-dialog v-model="showCreateDialog" title="新建转账凭证" width="720px">
      <el-form ref="formRef" :model="form" :rules="formRules" label-width="100px">
        <el-form-item label="凭证编号" prop="voucher_no" required
          ><el-input v-model="form.voucher_no"
        /></el-form-item>
        <el-form-item label="转账方向" prop="direction" required>
          <el-radio-group v-model="form.direction">
            <el-radio value="military_to_local">专项资金发地方</el-radio>
            <el-radio value="local_to_military">地方拨专项资金</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="金额(万元)" prop="amount" required
          ><el-input-number v-model="form.amount" :min="0.01" :precision="4"
        /></el-form-item>
        <el-form-item label="付款账户" prop="payer_account"
          ><el-input v-model="form.payer_account"
        /></el-form-item>
        <el-form-item label="收款账户" prop="payee_account"
          ><el-input v-model="form.payee_account"
        /></el-form-item>
        <el-form-item label="转账日期" prop="transfer_date"
          ><el-date-picker v-model="form.transfer_date" type="date" value-format="YYYY-MM-DD"
        /></el-form-item>
        <el-form-item label="备注"
          ><el-input v-model="form.remarks" type="textarea"
        /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" :loading="loading" @click="handleCreate">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { fundLifecycleApi } from '@/api/fundLifecycle'
import { safeRouteParam, useRouterSafe } from '@/composables/useRouterSafe'
import { logger } from '@/utils/logger'

const { pushSafe } = useRouterSafe()
const route = useRoute()
const projectId = route.query.project_id ? safeRouteParam(route.query.project_id) : undefined

const loading = ref(false)
const vouchers = ref<any[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const filters = reactive({ status: '' })
const showCreateDialog = ref(false)
const formRef = ref<FormInstance | null>(null)
const form = reactive({
  voucher_no: '',
  direction: 'military_to_local',
  amount: 0,
  payer_account: '',
  payee_account: '',
  transfer_date: '',
  remarks: '',
  project_id: projectId,
  fund_id: undefined as number | undefined,
})

const formRules: FormRules = {
  voucher_no: [{ required: true, message: '请填写凭证编号', trigger: 'blur' }],
  direction: [{ required: true, message: '请选择转账方向', trigger: 'change' }],
  amount: [{ required: true, message: '请填写金额', trigger: 'blur' }],
  payer_account: [{ required: false }],
  payee_account: [{ required: false }],
}

const uploadingId = ref<number | null>(null)

async function handleVoucherUpload(voucherId: number, file: File) {
  uploadingId.value = voucherId
  try {
    await fundLifecycleApi.uploadVoucherAttachment(voucherId, file)
    ElMessage.success('凭证附件已上传')
  } catch (e) {
    logger.error('凭证附件上传失败:', e)
    ElMessage.error('上传失败，请稍后重试')
  } finally {
    uploadingId.value = null
  }
}

async function loadData() {
  loading.value = true
  try {
    const data = await fundLifecycleApi.listTransferVouchers({
      project_id: projectId,
      status: filters.status || undefined,
      page: page.value,
      page_size: pageSize,
    })
    vouchers.value = data.items || []
    total.value = data.total || 0
  } catch (e: any) {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

// 新建凭证：每次打开都重置为空白表单（防止残留上次已新增的内容）
function openCreateDialog() {
  Object.assign(form, {
    voucher_no: '',
    direction: 'military_to_local',
    amount: 0,
    payer_account: '',
    payee_account: '',
    transfer_date: '',
    remarks: '',
    fund_id: undefined,
  })
  // 防御：测试环境/未挂载时 formRef 可能为空对象
  if (formRef.value && typeof formRef.value.clearValidate === 'function') {
    formRef.value.clearValidate()
  }
  showCreateDialog.value = true
}

async function handleCreate() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch {
    return
  }
  loading.value = true
  try {
    await fundLifecycleApi.createTransferVoucher(form)
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

async function handleConfirm(id: number) {
  try {
    await ElMessageBox.confirm('确认该凭证？', '确认')
    await fundLifecycleApi.confirmTransferVoucher(id)
    ElMessage.success('已确认')
    page.value = 1 // 重置到第1页，确保新建/编辑后的数据可见
    await loadData()
  } catch (e: any) {
    if (e !== 'cancel') ElMessage.error(e?.response?.data?.detail || '确认失败')
  }
}

async function handleDelete(id: number) {
  try {
    await ElMessageBox.confirm('确认删除？', '确认')
    await fundLifecycleApi.deleteTransferVoucher(id)
    ElMessage.success('已删除')
    page.value = 1 // 重置到第1页，确保新建/编辑后的数据可见
    await loadData()
  } catch (e: any) {
    if (e !== 'cancel') ElMessage.error(e?.response?.data?.detail || '删除失败')
  }
}

onMounted(loadData)
</script>

<style scoped>
.voucher-container {
  padding: 20px;
}
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.filters {
  display: flex;
  gap: 8px;
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
