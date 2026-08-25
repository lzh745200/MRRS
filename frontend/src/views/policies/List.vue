<template>
  <div class="policies-list">
    <!-- 搜索筛选卡片 -->
    <el-card class="search-card">
      <el-form :inline="true" :model="searchForm" @submit.prevent="handleSearch">
        <el-form-item label="政策名称">
          <el-input
            v-model="searchForm.title"
            placeholder="请输入关键词"
            clearable
            @clear="handleSearch"
          />
        </el-form-item>
        <el-form-item label="政策分类">
          <el-select
            v-model="searchForm.category"
            placeholder="请选择"
            clearable
            style="width: 140px"
            @change="handleCategoryChange"
          >
            <el-option label="专项政策" value="military" />
            <el-option label="地方政策" value="local" />
          </el-select>
        </el-form-item>
        <el-form-item label="组织层级">
          <el-select
            v-model="searchForm.organization_level"
            placeholder="请选择"
            clearable
            style="width: 140px"
            :disabled="!searchForm.category"
          >
            <el-option
              v-for="level in levelOptions"
              :key="level.value"
              :label="level.label"
              :value="level.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select
            v-model="searchForm.status"
            placeholder="请选择"
            clearable
            style="width: 140px"
          >
            <el-option label="有效" value="active" />
            <el-option label="失效" value="invalid" />
            <el-option label="草稿" value="draft" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">
            <el-icon><Search /></el-icon>
            查询
          </el-button>
          <el-button @click="handleReset">
            <el-icon><Refresh /></el-icon>
            重置
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 数据表格卡片 -->
    <el-card class="table-card">
      <template #header>
        <div class="card-header">
          <span class="title">政策列表</span>
          <div class="actions">
            <el-button type="info" plain @click="handleDownloadTemplate">
              <el-icon><Download /></el-icon>
              下载模板
            </el-button>
            <el-button v-if="canEdit" @click="handleImport">
              <el-icon><Upload /></el-icon>
              导入
            </el-button>
            <el-button @click="handleExportPDF">
              <el-icon><Download /></el-icon>
              导出PDF
            </el-button>
            <el-button @click="handleExportWPS">
              <el-icon><Download /></el-icon>
              导出WPS
            </el-button>
            <el-button
              v-if="canDelete"
              type="danger"
              :disabled="selectedIds.length === 0"
              @click="handleBatchDelete"
            >
              <el-icon><Delete /></el-icon>
              批量删除 ({{ selectedIds.length }})
            </el-button>
            <el-button v-if="canEdit" type="primary" @click="handleAdd">
              <el-icon><Plus /></el-icon>
              新增政策
            </el-button>
          </div>
        </div>
      </template>

      <!-- 加载失败占位 -->
      <el-result
        v-if="loadError"
        icon="error"
        title="加载失败"
        sub-title="政策列表加载失败，请检查网络或稍后重试"
      >
        <template #extra>
          <el-button type="primary" @click="loadData">重试</el-button>
        </template>
      </el-result>

      <el-table
        v-else
        v-loading="policyStore.loading"
        :data="policiesData"
        stripe
        border
        @sort-change="handleSortChange"
        @selection-change="handleSelectionChange"
      >
        <el-table-column v-if="canDelete" type="selection" width="50" align="center" />
        <el-table-column type="index" label="序号" width="60" align="center" />
        <el-table-column prop="title" label="政策名称" min-width="200" show-overflow-tooltip />
        <el-table-column label="文号" width="150" show-overflow-tooltip>
          <template #default="{ row }">{{ row.document_number || row.code || '-' }}</template>
        </el-table-column>
        <el-table-column prop="category_name" label="政策分类" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.category === 'military' ? 'danger' : 'primary'">
              {{ row.category_name || getCategoryLabel(row.category) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="level_name" label="组织层级" width="100" align="center">
          <template #default="{ row }">
            {{ row.level_name || getLevelLabel(row.category, row.organization_level) }}
          </template>
        </el-table-column>
        <el-table-column prop="publish_date" label="发布日期" width="120" sortable="custom">
          <template #default="{ row }">
            {{ formatDate(row.publish_date) }}
          </template>
        </el-table-column>
        <el-table-column prop="department" label="发布部门" min-width="150" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusTagType(row.status)">
              {{ row.status_name || getStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="260" align="center" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" size="small" link @click="handleDetail(row)">
              详情
            </el-button>
            <el-button v-if="canEdit" type="warning" size="small" link @click="handleEdit(row)">
              编辑
            </el-button>
            <el-button v-if="canDelete" type="danger" size="small" link @click="handleDelete(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="policyStore.total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        class="pagination"
        @size-change="handleSizeChange"
        @current-change="handlePageChange"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { logger } from '@/utils/logger'

import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useRouterSafe } from '@/composables/useRouterSafe'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search, Refresh, Upload, Download, Delete } from '@element-plus/icons-vue'
import { usePolicyStore } from '@/stores/policy'
import { useAuthStore } from '@/stores/auth'
import {
  getCategoryLabel,
  getLevelLabel as _getLevelLabel,
  getStatusLabel,
  getStatusColor,
  getLevelOptions,
  importPolicies,
  exportPoliciesPDF,
  exportPoliciesWPS,
  type PolicyCategory,
  type PolicyStatus,
} from '@/api/policy'
import { downloadImportTemplateAndSave } from '@/api/import'

type OrganizationLevel = string

// Wrapper: API defines getLevelLabel(level) but view calls it with (category, level)
const getLevelLabel = (...args: any[]): string => (_getLevelLabel as any)(...args)

// Typed wrapper for el-tag :type (getStatusColor returns `string`, el-tag expects a union)
type ElTagType = 'success' | 'warning' | 'danger' | 'info' | 'primary' | undefined
const getStatusTagType = (status: string): ElTagType =>
  (getStatusColor(status) || undefined) as ElTagType

const { pushSafe } = useRouterSafe()
const route = useRoute()
const policyStore = usePolicyStore()
const authStore = useAuthStore()

// Store uses different property names; bridge with computed
const policiesData = computed(() => (policyStore as any).policyList ?? [])
const loadError = ref(false)

// 搜索表单
const searchForm = reactive({
  title: '',
  category: '' as PolicyCategory | '',
  organization_level: '' as OrganizationLevel | '',
  status: '' as PolicyStatus | '',
})

// 分页
const currentPage = ref(1)
const pageSize = ref(10)

// 批量选择
const selectedIds = ref<number[]>([])
const handleSelectionChange = (rows: any[]) => {
  selectedIds.value = rows.map((r) => r.id)
}

// 权限检查（2026-08-15）：政策法规对普通用户与管理员完全一致，全部可增删改
const canEdit = computed(() => !!authStore.user)
const canDelete = computed(() => !!authStore.user)

// 层级选项（根据分类动态变化）——getLevelOptions 返回 Promise，必须异步填充
const levelOptions = ref<Array<{ value: string; label: string }>>([])
let levelOptionsRequestId = 0

async function refreshLevelOptions() {
  const category = searchForm.category
  if (!category) {
    levelOptions.value = []
    return
  }
  const reqId = ++levelOptionsRequestId
  try {
    const res: any = await getLevelOptions()
    // 兼容信封/裸数组/嵌套 data.data
    const nested = res?.data?.data
    let list: any = []
    if (Array.isArray(res)) list = res
    else if (res?.items) list = res.items
    else if (Array.isArray(res?.data)) list = res.data
    else if (Array.isArray(nested)) list = nested
    if (reqId === levelOptionsRequestId) levelOptions.value = list
  } catch {
    if (reqId === levelOptionsRequestId) levelOptions.value = []
  }
}

// 格式化日期
const formatDate = (dateStr: string) => {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleDateString('zh-CN')
}

// 分类变化时清空层级选择并异步加载层级选项
const handleCategoryChange = () => {
  searchForm.organization_level = ''
  refreshLevelOptions()
}

// 搜索
const handleSearch = () => {
  currentPage.value = 1
  loadData()
}

// 重置
const handleReset = () => {
  Object.assign(searchForm, {
    title: '',
    category: '',
    organization_level: '',
    status: '',
  })
  policyStore.setFilters({}) // 清空 store 残留排序等筛选条件
  currentPage.value = 1
  refreshLevelOptions()
  loadData()
}

// 加载数据
const loadData = async () => {
  loadError.value = false
  try {
    await policyStore.fetchPolicies({
      page: currentPage.value,
      page_size: pageSize.value,
      category: searchForm.category || undefined,
      organization_level: searchForm.organization_level || undefined,
      status: searchForm.status || undefined,
      search: searchForm.title || undefined,
    })
  } catch (error) {
    ElMessage.error('加载数据失败')
    loadError.value = true
  }
}

// 排序变化
const handleSortChange = ({ prop, order }: { prop: string | null; order: string | null }) => {
  ;(policyStore as any).setFilters({
    order_by: prop || 'publish_date',
    order_desc: order !== 'ascending',
  })
  loadData()
}

// 分页大小变化
const handleSizeChange = (size: number) => {
  pageSize.value = size
  currentPage.value = 1
  loadData()
}

// 页码变化
const handlePageChange = (page: number) => {
  currentPage.value = page
  loadData()
}

// 新增
const handleAdd = () => {
  pushSafe('/policies/create')
}

// 详情
const handleDetail = (row: any) => {
  pushSafe(`/policies/${row.id}`)
}

// 编辑
const handleEdit = (row: any) => {
  pushSafe(`/policies/${row.id}/edit`)
}

// 删除
const handleDelete = async (row: any) => {
  try {
    await ElMessageBox.confirm(`确定删除政策"${row.title}"吗？删除后可在管理员回收站中恢复。`, '删除确认', {
      type: 'warning',
    })
    await (policyStore as any).removePolicy(row.id)
    // 成功静默：删除成功仅刷新列表
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '删除失败')
    }
  }
}

