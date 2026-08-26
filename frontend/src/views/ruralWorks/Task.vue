<template>
  <div class="rural-works-task">
    <!-- 页面头部 -->
    <PageHeader title="任务分配" subtitle="精准分配乡村振兴工作任务，确保高效执行与责任到人" />

    <!-- 工具栏：操作 + 筛选一体化 -->
    <div class="toolbar-section">
      <div class="toolbar-row">
        <div class="toolbar-left">
          <el-input
            v-model="searchQuery"
            placeholder="搜索任务名称、负责人、所属项目"
            clearable
            style="width: 280px"
            @keyup.enter="handleSearch"
          >
            <template #prefix
              ><el-icon><Search /></el-icon
            ></template>
          </el-input>
          <el-select v-model="selectedStatus" placeholder="任务状态" clearable style="width: 130px">
            <el-option label="全部状态" value="" />
            <el-option label="待分配" value="pending" />
            <el-option label="进行中" value="in_progress" />
            <el-option label="已完成" value="completed" />
            <el-option label="已延期" value="delayed" />
            <el-option label="已取消" value="cancelled" />
          </el-select>
          <el-select v-model="selectedPriority" placeholder="优先级" clearable style="width: 120px">
            <el-option label="全部" value="" />
            <el-option label="高" value="high" />
            <el-option label="中" value="medium" />
            <el-option label="低" value="low" />
          </el-select>
          <el-select v-model="selectedAssignee" placeholder="负责人" clearable style="width: 130px">
            <el-option label="全部人员" value="" />
            <el-option
              v-for="person in staff"
              :key="person.id"
              :label="person.name"
              :value="person.id"
            />
          </el-select>
          <el-button type="primary" @click="handleSearch">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </div>
        <div class="toolbar-right">
          <el-button @click="importTasks">
            <el-icon><Upload /></el-icon> 导入
          </el-button>
          <el-button @click="exportTasks">
            <el-icon><Download /></el-icon> 导出
          </el-button>
          <el-button
            type="warning"
            :disabled="selectedTasks.length === 0"
            @click="batchAssignTasks"
          >
            批量分配<template v-if="selectedTasks.length > 0"
              >({{ selectedTasks.length }})</template
            >
          </el-button>
          <el-button type="primary" @click="openCreateTaskDialog">
            <el-icon><Plus /></el-icon> 新建任务
          </el-button>
        </div>
      </div>
    </div>

    <!-- 任务列表表格 -->
    <div class="task-table-section">
      <el-table
        v-loading="loading"
        :data="filteredTasks"
        border
        stripe
        style="width: 100%"
        @selection-change="handleSelectionChange"
        @row-dblclick="handleRowDoubleClick"
      >
        <el-table-column type="selection" width="45" align="center" />
        <el-table-column prop="id" label="编号" width="80" align="center" />
        <el-table-column prop="name" label="任务名称" min-width="200">
          <template #default="scope">
            <div class="task-name-cell">
              <el-tag
                :type="
                  scope.row.priority === 'high'
                    ? 'danger'
                    : scope.row.priority === 'medium'
                      ? 'warning'
                      : 'success'
                "
                size="small"
                effect="dark"
                class="priority-tag"
                >{{ getPriorityLabel(scope.row.priority).replace('优先级', '') }}</el-tag
              >
              <span class="task-name-text">{{ scope.row.name }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="projectName" label="所属项目" width="150" show-overflow-tooltip />
        <el-table-column prop="assigneeName" label="负责人" width="100" align="center">
          <template #default="scope">
            <span>{{ scope.row.assigneeName || '未分配' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="90" align="center">
          <template #default="scope">
            <el-tag :type="getStatusTagType(scope.row.status)" size="small">{{
              getStatusLabel(scope.row.status)
            }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="progress" label="进度" width="130">
          <template #default="scope">
            <el-progress
              :percentage="scope.row.progress"
              :status="
                scope.row.progress === 100 ? 'success' : scope.row.progress > 60 ? '' : 'warning'
              "
              :stroke-width="8"
            />
          </template>
        </el-table-column>
        <el-table-column prop="deadline" label="截止日期" width="110" align="center">
          <template #default="scope">
            <div>
              <span :class="getDeadlineClass(scope.row as Task)">{{
                formatDate(scope.row.deadline)
              }}</span>
              <el-tag
                v-if="isOverdue(scope.row as Task)"
                type="danger"
                size="small"
                effect="dark"
                style="margin-left: 4px"
                >过期</el-tag
              >
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right" align="center">
          <template #default="scope">
            <div class="action-cell">
              <el-button link type="primary" size="small" @click="editTask(scope.row as Task)"
                >编辑</el-button
              >
              <el-button
                v-if="scope.row.status === 'pending'"
                link
                type="success"
                size="small"
                @click="assignTask(scope.row as Task)"
                >分配</el-button
              >
              <el-dropdown
                trigger="click"
                @command="(cmd: string) => handleActionCommand(cmd, scope.row as Task)"
              >
                <el-button link type="info" size="small"
                  >更多<el-icon class="el-icon--right"><ArrowDown /></el-icon
                ></el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item v-if="scope.row.status !== 'cancelled'" command="progress"
                      >查看进度</el-dropdown-item
                    >
                    <el-dropdown-item command="delete" divided style="color: var(--color-danger)"
                      >删除任务</el-dropdown-item
                    >
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </template>
        </el-table-column>
      </el-table>
      <div class="pagination-container">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          :total="tasks.length"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </div>

    <!-- 创建/编辑任务对话框 -->
    <el-dialog
      v-model="taskDialogVisible"
      :title="isEditMode ? '编辑任务' : '新建任务'"
      :width="DIALOG_LG"
      class="task-dialog"
    >
      <el-form
        ref="taskFormRef"
        :model="currentTask"
        :rules="taskRules"
        label-width="120px"
        class="task-form"
      >
        <el-row :gutter="20">
          <el-col :span="24">
            <el-form-item label="任务名称" prop="name">
              <el-input
                v-model="currentTask.name"
                placeholder="请输入任务名称"
                maxlength="100"
                show-word-limit
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="所属项目" prop="projectId">
              <el-select v-model="currentTask.projectId" placeholder="请选择所属项目" clearable>
                <el-option
                  v-for="project in projects"
                  :key="project.id"
                  :label="project.name"
                  :value="project.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="优先级" prop="priority">
              <el-radio-group v-model="currentTask.priority">
                <el-radio-button value="high">高</el-radio-button>
                <el-radio-button value="medium">中</el-radio-button>
                <el-radio-button value="low">低</el-radio-button>
              </el-radio-group>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="负责人" prop="assigneeId">
              <el-select v-model="currentTask.assigneeId" placeholder="请选择负责人" clearable>
                <el-option
                  v-for="person in staff"
                  :key="person.id"
                  :label="person.name"
                  :value="person.id"
                >
                  <div class="select-assignee-item">
                    <el-avatar :size="24" :src="person.avatar" :alt="person.name">
                      {{ person.name[0] }}
                    </el-avatar>
                    <span>{{ person.name }} - {{ person.position }}</span>
                  </div>
                </el-option>
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态" prop="status">
              <el-select v-model="currentTask.status" placeholder="请选择任务状态">
                <el-option label="待分配" value="pending" />
                <el-option label="进行中" value="in_progress" />
                <el-option label="已完成" value="completed" />
                <el-option label="已取消" value="cancelled" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="开始日期" prop="startDate">
              <el-date-picker
                v-model="currentTask.startDate"
                type="date"
                placeholder="选择开始日期"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="截止日期" prop="deadline">
              <el-date-picker
                v-model="currentTask.deadline"
                type="date"
                placeholder="选择截止日期"
                :min-date="currentTask.startDate ? new Date(currentTask.startDate) : undefined"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="任务描述" prop="description">
              <el-input
                v-model="currentTask.description"
                type="textarea"
                placeholder="请输入任务描述"
                :rows="4"
                maxlength="500"
                show-word-limit
              />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="任务附件">
              <el-upload
                class="upload-demo"
                action=""
                :on-change="handleFileChange"
                :auto-upload="false"
                :file-list="currentTask.attachments || []"
                list-type="picture-card"
                multiple
              >
                <el-icon><Plus /></el-icon>
                <div class="el-upload__text">上传附件</div>
              </el-upload>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="taskDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="saveTask">保存</el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 任务分配对话框 -->
    <el-dialog
      v-model="assignDialogVisible"
      title="分配任务"
      :width="DIALOG_SM"
      class="assign-dialog"
    >
      <el-form
        ref="assignFormRef"
        :model="assignForm"
        :rules="assignRules"
        label-width="100px"
        class="assign-form"
      >
        <el-form-item label="选择负责人" prop="assigneeId">
          <el-select v-model="assignForm.assigneeId" placeholder="请选择负责人">
            <el-option
              v-for="person in staff"
              :key="person.id"
              :label="person.name"
              :value="person.id"
            >
              <div class="select-assignee-item">
                <el-avatar :size="24" :src="person.avatar" :alt="person.name">
                  {{ person.name[0] }}
                </el-avatar>
                <span>{{ person.name }} - {{ person.position }}</span>
              </div>
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="分配说明">
          <el-input
            v-model="assignForm.note"
            type="textarea"
            placeholder="请输入分配说明（可选）"
            :rows="3"
            maxlength="200"
            show-word-limit
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="assignDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="confirmAssign">确认分配</el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 任务进度对话框 -->
    <el-dialog
      v-model="progressDialogVisible"
      title="任务进度"
      :width="DIALOG_MD"
      class="progress-dialog"
    >
      <div v-if="currentTaskProgress" class="task-progress-content">
        <div class="task-progress-header">
          <h3 class="task-title">{{ currentTaskProgress.name }}</h3>
          <el-tag :type="getStatusTagType(currentTaskProgress.status)">{{
            getStatusLabel(currentTaskProgress.status)
          }}</el-tag>
        </div>
        <div class="task-progress-info">
          <el-form :model="currentTaskProgress" label-width="100px">
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="负责人">
                  <div class="assignee-wrapper">
                    <el-avatar
                      :size="24"
                      :src="getAssigneeAvatar(currentTaskProgress?.assigneeId || '')"
                      :alt="currentTaskProgress?.assigneeName || '未分配'"
                    >
                      {{
                        currentTaskProgress?.assigneeName
                          ? currentTaskProgress.assigneeName[0]
                          : '未'
                      }}
                    </el-avatar>
                    <span>{{ currentTaskProgress?.assigneeName || '未分配' }}</span>
                  </div>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="截止日期">
                  <span :class="currentTaskProgress ? getDeadlineClass(currentTaskProgress) : ''">
                    {{ formatDate(currentTaskProgress.deadline) }}
                    <span
                      v-if="currentTaskProgress && isOverdue(currentTaskProgress)"
                      class="overdue-badge"
                      >已过期</span
                    >
                  </span>
                </el-form-item>
              </el-col>
              <el-col :span="24">
                <el-form-item label="当前进度">
                  <el-progress
                    :percentage="currentTaskProgress?.progress || 0"
                    :status="getProgressStatus(currentTaskProgress?.progress || 0) as any"
                    :stroke-width="10"
                    :format="(percentage: number) => `${percentage}%`"
                  />
                </el-form-item>
              </el-col>
            </el-row>
          </el-form>
        </div>
        <div class="task-progress-update">
          <h4 class="section-title">更新进度</h4>
          <el-form :model="progressUpdateForm" label-width="100px">
            <el-form-item label="完成进度">
              <el-slider
                v-model="progressUpdateForm.progress"
                :min="0"
                :max="100"
                :step="5"
                :marks="{
                  0: '0%',
                  25: '25%',
                  50: '50%',
                  75: '75%',
                  100: '100%',
                }"
                show-input
                show-input-controls
              />
            </el-form-item>
            <el-form-item label="进度描述">
              <el-input
                v-model="progressUpdateForm.description"
                type="textarea"
                placeholder="请输入进度描述（可选）"
                :rows="3"
                maxlength="300"
                show-word-limit
              />
            </el-form-item>
            <el-form-item label="上传附件">
              <el-upload
                class="upload-demo"
                action=""
                :on-change="handleProgressFileChange"
                :auto-upload="false"
                :file-list="(progressUpdateForm.attachments || []) as any"
                list-type="picture-card"
                multiple
              >
                <el-icon><Plus /></el-icon>
                <div class="el-upload__text">上传附件</div>
              </el-upload>
            </el-form-item>
          </el-form>
        </div>
        <div class="task-progress-history">
          <h4 class="section-title">进度历史</h4>
          <div
            v-if="currentTaskProgress?.history && currentTaskProgress.history.length > 0"
            class="progress-history-list"
          >
            <div
              v-for="(record, index) in currentTaskProgress.history"
              :key="index"
              class="progress-history-item"
            >
              <div class="history-header">
                <div class="history-info">
                  <span class="history-assignee">{{ record.assigneeName }}</span>
                  <span class="history-time">{{ formatDateTime(record.timestamp) }}</span>
                </div>
                <div class="history-progress-change">
                  进度更新:
                  <span class="history-old-progress">{{ record.oldProgress }}%</span>
                  <span class="history-arrow">→</span>
                  <span class="history-new-progress">{{ record.newProgress }}%</span>
                </div>
              </div>
              <div v-if="record.description" class="history-description">
                {{ record.description }}
              </div>
              <div
                v-if="record.attachments && record.attachments.length > 0"
                class="history-attachments"
              >
                <el-tag
                  v-for="(file, fileIndex) in record.attachments"
                  :key="fileIndex"
                  size="small"
                  type="info"
                >
                  <el-icon><Document /></el-icon> {{ file.name }}
                </el-tag>
              </div>
            </div>
          </div>
          <div v-else class="no-history">暂无进度记录</div>
        </div>
      </div>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="progressDialogVisible = false">关闭</el-button>
          <el-button
            type="primary"
            :disabled="currentTaskProgress?.status === 'completed'"
            @click="updateTaskProgress"
            >{{
              currentTaskProgress?.status === 'completed' ? '任务已完成' : '更新进度'
            }}</el-button
          >
        </span>
      </template>
    </el-dialog>

    <!-- 批量分配对话框 -->
    <el-dialog
      v-model="batchAssignDialogVisible"
      title="批量分配任务"
      :width="DIALOG_SM"
      class="batch-assign-dialog"
    >
      <div class="batch-assign-content">
        <p class="batch-assign-count">已选择 {{ selectedTasks.length }} 个任务</p>
        <el-form
          ref="batchAssignFormRef"
          :model="batchAssignForm"
          :rules="batchAssignRules"
          label-width="100px"
          class="batch-assign-form"
        >
          <el-form-item label="负责人" prop="assigneeId">
            <el-select v-model="batchAssignForm.assigneeId" placeholder="请选择负责人">
              <el-option
                v-for="person in staff"
                :key="person.id"
                :label="person.name"
                :value="person.id"
              >
                <div class="select-assignee-item">
                  <el-avatar :size="24" :src="person.avatar" :alt="person.name">
                    {{ person.name[0] }}
                  </el-avatar>
                  <span>{{ person.name }} - {{ person.position }}</span>
                </div>
              </el-option>
            </el-select>
          </el-form-item>
          <el-form-item label="分配说明">
            <el-input
              v-model="batchAssignForm.note"
              type="textarea"
              placeholder="请输入分配说明（可选）"
              :rows="3"
              maxlength="200"
              show-word-limit
            />
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="batchAssignDialogVisible = false">取消</el-button>
          <el-button
            type="primary"
            :disabled="selectedTasks.length === 0"
            @click="confirmBatchAssign"
            >确认分配</el-button
          >
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script lang="ts" setup>
import { DIALOG_LG, DIALOG_MD, DIALOG_SM } from '@/config/dialog'
import PageHeader from '@/components/common/PageHeader.vue'
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Plus, Upload, Download, ArrowDown, Document } from '@element-plus/icons-vue'
import { getRuralWorks, createRuralWork, updateRuralWork, deleteRuralWork } from '@/api/ruralWork'
import { logger } from '@/utils/logger'
// 为 FormRules 定义类型
type FormRules = Record<string, any[]>

// 修复FormRules类型导入 - 已使用正确的导入路径

// 类型定义
interface Task {
  id: string
  name: string
  projectId: string
  projectName: string
  assigneeId: string
  assigneeName: string
  status: 'pending' | 'in_progress' | 'completed' | 'delayed' | 'cancelled'
  priority: 'high' | 'medium' | 'low'
  progress: number
  startDate: string
  deadline: string
  createdDate: string
  description: string
  attachments?: any[]
}

interface TaskProgress extends Task {
  history?: TaskHistory[]
}

interface TaskHistory {
  timestamp: string
  assigneeName: string
  oldProgress: number
  newProgress: number
  description: string
  attachments?: any[]
}

interface Staff {
  id: string
  name: string
  position: string
  avatar?: string
}

interface Project {
  id: string
  name: string
}

// 状态管理
const loading = ref(false)
const searchQuery = ref('')
const selectedStatus = ref('')
const selectedPriority = ref('')
const selectedAssignee = ref('')
const selectedTasks = ref<Task[]>([])
const currentPage = ref(1)
const pageSize = ref(10)

// 对话框状态
const taskDialogVisible = ref(false)
const assignDialogVisible = ref(false)
const progressDialogVisible = ref(false)
const batchAssignDialogVisible = ref(false)
const isEditMode = ref(false)

// 表单实例类型已在上方导入

// 表单引用 - 修复Ref使用
const taskFormRef = ref<InstanceType<(typeof import('element-plus'))['ElForm']> | null>(null)
const assignFormRef = ref<InstanceType<(typeof import('element-plus'))['ElForm']> | null>(null)
const batchAssignFormRef = ref<InstanceType<(typeof import('element-plus'))['ElForm']> | null>(null)

// 人员数据（从 API 加载，初始为空）
const staff = ref<Staff[]>([])

async function loadStaffFromApi() {
  try {
    const { get } = await import('@/api/request')
    const response = await get('/users/staff-list')
    const users = response?.data?.items || response?.items || response || []
    if (Array.isArray(users) && users.length > 0) {
      staff.value = users.map((u: any) => ({
        id: String(u.id),
        name: u.name || u.real_name || u.username || `用户${u.id}`,
        position: u.position || u.role || '员工',
        avatar: u.avatar || '',
      }))
    }
  } catch (e: any) {
    logger.warn('[Task] 加载人员列表失败，保持空列表:', e?.message)
  }
}

const projects = ref<Project[]>([])

async function loadProjectsFromApi() {
  try {
    const { get } = await import('@/api/request')
    const response = await get('/projects', { page_size: 100 })
    const items = response?.items || response || []
    if (Array.isArray(items) && items.length > 0) {
      projects.value = items.map((p: any) => ({
        id: String(p.id),
        name: p.name || p.title || `项目${p.id}`,
      }))
    }
  } catch (e: any) {
    logger.warn('[Task] 加载项目列表失败，保持空列表:', e?.message)
  }
}

// 任务数据（从 API 加载，初始为空）
const tasks = ref<Task[]>([])

// 表单数据
const currentTask = ref<Task>({
  id: '',
  name: '',
  projectId: '',
  projectName: '',
  assigneeId: '',
  assigneeName: '',
  status: 'pending',
  priority: 'medium',
  progress: 0,
  startDate: '',
  deadline: '',
  createdDate: new Date().toISOString().split('T')[0],
  description: '',
  attachments: [],
})

interface AssignForm {
  assigneeId: string
  note: string
}

const assignForm = ref<AssignForm>({
  assigneeId: '',
  note: '',
})

const batchAssignForm = ref<AssignForm>({
  assigneeId: '',
  note: '',
})

const currentTaskProgress = ref<TaskProgress | null>(null)

interface ProgressUpdateForm {
  progress: number
  description: string
  attachments: Array<{
    name: string
    url: string
    uid: string
    status?: string
  }>
}

const progressUpdateForm = ref<ProgressUpdateForm>({
  progress: 0,
  description: '',
  attachments: [],
})

// 表单验证规则 - 修复FormRules使用
const taskRules: FormRules = {
  name: [
    { required: true, message: '请输入任务名称', trigger: 'blur' },
    {
      min: 2,
      max: 100,
      message: '任务名称长度应在 2 到 100 个字符之间',
      trigger: 'blur',
    },
  ],
  projectId: [{ required: true, message: '请选择所属项目', trigger: 'change' }],
  priority: [{ required: true, message: '请选择优先级', trigger: 'change' }],
  startDate: [{ required: true, message: '请选择开始日期', trigger: 'change' }],
  deadline: [
    { required: true, message: '请选择截止日期', trigger: 'change' },
    {
      validator: (_rule: any, value: any, callback: any) => {
        if (!value) {
          callback(new Error('请选择截止日期'))
        } else if (
          currentTask.value.startDate &&
          new Date(value) < new Date(currentTask.value.startDate)
        ) {
          callback(new Error('截止日期不能早于开始日期'))
        } else {
          callback()
        }
      },
      trigger: 'change',
    },
  ],
}

const assignRules: FormRules = {
  assigneeId: [{ required: true, message: '请选择负责人', trigger: 'change' }],
}

const batchAssignRules: FormRules = {
  assigneeId: [{ required: true, message: '请选择负责人', trigger: 'change' }],
}

// 计算属性
const filteredTasks = computed(() => {
  let filtered = [...tasks.value]

  // 搜索过滤
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    filtered = filtered.filter(
      (task) =>
        (task.name || '').toLowerCase().includes(query) ||
        (task.assigneeName && task.assigneeName.toLowerCase().includes(query)) ||
        (task.projectName || '').toLowerCase().includes(query)
    )
  }

  // 状态过滤
  if (selectedStatus.value) {
    filtered = filtered.filter((task) => task.status === selectedStatus.value)
  }

  // 优先级过滤
  if (selectedPriority.value) {
    filtered = filtered.filter((task) => task.priority === selectedPriority.value)
  }

  // 负责人过滤
  if (selectedAssignee.value) {
    filtered = filtered.filter((task) => task.assigneeId === selectedAssignee.value)
  }

  // 分页处理（客户端分页）
  const start = (currentPage.value - 1) * pageSize.value
  const end = start + pageSize.value

  return filtered.slice(start, end)
})

// 生命周期
onMounted(() => {
  loadStaffFromApi()
  loadProjectsFromApi()
  loadData()
})

// 方法
const loadData = async () => {
  loading.value = true
  try {
    const res = await getRuralWorks({ limit: 100 })
    if (res && (res as any).items && (res as any).items.length > 0) {
      tasks.value = (res as any).items.map((item: any, idx: number) => ({
        id: String(item.id) || `T${String(idx + 1).padStart(3, '0')}`,
        name: item.name || '',
        projectId: '',
        projectName: item.village_name || '',
        assigneeId: '',
        assigneeName: item.responsible_person || '',
        status: item.status === 'planned' ? 'pending' : item.status || 'pending',
        priority: 'medium' as const,
        progress: item.progress || 0,
        startDate: item.start_date || '',
        deadline: item.end_date || '',
        createdDate: item.created_at ? item.created_at.split('T')[0] : '',
        description: item.description || '',
      }))
    }
  } catch {
    // API不可用，使用本地模拟数据
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  currentPage.value = 1
  loadData()
}

const resetFilters = () => {
  searchQuery.value = ''
  selectedStatus.value = ''
  selectedPriority.value = ''
  selectedAssignee.value = ''
  currentPage.value = 1
  loadData()
}

const handleSelectionChange = (val: Task[]) => {
  selectedTasks.value = val
}

const handleRowDoubleClick = (row: Task) => {
  editTask(row)
}

const handleActionCommand = (command: string, row: Task) => {
  switch (command) {
    case 'progress':
      viewTaskProgress(row)
      break
    case 'delete':
      deleteTask(row.id)
      break
  }
}

const handleSizeChange = (size: number) => {
  pageSize.value = size
  currentPage.value = 1
}

const handleCurrentChange = (current: number) => {
  currentPage.value = current
}

const openCreateTaskDialog = () => {
  isEditMode.value = false
  // 重置表单
  if (taskFormRef.value) {
    taskFormRef.value.resetFields()
  }
  currentTask.value = {
    id: '',
    name: '',
    projectId: '',
    projectName: '',
    assigneeId: '',
    assigneeName: '',
    status: 'pending',
    priority: 'medium',
    progress: 0,
    startDate: '',
    deadline: '',
    createdDate: new Date().toISOString().split('T')[0],
    description: '',
    attachments: [],
  }
  taskDialogVisible.value = true
}

const editTask = (task: Task) => {
  isEditMode.value = true
  currentTask.value = { ...task }
  // 设置项目名称
  if (currentTask.value.projectId) {
    const project = projects.value.find((p) => p.id === currentTask.value.projectId)
    if (project) {
      currentTask.value.projectName = project.name
    }
  }
  taskDialogVisible.value = true
}

const saveTask = async () => {
  if (!taskFormRef.value) return

  try {
    await taskFormRef.value.validate()

    // 设置项目名称
    if (currentTask.value.projectId) {
      const project = projects.value.find((p) => p.id === currentTask.value.projectId)
      if (project) {
        currentTask.value.projectName = project.name
      }
    }

    // 设置负责人名称
    if (currentTask.value.assigneeId) {
      const assignee = staff.value.find((s) => s.id === currentTask.value.assigneeId)
      if (assignee) {
        currentTask.value.assigneeName = assignee.name
      }
    } else {
      currentTask.value.assigneeName = ''
    }

    // 构建API请求数据
    const apiPayload = {
      name: currentTask.value.name,
      type: 'infrastructure' as const,
      status:
        currentTask.value.status === 'pending'
          ? ('planned' as const)
          : currentTask.value.status === 'in_progress'
            ? ('in_progress' as const)
            : ('completed' as const),
      responsible_person: currentTask.value.assigneeName,
      start_date: currentTask.value.startDate,
      end_date: currentTask.value.deadline,
      description: currentTask.value.description,
      progress: currentTask.value.progress,
    }

    if (isEditMode.value) {
      try {
        await updateRuralWork(Number(currentTask.value.id), apiPayload as any)
        ElMessage.success('任务更新成功')
      } catch {
        // API不可用，回退到本地
        const index = tasks.value.findIndex((t) => t.id === currentTask.value.id)
        if (index !== -1) {
          tasks.value[index] = { ...currentTask.value }
        }
        ElMessage.success('任务更新成功（本地）')
      }
    } else {
      try {
        const result = await createRuralWork(apiPayload as any)
        currentTask.value.id = String(result?.id || Date.now())
        ElMessage.success('任务创建成功')
      } catch {
        // API不可用，回退到本地
        const newTask = {
          ...currentTask.value,
          id: `T${String(tasks.value.length + 1).padStart(3, '0')}`,
        }
        tasks.value.unshift(newTask)
        ElMessage.success('任务创建成功（本地）')
      }
    }

    taskDialogVisible.value = false
    currentPage.value = 1 // 重置到第1页，确保新建/编辑后的数据可见
    loadData()
  } catch (error) {
    // 表单验证失败
  }
}

const assignTask = (task: Task) => {
  currentTask.value = { ...task }
  assignForm.value = {
    assigneeId: '',
    note: '',
  }
  assignDialogVisible.value = true
}

const confirmAssign = async () => {
  if (!assignFormRef.value) return

  try {
    await assignFormRef.value.validate()

    // 更新任务负责人
    const index = tasks.value.findIndex((t) => t.id === currentTask.value.id)
    if (index !== -1) {
      const assignee = staff.value.find((s) => s.id === assignForm.value.assigneeId)
      if (assignee) {
        tasks.value[index].assigneeId = assignForm.value.assigneeId
        tasks.value[index].assigneeName = assignee.name
        tasks.value[index].status = 'in_progress' // 分配后自动设置为进行中
      }
    }

    ElMessage.success('任务分配成功')
    assignDialogVisible.value = false
    currentPage.value = 1 // 重置到第1页，确保新建/编辑后的数据可见
    loadData()
  } catch (error) {
    // 表单验证失败
  }
}

const batchAssignTasks = () => {
  if (selectedTasks.value.length === 0) {
    ElMessage.warning('请先选择需要分配的任务')
    return
  }

  batchAssignForm.value = {
    assigneeId: '',
    note: '',
  }
  batchAssignDialogVisible.value = true
}

const confirmBatchAssign = async () => {
  if (!batchAssignFormRef.value) return

  try {
    await batchAssignFormRef.value.validate()

    // 批量更新任务负责人
    const assignee = staff.value.find((s) => s.id === batchAssignForm.value.assigneeId)
    if (assignee) {
      selectedTasks.value.forEach((selectedTask) => {
        const index = tasks.value.findIndex((t) => t.id === selectedTask.id)
        if (index !== -1) {
          tasks.value[index].assigneeId = batchAssignForm.value.assigneeId
          tasks.value[index].assigneeName = assignee.name
          tasks.value[index].status = 'in_progress' // 分配后自动设置为进行中
        }
      })
    }

    ElMessage.success(`成功分配 ${selectedTasks.value.length} 个任务`)
    selectedTasks.value = []
    batchAssignDialogVisible.value = false
    currentPage.value = 1 // 重置到第1页，确保新建/编辑后的数据可见
    loadData()
  } catch (error) {
    // 表单验证失败
  }
}

const viewTaskProgress = (task: Task) => {
  const progressTask: TaskProgress = {
    ...task,
    history: [],
  }

  currentTaskProgress.value = progressTask
  progressUpdateForm.value = {
    progress: task.progress,
    description: '',
    attachments: [],
  }
  progressDialogVisible.value = true
}

const updateTaskProgress = async () => {
  if (!currentTaskProgress.value) return

  // 验证进度是否有变化
  if (progressUpdateForm.value.progress === currentTaskProgress.value.progress) {
    ElMessage.warning('进度没有变化')
    return
  }

  // 更新任务进度
  const index = tasks.value.findIndex((t) => t.id === currentTaskProgress.value!.id)
  if (index !== -1) {
    const oldProgress = tasks.value[index].progress
    tasks.value[index].progress = progressUpdateForm.value.progress

    // 如果进度达到100%，自动设置为已完成
    if (progressUpdateForm.value.progress === 100) {
      tasks.value[index].status = 'completed'
    } else if (tasks.value[index].status === 'completed') {
      tasks.value[index].status = 'in_progress'
    }

    // 更新进度历史
    if (!currentTaskProgress.value.history) {
      currentTaskProgress.value.history = []
    }

    const newHistoryRecord = {
      timestamp: new Date().toISOString(),
      assigneeName: currentTaskProgress.value.assigneeName || '系统',
      oldProgress,
      newProgress: progressUpdateForm.value.progress,
      description: progressUpdateForm.value.description,
      attachments: progressUpdateForm.value.attachments,
    }

    currentTaskProgress.value.history.unshift(newHistoryRecord)
    currentTaskProgress.value.progress = progressUpdateForm.value.progress

    // 重置进度更新表单
    progressUpdateForm.value = {
      progress: progressUpdateForm.value.progress,
      description: '',
      attachments: [],
    }

    ElMessage.success('进度更新成功')
  }
}

const deleteTask = (taskId: string) => {
  ElMessageBox.confirm('确定要删除该任务吗？此操作不可恢复。', '警告', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  })
    .then(async () => {
      try {
        await deleteRuralWork(Number(taskId))
        ElMessage.success('任务删除成功')
      } catch {
        // API不可用，回退到本地
        const index = tasks.value.findIndex((t) => t.id === taskId)
        if (index !== -1) {
          tasks.value.splice(index, 1)
        }
        ElMessage.success('任务删除成功（本地）')
      }
      currentPage.value = 1 // 重置到第1页，确保新建/编辑后的数据可见
      loadData()
    })
    .catch(() => {
      // 取消删除
    })
}

const importTasks = () => {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.csv,.xlsx,.xls'
  input.onchange = (e: any) => {
    const file = e.target?.files?.[0]
    if (!file) return

    const reader = new FileReader()
    reader.onload = (event) => {
      try {
        const text = event.target?.result as string
        const lines = text.split('\n').filter((line) => line.trim())
        if (lines.length < 2) {
          ElMessage.warning('文件内容为空或格式不正确')
          return
        }

        let importCount = 0
        for (let i = 1; i < lines.length; i++) {
          const cols = lines[i].split(',').map((c) => c.replace(/^"|"$/g, '').trim())
          if (cols.length >= 2 && cols[1]) {
            const newTask: Task = {
              id: `T${String(tasks.value.length + importCount + 1).padStart(3, '0')}`,
              name: cols[1],
              projectId: '',
              projectName: cols[3] || '',
              assigneeId: '',
              assigneeName: cols[4] || '',
              status: 'pending',
              priority: 'medium',
              progress: 0,
              startDate: cols[7] || '',
              deadline: cols[8] || '',
              createdDate: new Date().toISOString().split('T')[0],
              description: cols[9] || '',
            }
            tasks.value.push(newTask)
            importCount++
          }
        }
        ElMessage.success(`成功导入 ${importCount} 个任务`)
      } catch {
        ElMessage.error('文件解析失败，请检查文件格式')
      }
    }
    reader.readAsText(file, 'UTF-8')
  }
  input.click()
}

const exportTasks = () => {
  if (tasks.value.length === 0) {
    ElMessage.warning('没有可导出的任务数据')
    return
  }

  const statusMap: Record<string, string> = {
    pending: '待分配',
    in_progress: '进行中',
    completed: '已完成',
    delayed: '已延期',
    cancelled: '已取消',
  }
  const priorityMap: Record<string, string> = {
    high: '高',
    medium: '中',
    low: '低',
  }

  const headers = [
    '任务编号',
    '任务名称',
    '所属项目',
    '负责人',
    '状态',
    '优先级',
    '进度(%)',
    '开始日期',
    '截止日期',
    '创建日期',
    '描述',
  ]
  const rows = tasks.value.map((task) => [
    task.id,
    task.name,
    task.projectName,
    task.assigneeName || '未分配',
    statusMap[task.status] || task.status,
    priorityMap[task.priority] || task.priority,
    task.progress,
    task.startDate,
    task.deadline,
    task.createdDate,
    task.description || '',
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
  link.download = `任务分配列表_${new Date().toISOString().slice(0, 10)}.csv`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
  ElMessage.success('任务数据导出成功')
}

const handleFileChange = (_file: any, fileList: any[]) => {
  currentTask.value.attachments = fileList
}

const handleProgressFileChange = (_file: any, fileList: any[]) => {
  progressUpdateForm.value.attachments = fileList
}

// 辅助函数

const getPriorityLabel = (priority: string) => {
  switch (priority) {
    case 'high':
      return '高优先级'
    case 'medium':
      return '中优先级'
    case 'low':
      return '低优先级'
    default:
      return '未知优先级'
  }
}

const getStatusLabel = (status: string) => {
  switch (status) {
    case 'pending':
      return '待分配'
    case 'in_progress':
      return '进行中'
    case 'completed':
      return '已完成'
    case 'delayed':
      return '已延期'
    case 'cancelled':
      return '已取消'
    default:
      return '未知状态'
  }
}

const getStatusTagType = (status: string) => {
  switch (status) {
    case 'pending':
      return 'info'
    case 'in_progress':
      return 'primary'
    case 'completed':
      return 'success'
    case 'delayed':
      return 'danger'
    case 'cancelled':
      return 'warning'
    default:
      return 'info'
  }
}

const getProgressStatus = (progress: number): '' | 'success' | 'warning' | 'exception' => {
  if (progress === 100) return 'success'
  if (progress > 70) return ''
  if (progress > 30) return 'warning'
  return ''
}

const getAssigneeAvatar = (assigneeId: string) => {
  if (!assigneeId) return ''
  const assignee = staff.value.find((s) => s.id === assigneeId)
  return assignee?.avatar || ''
}

const getDeadlineClass = (task: Task) => {
  if (task.status === 'completed' || task.status === 'cancelled') {
    return 'deadline-normal'
  }

  const now = new Date()
  const deadline = new Date(task.deadline)
  const daysLeft = Math.floor((deadline.getTime() - now.getTime()) / (1000 * 60 * 60 * 24))

  if (daysLeft < 0) {
    return 'deadline-overdue'
  } else if (daysLeft <= 3) {
    return 'deadline-warning'
  } else {
    return 'deadline-normal'
  }
}

const isOverdue = (task: Task) => {
  if (task.status === 'completed' || task.status === 'cancelled') {
    return false
  }

  const now = new Date()
  const deadline = new Date(task.deadline)
  return now > deadline
}

const formatDate = (dateString: string) => {
  if (!dateString) return ''
  const date = new Date(dateString)
  return date.toLocaleDateString('zh-CN')
}

const formatDateTime = (dateTimeString: string) => {
  if (!dateTimeString) return ''
  const date = new Date(dateTimeString)
  return date.toLocaleString('zh-CN')
}
</script>

<style lang="scss" scoped>
.rural-works-task {
  padding: 20px;
  background-color: var(--color-bg-hover);
  min-height: 100vh;
}

// 页面头部
.page-header {
  margin-bottom: 20px;
  background: white;
  border-radius: 8px;
  padding: 24px 28px 20px;
  border-left: 4px solid $military-dark;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);

  .page-header-inner {
    display: flex;
    align-items: baseline;
    gap: 16px;
  }

  .page-title {
    font-size: 22px;
    font-weight: 700;
    color: $military-dark;
    margin: 0;
    letter-spacing: 1px;
  }

  .page-subtitle {
    font-size: 14px;
    color: var(--color-info);
    margin: 0;
  }

  .decoration-line {
    width: 60px;
    height: 3px;
    background: linear-gradient(90deg, $military-dark, var(--color-primary-light-1));
    margin-top: 12px;
    border-radius: 2px;
  }
}

// 工具栏
.toolbar-section {
  background: white;
  border-radius: 8px;
  padding: 16px 20px;
  margin-bottom: 16px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);

  .toolbar-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
  }

  .toolbar-left {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
    flex: 1;
  }

  .toolbar-right {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;
  }
}

