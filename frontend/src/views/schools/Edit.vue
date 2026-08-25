<template>
  <div class="school-edit">
    <el-card v-loading="loading" class="edit-card">
      <template #header>
        <div class="card-header">
          <span class="title">{{ isEdit ? '编辑学校' : '新增学校' }}</span>
          <el-button @click="handleBack">返回</el-button>
        </div>
      </template>

      <el-form ref="formRef" :model="formData" :rules="rules" label-width="120px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="学校名称" prop="name">
              <el-input v-model="formData.name" placeholder="请输入学校名称" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="学校编码" prop="code">
              <el-input v-model="formData.code" placeholder="请输入学校编码（选填）" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="学校类型" prop="type">
              <el-select v-model="formData.type" placeholder="请选择" style="width: 100%">
                <el-option label="小学" value="primary" />
                <el-option label="初中" value="middle" />
                <el-option label="高中" value="high" />
                <el-option label="职业学校" value="vocational" />
                <el-option label="其他" value="other" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="帮扶状态" prop="support_status">
              <el-select v-model="formData.support_status" placeholder="请选择" style="width: 100%">
                <el-option label="帮扶中" value="active" />
                <el-option label="未帮扶" value="inactive" />
                <el-option label="已完成" value="completed" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="24">
            <GuizhouRegionSelector
              :model-value="regionValue"
              :show-township="false"
              @update:model-value="onRegionChange"
            />
          </el-col>
        </el-row>

        <el-form-item label="详细地址">
          <el-input v-model="formData.address" placeholder="请输入详细地址" />
        </el-form-item>

        <el-form-item label="坐标设置">
          <MapPicker v-model:latitude="formData.latitude" v-model:longitude="formData.longitude" />
        </el-form-item>

        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="学生人数" prop="student_count">
              <el-input-number
                v-model="formData.student_count"
                :min="0"
                controls-position="right"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="教师人数" prop="teacher_count">
              <el-input-number
                v-model="formData.teacher_count"
                :min="0"
                controls-position="right"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="班级数量">
              <el-input-number
                v-model="formData.class_count"
                :min="0"
                controls-position="right"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="帮扶单位">
              <el-input v-model="formData.support_unit" placeholder="请输入帮扶单位" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="校长姓名">
              <el-input v-model="formData.principal" placeholder="请输入校长姓名" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="联系电话" prop="contact_phone">
              <el-input v-model="formData.contact_phone" placeholder="请输入联系电话" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="邮箱" prop="email">
              <el-input v-model="formData.email" placeholder="请输入邮箱" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="学校简介">
          <el-input
            v-model="formData.description"
            type="textarea"
            :rows="4"
            placeholder="请输入学校简介"
          />
        </el-form-item>

        <el-form-item label="备注">
          <el-input v-model="formData.remarks" type="textarea" :rows="2" placeholder="请输入备注" />
        </el-form-item>

        <!-- 电子资料上传（仅编辑模式） -->
        <el-form-item v-if="isEdit" label="电子资料">
          <div class="attachment-section">
            <el-upload
              :action="attachmentUploadUrl"
              :headers="uploadHeaders"
              :on-success="onAttachmentUploaded"
              :on-error="onAttachmentError"
              :before-upload="beforeAttachmentUpload"
              multiple
              :show-file-list="false"
            >
              <el-button type="primary" plain size="small">
                <el-icon><Upload /></el-icon>上传资料
              </el-button>
            </el-upload>
            <div class="upload-tip">支持 PDF、Word、Excel、图片等格式，单文件不超过10MB</div>

            <!-- 已上传文件列表 -->
            <div v-if="attachments.length" class="attachment-list">
              <div v-for="att in attachments" :key="att.id" class="attachment-item">
                <div class="att-info">
                  <span class="att-icon">
                    <el-icon><component :is="getFileIcon(att.file_name)" /></el-icon>
                  </span>
                  <span class="att-name">{{ att.file_name }}</span>
                  <span class="att-size">{{ formatFileSize(att.file_size) }}</span>
                </div>
                <div class="att-actions">
                  <el-button type="primary" link size="small" @click="downloadAttachment(att)"
                    >下载</el-button
                  >
                  <el-popconfirm title="确定删除该文件？" @confirm="deleteAttachment(att)">
                    <template #reference>
                      <el-button type="danger" link size="small">删除</el-button>
                    </template>
                  </el-popconfirm>
                </div>
              </div>
            </div>
            <el-empty v-else description="暂无电子资料" :image-size="40" />
          </div>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="submitLoading" @click="handleSubmit">保存</el-button>
          <el-button @click="handleBack">取消</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { logger } from '@/utils/logger'
import { AuthStorage } from '@/utils/authStorage'
import { useUploadHeaders } from '@/composables/useUploadHeaders'

import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useRouterSafe } from '@/composables/useRouterSafe'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import {
  Upload,
  Document,
  EditPen,
  DataAnalysis,
  Picture,
  Box,
  Folder,
} from '@element-plus/icons-vue'
import { get, post, put, del } from '@/api/request'
import MapPicker from '@/components/MapPicker.vue'
import GuizhouRegionSelector from '@/components/common/GuizhouRegionSelector.vue'
import type { RegionValue } from '@/components/common/GuizhouRegionSelector.vue'
import { DEFAULT_PROVINCE } from '@/data/guizhouRegion'

const route = useRoute()
const { pushSafe } = useRouterSafe()