// 批量删除
const handleBatchDelete = async () => {
  if (selectedIds.value.length === 0) return
  try {
    await ElMessageBox.confirm(
      `确定删除选中的 ${selectedIds.value.length} 条政策吗？删除后可在管理员回收站中恢复。`,
      '批量删除确认',
      { type: 'warning' }
    )
    await (policyStore as any).removePolicies(selectedIds.value)
    selectedIds.value = []
    ElMessage.success('批量删除成功')
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '批量删除失败')
    }
  }
}

// 导入
const handleImport = () => {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.xlsx,.xls'
  input.onchange = async (e: any) => {
    const file = e.target.files[0]
    if (!file) return

    try {
      const result = await importPolicies(file)
      if ((result as any).errors && (result as any).errors.length > 0) {
        const errorDetails = (result as any).errors
          .slice(0, 5)
          .map((err: any) => `第${err.row}行「${err.title}」: ${err.error}`)
          .join('\n')
        const moreText =
          (result as any).errors.length > 5
            ? `\n...还有 ${(result as any).errors.length - 5} 条错误`
            : ''

        ElMessage.warning({
          message: `导入完成：成功${result.imported}条，${result.errors.length}条有错误`,
          duration: 5000,
        })

        // 显示详细错误对话框
        ElMessageBox.alert(
          `导入完成：成功${result.imported}条，${result.errors.length}条有错误\n\n错误详情：\n${errorDetails}${moreText}`,
          '导入结果',
          {
            confirmButtonText: '确定',
            type: 'warning',
          }
        )
      } else {
        ElMessage.success(`导入成功：${result.imported}条政策`)
      }
      currentPage.value = 1 // 重置到第1页，确保新建/编辑后的数据可见
      loadData()
    } catch (error: any) {
      ElMessage.error(error.message || '导入失败')
    }
  }
  input.click()
}

