<template>
  <div class="school-projects-page">
    <div class="page-header">
      <div class="header-left">
        <el-button :icon="ArrowLeft" @click="pushSafe(`/schools/${schoolId}`)">返回详情</el-button>
        <h2 class="page-title">助学兴教项目管理</h2>
      </div>
      <el-button type="primary" @click="openDialog()">
        <el-icon><Plus /></el-icon>新增项目
      </el-button>
    </div>

    <!-- 筛选栏 -->
    <div
      class="filter-bar"
      style="margin-bottom: 16px; display: flex; gap: 12px; align-items: center"
    >
      <el-select
        v-model="filterPhase"
        placeholder="筛选阶段"
        clearable
        style="width: 130px"
        @change="filterProjects"
      >
        <el-option v-for="(label, val) in phaseMap" :key="val" :label="label" :value="val" />
      </el-select>
      <el-date-picker
        v-model="filterDateRange"
        type="daterange"
        range-separator="至"
        start-placeholder="开始日期"
        end-placeholder="结束日期"
        style="width: 260px"
        @change="filterProjects"
      />
    </div>

    <el-table v-loading="loading" :data="filteredProjects" stripe border>
      <el-table-column type="index" label="序号" width="60" align="center" />
      <el-table-column prop="name" label="项目名称" min-width="180" />
      <el-table-column prop="category" label="类别" width="100" />
      <el-table-column prop="phase" label="阶段" width="100">
        <template #default="{ row }">
          <el-tag size="small" :type="phaseTagType(row.phase)">{{
            phaseMap[row.phase] || row.phase
          }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="budget" label="预算(万元)" width="110" align="right" />
      <el-table-column prop="actual_cost" label="实际投入(万元)" width="130" align="right" />
      <el-table-column prop="start_date" label="开始日期" width="110">
        <template #default="{ row }">{{
          row.start_date ? row.start_date.split('T')[0] : '-'
        }}</template>
      </el-table-column>
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" link size="small" @click="openDialog(row)">编辑</el-button>
          <el-popconfirm title="确定删除？" @confirm="handleDelete(row)">
            <template #reference>
              <el-button type="danger" link size="small">删除</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <!-- 新增/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="editingProject ? '编辑项目' : '新增项目'"
      :width="DIALOG_MD"
      destroy-on-close
    >
      <el-form :model="form" label-width="100px">
        <el-form-item label="项目名称" required>
          <el-input v-model="form.name" placeholder="请输入项目名称" />
        </el-form-item>
        <el-form-item label="项目类别">
          <el-input v-model="form.category" placeholder="如：教学设施、师资培训" />
        </el-form-item>
        <el-form-item label="项目阶段">
          <el-select
            v-model="form.phase"
            placeholder="请选择项目阶段"
            clearable
            style="width: 100%"
          >
            <el-option v-for="(label, val) in phaseMap" :key="val" :label="label" :value="val" />
          </el-select>
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="预算(万元)">
              <el-input-number v-model="form.budget" :min="0" :precision="4" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="实际投入">
              <el-input-number
                v-model="form.actual_cost"
                :min="0"
                :precision="4"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="开始日期">
              <el-date-picker v-model="form.start_date" type="date" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="结束日期">
              <el-date-picker v-model="form.end_date" type="date" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="项目描述">
          <el-input v-model="form.description" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { DIALOG_MD } from '@/config/dialog'
import { logger } from '@/utils/logger'

import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useRouterSafe, safeRouteParam } from '@/composables/useRouterSafe'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Plus } from '@element-plus/icons-vue'
import { schoolApi } from '@/api/schools'

const { pushSafe } = useRouterSafe()
const route = useRoute()
const schoolId = safeRouteParam(route.params.id)

const loading = ref(false)
const saving = ref(false)
const projects = ref<any[]>([])
const dialogVisible = ref(false)
const editingProject = ref<any>(null)
const filterPhase = ref('')
const filterDateRange = ref<[Date, Date] | null>(null)

const filteredProjects = computed(() => {
  let list = projects.value
  if (filterPhase.value) {
    list = list.filter((p) => p.phase === filterPhase.value)
  }
  if (filterDateRange.value && filterDateRange.value[0] && filterDateRange.value[1]) {
    const start = new Date(filterDateRange.value[0]).getTime()
    const end = new Date(filterDateRange.value[1]).getTime()
    list = list.filter((p) => {
      const d = p.start_date ? new Date(p.start_date).getTime() : 0
      return d >= start && d <= end
    })
  }
  return list
})
function filterProjects() {
  /* computed auto-updates */
}

const phaseMap: Record<string, string> = {
  research: '调研',
  approval: '立项审批',
  implementation: '实施',
  acceptance: '验收',
  completed: '已完成',
}
function phaseTagType(p: string) {
  if (p === 'completed') return 'success'
  if (p === 'implementation') return 'primary'
  if (p === 'acceptance') return 'warning'
  return 'info'
}

const form = ref({
  name: '',
  category: '',
  phase: 'research',
  budget: 0,
  actual_cost: 0,
  start_date: null as any,
  end_date: null as any,
  description: '',
})

async function loadProjects() {
  loading.value = true
  try {
    const res = await schoolApi.listProjects(schoolId)
    projects.value = res.items || []
  } catch (error) {
    logger.error('Failed to load projects:', error)
  } finally {
    loading.value = false
  }
}

function openDialog(row?: any) {
  editingProject.value = row || null
  if (row) {
    form.value = {
      ...row,
      start_date: row.start_date || null,
      end_date: row.end_date || null,
    }
  } else {
    form.value = {
      name: '',
      category: '',
      phase: 'research',
      budget: 0,
      actual_cost: 0,
      start_date: null,
      end_date: null,
      description: '',
    }
  }
  dialogVisible.value = true
}

async function handleSave() {
  if (!form.value.name) {
    ElMessage.warning('请输入项目名称')
    return
  }
  saving.value = true
  try {
    if (editingProject.value) {
      await schoolApi.updateProject(schoolId, editingProject.value.id, form.value)
      ElMessage.success('更新成功')
    } else {
      await schoolApi.createProject(schoolId, form.value)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    loadProjects()
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

async function handleDelete(row: any) {
  try {
    await schoolApi.deleteProject(schoolId, row.id)
    ElMessage.success('删除成功')
    loadProjects()
  } catch (error) {
    logger.error('Failed to delete project:', error)
  }
}

onMounted(() => loadProjects())
</script>

<style lang="scss" scoped>
.school-projects-page {
  padding: 20px;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}
.page-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: var(--color-primary-dark-1);
}
</style>
