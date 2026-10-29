<template>
  <div class="policy-edit">
    <el-card v-loading="loading" class="edit-card">
      <template #header>
        <div class="card-header">
          <span class="title">{{ isEdit ? '编辑政策' : '新增政策' }}</span>
          <div class="actions">
            <el-button @click="handleBack">
              <el-icon><Back /></el-icon>
              返回列表
            </el-button>
          </div>
        </div>
      </template>

      <el-form ref="formRef" :model="formData" :rules="rules" label-width="120px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="政策标题" prop="title">
              <el-input
                v-model="formData.title"
                placeholder="请输入政策标题"
                maxlength="500"
                show-word-limit
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="文号" prop="document_number">
              <el-input
                v-model="formData.document_number"
                placeholder="请输入文号（可选）"
                maxlength="100"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="政策分类" prop="category">
              <el-select
                v-model="formData.category"
                placeholder="请选择政策分类"
                style="width: 100%"
                @change="handleCategoryChange"
              >
                <el-option label="专项政策" value="military" />
                <el-option label="地方政策" value="local" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="组织层级" prop="organization_level">
              <el-select
                v-model="formData.organization_level"
                placeholder="请选择组织层级"
                style="width: 100%"
                :disabled="!formData.category"
              >
                <el-option
                  v-for="level in levelOptions"
                  :key="level.value"
                  :label="level.label"
                  :value="level.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="发布部门" prop="issuing_authority">
              <el-input
                v-model="formData.issuing_authority"
                placeholder="请输入发布部门（可选）"
                maxlength="200"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="发布日期" prop="publish_date">
              <el-date-picker
                v-model="formData.publish_date"
                type="date"
                value-format="YYYY-MM-DDTHH:mm:ss"
                placeholder="请选择发布日期"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="生效日期" prop="effective_date">
              <el-date-picker
                v-model="formData.effective_date"
                type="date"
                value-format="YYYY-MM-DDTHH:mm:ss"
                placeholder="请选择生效日期（可选）"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="关键词" prop="keywords">
              <el-input
                v-model="formData.keywords"
                placeholder="多个关键词用逗号分隔（可选）"
                maxlength="500"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="状态" prop="status">
          <el-radio-group v-model="formData.status">
            <el-radio value="active">有效</el-radio>
            <el-radio value="invalid">失效</el-radio>
            <el-radio value="draft">草稿</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="政策摘要" prop="summary">
          <el-input
            v-model="formData.summary"
            type="textarea"
            :rows="3"
            placeholder="请输入政策摘要（可选）"
            maxlength="500"
            show-word-limit
          />
        </el-form-item>

        <el-form-item label="政策内容" prop="content">
          <el-input
            v-model="formData.content"
            type="textarea"
            :rows="12"
            placeholder="请输入政策内容"
          />
        </el-form-item>

        <el-form-item label="附件">
          <el-upload
            class="upload-demo"
            :action="uploadAction"
            :headers="uploadHeaders"
            :file-list="fileList"
            :on-success="handleUploadSuccess"
            :on-remove="handleUploadRemove"
            :before-upload="beforeUpload"
            :auto-upload="true"
            multiple
          >
            <el-button type="primary">
              <el-icon><Upload /></el-icon>
              选择文件
            </el-button>
            <template #tip>
              <div class="el-upload__tip">
                支持上传 jpg/png/pdf/doc/docx/pptx 文件，单个文件不超过 50MB
              </div>
            </template>
          </el-upload>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="submitLoading" @click="handleSubmit">
            <el-icon><Check /></el-icon>
            保存
          </el-button>
          <el-button @click="handleBack">取消</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { getErrorMessage } from '@/utils/getErrorMessage'
