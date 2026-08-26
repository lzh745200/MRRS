<template>
  <div class="todos-page">
    <div class="page-header">
      <div class="header-info">
        <h2 class="page-title">待办事项</h2>
        <p class="page-desc">管理工作待办事项，跟踪任务完成情况</p>
      </div>
    </div>

    <!-- 添加待办 -->
    <div class="add-card">
      <el-form :model="addForm" inline @submit.prevent="handleAdd">
        <el-form-item label="标题">
          <el-input
            v-model="addForm.title"
            placeholder="输入待办事项..."
            style="width: 360px"
            clearable
            @keyup.enter="handleAdd"
          />
        </el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="addForm.priority" style="width: 120px">
            <el-option label="高" value="high" />
            <el-option label="中" value="medium" />
            <el-option label="低" value="low" />
          </el-select>
        </el-form-item>
        <el-form-item label="截止日期">
          <el-date-picker
            v-model="addForm.deadline"
            type="date"
            placeholder="选择日期"
            value-format="YYYY-MM-DD"
            style="width: 160px"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="adding" @click="handleAdd">
            <el-icon><Plus /></el-icon>添加
          </el-button>
        </el-form-item>
      </el-form>
    </div>

    <!-- 筛选 -->
    <div class="filter-bar">
      <el-radio-group v-model="filterStatus" @change="handleFilterChange">
        <el-radio-button value="">全部</el-radio-button>
        <el-radio-button value="false">未完成</el-radio-button>
        <el-radio-button value="true">已完成</el-radio-button>
      </el-radio-group>
      <el-select
        v-model="filterPriority"
        placeholder="按优先级"
        clearable
        style="width: 120px; margin-left: 12px"
        @change="handleFilterChange"
      >
        <el-option label="高优先级" value="high" />
        <el-option label="中优先级" value="medium" />
        <el-option label="低优先级" value="low" />
      </el-select>
    </div>

    <!-- 加载/错误/空状态 -->
    <div v-if="loading" class="state-container">
      <el-icon class="is-loading" :size="32"><Loading /></el-icon>
      <p>加载中...</p>
    </div>

    <div v-else-if="loadError" class="state-container">
      <el-empty description="加载失败，请重试">
        <el-button type="primary" @click="fetchTodos">重新加载</el-button>
      </el-empty>
    </div>

    <div v-else-if="todoList.length === 0" class="state-container">
      <el-empty description="暂无待办事项">
        <el-button type="primary" @click="scrollToAdd">添加待办</el-button>
      </el-empty>
    </div>

    <!-- 待办列表 -->
    <div v-else class="todo-list">
      <div
        v-for="todo in todoList"
        :key="todo.id"
        class="todo-item"
        :class="{ completed: todo.completed }"
      >
        <el-checkbox
          :model-value="todo.completed"
          class="todo-checkbox"
          @change="handleToggle(todo)"
        />

        <div class="todo-content" @click="handleEdit(todo)">
          <div class="todo-title">{{ todo.title }}</div>
          <div class="todo-meta">
            <el-tag v-if="todo.priority" :type="priorityTagType(todo.priority)" size="small">
              {{ priorityLabel(todo.priority) }}
            </el-tag>
            <span
              v-if="todo.deadline"
              class="todo-deadline"
              :class="{ 'todo-deadline--overdue': isOverdue(todo) }"
            >
              <el-icon><Calendar /></el-icon>
              {{ todo.deadline?.split('T')[0] || todo.deadline }}
              <el-tag v-if="isOverdue(todo)" type="danger" size="small" style="margin-left: 4px"
                >已逾期</el-tag
              >
            </span>
            <span v-if="todo.created_at" class="todo-date">
              创建于 {{ formatDate(todo.created_at) }}
            </span>
          </div>
          <div v-if="todo.description" class="todo-desc">
            {{ todo.description }}
          </div>
        </div>

        <div class="todo-actions">
          <el-button type="primary" link size="small" @click="handleEdit(todo)">
            <el-icon><Edit /></el-icon>
          </el-button>
          <el-popconfirm title="确定删除该待办事项吗？" @confirm="handleDelete(todo)">
            <template #reference>
              <el-button type="danger" link size="small">
                <el-icon><Delete /></el-icon>
              </el-button>
            </template>
          </el-popconfirm>
        </div>
      </div>
    </div>

    <!-- 分页 -->
    <div v-if="total > 0" class="pagination-wrapper">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :page-sizes="[10, 20, 50]"
        :total="total"
        layout="total, sizes, prev, pager, next"
        @size-change="fetchTodos"
        @current-change="fetchTodos"
      />
    </div>

    <!-- 编辑对话框 -->
    <el-dialog v-model="editDialogVisible" title="编辑待办事项" :width="DIALOG_SM" destroy-on-close>
      <el-form :model="editForm" label-width="80px">
        <el-form-item label="标题">
          <el-input v-model="editForm.title" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="editForm.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="editForm.priority" style="width: 100%">
            <el-option label="高" value="high" />
            <el-option label="中" value="medium" />
            <el-option label="低" value="low" />
          </el-select>
        </el-form-item>
        <el-form-item label="截止日期">
          <el-date-picker
            v-model="editForm.deadline"
            type="date"
            placeholder="选择日期"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="已完成">
          <el-switch v-model="editForm.completed" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave"> 保存 </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { DIALOG_SM } from '@/config/dialog'
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Edit, Delete, Loading, Calendar } from '@element-plus/icons-vue'
import { listTodos, createTodo, updateTodo, deleteTodo, toggleTodo } from '@/api/todos'