// 下载导入模板（自动解析后端 Content-Disposition 文件名）
const handleDownloadTemplate = async () => {
  try {
    await downloadImportTemplateAndSave('policy', '政策法规')
  } catch {
    ElMessage.error('下载模板失败，请重试')
  }
}

// 导出PDF
const handleExportPDF = async () => {
  try {
    await exportPoliciesPDF({
      category: searchForm.category || undefined,
      organization_level: searchForm.organization_level || undefined,
      status: searchForm.status || undefined,
      search: searchForm.title || undefined,
    })
    ElMessage.success('导出PDF成功')
  } catch (error: any) {
    logger.error('导出PDF失败:', error)
    ElMessage.error('导出PDF功能需要后端支持，请先启动后端服务')
  }
}

// 导出WPS
const handleExportWPS = async () => {
  try {
    await exportPoliciesWPS({
      category: searchForm.category || undefined,
      organization_level: searchForm.organization_level || undefined,
      status: searchForm.status || undefined,
      search: searchForm.title || undefined,
    })
    ElMessage.success('导出WPS成功')
  } catch (error: any) {
    logger.error('导出WPS失败:', error)
    ElMessage.error('导出WPS功能需要后端支持，请先启动后端服务')
  }
}

// 监听路由参数变化（支持从分类页面跳转）
watch(
  () => route.query,
  (query) => {
    if (query.category) {
      searchForm.category = query.category as PolicyCategory
    }
    if (query.level) {
      searchForm.organization_level = query.level as OrganizationLevel
    }
    loadData()
  },
  { immediate: false }
)

