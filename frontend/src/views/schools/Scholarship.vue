<template>
  <div class="school-scholarship-page">
    <div class="page-header">
      <div class="header-left">
        <el-button :icon="ArrowLeft" @click="pushSafe(`/schools/${schoolId}`)">返回详情</el-button>
        <h2 class="page-title">资助学生管理</h2>
        <el-tag v-if="schoolName" type="primary" size="small">{{ schoolName }}</el-tag>
      </div>
      <div class="header-actions">
        <el-button @click="handleImport">
          <el-icon><Upload /></el-icon>导入
        </el-button>
        <el-button type="primary" @click="openDialog()">
          <el-icon><Plus /></el-icon>新增学生
        </el-button>
      </div>
    </div>

    <!-- 筛选栏 -->
    <div class="filter-bar">
      <el-select
        v-model="filterYear"
        placeholder="筛选年度"
        clearable
        style="width: 140px"
        @change="loadData"
      >
        <el-option v-for="y in yearOptions" :key="y" :label="`${y} 年`" :value="y" />
      </el-select>
      <el-select
        v-model="filterStatus"
        placeholder="筛选状态"
        clearable
        style="width: 140px"
        @change="filterLocal"
      >
        <el-option v-for="(label, val) in statusMap" :key="val" :label="label" :value="val" />
      </el-select>
    </div>

    <el-table v-loading="loading" :data="filteredStudents" stripe border>
      <el-table-column type="index" label="序号" width="60" align="center" />
      <el-table-column prop="student_name" label="学生姓名" min-width="110" />
      <el-table-column prop="grade" label="年级" width="90" />
      <el-table-column prop="year" label="年度" width="80" align="center" />
      <el-table-column prop="amount" label="资助金额(元)" width="120" align="right">
        <template #default="{ row }">{{ row.amount ?? 0 }}</template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag size="small" :type="statusTagType(row.status)">{{
            statusMap[row.status] || row.status || '待审批'
          }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="reason" label="资助原因" min-width="160" show-overflow-tooltip />
      <el-table-column prop="contact_info" label="联系方式" width="130" show-overflow-tooltip />
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

    <el-empty v-if="!loading && students.length === 0" description="暂无资助学生" />

    <!-- 新增/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="editingStudent ? '编辑资助学生' : '新增资助学生'"
      width="480px"
      destroy-on-close
    >
      <el-form ref="formRef" :model="form" :rules="formRules" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="学生姓名" prop="student_name">
              <el-input v-model="form.student_name" placeholder="请输入学生姓名" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="年级">
              <el-input v-model="form.grade" placeholder="如：三年级" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="年度" prop="year">
              <el-select v-model="form.year" placeholder="选择年度" style="width: 100%">
                <el-option v-for="y in yearOptions" :key="y" :label="`${y} 年`" :value="y" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="资助金额(元)" prop="amount">
              <el-input-number v-model="form.amount" :min="0" :precision="4" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="资助状态" prop="status">
          <el-select v-model="form.status" style="width: 100%">
            <el-option v-for="(label, val) in statusMap" :key="val" :label="label" :value="val" />
          </el-select>
        </el-form-item>
        <el-form-item label="资助原因">
          <el-input v-model="form.reason" type="textarea" :rows="2" placeholder="请输入资助原因" />
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="联系方式">
              <el-input v-model="form.contact_info" placeholder="请输入联系方式" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="备注">
              <el-input v-model="form.remarks" placeholder="请输入备注" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">保存</el-button>
      </template>
    </el-dialog>

    <input
      ref="fileInputRef"
      type="file"
      accept=".xlsx,.xls"
      style="display: none"
      @change="handleFileChange"
    />
  </div>
</template>

<script setup lang="ts">
import { logger } from '@/utils/logger'
import { getYearOptions } from '@/utils/yearOptions'

import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useRouterSafe, safeRouteParam } from '@/composables/useRouterSafe'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { ArrowLeft, Plus, Upload } from '@element-plus/icons-vue'
import { schoolsApi } from '@/api/schools'

const route = useRoute()
const { pushSafe } = useRouterSafe()

const schoolId = computed(() => safeRouteParam(route.params.id) ?? '')
const schoolName = ref('')
const students = ref<any[]>([])
const filteredStudents = ref<any[]>([])
const loading = ref(false)
const submitting = ref(false)
const filterYear = ref<number | undefined>(undefined)
const filterStatus = ref('')
const dialogVisible = ref(false)
const editingStudent = ref<any>(null)
const formRef = ref<FormInstance>()
const fileInputRef = ref<HTMLInputElement>()

