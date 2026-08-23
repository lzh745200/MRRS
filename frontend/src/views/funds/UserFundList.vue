<template>
  <div class="fund-list-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-info">
        <h2 class="page-title">经费申请</h2>
        <p class="page-desc">查看和管理您的经费申请记录，提交新申请或跟踪审批进度</p>
      </div>
      <div class="header-actions">
        <el-button type="primary" @click="openApplyDialog">
          <el-icon><EditPen /></el-icon>提交经费申请
        </el-button>
        <el-button @click="pushSafe('/approval/my')">
          <el-icon><Tickets /></el-icon>我的申请
        </el-button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-row">
      <div class="stat-item">
        <div class="stat-value">{{ stats.totalAmount }}</div>
        <div class="stat-label">经费总额(万元)</div>
      </div>
      <div class="stat-item">
        <div class="stat-value text-success">{{ stats.allocatedAmount }}</div>
        <div class="stat-label">已拨付(万元)</div>
      </div>
      <div class="stat-item">
        <div class="stat-value text-warning">{{ stats.pendingCount }}</div>
        <div class="stat-label">待审批</div>
      </div>
      <div class="stat-item">
        <div class="stat-value text-primary">{{ stats.totalCount }}</div>
        <div class="stat-label">记录总数</div>
      </div>
    </div>

    <!-- 搜索筛选 -->
    <div class="filter-card">
      <el-form :model="filterForm" inline>
        <el-form-item label="经费名称">
          <el-input
            v-model="filterForm.keyword"
            placeholder="名称/项目/来源"
            clearable
            style="width: 200px"
            @keyup.enter="handleSearch"
          />
        </el-form-item>
        <el-form-item label="经费类型">
          <el-select
            v-model="filterForm.type"
            placeholder="全部类型"
            clearable
            style="width: 130px"
          >
            <el-option label="项目经费" value="project" />
            <el-option label="运营经费" value="operation" />
            <el-option label="教育帮扶" value="education" />
            <el-option label="基础设施" value="infrastructure" />
            <el-option label="应急经费" value="emergency" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select
            v-model="filterForm.status"
            placeholder="全部状态"
            clearable
            style="width: 130px"
          >
            <el-option label="待审批" value="pending" />
            <el-option label="已计划" value="planned" />
            <el-option label="已批准" value="approved" />
            <el-option label="已拨付" value="allocated" />
            <el-option label="使用中" value="in_use" />
            <el-option label="已完成" value="completed" />
            <el-option label="已驳回" value="rejected" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">
            <el-icon><Search /></el-icon>搜索
          </el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </div>

    <!-- 数据表格 -->
    <div class="table-card">
      <el-table v-loading="loading" :data="tableData" stripe>
        <el-table-column type="index" label="序号" width="60" align="center" />
        <el-table-column prop="name" label="经费名称" min-width="180">
          <template #default="scope">
            <el-link type="primary" @click="handleView(scope.row)">{{ scope.row.name }}</el-link>
          </template>
        </el-table-column>
        <el-table-column prop="type" label="类型" width="110" align="center">
          <template #default="scope">
            <el-tag size="small">{{ getTypeName(scope.row.type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="amount" label="金额(万元)" width="120" align="right">
          <template #default="scope">
            <span class="amount-text">{{ formatAmount(scope.row.amount) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="project_name" label="关联项目" width="160" show-overflow-tooltip>
          <template #default="scope">
            {{ scope.row.project_name || scope.row.project || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="scope">
            <el-tag :type="getStatusType(scope.row.status)" size="small">
              {{ getStatusText(scope.row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="source" label="经费来源" width="120" show-overflow-tooltip />
        <el-table-column prop="date" label="日期" width="110" align="center">
          <template #default="scope">
            {{
              scope.row.date || (scope.row.created_at ? scope.row.created_at.split('T')[0] : '-')
            }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="scope">
            <el-button type="primary" link size="small" @click="handleView(scope.row)"
              >查看</el-button
            >
            <el-button
              v-if="canEdit(scope.row)"
              type="warning"
              link
              size="small"
              @click="openEditDialog(scope.row)"
              >编辑</el-button
            >
            <el-button
              v-if="canDelete(scope.row)"
              type="danger"
              link
              size="small"
              @click="handleDelete(scope.row)"
              >删除</el-button
            >
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50]"
          :total="total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSizeChange"
          @current-change="handlePageChange"
        />
      </div>
    </div>

    <!-- 新增/编辑/申请经费弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="700px"
      :close-on-click-modal="false"
      @close="resetDialogForm"
    >
      <el-form ref="dialogFormRef" :model="dialogForm" :rules="dialogRules" label-width="120px">
        <el-form-item label="经费名称" prop="name">
          <el-input
            v-model="dialogForm.name"
            placeholder="请输入经费名称"
            maxlength="100"
            show-word-limit
          />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="经费类型" prop="type">
              <el-select v-model="dialogForm.type" placeholder="请选择类型" style="width: 100%">
                <el-option label="项目经费" value="project" />
                <el-option label="运营经费" value="operation" />
                <el-option label="教育帮扶" value="education" />
                <el-option label="基础设施" value="infrastructure" />
                <el-option label="应急经费" value="emergency" />
                <el-option label="其他" value="other" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="经费来源" prop="fund_source">
              <el-select
                v-model="dialogForm.fund_source"
                placeholder="请选择经费来源"
                clearable
                style="width: 100%"
              >
                <el-option label="专项投资" value="military" />
                <el-option label="政府拨款" value="government" />
                <el-option label="社会捐赠" value="donation" />
                <el-option label="企业投资" value="enterprise" />
                <el-option label="其他" value="other" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="金额(万元)" prop="amount">
              <el-input-number
                v-model="dialogForm.amount"
                :min="0"
                :precision="4"
                :step="1"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="日期" prop="date">
              <el-date-picker
                v-model="dialogForm.date"
                type="date"
                placeholder="选择日期"
                value-format="YYYY-MM-DD"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="关联帮扶村">
              <el-select
                v-model="dialogForm.village_id"
                placeholder="选择帮扶村（可选）"
                clearable
                filterable
                style="width: 100%"
                :loading="villageLoading"
              >
                <el-option
                  v-for="v in villageOptions"
                  :key="v.id"
                  :label="v.village_name || v.name"
                  :value="v.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="关联帮扶学校">
              <el-select
                v-model="dialogForm.school_id"
                placeholder="选择帮扶学校（可选）"
                clearable
                filterable
                style="width: 100%"
                :loading="schoolLoading"
              >
                <el-option
                  v-for="s in schoolOptions"
                  :key="s.id"
                  :label="s.school_name || s.name"
                  :value="s.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="关联项目">
          <el-input
            v-model="dialogForm.project_name"
            placeholder="可选，填写关联项目名称"
            maxlength="200"
          />
        </el-form-item>
        <el-form-item label="用途说明" prop="purpose">
          <el-input
            v-model="dialogForm.purpose"
            type="textarea"
            :rows="3"
            placeholder="请详细说明经费用途"
            maxlength="500"
            show-word-limit
          />
        </el-form-item>
        <el-form-item label="备注">
          <el-input
            v-model="dialogForm.remarks"
            type="textarea"
            :rows="2"
            placeholder="其他说明（可选）"
            maxlength="200"
            show-word-limit
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmitDialog">
          {{ submitButtonText }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { logger } from '@/utils/logger'

import { ref, reactive, computed, onMounted } from 'vue'
import { useRouterSafe } from '@/composables/useRouterSafe'
import { EditPen, Search, Tickets } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { get, post, put, del, apiRequest } from '@/api/request'
import { useAuthStore } from '@/stores/auth'
import { getSupportedVillages } from '@/api/supportedVillage'
import { schoolsApi } from '@/api/schools'

defineOptions({ name: 'UserFundList' })

const { pushSafe } = useRouterSafe()
const authStore = useAuthStore()

// 检查用户是否有管理权限（管理员、超级管理员；manager 历史角色已归一化为 admin）
const isManager = computed(() => {
  const role = authStore.user?.role || ''
  return ['admin', 'super_admin'].includes(role)
})

// 经费操作权限：与后端 require_funds_operator_role 对齐——viewer 只读，user 及以上可操作
const canOperate = computed(() => {
  const role = authStore.user?.role || ''
  return role !== '' && role !== 'viewer'
})

// 获取当前用户ID
const currentUserId = computed(() => authStore.user?.id)

// 判断是否可以编辑：管理员可编辑所有，普通用户只能编辑自己创建的待审批/驳回状态
function canEdit(row: any): boolean {
  if (!canOperate.value) return false
  if (isManager.value) return true
  // 普通用户：自己创建 AND (待审批状态 OR 驳回状态)
  const editableStatuses = ['pending', 'rejected']
  return row.created_by === currentUserId.value && editableStatuses.includes(row.status)
}

// 判断是否可以删除：与后端一致——非 viewer 可删除待审批(pending)状态经费（普通用户仅限本人创建）
function canDelete(row: any): boolean {
  if (!canOperate.value || row.status !== 'pending') return false
  return isManager.value || row.created_by === currentUserId.value
}
const tableData = ref<any[]>([])
const loading = ref(false)
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)

// 申请/编辑弹窗状态
type DialogMode = 'edit' | 'apply'
const dialogVisible = ref(false)
const dialogMode = ref<DialogMode>('apply')
const editingId = ref<number | null>(null)
const submitting = ref(false)
const dialogFormRef = ref<FormInstance>()
const villageLoading = ref(false)
const schoolLoading = ref(false)
const villageOptions = ref<any[]>([])
const schoolOptions = ref<any[]>([])
const dialogForm = reactive({
  name: '',
  type: '',
  fund_source: '',
  amount: 0,
  village_id: undefined as number | undefined,
  school_id: undefined as number | undefined,
  project_name: '',
  purpose: '',
  remarks: '',
  date: '',
})
const dialogRules: FormRules = {
  name: [{ required: true, message: '请输入经费名称', trigger: 'blur' }],
  type: [{ required: true, message: '请选择经费类型', trigger: 'change' }],
  amount: [{ required: true, message: '请输入金额', trigger: 'blur' }],
}

const dialogTitle = computed(() => (dialogMode.value === 'apply' ? '提交经费申请' : '编辑经费记录'))
const submitButtonText = computed(() => (dialogMode.value === 'apply' ? '提交申请' : '保存修改'))

const filterForm = reactive({
  keyword: '',
  type: '',
  status: '',
})

// 服务端全量统计（优先），回退到当前页数据
const serverFundStats = ref<any>(null)
const stats = computed(() => {
  const s = serverFundStats.value
  if (s) {
    return {
      totalAmount: formatAmount(s.total_amount ?? 0),
      allocatedAmount: formatAmount(s.total_allocated ?? 0),
      pendingCount: s.by_status?.pending?.count ?? 0,
      totalCount: s.total_count ?? total.value,
    }
  }
  // 回退：当前页数据
  const list = tableData.value
  const totalAmount = list.reduce((sum, f) => sum + (Number(f.amount) || 0), 0)
  const allocatedAmount = list
    .filter((f) => f.status === 'allocated' || f.status === 'completed' || f.status === 'audited')
    .reduce((sum, f) => sum + (Number(f.amount) || 0), 0)
  return {
    totalAmount: formatAmount(totalAmount),
    allocatedAmount: formatAmount(allocatedAmount),
    pendingCount: list.filter((f) => f.status === 'pending').length,
    totalCount: total.value || list.length,
  }
})

async function loadFundStats() {
  try {
    const res: any = await get('/funds/statistics/overview')
    // data 显式为 null 表示"无统计"→ 不覆盖已有值（避免 serverFundStats 变成 {data:null}）
    const d = res?.data === null ? null : (res?.data ?? res)
    if (d) serverFundStats.value = d
  } catch {
    /* 统计加载失败不阻塞主流程 */
  }
}

function formatAmount(val: any) {
  const num = Number(val)
  if (isNaN(num)) return '0'
  return num.toLocaleString('zh-CN', {
    maximumFractionDigits: 4,
  })
}

async function fetchData() {
  loading.value = true
  try {
    const response = await apiRequest({
      method: 'GET',
      url: '/funds',
      params: {
        page: currentPage.value,
        page_size: pageSize.value,
        keyword: filterForm.keyword || undefined,
        fund_type: filterForm.type || undefined,
        status: filterForm.status || undefined,
      },
    })
    // 防御：apiRequest 已解包；信封保留 data 键，裸数据直接使用
    const resData = (response as any)?.data ?? response
    tableData.value =
      resData?.items || resData?.data?.items || (Array.isArray(resData) ? resData : [])
    total.value = resData?.total || resData?.data?.total || tableData.value.length
  } catch (e) {
    logger.error('加载数据失败:', e)
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  currentPage.value = 1
  fetchData()
}
function handleReset() {
  filterForm.keyword = ''
  filterForm.type = ''
  filterForm.status = ''
  currentPage.value = 1
  fetchData()
}
function handleSizeChange() {
  currentPage.value = 1
  fetchData()
}
function handlePageChange() {
  fetchData()
}
function handleView(row: any) {
  pushSafe(`/funds/${row.id}`)
}

// 提交经费申请
function openApplyDialog() {
  dialogMode.value = 'apply'
  editingId.value = null
  resetDialogForm()
  dialogVisible.value = true
}

// 编辑经费记录
function openEditDialog(row: any) {
  dialogMode.value = 'edit'
  editingId.value = row.id
  dialogForm.name = row.name || ''
  dialogForm.type = row.type || ''
  dialogForm.fund_source = row.fund_source || ''
  dialogForm.amount = Number(row.amount) || 0
  dialogForm.village_id = row.village_id || undefined
  dialogForm.school_id = row.school_id || undefined
  dialogForm.project_name = row.project_name || row.project || ''
  dialogForm.purpose = row.purpose || ''
  dialogForm.remarks = row.remarks || ''
  dialogForm.date = row.date || (row.created_at ? row.created_at.split('T')[0] : '')
  dialogVisible.value = true
}

function resetDialogForm() {
  dialogForm.name = ''
  dialogForm.type = ''
  dialogForm.fund_source = ''
  dialogForm.amount = 0
  dialogForm.village_id = undefined
  dialogForm.school_id = undefined
  dialogForm.project_name = ''
  dialogForm.purpose = ''
  dialogForm.remarks = ''
  dialogForm.date = ''
  dialogFormRef.value?.resetFields()
}

async function handleSubmitDialog() {
  if (!dialogFormRef.value) return
  await dialogFormRef.value.validate(async (valid) => {
    if (!valid) return
    submitting.value = true
    try {
      const payload: Record<string, any> = {
        name: dialogForm.name,
        type: dialogForm.type,
        amount: dialogForm.amount,
        project_name: dialogForm.project_name || undefined,
        purpose: dialogForm.purpose || undefined,
        remarks: dialogForm.remarks || undefined,
        date: dialogForm.date || undefined,
      }
      if (dialogForm.fund_source) payload.fund_source = dialogForm.fund_source
      if (dialogForm.village_id) payload.village_id = dialogForm.village_id
      if (dialogForm.school_id) payload.school_id = dialogForm.school_id

      if (dialogMode.value === 'apply') {
        await post('/funds/apply', { ...payload, status: 'pending' })
        ElMessage.success('经费申请已提交，等待审批')
      } else if (dialogMode.value === 'edit' && editingId.value) {
        await put(`/funds/${editingId.value}`, payload)
        ElMessage.success('经费记录已更新')
      }
      dialogVisible.value = false
      currentPage.value = 1
      fetchData()
      loadFundStats()
    } catch (e: any) {
      ElMessage.error(e?.response?.data?.detail || e?.message || '操作失败')
    } finally {
      submitting.value = false
    }
  })
}

async function loadVillageOptions() {
  villageLoading.value = true
  try {
    const res = await getSupportedVillages({ page: 1, page_size: 200 })
    const body: any = res.data || res
    const items = body?.items || body?.data?.items || (Array.isArray(body) ? body : [])
    villageOptions.value = items
  } catch {
    /* 非关键路径，静默失败 */
  } finally {
    villageLoading.value = false
  }
}

async function loadSchoolOptions() {
  schoolLoading.value = true
  try {
    const res = await schoolsApi.list({ page: 1, page_size: 200 })
    const body: any = res.data || res
    const items = body?.items || body?.data?.items || (Array.isArray(body) ? body : [])
    schoolOptions.value = items
  } catch {
    /* 非关键路径，静默失败 */
  } finally {
    schoolLoading.value = false
  }
}

async function handleDelete(row: any) {
  try {
    await ElMessageBox.confirm(`确定要删除经费记录「${row.name}」吗？`, '删除确认', {
      type: 'warning',
    })
    await del(`/funds/${row.id}`)
    ElMessage.success('删除成功')
    currentPage.value = 1
    fetchData()
    loadFundStats()
  } catch (error: any) {
    if (error !== 'cancel' && error?.toString?.() !== 'cancel') {
      ElMessage.error(error?.response?.data?.detail || error?.message || '删除失败')
    }
  }
}

function getTypeName(type: string) {
  const m: Record<string, string> = {
    project: '项目经费',
    operation: '运营经费',
    education: '教育帮扶',
    infrastructure: '基础设施',
    emergency: '应急经费',
    other: '其他',
  }
  return m[type] || type || '-'
}
function getStatusType(status: string): 'info' | 'primary' | 'success' | 'warning' | 'danger' {
  const m: Record<string, 'info' | 'primary' | 'success' | 'warning' | 'danger'> = {
    draft: 'info',
    pending: 'warning',
    planned: 'info',
    approved: 'primary',
    allocated: 'primary',
    in_use: 'primary',
    completed: 'success',
    audited: 'success',
    rejected: 'danger',
  }
  return m[status] || 'info'
}
function getStatusText(status: string) {
  const m: Record<string, string> = {
    draft: '草稿',
    pending: '待审批',
    planned: '已计划',
    approved: '已批准',
    allocated: '已拨付',
    in_use: '使用中',
    completed: '已完成',
    audited: '已审计',
    rejected: '已驳回',
  }
  return m[status] || status || '-'
}

onMounted(() => {
  fetchData()
  loadFundStats()
  loadVillageOptions()
  loadSchoolOptions()
})
</script>

<style scoped>
.fund-list-page {
  padding: 20px;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.page-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #1b4332;
}
.page-desc {
  margin: 4px 0 0;
  font-size: 13px;
  color: #666;
}
.header-actions {
  display: flex;
  gap: 10px;
}
.stats-row {
  display: flex;
  gap: 16px;
  margin-bottom: 20px;
}
.stat-item {
  flex: 1;
  background: linear-gradient(135deg, rgba(27, 67, 50, 0.08) 0%, rgba(45, 106, 79, 0.05) 100%);
  border: 1px solid rgba(45, 106, 79, 0.2);
  border-radius: 8px;
  padding: 16px 20px;
  text-align: center;
}
.stat-value {
  font-size: 26px;
  font-weight: 700;
  color: #1b4332;
  line-height: 1.2;
}
.stat-label {
  font-size: 13px;
  color: #666;
  margin-top: 4px;
}
.text-success {
  color: #40916c;
}
.text-primary {
  color: #2d6a4f;
}
.text-warning {
  color: var(--color-warning);
}
.filter-card {
  background: white;
  border-radius: 8px;
  padding: 16px 20px 4px;
  margin-bottom: 20px;
  border: 1px solid #e4e7ed;
}
.table-card {
  background: white;
  border-radius: 8px;
  padding: 20px;
  border: 1px solid #e4e7ed;
}
.amount-text {
  font-weight: 600;
  color: #1b4332;
}
.pagination-wrapper {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
