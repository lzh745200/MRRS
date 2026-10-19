<template>
  <section class="todo-list-card app-card" data-testid="todo-list-card">
    <div class="card-head">
      <h3 class="card-title">待办清单</h3>
      <span v-if="!loading && !error" class="card-count" data-testid="todo-count">
        {{ todos.length }} 项
      </span>
    </div>

    <div v-if="loading" class="app-loading todo-loading" data-testid="todo-loading">
      <el-skeleton animated :rows="3" />
    </div>
    <div v-else-if="error" class="app-error todo-error" data-testid="todo-error">
      <span>待办加载失败，请稍后重试</span>
      <el-button type="primary" @click="loadTodos">重试</el-button>
    </div>
    <div v-else-if="todos.length === 0" class="app-empty todo-empty" data-testid="todo-empty">
      暂无待办事项
    </div>
    <ul v-else class="todo-list" data-testid="todo-list">
      <li v-for="todo in todos" :key="todo.id" class="todo-item">
        <span class="todo-dot" />
        <span class="todo-title">{{ todo.title || '未命名待办' }}</span>
        <el-tag :type="priorityType(todo.priority)" size="small" class="todo-priority">
          {{ priorityLabel(todo.priority) }}
        </el-tag>
        <span v-if="todo.deadline" class="todo-deadline">{{ formatDeadline(todo.deadline) }}</span>
      </li>
    </ul>

    <div class="card-foot">
      <el-button text type="primary" data-testid="todo-view-all" @click="viewAll">
        查看全部待办
      </el-button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { listTodos } from '@/api/todos'
import { unwrapList } from '@/utils/unwrapList'
import { formatDateTime } from '@/utils'
import { useRouterSafe } from '@/composables/useRouterSafe'
import { logger } from '@/utils/logger'

interface TodoItem {
  id: number
  title: string
  completed?: boolean
  priority?: string
  deadline?: string | null
}

const { pushSafe } = useRouterSafe()

const todos = ref<TodoItem[]>([])
const loading = ref(true)
const error = ref(false)

/** 优先级 → 中文标签（未知值兜底「普通」） */
function priorityLabel(priority?: string): string {
  const labels: Record<string, string> = {
    high: '紧急',
    medium: '普通',
    low: '较低',
  }
  return labels[priority ?? ''] ?? '普通'
}

/** 优先级 → el-tag 语义色（未知值用 info） */
function priorityType(priority?: string): 'danger' | 'warning' | 'info' {
  const types: Record<string, 'danger' | 'warning' | 'info'> = {
    high: 'danger',
    medium: 'warning',
    low: 'info',
  }
  return types[priority ?? ''] ?? 'info'
}

/** 截止时间展示（无截止时间返回空串） */
function formatDeadline(value?: string | null): string {
  return value ? formatDateTime(value, 'MM-DD HH:mm', '') : ''
}

/** 加载未完成待办（取前 5 条） */
async function loadTodos(): Promise<void> {
  loading.value = true
  error.value = false
  try {
    const res = await listTodos({ completed: false, page: 1, page_size: 5 })
    const { items } = unwrapList<TodoItem>(res)
    todos.value = Array.isArray(items) ? items.slice(0, 5) : []
  } catch (e) {
    logger.error('待办清单加载失败', e)
    error.value = true
    todos.value = []
  } finally {
    loading.value = false
  }
}

function viewAll(): void {
  pushSafe('/todos')
}

onMounted(() => {
  void loadTodos()
})
</script>

<style scoped lang="scss">
.todo-list-card {
  background: var(--color-bg-card);
  border: 1px solid var(--color-card-border, var(--color-border-light));
  border-radius: var(--radius-card, 8px);
  padding: var(--spacing-lg, 20px);
  box-shadow: var(--shadow-card);
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--spacing-md, 16px);
}

.card-title {
  font-size: var(--text-lg, 16px);
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 0;
  display: flex;
  align-items: center;
  gap: 8px;

  &::before {
    content: '';
    display: inline-block;
    width: 4px;
    height: 16px;
    border-radius: 2px;
    background: var(--color-primary);
  }
}

.card-count {
  font-size: var(--text-xs, 12px);
  color: var(--color-text-secondary);
  font-variant-numeric: tabular-nums;
}

.todo-loading {
  min-height: 80px;
}

.todo-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs, 8px);
}

.todo-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm, 12px);
  padding: 8px 0;
  border-bottom: 1px solid var(--color-border-lighter);

  &:last-child {
    border-bottom: none;
  }
}

.todo-dot {
  width: 6px;
  height: 6px;
  border-radius: var(--radius-pill, 999px);
  background: var(--color-warning);
  flex-shrink: 0;
}

.todo-title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--text-sm, 13px);
  color: var(--color-text-primary);
}

.todo-deadline {
  font-size: var(--text-xs, 12px);
  color: var(--color-text-secondary);
  font-variant-numeric: tabular-nums;
}

.card-foot {
  margin-top: var(--spacing-sm, 12px);
  display: flex;
  justify-content: flex-end;
}
</style>