const statusMap: Record<string, string> = {
  pending: '待审批',
  approved: '已批准',
  disbursed: '已发放',
  completed: '已完成',
}

const statusTagType = (status: string): 'primary' | 'success' | 'warning' | 'info' | 'danger' => {
  const map: Record<string, 'primary' | 'success' | 'warning' | 'info' | 'danger'> = {
    pending: 'warning',
    approved: 'primary',
    disbursed: 'success',
    completed: 'info',
  }
  return map[status] || 'info'
}

const currentYear = new Date().getFullYear()
const yearOptions = computed(() => {
  // 滚动窗口（当前年 ~ 当前年+10）∪ 学生数据年份，倒序合并
  const years = new Set<number>(getYearOptions({ start: currentYear }))
  students.value.forEach((s) => {
    if (s.year) years.add(Number(s.year))
  })
  const list = Array.from(years).sort((a, b) => b - a)
  if (filterYear.value && !list.includes(filterYear.value)) list.unshift(filterYear.value)
  return list
})

const form = ref<any>({
  student_name: '',
  grade: '',
  year: currentYear,
  amount: 0,
  reason: '',
  status: 'pending',
  contact_info: '',
  remarks: '',
})

const formRules: FormRules = {
  student_name: [{ required: true, message: '请输入学生姓名', trigger: 'blur' }],
  year: [{ required: true, message: '请选择年度', trigger: 'change' }],
}

const loadSchoolName = async () => {
  try {
    const res = await schoolsApi.get(Number(schoolId.value))
    schoolName.value = res?.name || ''
  } catch (e) {
    logger.error('加载学校信息失败:', e)
  }
}

const loadData = async () => {
  if (!schoolId.value) return
  loading.value = true
  try {
    const res: any = await schoolsApi.listScholarshipStudents(schoolId.value, filterYear.value)
    students.value = res?.items || res || []
    filterLocal()
  } catch (e) {
    logger.error('加载资助学生失败:', e)
    ElMessage.error('加载资助学生失败')
  } finally {
    loading.value = false
  }
}

function filterLocal() {
  filteredStudents.value = filterStatus.value
    ? students.value.filter((s) => s.status === filterStatus.value)
    : students.value
}

function openDialog(row?: any) {
  editingStudent.value = row || null
  if (row) {
    Object.assign(form.value, {
      student_name: row.student_name || '',
      grade: row.grade || '',
      year: row.year || currentYear,
      amount: row.amount ?? 0,
      reason: row.reason || '',
      status: row.status || 'pending',
      contact_info: row.contact_info || '',
      remarks: row.remarks || '',
    })
  } else {
    Object.assign(form.value, {
      student_name: '',
      grade: '',
      year: filterYear.value || currentYear,
      amount: 0,
      reason: '',
      status: 'pending',
      contact_info: '',
      remarks: '',
    })
  }
  dialogVisible.value = true
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
    const payload = { ...form.value }
    if (editingStudent.value) {
      await schoolsApi.updateScholarshipStudent(schoolId.value, editingStudent.value.id, payload)
      ElMessage.success('更新成功')
    } else {
      await schoolsApi.createScholarshipStudent(schoolId.value, payload)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    await loadData()
  } catch (err: any) {
    ElMessage.error(err?.message || '保存失败')
  } finally {
    submitting.value = false
  }
}

async function handleDelete(row: any) {
  try {
    await schoolsApi.deleteScholarshipStudent(schoolId.value, row.id)
    ElMessage.success('删除成功')
    await loadData()
  } catch (err: any) {
    ElMessage.error(err?.message || '删除失败')
  }
}

function handleImport() {
  fileInputRef.value?.click()
}

async function handleFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  try {
    await schoolsApi.importScholarshipStudents(schoolId.value, file)
    ElMessage.success('导入成功')
    await loadData()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || err?.message || '导入失败')
  } finally {
    input.value = ''
  }
}

onMounted(() => {
  loadSchoolName()
  loadData()
})
</script>

<style scoped>
.school-scholarship-page {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.page-title {
  font-size: 18px;
  font-weight: bold;
  margin: 0;
}

.filter-bar {
  margin-bottom: 16px;
  display: flex;
  gap: 12px;
  align-items: center;
}
</style>
