<template>
  <div class="project-management">
    <div class="page-header">
      <h1>项目管理</h1>
      <div class="header-actions">
        <el-button type="primary" @click="handleCreate">
          <el-icon><Plus /></el-icon>
          新增项目
        </el-button>
        <el-button @click="handleExport">
          <el-icon><Download /></el-icon>
          导出数据
        </el-button>
        <el-button @click="handleImport">
          <el-icon><Upload /></el-icon>
          导入数据
        </el-button>
      </div>
    </div>

    <div class="filter-bar">
      <el-form :inline="true" :model="filterForm" @submit.prevent="handleSearch">
        <el-form-item label="项目名称">
          <el-input
            v-model="filterForm.search"
            placeholder="请输入项目名称"
            clearable
            @clear="handleSearch"
          />
        </el-form-item>
        <el-form-item label="状态">
          <el-select
            v-model="filterForm.status"
            placeholder="请选择状态"
            clearable
            @change="handleSearch"
          >
            <el-option label="待处理" value="pending" />
            <el-option label="进行中" value="in_progress" />
            <el-option label="已完成" value="completed" />
            <el-option label="已取消" value="cancelled" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-select
            v-model="filterForm.priority"
            placeholder="请选择优先级"
            clearable
            @change="handleSearch"
          >
            <el-option label="低" value="low" />
            <el-option label="中" value="medium" />
            <el-option label="高" value="high" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">搜索</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </div>

    <div class="table-container">
      <el-table v-loading="loading" :data="projects" @selection-change="handleSelectionChange">
        <el-table-column type="selection" width="55" />
        <el-table-column prop="name" label="项目名称" min-width="200" />
        <el-table-column prop="description" label="描述" min-width="300" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="priority" label="优先级" width="100">
          <template #default="{ row }">
            <el-tag :type="getPriorityType(row.priority)">
              {{ getPriorityText(row.priority) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="start_date" label="开始日期" width="120" />
        <el-table-column prop="end_date" label="结束日期" width="120" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="handleView(row)"> 查看 </el-button>
            <el-button link type="primary" @click="handleEdit(row)"> 编辑 </el-button>
            <el-button link type="danger" @click="handleDelete(row)"> 删除 </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.page_size"
          :page-sizes="[10, 20, 50, 100]"
          :total="pagination.total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSizeChange"
          @current-change="handlePageChange"
        />
      </div>
    </div>

    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="600px"
      @close="handleDialogClose"
    >
      <el-form ref="formRef" :model="formData" :rules="formRules" label-width="100px">
        <el-form-item label="项目名称" prop="name">
          <el-input v-model="formData.name" placeholder="请输入项目名称" />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input
            v-model="formData.description"
            type="textarea"
            :rows="4"
            placeholder="请输入项目描述"
          />
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-select
            v-model="formData.status"
            placeholder="请选择状态"
            clearable
            style="width: 100%"
          >
            <el-option label="待处理" value="pending" />
            <el-option label="进行中" value="in_progress" />
            <el-option label="已完成" value="completed" />
            <el-option label="已取消" value="cancelled" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级" prop="priority">
          <el-select
            v-model="formData.priority"
            placeholder="请选择优先级"
            clearable
            style="width: 100%"
          >
            <el-option label="低" value="low" />
            <el-option label="中" value="medium" />
            <el-option label="高" value="high" />
          </el-select>
        </el-form-item>
        <el-form-item label="开始日期" prop="start_date">
          <el-date-picker
            v-model="formData.start_date"
            type="date"
            placeholder="请选择开始日期"
            value-format="YYYY-MM-DD"
          />
        </el-form-item>
        <el-form-item label="结束日期" prop="end_date">
          <el-date-picker
            v-model="formData.end_date"
            type="date"
            placeholder="请选择结束日期"
            value-format="YYYY-MM-DD"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button :disabled="submitting" @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" :disabled="submitting" @click="handleSubmit"
          >确定</el-button
        >
      </template>
    </el-dialog>

    <input
      ref="fileInput"
      type="file"
      accept=".xlsx,.xls"
      style="display: none"
      @change="handleFileChange"
    />
  </div>
</template>

<script setup lang="ts">
import { logger } from '@/utils/logger'

import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Plus, Download, Upload } from '@element-plus/icons-vue'
import { projectApi, type Project } from '@/api/projects'

const loading = ref(false)
const submitting = ref(false)
const projects = ref<Project[]>([])
const selectedProjects = ref<Project[]>([])
const dialogVisible = ref(false)
const dialogTitle = ref('新增项目')
const dialogMode = ref<'create' | 'edit' | 'view'>('create')
const currentProject = ref<Project | null>(null)
const fileInput = ref<HTMLInputElement>()

const filterForm = reactive({
  search: '',
  status: '',
  priority: '',
})

const pagination = reactive({
  page: 1,
  page_size: 20,
  total: 0,
})

const formRef = ref<FormInstance>()
const formData = reactive({
  name: '',
  description: '',
  status: 'pending',
  priority: 'medium',
  start_date: '',
  end_date: '',
})

const formRules: FormRules = {
  name: [
    { required: true, message: '请输入项目名称', trigger: 'blur' },
    { min: 2, max: 100, message: '长度在 2 到 100 个字符', trigger: 'blur' },
  ],
  description: [
    { required: true, message: '请输入项目描述', trigger: 'blur' },
    { min: 10, max: 500, message: '长度在 10 到 500 个字符', trigger: 'blur' },
  ],
  status: [{ required: true, message: '请选择状态', trigger: 'change' }],
  priority: [{ required: true, message: '请选择优先级', trigger: 'change' }],
  start_date: [{ required: true, message: '请选择开始日期', trigger: 'change' }],
  end_date: [{ required: true, message: '请选择结束日期', trigger: 'change' }],
}

const loadProjects = async () => {
  loading.value = true
  try {
    const response = await projectApi.list({
      page: pagination.page,
      page_size: pagination.page_size,
      keyword: filterForm.search || undefined,
      status: filterForm.status || undefined,
    })
    // 防御：兼容信封（data.items）与裸分页（items）两种形态
    projects.value = (response as any)?.data?.items ?? (response as any)?.items ?? []
    pagination.total = (response as any)?.data?.total ?? (response as any)?.total ?? 0
  } catch (error) {
    ElMessage.error('加载项目列表失败')
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pagination.page = 1
  loadProjects()
}

const handleReset = () => {
  filterForm.search = ''
  filterForm.status = ''
  filterForm.priority = ''
  handleSearch()
}

const handleCreate = () => {
  dialogMode.value = 'create'
  dialogTitle.value = '新增项目'
  dialogVisible.value = true
  resetForm()
}

const handleEdit = (row: any) => {
  dialogMode.value = 'edit'
  dialogTitle.value = '编辑项目'
  currentProject.value = row
  dialogVisible.value = true
  Object.assign(formData, {
    name: row.name,
    description: row.description,
    status: row.status,
    priority: row.priority,
    start_date: row.start_date,
    end_date: row.end_date,
  })
}

const handleView = (row: any) => {
  dialogMode.value = 'view'
  dialogTitle.value = '查看项目'
  currentProject.value = row
  dialogVisible.value = true
  Object.assign(formData, {
    name: row.name,
    description: row.description,
    status: row.status,
    priority: row.priority,
    start_date: row.start_date,
    end_date: row.end_date,
  })
}

const handleDelete = async (row: any) => {
  try {
    await ElMessageBox.confirm('确定要删除该项目吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    // 用户取消，不处理
    return
  }

  try {
    await projectApi.delete(row.id)
    ElMessage.success('删除成功')
    pagination.page = 1 // 重置到第1页，确保新建/编辑后的数据可见
    await loadProjects()
  } catch {
    ElMessage.error('删除失败')
  }
}

const handleSelectionChange = (selection: Project[]) => {
  selectedProjects.value = selection
}

const handleSubmit = async () => {
  if (!formRef.value) return
  if (submitting.value) return

  await formRef.value.validate(async (valid) => {
    if (!valid) return

    submitting.value = true
    try {
      if (dialogMode.value === 'create') {
        await projectApi.create(formData)
        ElMessage.success('创建成功')
      } else if (dialogMode.value === 'edit' && currentProject.value) {
        await projectApi.update(currentProject.value.id, formData)
        ElMessage.success('更新成功')
      }

      dialogVisible.value = false
      pagination.page = 1 // 重置到第1页，确保新建/编辑后的数据可见
      await loadProjects()
    } catch (error) {
      ElMessage.error(dialogMode.value === 'create' ? '创建失败' : '更新失败')
    } finally {
      submitting.value = false
    }
  })
}

const handleDialogClose = () => {
  resetForm()
}

const resetForm = () => {
  formRef.value?.resetFields()
  Object.assign(formData, {
    name: '',
    description: '',
    status: 'pending',
    priority: 'medium',
    start_date: '',
    end_date: '',
  })
}

const handleExport = async () => {
  try {
    await projectApi.exportList({
      keyword: filterForm.search || undefined,
      status: filterForm.status || undefined,
    })
    ElMessage.success('导出成功')
  } catch (error) {
    ElMessage.error('导出失败')
  }
}

const handleImport = () => {
  fileInput.value?.click()
}

const handleFileChange = async (event: Event) => {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return

  try {
    await (projectApi.importData as any)(file, 'incremental', (progress: number) => {
      logger.info(`上传进度: ${progress}%`)
    })
    ElMessage.success('导入成功')
    pagination.page = 1 // 重置到第1页，确保新建/编辑后的数据可见
    loadProjects()
  } catch (error) {
    ElMessage.error('导入失败')
  } finally {
    target.value = ''
  }
}

const handlePageChange = (page: number) => {
  pagination.page = page
  loadProjects()
}

const handleSizeChange = (size: number) => {
  pagination.page_size = size
  pagination.page = 1
  loadProjects()
}

const getStatusType = (status: string) => {
  const typeMap: Record<string, any> = {
    pending: 'info',
    in_progress: 'warning',
    completed: 'success',
    cancelled: 'danger',
  }
  return typeMap[status] || 'info'
}

const getStatusText = (status: string) => {
  const textMap: Record<string, string> = {
    pending: '待处理',
    in_progress: '进行中',
    completed: '已完成',
    cancelled: '已取消',
  }
  return textMap[status] || status
}

const getPriorityType = (priority: string) => {
  const typeMap: Record<string, any> = {
    low: 'info',
    medium: 'warning',
    high: 'danger',
  }
  return typeMap[priority] || 'info'
}

const getPriorityText = (priority: string) => {
  const textMap: Record<string, string> = {
    low: '低',
    medium: '中',
    high: '高',
  }
  return textMap[priority] || priority
}

onMounted(() => {
  loadProjects()
})
</script>

<style scoped>
.project-management {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h1 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.filter-bar {
  background: #fff;
  padding: 20px;
  border-radius: 4px;
  margin-bottom: 20px;
}

.table-container {
  background: #fff;
  padding: 20px;
  border-radius: 4px;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}
</style>