import { ref, reactive, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import {
  ElMessage,
  ElMessageBox,
  type FormInstance,
  type FormRules,
  type UploadFile,
} from 'element-plus'
import { useDirtyGuard } from '@/composables/useDirtyGuard'
import { useFormDraft } from '@/composables/useFormDraft'
import { useRoute } from 'vue-router'
import { useRouterSafe, safeRouteParam } from '@/composables/useRouterSafe'
import { useUploadHeaders } from '@/composables/useUploadHeaders'
import { Back, Upload, Check } from '@element-plus/icons-vue'
import { usePolicyStore } from '@/stores/policy'
import { getLevelOptions, type PolicyCategory, type PolicyStatus } from '@/api/policy'

type OrganizationLevel = string

const route = useRoute()
const { pushSafe } = useRouterSafe()
const policyStore = usePolicyStore()

// 上传配置：通用文件上传端点 + 认证/CSRF 头
const uploadAction = ref(`${import.meta.env.VITE_API_BASE_URL || '/api/v1'}/files/upload`)
const { uploadHeaders, ensureCsrf } = useUploadHeaders()

const loading = ref(false)
const submitLoading = ref(false)
const isEdit = computed(() => !!route.params.id)

// 表单数据
const formData = reactive({
  title: '',
  category: '' as PolicyCategory | '',
  organization_level: '' as OrganizationLevel | '',
  publish_date: '',
  effective_date: '',
  issuing_authority: '',
  content: '',
  summary: '',
  document_number: '',
  keywords: '',
  attachment_urls: [] as string[],
  status: 'active' as PolicyStatus,
})

const fileList = ref<UploadFile[]>([])

// ── ③ 录入效率：草稿自动保存 + 未保存离开拦截 ──────────────────────────
// 草稿按业务键隔离：新建与编辑不同记录互不污染。
const draftKey = isEdit.value
  ? `policies:edit:${safeRouteParam(route.params.id)}`
  : 'policies:edit:new'
const {
  hasDraft,
  restore: restoreDraft,
  clear: clearDraft,
  flush: flushDraft,
} = useFormDraft(formData, { key: draftKey })

// 脏标记：初始化（loadData 回填 / 草稿恢复）完成后由 onMounted 复位，
// 因此不必再造"只在初始化后注册 watcher"的可选链 —— 那会留下永不进入的分支（覆盖率黑洞）。
const isDirty = ref(false)
const stopDirtyWatch = watch(
  formData,
  () => {
    isDirty.value = true
  },
  { deep: true }
)
useDirtyGuard(isDirty)

// 层级选项（根据分类动态变化）
// Level options (loaded async on category change)
const levelOptions = ref<{ value: string; label: string }[]>([])
const levelOptionsLoading = ref(false)

async function loadLevelOptions() {
  if (!formData.category) {
    levelOptions.value = []
    return
  }
  levelOptionsLoading.value = true
  try {
    // 后端 /policies/options/levels 不接收分类参数（曾用 (fn 宽松断言)(category) 假传，
    // 参数被静默忽略）；这里按真实契约调用，去掉无效入参。
    const res = await getLevelOptions()
    const data = res?.data?.data ?? res?.data ?? res
    levelOptions.value = Array.isArray(data) ? (data as { value: string; label: string }[]) : []
  } catch {
    levelOptions.value = []
  } finally {
    levelOptionsLoading.value = false
  }
}

// 表单验证规则
const rules: FormRules = {
  title: [
    { required: true, message: '请输入政策标题', trigger: 'blur' },
    {
      min: 2,
      max: 500,
      message: '标题长度在 2 到 500 个字符',
      trigger: 'blur',
    },
  ],
  category: [{ required: true, message: '请选择政策分类', trigger: 'change' }],
  organization_level: [{ required: true, message: '请选择组织层级', trigger: 'change' }],
  publish_date: [{ required: true, message: '请选择发布日期', trigger: 'change' }],
  content: [
    { required: true, message: '请输入政策内容', trigger: 'blur' },
    { max: 100000, message: '政策内容不能超过10万字符', trigger: 'blur' },
  ],
}

const formRef = ref<FormInstance>()

// 分类变化时清空层级选择并重新加载选项
const handleCategoryChange = () => {
  formData.organization_level = ''
  loadLevelOptions()
}

// 加载政策数据（编辑模式）
const loadData = async () => {
  const id = safeRouteParam(route.params.id)
  if (!id || isNaN(id)) return

  loading.value = true
  try {
    await policyStore.fetchPolicy(id)
    const policy = policyStore.current

    if (policy) {
      // 边界类型把字段声明为可选（后端可能省略），表单要求字符串 → 统一给默认值，
      // 避免把 undefined 塞进必填字段（此前靠宽松断言躲过了编译期检查）。
      formData.title = policy.title ?? ''
      formData.category = policy.category ?? ''
      formData.organization_level = policy.organization_level ?? ''
      formData.publish_date = policy.publish_date ?? ''
      formData.effective_date = policy.effective_date || ''
      formData.issuing_authority = policy.department || policy.issuing_authority || ''
      formData.content = policy.content ?? ''
      formData.summary = policy.summary || ''
      formData.document_number = policy.document_number || ''
      formData.keywords = policy.keywords || ''
      formData.attachment_urls = policy.attachment_urls || []
      // status 只透传、不臆造默认值：详情响应省略 status 时若填 'draft'，
      // 用户一保存就会把"已发布"政策静默降级为草稿（且与新增表单默认 'active' 不一致）。
      formData.status = policy.status as typeof formData.status

      // 处理附件列表
      if (policy.attachment_urls && policy.attachment_urls.length > 0) {
        fileList.value = policy.attachment_urls.map((url: string, index: number) => ({
          name: url.split('/').pop() || `附件${index + 1}`,
          url: url,
          uid: index,
        })) as UploadFile[]
      }
    } else {
      ElMessage.error('未找到该政策')
      pushSafe('/policies')
    }
  } catch (error: any) {
    ElMessage.error(getErrorMessage(error, '加载政策数据失败'))
    pushSafe('/policies')
  } finally {
    loading.value = false
  }
}

// 返回列表
const handleBack = () => {
  pushSafe('/policies')
}

// 上传成功处理（兼容新旧两种响应格式：{url} 直返 与 {code,data:{url}} 信封）
/** el-upload 的 file 对象在运行时会被我们回填 url / 保存原始响应（类型上未声明） */
type UploadedFileLike = UploadFile & {
  url?: string
  response?: { data?: { url?: string }; url?: string }
}

const handleUploadSuccess = (response: any, _file: UploadFile) => {
  const url = response?.data?.url ?? response?.url
  if (url) {
    formData.attachment_urls.push(url)
    // 关键：回填 file.url，否则点"移除"无法从 attachment_urls 中删除该附件
    ;(_file as UploadedFileLike).url = url
  }
  ElMessage.success('上传成功')
}

// 上传移除处理（优先 file.url，回退响应体；比较前去除首尾空白以增强健壮性）
const handleUploadRemove = (file: UploadFile) => {
  const shaped = file as UploadedFileLike
  const raw = shaped.url ?? shaped.response?.data?.url ?? shaped.response?.url
  const url = typeof raw === 'string' ? raw.trim() : ''
  if (!url) return
  const index = formData.attachment_urls.findIndex((u) => typeof u === 'string' && u.trim() === url)
  if (index > -1) {
    formData.attachment_urls.splice(index, 1)
  }
}

// 上传前检查（同步等待 CSRF token 就绪，避免原生 XHR 上传被 403 拦截）
// 限制与后端 /policies/{id}/upload、/files/upload 对齐：pdf/doc/docx/pptx/jpg/png，≤50MB
const beforeUpload = async (file: File) => {
  const allowedTypes = [
    'image/jpeg',
    'image/png',
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  ]
  const maxSize = 50 * 1024 * 1024 // 50MB（与后端一致）

  if (!allowedTypes.includes(file.type)) {
    ElMessage.error('只能上传 jpg/png/pdf/doc/docx/pptx 文件!')
    return false
  }

  if (file.size > maxSize) {
    ElMessage.error('文件大小不能超过 50MB!')
    return false
  }

  await ensureCsrf()
  return true
}

// 提交表单
const handleSubmit = async () => {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (!valid) return

    submitLoading.value = true
    try {
      const data = {
        title: formData.title,
        category: formData.category as PolicyCategory,
        organization_level: formData.organization_level as OrganizationLevel,
        publish_date: formData.publish_date,
        effective_date: formData.effective_date || undefined,
        issuing_authority: formData.issuing_authority || undefined,
        content: formData.content,
        summary: formData.summary || undefined,
        document_number: formData.document_number || undefined,
        keywords: formData.keywords || undefined,
        status: formData.status,
        attachment_urls: formData.attachment_urls || [],
      }

      if (isEdit.value) {
        // 更新政策
        const id = safeRouteParam(route.params.id)
        const res = await policyStore.updatePolicy(id, data)
        if (res?.code !== 200) throw new Error(res?.message || '更新失败，请稍后重试')
        ElMessage.success('更新成功')
      } else {
        // 新增政策
        const res = await policyStore.createPolicy(data)
        if (res?.code !== 200 || !res?.data) {
          throw new Error(res?.message || '新增失败，请稍后重试')
        }
        ElMessage.success('新增成功')
      }

      // 提交成功：清掉草稿并复位脏标记（否则下次进来会"复活"已提交的数据）
      clearDraft()
      isDirty.value = false
      pushSafe('/policies')
    } catch (error: any) {
      ElMessage.error(getErrorMessage(error, '保存失败'))
    } finally {
      submitLoading.value = false
    }
  })
}

