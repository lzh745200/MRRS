<template>
  <div class="work-calendar-page">
    <div class="page-header">
      <h2 class="page-title">工作日历</h2>
      <p class="page-desc">帮扶工作安排与日程管理</p>
      <el-button type="primary" @click="openDialog()">添加工作安排</el-button>
    </div>

    <el-card shadow="never">
      <el-calendar v-model="currentDate">
        <template #date-cell="{ data }">
          <div
            class="calendar-day"
            :class="{ today: isToday(data.date) }"
            @click="selectDate(data.date)"
          >
            <span class="day-num">{{ data.day.split('-').pop()?.replace(/^0/, '') }}</span>
            <div class="events">
              <el-tag
                v-for="evt in getEvents(data.date)"
                :key="evt.id"
                :type="(evt.type || 'primary') as any"
                size="small"
                class="event-tag"
                @click.stop="editEvent(evt)"
              >
                {{ evt.title }}
              </el-tag>
            </div>
          </div>
        </template>
      </el-calendar>
    </el-card>

    <!-- 编辑对话框 -->
    <el-dialog
      append-to-body
      :model-value="dialogVisible"
      :title="editingId ? '编辑工作安排' : '添加工作安排'"
      :width="DIALOG_SM"
      @update:model-value="closeDialog"
    >
      <el-form :model="form" label-width="100px">
        <el-form-item label="日期" required>
          <el-date-picker
            v-model="form.date"
            type="date"
            placeholder="选择日期"
            value-format="YYYY-MM-DD"
          />
        </el-form-item>
        <el-form-item label="标题" required>
          <el-input v-model="form.title" placeholder="工作标题" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="form.type">
            <el-option label="会议" value="primary" />
            <el-option label="调研" value="success" />
            <el-option label="培训" value="warning" />
            <el-option label="检查" value="danger" />
            <el-option label="其他" value="info" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="工作描述" />
        </el-form-item>
        <el-form-item label="地点">
          <el-input v-model="form.location" placeholder="工作地点" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="closeDialog">取消</el-button>
        <el-button v-if="editingId" type="danger" @click="deleteEvent">删除</el-button>
        <el-button type="primary" @click="saveEvent">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { DIALOG_SM } from '@/config/dialog'
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

interface WorkEvent {
  id: number
  date: string
  title: string
  type: string
  description?: string
  location?: string
}

const STORAGE_KEY = 'work_calendar_events'
const currentDate = ref(new Date())
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const selectedDate = ref('')

const form = ref({
  date: '',
  title: '',
  type: 'primary' as string,
  description: '',
  location: '',
})

// 从 localStorage 加载事件
const events = ref<WorkEvent[]>(JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]'))

function saveEvents() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(events.value))
}

function isToday(date: Date): boolean {
  const now = new Date()
  return (
    date.getFullYear() === now.getFullYear() &&
    date.getMonth() === now.getMonth() &&
    date.getDate() === now.getDate()
  )
}

function getEvents(date: Date): WorkEvent[] {
  const ds = formatDate(date)
  return events.value.filter((e) => e.date === ds)
}

function formatDate(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function selectDate(date: Date) {
  selectedDate.value = formatDate(date)
  openDialog()
}

function openDialog(evt?: WorkEvent) {
  editingId.value = evt?.id ?? null
  form.value = {
    date: evt?.date || selectedDate.value || formatDate(new Date()),
    title: evt?.title || '',
    type: evt?.type || 'primary',
    description: evt?.description || '',
    location: evt?.location || '',
  }
  dialogVisible.value = true
}

function editEvent(evt: WorkEvent) {
  openDialog(evt)
}

function closeDialog() {
  dialogVisible.value = false
  editingId.value = null
}

function saveEvent() {
  if (!form.value.date || !form.value.title) {
    ElMessage.warning('请填写日期和标题')
    return
  }
  if (editingId.value) {
    const idx = events.value.findIndex((e) => e.id === editingId.value)
    if (idx >= 0) {
      events.value[idx] = { ...events.value[idx], ...form.value }
    }
    ElMessage.success('已更新')
  } else {
    events.value.push({
      id: Date.now(),
      ...form.value,
    })
    ElMessage.success('已添加')
  }
  saveEvents()
  closeDialog()
}

function deleteEvent() {
  if (editingId.value) {
    events.value = events.value.filter((e) => e.id !== editingId.value)
    saveEvents()
    ElMessage.success('已删除')
    closeDialog()
  }
}
</script>

<style lang="scss" scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.page-title {
  font-size: 24px;
  font-weight: 700;
  color: var(--color-primary-dark-1);
  margin: 0;
}
.page-desc {
  color: var(--color-text-regular);
  font-size: 14px;
  margin: 0;
}
.calendar-day {
  min-height: 60px;
  cursor: pointer;
  padding: 4px;
}
.calendar-day:hover {
  background: var(--color-success-lightest);
  border-radius: 4px;
}
.day-num {
  font-weight: 600;
}
.today .day-num {
  color: var(--color-accent-gold);
  font-weight: 700;
}
.events {
  margin-top: 2px;
}
.event-tag {
  margin: 1px 0;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: pointer;
}
</style>
