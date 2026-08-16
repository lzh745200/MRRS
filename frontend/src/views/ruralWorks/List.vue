<template>
  <div class="rural-work-list-page">
    <!-- 统计概览 -->
    <div class="stats-overview">
      <div v-for="stat in statsCards" :key="stat.label" class="stat-card">
        <div class="stat-value" :style="{ color: stat.color }">
          {{ stat.value }}
        </div>
        <div class="stat-label">{{ stat.label }}</div>
      </div>
    </div>

    <!-- 操作与筛选 -->
    <el-card class="filter-card">
      <div class="filter-bar">
        <div class="filter-left">
          <el-input
            v-model="searchText"
            placeholder="搜索工作名称、负责人..."
            clearable
            style="width: 240px"
            @clear="handleSearch"
            @keyup.enter="handleSearch"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
          <el-select
            v-model="filterStatus"
            placeholder="状态筛选"
            clearable
            style="width: 140px"
            @change="handleSearch"
          >
            <el-option label="全部状态" value="" />
            <el-option label="计划中" value="planned" />
            <el-option label="进行中" value="in_progress" />
            <el-option label="已完成" value="completed" />
            <el-option label="已延期" value="delayed" />
          </el-select>
          <el-select
            v-model="filterType"
            placeholder="类型筛选"
            clearable
            style="width: 160px"
            @change="handleSearch"
          >
            <el-option label="全部类型" value="" />
            <el-option label="基础设施建设" value="infrastructure" />
            <el-option label="产业发展" value="industry" />
            <el-option label="教育培训" value="education" />
            <el-option label="医疗健康" value="healthcare" />
            <el-option label="生态环境保护" value="environment" />
          </el-select>
          <el-select
            v-model="filterYear"
            placeholder="年度筛选"
            clearable
            style="width: 130px"
            @change="handleSearch"
          >
            <el-option label="全部年份" value="" />
            <el-option v-for="y in yearOptions" :key="y" :label="y + '年'" :value="y" />
          </el-select>
          <el-button @click="resetFilters">重置</el-button>
        </div>
        <div class="filter-right">
          <el-button type="success" @click="handleExport">
            <el-icon><Download /></el-icon> 导出
          </el-button>
          <el-button type="primary" @click="handleCreate">
            <el-icon><Plus /></el-icon> 新增工作
          </el-button>
        </div>
      </div>
    </el-card>

    <!-- 数据表格 -->
    <el-card class="table-card">
      <!-- 加载失败占位 -->
      <el-result
        v-if="loadError"
        icon="error"
        title="加载失败"
        sub-title="数据加载失败，请检查网络或稍后重试"
      >
        <template #extra>
          <el-button type="primary" @click="fetchData">重试</el-button>
        </template>
      </el-result>
      <el-table v-else v-loading="loading" :data="filteredData" border stripe style="width: 100%">
        <el-table-column type="index" label="序号" width="60" align="center" />
        <el-table-column prop="name" label="工作名称" min-width="180" show-overflow-tooltip />
        <el-table-column prop="type" label="工作类型" width="130">
          <template #default="{ row }">
            <el-tag :type="getTypeTagColor(row.type)" size="small">{{
              typeLabels[row.type] || row.type
            }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="village_name" label="所属村庄" width="120" />
        <el-table-column prop="responsible_person" label="负责人" width="100">
          <template #default="{ row }">
            {{ ds(row.responsible_person, 'name') }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="statusColors[row.status] || 'info'" size="small">{{
              statusLabels[row.status] || row.status
            }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="progress" label="进度" width="140">
          <template #default="{ row }">
            <el-progress
              :percentage="row.progress"
              :status="row.progress === 100 ? 'success' : row.progress > 60 ? '' : 'warning'"
              :stroke-width="8"
            />
          </template>
        </el-table-column>
        <el-table-column prop="start_date" label="开始日期" width="120" />
        <el-table-column prop="end_date" label="结束日期" width="120" />
        <el-table-column label="操作" width="200" fixed="right" align="center">
          <template #default="{ row }">
            <el-button size="small" @click="handleView(row)">查看</el-button>
            <el-button size="small" type="primary" @click="handleEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrap">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50]"
          :total="total"
          layout="total, sizes, prev, pager, next"
          @size-change="handleSearch"
          @current-change="handleSearch"
        />
      </div>
    </el-card>

    <!-- 查看/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="700px" destroy-on-close>
      <el-form
        ref="formRef"
        :model="formData"
        :rules="formRules"
        label-width="100px"
        :disabled="dialogMode === 'view'"
      >
        <el-row :gutter="20">
          <el-col :span="24">
            <el-form-item label="工作名称" prop="name">
              <el-input
                v-model="formData.name"
                placeholder="请输入工作名称"
                maxlength="100"
                show-word-limit
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="工作类型" prop="type">
              <el-select v-model="formData.type" placeholder="请选择类型" style="width: 100%">
                <el-option label="基础设施建设" value="infrastructure" />
                <el-option label="产业发展" value="industry" />
                <el-option label="教育培训" value="education" />
                <el-option label="医疗健康" value="healthcare" />
                <el-option label="生态环境保护" value="environment" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态" prop="status">
              <el-select v-model="formData.status" placeholder="请选择状态" style="width: 100%">
                <el-option label="计划中" value="planned" />
                <el-option label="进行中" value="in_progress" />
                <el-option label="已完成" value="completed" />
                <el-option label="已延期" value="delayed" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="所属村庄">
              <el-select
                v-model="formData.village_id"
                placeholder="请选择村庄"
                clearable
                filterable
                style="width: 100%"
              >
                <el-option
                  v-for="village in villageOptions"
                  :key="village.id"
                  :label="village.name"
                  :value="village.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="负责人">
              <el-input v-model="formData.responsible_person" placeholder="请输入负责人" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="开始日期">
              <el-date-picker
                v-model="formData.start_date"
                type="date"
                placeholder="选择开始日期"
                value-format="YYYY-MM-DD"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="结束日期">
              <el-date-picker
                v-model="formData.end_date"
                type="date"
                placeholder="选择结束日期"
                value-format="YYYY-MM-DD"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="进度">
              <el-slider v-model="formData.progress" :min="0" :max="100" :step="5" show-input />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="工作描述">
              <el-input
                v-model="formData.description"
                type="textarea"
                :rows="3"
                placeholder="请输入工作描述"
                maxlength="500"
                show-word-limit
              />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template v-if="dialogMode !== 'view'" #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, reactive } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { logger } from '@/utils/logger'
import { getErrorMessage } from '@/utils/getErrorMessage'
import { getYearOptions } from '@/utils/yearOptions'
import { useDesensitize } from '@/composables/useDesensitize'
import { Search, Plus, Download } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'
import type { WorkStatus, WorkType } from '@/api/ruralWork'

// 类型映射
const typeLabels: Record<string, string> = {
  infrastructure: '基础设施建设',
  industry: '产业发展',
  education: '教育培训',
  healthcare: '医疗健康',
  environment: '生态环境保护',
}

const statusLabels: Record<string, string> = {
  planned: '计划中',
  in_progress: '进行中',
  completed: '已完成',
  delayed: '已延期',
}

const statusColors: Record<string, 'info' | 'primary' | 'success' | 'warning' | 'danger'> = {
  planned: 'info',
  in_progress: 'primary',
  completed: 'success',
  delayed: 'danger',
}

const { ds } = useDesensitize()

// 状态
const loading = ref(false)
const loadError = ref(false)
const searchText = ref('')
const filterStatus = ref('')
const filterType = ref('')
const filterYear = ref<number | string>('') // 默认不筛选年份，显示所有数据
const yearOptions = ref<number[]>([])
const currentPage = ref(1)
const pageSize = ref(10)
const total = ref(0)
const tableData = ref<any[]>([])
const saving = ref(false)
const villageOptions = ref<any[]>([])

// 对话框
const dialogVisible = ref(false)
const dialogMode = ref<'create' | 'edit' | 'view'>('create')
const dialogTitle = computed(() => {
  if (dialogMode.value === 'create') return '新增乡村工作'
  if (dialogMode.value === 'edit') return '编辑乡村工作'
  return '查看乡村工作'
})
const formRef = ref<FormInstance>()
const formData = reactive({
  id: 0,
  name: '',
  type: '' as string,
  status: 'planned' as string,
  village_id: undefined as number | undefined,
  responsible_person: '',
  progress: 0,
  start_date: '',
  end_date: '',
  description: '',
})
const formRules: FormRules = {
  name: [{ required: true, message: '请输入工作名称', trigger: 'blur' }],
  type: [{ required: true, message: '请选择工作类型', trigger: 'change' }],
}

// 数据源：直接使用 tableData
const dataSource = computed(() => {
  return tableData.value
})

// 服务端统计（优先），回退到当前页数据
const serverStats = ref<any>(null)
const statsCards = computed(() => {
  const s = serverStats.value
  if (s) {
    return [
      { label: '工作总数', value: s.total ?? 0, color: 'var(--color-primary)' },
      { label: '进行中', value: s.in_progress ?? 0, color: 'var(--color-warning)' },
      { label: '已完成', value: s.completed ?? 0, color: 'var(--color-success)' },
      { label: '已延期', value: s.delayed ?? 0, color: 'var(--color-danger)' },
    ]
  }
  const data = dataSource.value
  return [
    { label: '工作总数', value: total.value || data.length, color: 'var(--color-primary)' },
    {
      label: '进行中',
      value: data.filter((d: any) => d.status === 'in_progress').length,
      color: 'var(--color-warning)',
    },
    {
      label: '已完成',
      value: data.filter((d: any) => d.status === 'completed').length,
      color: 'var(--color-success)',
    },
    {
      label: '已延期',
      value: data.filter((d: any) => d.status === 'delayed').length,
      color: 'var(--color-danger)',
    },
  ]
})

async function loadServerStats() {
  try {
    const { ruralWorkApi } = await import('@/api/ruralWork')
    const stats = await ruralWorkApi.getStatistics()
    if (stats) serverStats.value = stats
  } catch {
    /* 统计加载失败不阻塞主流程 */
  }
}

// 显示的数据：直接使用 tableData，不再进行客户端过滤
const filteredData = computed(() => {
  return tableData.value
})

function getTypeTagColor(type: string): 'info' | 'primary' | 'success' | 'warning' | 'danger' {
  const map: Record<string, 'info' | 'primary' | 'success' | 'warning' | 'danger'> = {
    infrastructure: 'primary',
    industry: 'success',
    education: 'warning',
    healthcare: 'danger',
    environment: 'info',
  }
  return map[type] || 'info'
}

async function fetchData() {
  loading.value = true
  loadError.value = false
  try {
    const { getRuralWorks } = await import('@/api/ruralWork')
    const result = await getRuralWorks({
      skip: (currentPage.value - 1) * pageSize.value,
      limit: pageSize.value,
      search: searchText.value || undefined,
      status: (filterStatus.value as WorkStatus) || undefined,
      type: (filterType.value as WorkType) || undefined,
      year: typeof filterYear.value === 'number' ? filterYear.value : undefined,
    })
    tableData.value = result.items || []
    total.value = result.total || 0
  } catch (error) {
    logger.error('加载数据失败', error)
    ElMessage.error('加载数据失败')
    loadError.value = true
    tableData.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  currentPage.value = 1
  fetchData()
}

function resetFilters() {
  searchText.value = ''
  filterStatus.value = ''
  filterType.value = ''
  filterYear.value = ''
  currentPage.value = 1
  fetchData()
}

function resetForm() {
  Object.assign(formData, {
    id: 0,
    name: '',
    type: '',
    status: 'planned',
    village_id: undefined,
    responsible_person: '',
    progress: 0,
    start_date: '',
    end_date: '',
    description: '',
  })
}

function handleCreate() {
  dialogMode.value = 'create'
  resetForm()
  dialogVisible.value = true
}

function handleView(row: any) {
  dialogMode.value = 'view'
  Object.assign(formData, row)
  dialogVisible.value = true
}

function handleEdit(row: any) {
  dialogMode.value = 'edit'
  Object.assign(formData, row)
  dialogVisible.value = true
}

async function handleSave() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch {
    return
  }

  saving.value = true
  try {
    const payload = {
      name: formData.name,
      type: formData.type,
      status: formData.status,
      village_id: formData.village_id,
      responsible_person: formData.responsible_person,
      progress: formData.progress,
      start_date: formData.start_date,
      end_date: formData.end_date,
      description: formData.description,
    }

    if (dialogMode.value === 'create') {
      const { createRuralWork } = await import('@/api/ruralWork')
      await createRuralWork(payload as any)
      ElMessage.success('新增成功')
    } else {
      const { updateRuralWork } = await import('@/api/ruralWork')
      await updateRuralWork(formData.id, payload as any)
      ElMessage.success('保存成功')
    }
    dialogVisible.value = false
    currentPage.value = 1
    await fetchData()
  } catch (error: any) {
    logger.error('保存失败', error)
    const msg = getErrorMessage(error, '保存失败，请稍后重试')
    ElMessage.error(msg)
  } finally {
    saving.value = false
  }
}

async function handleDelete(row: any) {
  try {
    await ElMessageBox.confirm('确认删除该工作项？此操作不可恢复。', '警告', {
      type: 'warning',
    })
    const { deleteRuralWork } = await import('@/api/ruralWork')
    await deleteRuralWork(row.id)
    ElMessage.success('删除成功')
    currentPage.value = 1
    await fetchData()
  } catch (error: any) {
    // 用户取消删除
    if (error === 'cancel') {
      return
    }
    // API 调用失败
    logger.error('删除失败', error)
    const errorMsg = error?.response?.data?.detail || error?.message || '删除失败'
    ElMessage.error(errorMsg)
  }
}

function handleExport() {
  const data = dataSource.value
  if (!data || data.length === 0) {
    ElMessage.warning('没有可导出的数据')
    return
  }

  const headers = [
    '序号',
    '工作名称',
    '工作类型',
    '所属村庄',
    '负责人',
    '状态',
    '进度(%)',
    '开始日期',
    '结束日期',
    '工作描述',
  ]
  const rows = data.map((item: any, index: number) => [
    index + 1,
    item.name || '',
    typeLabels[item.type] || item.type || '',
    item.village_name || '',
    item.responsible_person || '',
    statusLabels[item.status] || item.status || '',
    item.progress ?? 0,
    item.start_date || '',
    item.end_date || '',
    item.description || '',
  ])

  const BOM = '\uFEFF'
  const csvContent =
    BOM +
    [headers, ...rows]
      .map((row) =>
        row
          .map((cell: any) => {
            const str = String(cell).replace(/"/g, '""')
            return `"${str}"`
          })
          .join(',')
      )
      .join('\n')

  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `乡村工作列表_${new Date().toISOString().slice(0, 10)}.csv`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
  // 导出成功 — 浏览器已确认
}

async function loadYears() {
  try {
    const { ruralWorkApi } = await import('@/api/ruralWork')
    const years = await ruralWorkApi.getAvailableYears()
    yearOptions.value = years.length > 0 ? years : generateDefaultYears()
    // 确保当前年度在选项中
    const curYear = new Date().getFullYear()
    if (!yearOptions.value.includes(curYear)) {
      yearOptions.value.unshift(curYear)
    }
  } catch {
    yearOptions.value = generateDefaultYears()
  }
}

function generateDefaultYears(): number[] {
  const current = new Date().getFullYear()
  // 默认年份范围：当前年-5 ~ 当前年+10（滚动窗口，见 utils/yearOptions）
  return getYearOptions({ start: current - 5 })
}

async function loadVillages() {
  try {
    const { ruralWorkApi } = await import('@/api/ruralWork')
    const res: any = await ruralWorkApi.getVillagesForSelect()
    // 兼容信封展开：items / data / 纯数组
    villageOptions.value = Array.isArray(res) ? res : res?.items || res?.data || []
  } catch (error) {
    logger.error('加载村庄列表失败', error)
    villageOptions.value = []
  }
}

onMounted(() => {
  loadYears()
  loadVillages()
  fetchData()
  loadServerStats()
})
</script>

<style scoped>
.rural-work-list-page {
  padding: 20px;
}

.stats-overview {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 16px;
}

.stat-card {
  background: white;
  border-radius: 8px;
  padding: 20px;
  text-align: center;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  border-left: 4px solid #1b4332;
  transition: transform 0.2s;
}

.stat-card:hover {
  transform: translateY(-2px);
}

.stat-value {
  font-size: 32px;
  font-weight: 700;
  line-height: 1.2;
}

.stat-label {
  font-size: 14px;
  color: #606266;
  margin-top: 6px;
}

.filter-card {
  margin-bottom: 16px;
}

.filter-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}

.filter-left {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}

.pagination-wrap {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

@media (max-width: 768px) {
  .stats-overview {
    grid-template-columns: repeat(2, 1fr);
  }
  .filter-bar {
    flex-direction: column;
    align-items: stretch;
  }
  .filter-left {
    flex-direction: column;
  }
}
</style>