// 任务表格
.task-table-section {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);

  .task-name-cell {
    display: flex;
    align-items: center;
    gap: 8px;

    .priority-tag {
      flex-shrink: 0;
      font-size: 11px;
      padding: 0 6px;
      height: 20px;
      line-height: 20px;
      border-radius: 3px;
    }

    .task-name-text {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  }

  .action-cell {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
  }

  .deadline-normal {
    color: var(--color-text-regular);
  }

  .deadline-warning {
    color: var(--color-warning);
    font-weight: 500;
  }

  .deadline-overdue {
    color: var(--color-danger);
    font-weight: 600;
  }

  .pagination-container {
    margin-top: 16px;
    display: flex;
    justify-content: flex-end;
  }
}

// 对话框样式
.task-dialog,
.assign-dialog,
.progress-dialog,
.batch-assign-dialog {
  .dialog-footer {
    text-align: right;
  }
}

.task-form,
.assign-form,
.batch-assign-form {
  .select-assignee-item {
    display: flex;
    align-items: center;
    gap: 8px;
  }
}

.assignee-wrapper {
  display: flex;
  align-items: center;
  gap: 5px;
}

.task-progress-content {
  .task-progress-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
    padding-bottom: 15px;
    border-bottom: 2px solid var(--color-bg-hover);

    .task-title {
      margin: 0;
      font-size: 18px;
      font-weight: 600;
      color: $military-dark;
    }
  }

  .task-progress-info {
    margin-bottom: 30px;
  }

  .task-progress-update {
    margin-bottom: 30px;
    padding-bottom: 20px;
    border-bottom: 2px solid var(--color-bg-hover);

    .section-title {
      margin-bottom: 15px;
      font-size: 16px;
      font-weight: 600;
      color: $military-dark;
    }
  }

  .task-progress-history {
    .section-title {
      margin-bottom: 15px;
      font-size: 16px;
      font-weight: 600;
      color: $military-dark;
    }

    .progress-history-list {
      .progress-history-item {
        padding: 15px;
        background-color: #f9f9f9;
        border-radius: 6px;
        margin-bottom: 10px;

        .history-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 10px;

          .history-info {
            display: flex;
            align-items: center;
            gap: 15px;

            .history-assignee {
              font-weight: 500;
              color: $military-dark;
            }

            .history-time {
              color: var(--color-info);
              font-size: 14px;
            }
          }

          .history-progress-change {
            color: $military-dark;
            font-weight: 500;

            .history-old-progress {
              color: var(--color-info);
            }

            .history-arrow {
              margin: 0 5px;
              color: var(--color-info);
            }

            .history-new-progress {
              color: var(--color-primary-light-1);
              font-weight: 600;
            }
          }
        }

        .history-description {
          padding: 10px;
          background-color: white;
          border-radius: 4px;
          margin-bottom: 10px;
          font-size: 14px;
          line-height: 1.6;
        }

        .history-attachments {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
        }
      }
    }

    .no-history {
      text-align: center;
      color: var(--color-info);
      padding: 30px;
      font-style: italic;
    }
  }
}

.batch-assign-content {
  .batch-assign-count {
    margin-bottom: 20px;
    font-size: 16px;
    color: $military-dark;
    font-weight: 500;
  }
}

// 响应式设计
@media (max-width: 768px) {
  .rural-works-task {
    padding: 10px;
  }

  .page-title {
    font-size: 24px !important;
  }

  .operation-buttons,
  .filter-row {
    flex-direction: column;
    align-items: stretch;

    .search-input,
    .status-select,
    .priority-select,
    .assignee-select {
      width: 100% !important;
      min-width: unset !important;
    }
  }

  .military-decoration-corner {
    display: none;
  }

  .task-progress-header {
    flex-direction: column;
    align-items: flex-start !important;
    gap: 10px;
  }

  .history-header {
    flex-direction: column;
    align-items: flex-start !important;
    gap: 10px;
  }
}

@media (max-width: 1200px) {
  .operation-buttons,
  .filter-row {
    justify-content: center;
  }
}
</style>