// 初始化
onMounted(async () => {
  if (isEdit.value) {
    await loadData()
  }
  loadLevelOptions()

  // ③ 有未提交草稿时先问再恢复：不静默覆盖后端刚拉回来的数据。
  if (hasDraft.value) {
    try {
      await ElMessageBox.confirm('检测到上次未提交的草稿，是否恢复？', '恢复草稿', {
        confirmButtonText: '恢复',
        cancelButtonText: '忽略',
        type: 'info',
      })
      restoreDraft()
      ElMessage.success('已恢复草稿')
    } catch {
      clearDraft()
    }
  }

  // 初始化完成（含 loadData 回填与草稿恢复）后复位脏标记，
  // 否则上面那个 deep watcher 会在回填时把表单误判为"用户已修改"。
  isDirty.value = false
})

onBeforeUnmount(() => {
  stopDirtyWatch()
  // 离开前立刻落盘一次（防抖窗口内离开也不能丢）
  flushDraft()
})
</script>

<style scoped lang="scss">
.policy-edit {
  padding: 20px;
  background: rgba(10, 30, 20, 0.3);
  min-height: calc(100vh - 60px);
}

.edit-card {
  background: var(--color-white-95);
  border: 1px solid var(--color-primary-light-a30);
  box-shadow: 0 2px 8px var(--color-black-10);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.title {
  font-size: 18px;
  font-weight: bold;
  color: $military-dark;
}

.actions {
  display: flex;
  gap: 10px;
}

.upload-demo {
  width: 100%;
}

:deep(.el-form-item__label) {
  color: $military-dark;
  font-weight: 500;
}

:deep(.el-input__wrapper) {
  background-color: var(--color-white-90);
}

:deep(.el-textarea__inner) {
  background-color: var(--color-white-90);
  color: $military-dark;
}

:deep(.el-select__wrapper),
:deep(.el-select .el-input__wrapper) {
  background-color: var(--color-white-90);
}

:deep(.el-date-editor) {
  background-color: var(--color-white-90);
}

:deep(.el-radio-group) {
  color: $military-dark;
}

:deep(.el-radio__label) {
  color: $military-dark;
}

:deep(.el-upload__tip) {
  color: var(--color-text-secondary);
}
</style>
