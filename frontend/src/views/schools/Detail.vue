<template>
  <div class="school-detail-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-left">
        <el-button :icon="ArrowLeft" @click="handleBack">返回列表</el-button>
        <h2 class="page-title">帮扶学校详情</h2>
      </div>
      <div class="header-actions">
        <el-button type="primary" @click="handleEdit">
          <el-icon><Edit /></el-icon>编辑
        </el-button>
        <el-button type="danger" @click="handleDelete">
          <el-icon><Delete /></el-icon>删除
        </el-button>
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading-container">
      <el-icon class="loading-icon"><Loading /></el-icon>
      <span>加载中...</span>
    </div>

    <template v-else>
      <!-- 基本信息 -->
      <div class="detail-card">
        <div class="card-header">
          <h3>基本信息</h3>
        </div>
        <div class="card-body">
          <el-descriptions :column="3" border>
            <el-descriptions-item label="学校名称">{{ school.name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="学校编码">{{ school.code || '-' }}</el-descriptions-item>
            <el-descriptions-item label="学校类型">
              <el-tag>{{ getTypeDisplay(school.type) }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="所在省份">{{
              school.province || '-'
            }}</el-descriptions-item>
            <el-descriptions-item label="所在城市">{{ school.city || '-' }}</el-descriptions-item>
            <el-descriptions-item label="所在区县">{{
              school.district || '-'
            }}</el-descriptions-item>
            <el-descriptions-item label="详细地址" :span="3">{{
              ds(school.address, 'address')
            }}</el-descriptions-item>
          </el-descriptions>
        </div>
      </div>

      <!-- 规模信息 -->
      <div class="detail-card">
        <div class="card-header">
          <h3>规模信息</h3>
        </div>
        <div class="card-body">
          <div class="scale-stats">
            <div class="scale-item">
              <div class="scale-value">{{ school.student_count || 0 }}</div>
              <div class="scale-label">学生人数</div>
            </div>
            <div class="scale-item">
              <div class="scale-value">{{ school.teacher_count || 0 }}</div>
              <div class="scale-label">教师人数</div>
            </div>
            <div class="scale-item">
              <div class="scale-value">{{ school.class_count || 0 }}</div>
              <div class="scale-label">班级数量</div>
            </div>
            <div class="scale-item">
              <div class="scale-value">{{ teacherStudentRatio }}</div>
              <div class="scale-label">师生比</div>
            </div>
          </div>
          <el-descriptions :column="3" border style="margin-top: 16px">
            <el-descriptions-item label="校长姓名">{{
              ds(school.principal, 'name')
            }}</el-descriptions-item>
            <el-descriptions-item label="联系电话">{{
              ds(school.contact_phone, 'phone')
            }}</el-descriptions-item>
            <el-descriptions-item label="邮箱">{{
              ds(school.email, 'email')
            }}</el-descriptions-item>
          </el-descriptions>
        </div>
      </div>

      <!-- 帮扶信息 -->
      <div class="detail-card">
        <div class="card-header">
          <h3>帮扶信息</h3>
        </div>
        <div class="card-body">
          <el-descriptions :column="3" border>
            <el-descriptions-item label="帮扶状态">
              <el-tag :type="getStatusTagType(school.support_status)">
                {{ getStatusDisplay(school.support_status) }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="帮扶单位">{{
              school.support_unit || '-'
            }}</el-descriptions-item>
            <el-descriptions-item label="创建时间">{{
              formatDate(school.created_at)
            }}</el-descriptions-item>
            <el-descriptions-item label="学校简介" :span="3">{{
              school.description || '无'
            }}</el-descriptions-item>
            <el-descriptions-item label="备注" :span="3">{{
              school.remarks || '无'
            }}</el-descriptions-item>
          </el-descriptions>
        </div>
      </div>

      <!-- 助学兴教项目 -->
      <div class="detail-card">
        <div class="card-header">
          <h3>助学兴教项目</h3>
          <el-button
            size="small"
            type="primary"
            plain
            @click="pushSafe(`/schools/${school.id}/projects`)"
            >管理项目</el-button
          >
        </div>
        <div class="card-body">
          <el-table :data="relatedProjects" size="small">
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
          </el-table>
          <EmptyState v-if="relatedProjects.length === 0" text="暂无助学兴教项目" :size="60" />
        </div>
      </div>

      <!-- 资助学生 -->
      <div class="detail-card">
        <div class="card-header">
          <h3>资助学生</h3>
          <el-button
            size="small"
            type="primary"
            plain
            @click="pushSafe(`/schools/${school.id}/scholarship`)"
            >管理资助学生</el-button
          >
        </div>
        <div class="card-body">
          <el-table :data="scholarshipStudents" stripe size="small">
            <el-table-column prop="student_name" label="学生姓名" width="100" />
            <el-table-column prop="grade" label="年级" width="80" />
            <el-table-column prop="year" label="年度" width="80" />
            <el-table-column prop="amount" label="资助金额(元)" width="120" align="right" />
            <el-table-column prop="status" label="状态" width="90">
              <template #default="{ row }">
                <el-tag size="small">{{ scholarshipStatusMap[row.status] || row.status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="reason" label="资助原因" min-width="160" show-overflow-tooltip />
          </el-table>
          <EmptyState v-if="scholarshipStudents.length === 0" text="暂无资助学生" :size="60" />
        </div>
      </div>

      <!-- 电子资料 -->
      <div class="detail-card">
        <div class="card-header">
          <h3>电子资料</h3>
        </div>
        <div class="card-body">
          <div v-if="attachments.length" class="attachment-grid">
            <div v-for="att in attachments" :key="att.id" class="attachment-card">
              <div class="att-file-icon">
                <el-icon><component :is="getFileIcon(att.file_name)" /></el-icon>
              </div>
              <div class="att-file-info">
                <div class="att-file-name" :title="att.file_name">
                  {{ att.file_name }}
                </div>
                <div class="att-file-meta">
                  <span>{{ formatFileSize(att.file_size) }}</span>
                  <span v-if="att.uploaded_by"> · {{ att.uploaded_by }}</span>
                  <span v-if="att.created_at"> · {{ att.created_at.split('T')[0] }}</span>
                </div>
              </div>
              <el-button type="primary" link size="small" @click="downloadAttachment(att)"
                >下载</el-button
              >
            </div>
          </div>
          <el-empty v-else description="暂无电子资料" :image-size="60">
            <el-button type="primary" size="small" @click="handleEdit">去上传</el-button>
          </el-empty>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import EmptyState from '@/components/business/EmptyState/EmptyState.vue'
import { logger } from '@/utils/logger'
import { AuthStorage } from '@/utils/authStorage'

import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useRouterSafe } from '@/composables/useRouterSafe'
import { useDesensitize } from '@/composables/useDesensitize'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ArrowLeft,
  Edit,
  Delete,
  Loading,
  Document,
  EditPen,
  DataAnalysis,
  Picture,
  Box,
  Folder,
} from '@element-plus/icons-vue'
import { get, del } from '@/api/request'
import { schoolApi } from '@/api/schools'

const { pushSafe } = useRouterSafe()
const { ds } = useDesensitize()
const route = useRoute()
const loading = ref(true)

const school = ref<any>({
  id: '',
  name: '',
  code: '',
  type: '',
  province: '',
  city: '',
  district: '',
  address: '',
  student_count: 0,
  teacher_count: 0,
  class_count: 0,
  support_status: 'inactive',
  support_unit: '',
  principal: '',
  contact_phone: '',
  email: '',
  description: '',
  remarks: '',
  created_at: '',
})

const relatedProjects = ref<any[]>([])
const scholarshipStudents = ref<any[]>([])

const phaseMap: Record<string, string> = {
  research: '调研',
  approval: '立项审批',
  implementation: '实施',
  acceptance: '验收',
  completed: '已完成',
}
const scholarshipStatusMap: Record<string, string> = {
  pending: '待审批',
  approved: '已批准',
  disbursed: '已发放',
  completed: '已完成',
}
function phaseTagType(p: string) {
  if (p === 'completed') return 'success'
  if (p === 'implementation') return 'primary'
  if (p === 'acceptance') return 'warning'
  return 'info'
}

const attachments = ref<any[]>([])
const baseUrl = import.meta.env.VITE_API_BASE_URL || '/api/v1'

const teacherStudentRatio = computed(() => {
  const s = school.value.student_count || 0
  const t = school.value.teacher_count || 0
  if (t === 0) return '-'
  return `1:${Math.round(s / t)}`
})

const getTypeDisplay = (type: string) => {
  const map: Record<string, string> = {
    primary: '小学',
    middle: '初中',
    high: '高中',
    vocational: '职业学校',
    other: '其他',
  }
  return map[type] || type || '-'
}

const getStatusDisplay = (status: string) => {
  const map: Record<string, string> = {
    active: '帮扶中',
    inactive: '未帮扶',
    completed: '已完成',
  }
  return map[status] || '未帮扶'
}

const getStatusTagType = (status: string) => {
  if (status === 'active') return 'success'
  if (status === 'completed') return 'primary'
  return 'info'
}

const formatDate = (dateStr?: string) => {
  if (!dateStr) return '-'
  return dateStr.split('T')[0]
}

const loadAttachments = async () => {
  const id = route.params.id
  if (!id) return
  try {
    const resp = await get(`/schools/${id}/attachments`)
    const result = resp.data || resp
    attachments.value = result?.items || (Array.isArray(result) ? result : [])
  } catch (e) {
    logger.error('加载附件失败:', e)
  }
}

function downloadAttachment(att: any) {
  const url = `${baseUrl}/schools/attachments/${att.id}/download`
  const token = AuthStorage.getToken() || ''
  fetch(url, { headers: { Authorization: token ? `Bearer ${token}` : '' } })
    .then((r) => r.blob())
    .then((blob) => {
      const link = document.createElement('a')
      link.href = URL.createObjectURL(blob)
      link.download = att.file_name
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(link.href)
    })
    .catch((err: any) => {
      logger.error('[Schools/Detail] 下载附件失败', err)
      ElMessage.error('下载失败，请重试')
    })
}

function getFileIcon(name: string) {
  const ext = (name || '').split('.').pop()?.toLowerCase() || ''
  if (['pdf'].includes(ext)) return Document
  if (['doc', 'docx'].includes(ext)) return EditPen
  if (['xls', 'xlsx'].includes(ext)) return DataAnalysis
  if (['ppt', 'pptx'].includes(ext)) return DataAnalysis
  if (['jpg', 'jpeg', 'png', 'gif'].includes(ext)) return Picture
  if (['zip', 'rar'].includes(ext)) return Box
  return Folder
}

function formatFileSize(bytes: number) {
  if (!bytes) return '0B'
  if (bytes < 1024) return bytes + 'B'
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + 'KB'
  return (bytes / 1048576).toFixed(1) + 'MB'
}

const loadSchool = async () => {
  const id = route.params.id
  if (!id) {
    ElMessage.error('无效的学校ID')
    pushSafe('/schools')
    return
  }
  loading.value = true
  try {
    const response = await get(`/schools/${id}`)
    const result = response
    const data = result.data || result
    if (data) {
      Object.assign(school.value, {
        id: data.id,
        name: data.name || '',
        code: data.code || '',
        type: data.type || '',
        province: data.province || '',
        city: data.city || '',
        district: data.district || '',
        address: data.address || '',
        student_count: data.student_count || data.students || 0,
        teacher_count: data.teacher_count || data.teachers || 0,
        class_count: data.class_count || 0,
        support_status: data.support_status || 'inactive',
        support_unit: data.support_unit || '',
        principal: data.principal || '',
        contact_phone: data.contact_phone || '',
        email: data.email || '',
        description: data.description || '',
        remarks: data.remarks || '',
        created_at: data.created_at || '',
      })
    } else {
      ElMessage.error('加载学校信息失败')
      pushSafe('/schools')
    }
  } catch (error) {
    logger.error('加载学校信息失败:', error)
    ElMessage.error('加载学校信息失败')
  } finally {
    loading.value = false
  }
}

const handleEdit = () => {
  pushSafe(`/schools/${school.value.id}/edit`)
}

const handleDelete = async () => {
  try {
    await ElMessageBox.confirm('确定要删除这所学校吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await del(`/schools/${school.value.id}`)
    ElMessage.success('删除成功')
    pushSafe('/schools')
  } catch (error) {
    if (error !== 'cancel') {
      logger.error('删除失败:', error)
    }
  }
}

const handleBack = () => {
  pushSafe('/schools')
}

async function loadProjects() {
  const id = route.params.id
  if (!id) return
  try {
    const res = await schoolApi.listProjects(Number(id))
    relatedProjects.value = res.items || []
  } catch (error) {
    logger.error('Failed to load projects:', error)
  }
}
async function loadScholarship() {
  const id = route.params.id
  if (!id) return
  try {
    const res = await schoolApi.listScholarshipStudents(Number(id))
    scholarshipStudents.value = res.items || []
  } catch (error) {
    logger.error('Failed to load scholarship students:', error)
  }
}

onMounted(() => {
  loadSchool()
  loadAttachments()
  loadProjects()
  loadScholarship()
})
</script>

<style scoped>
.school-detail-page {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
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

.header-actions {
  display: flex;
  gap: 12px;
}

.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 100px 0;
  color: var(--color-text-secondary);
}

.loading-icon {
  font-size: 32px;
  animation: spin 1s linear infinite;
  margin-bottom: 16px;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.detail-card {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  margin-bottom: 20px;
  overflow: hidden;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  background: linear-gradient(135deg, var(--color-primary-dark-1) 0%, var(--color-primary) 100%);
  border-bottom: 1px solid var(--color-border-light);
}

.card-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: white;
}

.card-body {
  padding: 24px;
}

/* 规模信息统计 */
.scale-stats {
  display: flex;
  gap: 20px;
}

.scale-item {
  flex: 1;
  text-align: center;
  padding: 16px;
  background: linear-gradient(135deg, rgba(27, 67, 50, 0.08) 0%, rgba(45, 106, 79, 0.05) 100%);
  border-radius: 8px;
  border: 1px solid rgba(45, 106, 79, 0.15);
}

.scale-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--color-primary-dark-1);
}

.scale-label {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin-top: 4px;
}

:deep(.el-descriptions__label) {
  font-weight: 500;
  background-color: var(--color-bg-hover);
}

:deep(.el-descriptions__content) {
  color: var(--color-text-primary);
}

/* 电子资料 */
.attachment-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 12px;
}

.attachment-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border: 1px solid var(--color-border-light);
  border-radius: 8px;
  transition: all 0.2s;
  background: var(--color-bg-hover);
}

.attachment-card:hover {
  border-color: var(--color-primary);
  box-shadow: 0 2px 8px rgba(45, 106, 79, 0.12);
}

.att-file-icon {
  font-size: 28px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
}

.att-file-info {
  flex: 1;
  min-width: 0;
}

.att-file-name {
  font-size: 14px;
  color: var(--color-text-primary);
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.att-file-meta {
  font-size: 12px;
  color: var(--color-info);
  margin-top: 2px;
}
</style>
