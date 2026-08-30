<template>
  <div class="subordinate-management">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>下级单位管理</span>
          <div>
            <el-button size="small" @click="handleImportReport">导入上报包</el-button>
            <el-button size="small" type="primary" @click="showRegisterDialog = true"
              >注册下级单位</el-button
            >
          </div>
        </div>
      </template>

      <el-table v-loading="loading" :data="instances" stripe>
        <el-table-column
          prop="instanceCode"
          label="实例标识"
          min-width="140"
          show-overflow-tooltip
        />
        <el-table-column prop="organizationId" label="组织ID" width="80" />
        <el-table-column prop="systemVersion" label="版本" width="90" />
        <el-table-column prop="licenseStatus" label="授权状态" width="100">
          <template #default="{ row }">
            <el-tag :type="licenseTagType(row.licenseStatus)" size="small">{{
              licenseLabel(row.licenseStatus)
            }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="在线状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.status === 'online' ? 'success' : 'info'" size="small">{{
              row.status === 'online' ? '在线' : '离线'
            }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="userCount" label="用户数" width="80" />
        <el-table-column prop="lastReportAt" label="最后上报" width="160" show-overflow-tooltip />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button
              link
              size="small"
              type="primary"
              @click="handleGeneratePackage(row as SubordinateInstance)"
              >生成管控包</el-button
            >
            <el-button
              link
              size="small"
              type="warning"
              @click="handleToggleLicense(row as SubordinateInstance)"
            >
              {{ (row as SubordinateInstance).licenseStatus === 'active' ? '撤销' : '授权' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-if="total > pageSize"
        :current-page="page"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        style="margin-top: 16px; justify-content: flex-end"
        @current-change="handlePageChange"
      />
    </el-card>

    <!-- 注册对话框 -->
    <el-dialog v-model="showRegisterDialog" append-to-body title="注册下级单位" :width="DIALOG_SM">
      <el-form :model="registerForm" label-width="100px">
        <el-form-item label="组织ID" required>
          <el-input-number v-model="registerForm.organization_id" :min="1" />
        </el-form-item>
        <el-form-item label="实例标识" required>
          <el-input
            v-model="registerForm.instance_code"
            placeholder="下级系统唯一标识（至少8位）"
          />
        </el-form-item>
        <el-form-item label="机器码">
          <el-input v-model="registerForm.machine_code" placeholder="可选" />
        </el-form-item>
        <el-form-item label="授权到期">
          <el-date-picker
            v-model="registerForm.license_expiry"
            type="date"
            placeholder="可选"
            value-format="YYYY-MM-DD"
          />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="registerForm.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showRegisterDialog = false">取消</el-button>
        <el-button type="primary" :loading="registering" @click="handleRegister"
          >确认注册</el-button
        >
      </template>
    </el-dialog>

    <!-- 隐藏的文件输入 -->
    <input
      ref="fileInputRef"
      type="file"
      accept=".zip"
      style="display: none"
      @change="handleFileSelected"
    />
  </div>
</template>

<script setup lang="ts">
import { DIALOG_SM } from '@/config/dialog'
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { get, post, put } from '@/api/request'

interface SubordinateInstance {
  id: number
  instanceCode: string
  organizationId: number
  systemVersion: string | null
  licenseStatus: string
  status: string
  userCount: number
  lastReportAt: string | null
}

const instances = ref<SubordinateInstance[]>([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const showRegisterDialog = ref(false)
const registering = ref(false)
const fileInputRef = ref<HTMLInputElement>()

const registerForm = ref({
  organization_id: 1,
  instance_code: '',
  machine_code: '',
  license_expiry: null as string | null,
  remark: '',
})

function licenseTagType(status: string): 'primary' | 'success' | 'warning' | 'info' | 'danger' {
  const map: Record<string, 'primary' | 'success' | 'warning' | 'info' | 'danger'> = {
    active: 'success',
    pending: 'warning',
    expired: 'danger',
    revoked: 'info',
  }
  return map[status] || 'info'
}

function licenseLabel(status: string) {
  const map: Record<string, string> = {
    active: '已授权',
    pending: '待授权',
    expired: '已过期',
    revoked: '已撤销',
  }
  return map[status] || status
}

async function loadData() {
  loading.value = true
  try {
    const res = await get('/subordinates', { page: page.value, page_size: pageSize.value })
    const data = res.data || res
    instances.value = data.items || []
    total.value = data.total || 0
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

function handlePageChange(p: number) {
  page.value = p
  loadData()
}

async function handleRegister() {
  if (!registerForm.value.instance_code || registerForm.value.instance_code.length < 8) {
    ElMessage.warning('实例标识至少8位')
    return
  }
  registering.value = true
  try {
    await post('/subordinates', registerForm.value)
    ElMessage.success('注册成功')
    showRegisterDialog.value = false
    registerForm.value = {
      organization_id: 1,
      instance_code: '',
      machine_code: '',
      license_expiry: null,
      remark: '',
    }
    page.value = 1 // 重置到第1页，确保新建/编辑后的数据可见
    await loadData()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '注册失败')
  } finally {
    registering.value = false
  }
}

async function handleToggleLicense(row: SubordinateInstance) {
  const newStatus = row.licenseStatus === 'active' ? 'revoked' : 'active'
  const action = newStatus === 'active' ? '授权' : '撤销授权'
  try {
    await ElMessageBox.confirm(`确认${action}该下级单位？`, '提示', { type: 'warning' })
    // 后端授权/撤销接口为 PUT /subordinates/{id}（POST 会 405 静默失败）
    await put(`/subordinates/${row.id}`, { license_status: newStatus })
    ElMessage.success(`${action}成功`)
    page.value = 1 // 重置到第1页，确保新建/编辑后的数据可见
    await loadData()
  } catch {
    // 用户取消
  }
}

async function handleGeneratePackage(row: SubordinateInstance) {
  try {
    await post('/control-packages/generate', { organization_id: row.organizationId })
    ElMessage.success('管控配置包已生成，请下载')
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '生成失败')
  }
}

function handleImportReport() {
  fileInputRef.value?.click()
}

async function handleFileSelected(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return

  const formData = new FormData()
  formData.append('file', file)

  try {
    const res = await post('/subordinate-reports/import', formData)
    const data = res.data || res
    ElMessage.success(data.message || '上报包导入成功')
    page.value = 1 // 重置到第1页，确保新建/编辑后的数据可见
    await loadData()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '导入失败')
  } finally {
    input.value = ''
  }
}

onMounted(loadData)
</script>

<style lang="scss" scoped>
.subordinate-management {
  padding: 20px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