const addForm = reactive({
  title: '',
  priority: 'medium' as string,
  deadline: '' as string,
})

const editForm = reactive({
  id: 0,
  title: '',
  description: '',
  priority: 'medium' as string,
  deadline: '' as string,
  completed: false,
})

const todoList = ref<any[]>([])
const loading = ref(false)
const loadError = ref(false)
const adding = ref(false)
const saving = ref(false)
const editDialogVisible = ref(false)

const filterStatus = ref('')
const filterPriority = ref('')

const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)

const priorityTagType = (p: string) => {
  if (p === 'high') return 'danger'
  if (p === 'medium') return 'warning'
  return 'info'
}

const priorityLabel = (p: string) => {
  if (p === 'high') return '高'
  if (p === 'medium') return '中'
  return '低'
}

const formatDate = (d: string) => (d ? d.split('T')[0] : '-')

function isOverdue(todo: { deadline?: string; completed?: boolean }) {
  if (!todo.deadline || todo.completed) return false
  return new Date(todo.deadline) < new Date()
}

function scrollToAdd() {
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

async function fetchTodos() {
  loading.value = true
  loadError.value = false
  try {
    const params: Record<string, any> = {
      page: currentPage.value,
      page_size: pageSize.value,
    }
    if (filterStatus.value !== '') {
      params.completed = filterStatus.value === 'true'
    }
    if (filterPriority.value) {
      params.priority = filterPriority.value
    }
    const response = await listTodos(params)
    const data = response?.data ?? response
    todoList.value = data?.items ?? (Array.isArray(data) ? data : [])
    total.value = data?.total ?? todoList.value.length
  } catch {
    loadError.value = true
  } finally {
    loading.value = false
  }
}

function handleFilterChange() {
  currentPage.value = 1
  fetchTodos()
}

async function handleAdd() {
  if (!addForm.title.trim()) {
    ElMessage.warning('请输入标题')
    return
  }
  adding.value = true
  try {
    await createTodo({
      title: addForm.title.trim(),
      priority: addForm.priority,
      deadline: addForm.deadline || undefined,
    })
    ElMessage.success('已添加')
    addForm.title = ''
    addForm.deadline = ''
    currentPage.value = 1
    fetchTodos()
  } catch {
    ElMessage.error('添加失败')
  } finally {
    adding.value = false
  }
}

async function handleToggle(todo: any) {
  try {
    const response = await toggleTodo(todo.id)
    const updated = response?.data ?? response
    todo.completed = updated?.completed ?? !todo.completed
    ElMessage.success(todo.completed ? '已完成' : '已取消完成')
  } catch {
    ElMessage.error('操作失败')
  }
}

function handleEdit(todo: any) {
  editForm.id = todo.id
  editForm.title = todo.title || ''
  editForm.description = todo.description || ''
  editForm.priority = todo.priority || 'medium'
  editForm.deadline = todo.deadline ? (todo.deadline.split('T')[0] ?? todo.deadline) : ''
  editForm.completed = todo.completed ?? false
  editDialogVisible.value = true
}

async function handleSave() {
  if (!editForm.title.trim()) {
    ElMessage.warning('标题不能为空')
    return
  }
  saving.value = true
  try {
    await updateTodo(editForm.id, {
      title: editForm.title.trim(),
      description: editForm.description || undefined,
      priority: editForm.priority,
      deadline: editForm.deadline || undefined,
      completed: editForm.completed,
    })
    ElMessage.success('已保存')
    editDialogVisible.value = false
    currentPage.value = 1
    fetchTodos()
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

async function handleDelete(todo: any) {
  try {
    await deleteTodo(todo.id)
    ElMessage.success('已删除')
    currentPage.value = 1
    fetchTodos()
  } catch {
    ElMessage.error('删除失败')
  }
}

onMounted(() => {
  fetchTodos()
})
</script>

<style scoped>
.todos-page {
  padding: 20px;
}

.page-header {
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
  color: var(--color-text-secondary);
}

.add-card {
  background: white;
  border-radius: 8px;
  padding: 16px 20px 4px;
  margin-bottom: 16px;
  border: 1px solid var(--color-border-light);
}

.filter-bar {
  margin-bottom: 16px;
  display: flex;
  align-items: center;
}

.state-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 0;
  color: var(--color-text-secondary);
}

.todo-list {
  background: white;
  border-radius: 8px;
  border: 1px solid var(--color-border-light);
  overflow: hidden;
}

.todo-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 20px;
  border-bottom: 1px solid var(--color-bg-hover);
  transition: background 0.2s;
}

.todo-item:last-child {
  border-bottom: none;
}

.todo-item:hover {
  background: var(--color-bg-hover);
}

.todo-item.completed .todo-title {
  text-decoration: line-through;
  color: var(--color-info);
}

.todo-checkbox {
  margin-top: 2px;
}

.todo-content {
  flex: 1;
  cursor: pointer;
  min-width: 0;
}

.todo-title {
  font-size: 15px;
  font-weight: 500;
  color: var(--color-text-primary);
  margin-bottom: 4px;
}

.todo-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 12px;
  color: var(--color-info);
}

.todo-deadline {
  display: flex;
  align-items: center;
  gap: 4px;
}

.todo-deadline--overdue {
  color: var(--color-danger);
  font-weight: 600;
}

.todo-desc {
  font-size: 13px;
  color: var(--color-info);
  margin-top: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.todo-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}

.pagination-wrapper {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