// 初始化
onMounted(() => {
  // 从路由参数初始化筛选条件
  if (route.query.category) {
    searchForm.category = route.query.category as PolicyCategory
  }
  if (route.query.level) {
    searchForm.organization_level = route.query.level as OrganizationLevel
  }
  refreshLevelOptions()
  loadData()
})
</script>

<style scoped lang="scss">
.policies-list {
  padding: 20px;
  background: rgba(10, 30, 20, 0.3);
  min-height: calc(100vh - 60px);
}

.search-card,
.table-card {
  margin-bottom: 20px;
  background: rgba(255, 255, 255, 0.95);
  border: 1px solid rgba(64, 145, 108, 0.3);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.title {
  font-size: 16px;
  font-weight: bold;
  color: #1b4332;
}

.actions {
  display: flex;
  gap: 10px;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

:deep(.el-form-item) {
  margin-bottom: 10px;
}

:deep(.el-form-item__label) {
  color: #1b4332;
  font-weight: 500;
}

:deep(.el-input__wrapper) {
  background-color: rgba(255, 255, 255, 0.9);
}

:deep(.el-select__wrapper),
:deep(.el-select .el-input__wrapper) {
  background-color: rgba(255, 255, 255, 0.9);
}

:deep(.el-table) {
  --el-table-bg-color: rgba(255, 255, 255, 0.9);
  --el-table-tr-bg-color: rgba(255, 255, 255, 0.9);
  --el-table-header-bg-color: rgba(64, 145, 108, 0.15);
  --el-table-text-color: #1b4332;
  --el-table-header-text-color: #1b4332;
  --el-table-border-color: rgba(64, 145, 108, 0.2);
}

:deep(.el-table th) {
  background-color: rgba(64, 145, 108, 0.15);
  color: #1b4332;
  font-weight: 600;
}

:deep(.el-table td) {
  color: #1b4332;
}

:deep(.el-table--striped .el-table__body tr.el-table__row--striped td) {
  background-color: rgba(64, 145, 108, 0.05);
}

:deep(.el-table__body tr:hover > td) {
  background-color: rgba(64, 145, 108, 0.1);
}

:deep(.el-pagination) {
  --el-pagination-text-color: #1b4332;
  --el-pagination-bg-color: rgba(255, 255, 255, 0.9);
  --el-pagination-button-bg-color: rgba(255, 255, 255, 0.9);
  --el-pagination-button-disabled-bg-color: rgba(200, 200, 200, 0.3);
}

:deep(.el-pagination.is-background .el-pager li:not(.disabled).is-active) {
  background-color: #40916c;
  color: #fff;
}
</style>