const loading = ref(false)
const submitLoading = ref(false)
const formRef = ref<FormInstance>()

const isEdit = computed(() => !!route.params.id)
const attachments = ref<any[]>([])

// 上传配置
const baseUrl = import.meta.env.VITE_API_BASE_URL || '/api/v1'
const attachmentUploadUrl = computed(() => `${baseUrl}/schools/${route.params.id}/attachments`)
const { uploadHeaders } = useUploadHeaders()

const formData = reactive({
  name: '',
  code: '',
  type: 'primary',
  province: DEFAULT_PROVINCE,
  city: '',
  district: '',
  address: '',
  latitude: null as number | null,
  longitude: null as number | null,
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
})

// 区域选择器双向绑定
const regionValue = computed<RegionValue>(() => ({
  city: formData.city || undefined,
  county: formData.district || undefined,
}))

function onRegionChange(val: RegionValue) {
  formData.city = val.city || ''
  formData.district = val.county || ''
}

const rules: FormRules = {
  name: [
    { required: true, message: '请输入学校名称', trigger: 'blur' },
    { min: 2, max: 50, message: '学校名称长度为 2-50 个字符', trigger: 'blur' },
  ],
  type: [{ required: true, message: '请选择学校类型', trigger: 'change' }],
  support_status: [{ required: true, message: '请选择帮扶状态', trigger: 'change' }],
  student_count: [{ type: 'number', min: 0, message: '学生人数不能为负数', trigger: 'change' }],
  teacher_count: [{ type: 'number', min: 0, message: '教师人数不能为负数', trigger: 'change' }],
  contact_phone: [
    {
      pattern: /^1[3-9]\d{9}$|^0\d{2,3}-?\d{7,8}$/,
      message: '请输入有效的电话号码',
      trigger: 'blur',
    },
  ],
  email: [{ type: 'email', message: '请输入有效的邮箱地址', trigger: 'blur' }],
}

const loadData = async () => {
  const id = route.params.id
  if (!id) return

  loading.value = true
  try {
    const response = await get(`/schools/${id}`)
    const result = response
    const data = result.data || result // 兼容扁平格式
    if (data) {
      Object.assign(formData, {
        name: data.name || '',
        code: data.code || '',
        type: data.type || 'primary',
        province: data.province || DEFAULT_PROVINCE,
        city: data.city || '',
        district: data.district || '',
        address: data.address || '',
        latitude: data.latitude ?? null,
        longitude: data.longitude ?? null,
        student_count: data.student_count || 0,
        teacher_count: data.teacher_count || 0,
        class_count: data.class_count || 0,
        support_status: data.support_status || 'inactive',
        support_unit: data.support_unit || '',
        principal: data.principal || '',
        contact_phone: data.contact_phone || '',
        email: data.email || '',
        description: data.description || '',
        remarks: data.remarks || '',
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

const handleBack = () => {
  pushSafe('/schools')
}

// 附件管理
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

function beforeAttachmentUpload(file: any) {
  if (file.size > 10 * 1024 * 1024) {
    ElMessage.error('文件大小不能超过 10MB')
    return false
  }
  return true
}

function onAttachmentUploaded(_response: any) {
  ElMessage.success('上传成功')
  loadAttachments()
}

function onAttachmentError() {
  ElMessage.error('上传失败')
}

async function deleteAttachment(att: any) {
  try {
    await del(`/schools/attachments/${att.id}`)
    ElMessage.success('删除成功')
    loadAttachments()
  } catch {
    ElMessage.error('删除失败')
  }
}

function downloadAttachment(att: any) {
  const url = `${baseUrl}/schools/attachments/${att.id}/download`
  const token = AuthStorage.getToken() || ''
  // Use fetch to handle auth header then trigger download
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
      logger.error('[Schools/Edit] 下载附件失败', err)
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

const handleSubmit = async () => {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (!valid) return

    submitLoading.value = true
    try {
      if (isEdit.value) {
        await put(`/schools/${route.params.id}`, formData)
      } else {
        await post('/schools', formData)
      }
      ElMessage.success(isEdit.value ? '更新成功' : '创建成功')
      pushSafe('/schools')
    } catch (error) {
      logger.error('保存失败:', error)
      ElMessage.error('保存失败')
    } finally {
      submitLoading.value = false
    }
  })
}

onMounted(() => {
  if (isEdit.value) {
    loadData()
    loadAttachments()
  }
})
</script>

<style scoped>
.school-edit {
  padding: 20px;
}

.edit-card {
  background: #fff;
  border: 1px solid var(--color-border-light);
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
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

:deep(.el-form-item__label) {
  color: var(--color-text-primary);
}

/* 附件区域 */
.attachment-section {
  width: 100%;
}

.upload-tip {
  font-size: 12px;
  color: var(--color-info);
  margin-top: 4px;
}

.attachment-list {
  margin-top: 12px;
  border: 1px solid var(--color-border-light);
  border-radius: 4px;
  overflow: hidden;
}

.attachment-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  border-bottom: 1px solid var(--color-border-light);
  transition: background 0.2s;
}

.attachment-item:last-child {
  border-bottom: none;
}

.attachment-item:hover {
  background: var(--color-bg-hover);
}

.att-info {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.att-icon {
  font-size: 18px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
}

.att-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 14px;
  color: var(--color-text-primary);
}

.att-size {
  color: var(--color-info);
  font-size: 12px;
  flex-shrink: 0;
}

.att-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
  margin-left: 12px;
}
</style>
