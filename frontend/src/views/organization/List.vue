<template>
  <div class="organization-list-page">
    <!-- 统计卡片 -->
    <div class="stats-row">
      <el-card v-loading="statsLoading" shadow="hover" class="stat-card">
        <div class="stat-content">
          <div class="stat-icon" style="background: var(--color-primary-light-8)">
            <el-icon :size="24" color="var(--color-primary)"><OfficeBuilding /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.total || 0 }}</div>
            <div class="stat-label">组织总数</div>
          </div>
        </div>
      </el-card>
      <el-card shadow="hover" class="stat-card">
        <div class="stat-content">
          <div class="stat-icon" style="background: #e8f5e9">
            <el-icon :size="24" color="#4caf50"><CircleCheck /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.active || 0 }}</div>
            <div class="stat-label">正常运作</div>
          </div>
        </div>
      </el-card>
      <el-card shadow="hover" class="stat-card">
        <div class="stat-content">
          <div class="stat-icon" style="background: #e3f2fd">
            <el-icon :size="24" color="#2196f3"><User /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.total_members || 0 }}</div>
            <div class="stat-label">总成员数</div>
          </div>
        </div>
      </el-card>
      <el-card shadow="hover" class="stat-card">
        <div class="stat-content">
          <div class="stat-icon" style="background: #fff3e0">
            <el-icon :size="24" color="#ff9800"><Share /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.orgs_with_members || 0 }}</div>
            <div class="stat-label">已分配成员</div>
          </div>
        </div>
      </el-card>
    </div>

    <el-card>
      <template #header>
        <div class="page-header">
          <span class="page-title">组织管理</span>
          <div class="header-actions">
            <el-input
              v-model="searchText"
              placeholder="搜索组织名称/编码..."
              clearable
              style="width: 220px; margin-right: 10px"
              @clear="handleSearch"
              @keyup.enter="handleSearch"
            />
            <el-select
              v-model="filterType"
              placeholder="全部类型"
              clearable
              style="width: 140px; margin-right: 10px"
              @change="handleSearch"
            >
              <el-option label="部门单位" value="department" />
              <el-option label="帮扶单位" value="support_unit" />
            </el-select>
            <el-button v-if="isAdmin" :loading="exporting" @click="handleExport">
              <el-icon><Download /></el-icon>
              <span>导出</span>
            </el-button>
            <el-button v-if="isAdmin" type="primary" @click="handleCreate">
              <el-icon><Plus /></el-icon>
              <span>新增组织</span>
            </el-button>
          </div>
        </div>
      </template>

      <div v-if="isAdmin && !searchText && !filterType" class="drag-tip">
        <el-alert title="拖拽提示" type="info" :closable="false" show-icon>
          <template #default> 可以通过拖拽表格行来调整组织排序，松开鼠标后自动保存 </template>
        </el-alert>
      </div>

      <el-table ref="tableRef" v-loading="loading" :data="tableData" border stripe row-key="id">
        <el-table-column type="index" label="序号" width="60" />
        <el-table-column prop="name" label="组织名称" min-width="180">
          <template #default="scope">
            <span class="org-name-link" @click="handleViewDetail(scope.row)">{{
              scope.row.name
            }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="code" label="编码" width="120" />
        <el-table-column prop="org_type" label="类型" width="120">
          <template #default="scope">
            <el-tag v-if="scope.row.org_type === 'department'" type="primary">部门单位</el-tag>
            <el-tag v-else-if="scope.row.org_type === 'support_unit'" type="success"
              >帮扶单位</el-tag
            >
            <el-tag v-else type="info">{{ scope.row.org_type || '未设置' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="level" label="层级" width="100">
          <template #default="scope">
            <el-tag size="small" type="info">{{ formatLevel(scope.row.level) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="contact_person" label="联系人" width="100" show-overflow-tooltip />
        <el-table-column prop="contact_phone" label="联系电话" width="130" show-overflow-tooltip />
        <el-table-column prop="is_active" label="状态" width="80" align="center">
          <template #default="scope">
            <el-tag :type="scope.row.is_active ? 'success' : 'info'" size="small">
              {{ scope.row.is_active ? '正常' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="sort_order" label="排序" width="70" align="center" />
        <el-table-column v-if="isAdmin" label="操作" width="260" fixed="right">
          <template #default="scope">
            <el-button size="small" @click="handleViewDetail(scope.row)">详情</el-button>
            <el-button size="small" type="primary" @click="handleEdit(scope.row)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(scope.row)">删除</el-button>
          </template>
        </el-table-column>
        <el-table-column v-else label="操作" width="100" fixed="right">
          <template #default="scope">
            <el-button size="small" @click="handleViewDetail(scope.row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-if="total > pageSize"
        :current-page="currentPage"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        style="margin-top: 16px; justify-content: flex-end"
        @current-change="handlePageChange"
      />
    </el-card>

    <!-- 新增/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="640px"
      @close="handleDialogClose"
    >
      <el-form ref="formRef" :model="formData" :rules="formRules" label-width="100px">
        <el-form-item label="组织名称" prop="name">
          <el-input v-model="formData.name" placeholder="请输入组织名称" />
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="上级组织" prop="parent_id">
              <el-select
                v-model="formData.parent_id"
                placeholder="选择上级组织"
                clearable
                filterable
                style="width: 100%"
              >
                <el-option label="无（顶级组织）" :value="null as any" />
                <el-option
                  v-for="org in parentOrgOptions"
                  :key="org.id"
                  :label="org.name"
                  :value="org.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="组织类型" prop="org_type">
              <el-select v-model="formData.org_type" placeholder="选择组织类型" style="width: 100%">
                <el-option label="部门单位" value="department" />
                <el-option label="帮扶单位" value="support_unit" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="联系人">
              <el-input v-model="formData.contact_person" placeholder="请输入联系人" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="联系电话">
              <el-input v-model="formData.contact_phone" placeholder="请输入联系电话" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="地址">
          <el-input v-model="formData.address" placeholder="请输入地址" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input
            v-model="formData.description"
            type="textarea"
            :rows="3"
            placeholder="请输入组织描述"
          />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="formData.is_active" active-text="正常" inactive-text="停用" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { logger } from '@/utils/logger'

import { ref, onMounted, computed, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { OfficeBuilding, CircleCheck, User, Share, Download, Plus } from '@element-plus/icons-vue'
import { post, put, del, apiRequest } from '@/api/request'
import type { FormInstance, FormRules } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { useRouterSafe } from '@/composables/useRouterSafe'
import Sortable from 'sortablejs'
import { batchUpdateSortOrders } from '@/api/organization'

const { pushSafe } = useRouterSafe()

// 获取认证状态
const authStore = useAuthStore()
const isAdmin = computed(() => authStore.isAdmin)

const tableRef = ref()
const tableData = ref<any[]>([])
const loading = ref(false)
const searchText = ref('')
const filterType = ref('')
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
let sortableInstance: Sortable | null = null

// 统计数据
const stats = ref({
  total: 0,
  active: 0,
  inactive: 0,
  total_members: 0,
  orgs_with_members: 0,
})
const statsLoading = ref(false)
const exporting = ref(false)

// 对话框相关
const dialogVisible = ref(false)
const dialogTitle = computed(() => (formData.value.id ? '编辑组织' : '新增组织'))
const submitting = ref(false)
const formRef = ref<FormInstance>()
const formData = ref({
  id: null as number | null,
  name: '',
  parent_id: null as number | null,
  org_type: 'department',
  description: '',
  contact_person: '',
  contact_phone: '',
  address: '',
  is_active: true,
})

const formRules: FormRules = {
  name: [{ required: true, message: '请输入组织名称', trigger: 'blur' }],
  org_type: [{ required: true, message: '请选择组织类型', trigger: 'change' }],
}

// 格式化层级显示
function formatLevel(level: any): string {
  if (!level) return '未设置'
  const levelStr = String(level)
  const match = levelStr.match(/level_(\d+)/)
  if (match) return `第${match[1]}级`
  return levelStr
}

// 收集某组织及其所有后代的 id（当前页内），用于父级选项过滤
function collectDescendantIds(rootId: number, orgs: any[]): Set<number> {
  const ids = new Set<number>([rootId])
  let changed = true
  while (changed) {
    changed = false
    for (const org of orgs) {
      if (!ids.has(org.id) && org.parent_id !== null && ids.has(org.parent_id)) {
        ids.add(org.id)
        changed = true
      }
    }
  }
  return ids
}

// 上级组织选项（排除当前编辑的组织及其所有后代，防止形成循环层级）
const parentOrgOptions = computed(() => {
  if (!formData.value.id) return tableData.value
  const excluded = collectDescendantIds(formData.value.id, tableData.value)
  return tableData.value.filter((org) => !excluded.has(org.id))
})

async function fetchStats() {
  statsLoading.value = true
  try {
    const res = await apiRequest({
      method: 'GET',
      url: '/organizations/statistics/summary',
    })
    const data = res.data?.data || res.data
    stats.value = {
      total: data?.total || 0,
      active: data?.active || 0,
      inactive: data?.inactive || 0,
      total_members: data?.total_members || 0,
      orgs_with_members: data?.orgs_with_members || 0,
    }
  } catch {
    // 静默失败
  } finally {
    statsLoading.value = false
  }
}

async function fetchData() {
  loading.value = true
  try {
    const response = await apiRequest({
      method: 'GET',
      url: '/organizations',
      params: {
        page: currentPage.value,
        page_size: pageSize.value,
        search: searchText.value || undefined,
        org_type: filterType.value || undefined,
        is_active: true,
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
  fetchDataWithSort()
}
function handlePageChange(page: number) {
  currentPage.value = page
  fetchDataWithSort()
}

function handleCreate() {
  formData.value = {
    id: null,
    name: '',
    parent_id: null,
    org_type: 'department',
    description: '',
    contact_person: '',
    contact_phone: '',
    address: '',
    is_active: true,
  }
  dialogVisible.value = true
}

function handleEdit(row: any) {
  formData.value = {
    id: row.id,
    name: row.name || '',
    parent_id: row.parent_id || null,
    org_type: row.org_type || row.type || 'department',
    description: row.description || '',
    contact_person: row.contact_person || '',
    contact_phone: row.contact_phone || '',
    address: row.address || '',
    is_active: row.is_active !== false,
  }
  dialogVisible.value = true
}

function handleViewDetail(row: any) {
  pushSafe(`/organizations/${row.id}`)
}

function handleDialogClose() {
  formRef.value?.resetFields()
}

async function handleSubmit() {
  if (!formRef.value) return

  try {
    await formRef.value.validate()
  } catch {
    return
  }

  submitting.value = true
  try {
    const payload: Record<string, any> = { ...formData.value }
    delete payload.id

    if (formData.value.id) {
      await put(`/organizations/${formData.value.id}`, payload)
      // 成功静默：保存成功仅刷新列表
    } else {
      await post('/organizations', payload)
      ElMessage.success('已创建')
    }

    dialogVisible.value = false
    currentPage.value = 1
    fetchDataWithSort()
    fetchStats()
  } catch (err: any) {
    ElMessage.error(err.message || '操作失败')
  } finally {
    submitting.value = false
  }
}

async function handleDelete(row: any) {
  let confirmPassword = ''
  try {
    const { value } = await ElMessageBox.prompt(
      `确认删除组织"${row.name}"？\n\n` +
        '删除后该组织将被停用，不再显示在系统中。\n' +
        '如有子组织，请先删除子组织。\n\n' +
        '⚠️ 敏感操作：请输入当前登录用户的密码进行二次确认。',
      '删除组织',
      {
        type: 'warning',
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
        inputType: 'password',
        inputPlaceholder: '请输入当前用户密码',
        inputValidator: (v: string) => (v && v.trim() ? true : '请输入密码'),
      }
    )
    confirmPassword = value?.trim() ?? ''

    const response = await del(
      `/organizations/${row.id}?confirm_password=${encodeURIComponent(confirmPassword)}`
    )
    // del() 已自动解包（返回 res.data），message 在顶层
    ElMessage.success((response as any)?.message || '组织已删除')
    currentPage.value = 1
    await fetchDataWithSort()
    fetchStats()
  } catch (err: any) {
    if (err !== 'cancel' && err?.toString() !== 'cancel') {
      const detail = err?.response?.data?.detail || err?.message || '删除失败'
      ElMessage.error(detail)
    }
  }
}

async function handleExport() {
  exporting.value = true
  try {
    // apiRequest with responseType:'blob' returns the Blob directly (res.data = Blob)
    const blobData = await apiRequest({
      method: 'GET',
      url: '/organizations/export/list',
      responseType: 'blob',
      params: {
        org_type: filterType.value || undefined,
      },
    })
    const blob = new Blob([blobData], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = '组织机构列表.xlsx'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch (err: any) {
    ElMessage.error('导出失败')
  } finally {
    exporting.value = false
  }
}

// 初始化拖拽排序
function initSortable() {
  if (sortableInstance) {
    sortableInstance.destroy()
    sortableInstance = null
  }

  if (!isAdmin.value || searchText.value || filterType.value) {
    return
  }

  nextTick(() => {
    const tbody = tableRef.value?.$el.querySelector('.el-table__body-wrapper tbody')
    if (!tbody) return

    sortableInstance = Sortable.create(tbody, {
      animation: 150,
      handle: 'tr',
      onEnd: async (evt: any) => {
        const { oldIndex, newIndex } = evt
        if (oldIndex === newIndex) return

        const movedItem = tableData.value.splice(oldIndex, 1)[0]
        tableData.value.splice(newIndex, 0, movedItem)

        const sortItems = tableData.value.map((item, index) => ({
          id: item.id,
          sort_order: index + 1,
        }))

        try {
          await batchUpdateSortOrders(sortItems)
          ElMessage.success('排序已保存')
        } catch (error: any) {
          logger.error('保存排序失败', error)
          ElMessage.error(error.response?.data?.detail || '保存排序失败')
          await fetchData()
        }
      },
    })
  })
}

async function fetchDataWithSort() {
  await fetchData()
  initSortable()
}

onMounted(() => {
  fetchDataWithSort()
  fetchStats()
})
</script>

<style scoped>
.organization-list-page {
  padding: 20px;
}

/* 统计卡片 */
.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}
.stat-card {
  cursor: default;
}
.stat-content {
  display: flex;
  align-items: center;
  gap: 12px;
}
.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.stat-info {
  flex: 1;
}
.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: #1b4332;
  line-height: 1.2;
}
.stat-label {
  font-size: 13px;
  color: #909399;
  margin-top: 4px;
}

/* 表格 */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.page-title {
  font-size: 16px;
  font-weight: bold;
}
.header-actions {
  display: flex;
  align-items: center;
}
.drag-tip {
  margin-bottom: 16px;
}
.org-name-link {
  color: var(--color-primary);
  cursor: pointer;
  font-weight: 500;
}
.org-name-link:hover {
  text-decoration: underline;
}

/* 拖拽样式 */
:deep(.sortable-ghost) {
  opacity: 0.4;
  background: var(--color-primary-light-8);
}
:deep(.el-table__body-wrapper tbody tr) {
  cursor: move;
}

/* 响应式 */
@media (max-width: 992px) {
  .stats-row {
    grid-template-columns: repeat(2, 1fr);
  }
}
@media (max-width: 576px) {
  .stats-row {
    grid-template-columns: 1fr;
  }
}
</style>
