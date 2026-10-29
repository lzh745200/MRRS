<template>
  <div class="organization-edit">
    <el-card v-loading="loading" class="edit-card">
      <template #header>
        <div class="card-header">
          <span class="title">{{ isEdit ? '编辑组织' : '新增组织' }}</span>
          <el-button @click="handleBack">返回</el-button>
        </div>
      </template>

      <el-form ref="formRef" :model="formData" :rules="rules" label-width="120px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="组织名称" prop="name">
              <el-input v-model="formData.name" placeholder="请输入组织名称" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="组织编码" prop="code">
              <el-input
                v-model="formData.code"
                placeholder="6 位行政区划代码，如 520000 / 520100 / 520102"
                maxlength="6"
                :disabled="isEdit"
              />
              <div class="form-hint">
                省级 XX0000、市州级 XXYY00、县市级 XXYYZZ；创建后不可修改。
              </div>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="上级组织" prop="parent_id">
              <el-select
                v-model="formData.parent_id"
                placeholder="请选择上级组织（可选）"
                clearable
                filterable
                style="width: 100%"
              >
                <el-option label="无（顶级组织）" :value="null as unknown as number" />
                <el-option
                  v-for="item in parentOptions"
                  :key="item.id"
                  :label="item.name"
                  :value="item.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="组织类型" prop="org_type">
              <el-select
                v-model="formData.org_type"
                placeholder="请选择组织类型"
                style="width: 100%"
              >
                <el-option label="部门单位" value="department" />
                <el-option label="帮扶单位" value="support_unit" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="联系人">
              <el-input v-model="formData.contact_person" placeholder="请输入联系人" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="联系电话" prop="contact_phone">
              <el-input v-model="formData.contact_phone" placeholder="请输入联系电话" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="联系邮箱" prop="contact_email">
              <el-input v-model="formData.contact_email" placeholder="请输入联系邮箱" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态">
              <el-switch v-model="formData.is_active" active-text="正常" inactive-text="停用" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="地址">
          <el-input v-model="formData.address" placeholder="请输入地址" />
        </el-form-item>

        <el-form-item label="描述">
          <el-input
            v-model="formData.description"
            type="textarea"
            :rows="4"
            placeholder="请输入组织描述"
          />
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
import { getErrorMessage } from '@/utils/getErrorMessage'

import { ref, reactive, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useRouterSafe, safeRouteParam } from '@/composables/useRouterSafe'
import { useDirtyGuard } from '@/composables/useDirtyGuard'
import { useFormDraft } from '@/composables/useFormDraft'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import {
  getOrganization,
  getOrganizations,
  createOrganization,
  updateOrganization,
} from '@/api/organization'
import type { Organization } from '@/types/organization'

const route = useRoute()
const { pushSafe } = useRouterSafe()

const loading = ref(false)
const submitLoading = ref(false)
const formRef = ref<FormInstance>()
const parentOptions = ref<Organization[]>([])

const isEdit = computed(() => !!route.params.id)

const formData = reactive({
  name: '',
  code: '',
  parent_id: null as number | null,
  org_type: 'department',
  is_active: true,
  contact_person: '',
  contact_phone: '',
  contact_email: '',
  address: '',
  description: '',
})

// ── ③ 录入效率：草稿自动保存 + 未保存离开拦截（组织编辑页）──────────────
const draftKey = isEdit.value
  ? `organization:edit:${safeRouteParam(route.params.id)}`
  : 'organization:edit:new'
const {
  hasDraft,
  restore: restoreDraft,
  clear: clearDraft,
  flush: flushDraft,
} = useFormDraft(formData, { key: draftKey })

// 初始化（loadData 回填 / 草稿恢复）完成后由 onMounted 复位，避免回填被当成用户修改
const isDirty = ref(false)
const stopDirtyWatch = watch(
  formData,
  () => {
    isDirty.value = true
  },
  { deep: true }
)
useDirtyGuard(isDirty)

const rules: FormRules = {
  code: [
    { required: true, message: '请输入 6 位行政区划代码', trigger: 'blur' },
    { pattern: /^\d{6}$/, message: '必须是 6 位数字（如 520000）', trigger: 'blur' },
  ],
  name: [{ required: true, message: '请输入组织名称', trigger: 'blur' }],
  org_type: [{ required: true, message: '请选择组织类型', trigger: 'change' }],
  contact_phone: [
    {
      pattern: /^1[3-9]\d{9}$/,
      message: '请输入正确的手机号',
      trigger: 'blur',
    },
  ],
  contact_email: [
    {
      pattern: /^[\w.-]+@[\w.-]+\.\w+$/,
      message: '请输入正确的邮箱地址',
      trigger: 'blur',
    },
  ],
}

const loadParentOptions = async () => {
  try {
    const res = await getOrganizations({ page_size: 200, is_active: true })
    const currentId = safeRouteParam(route.params.id)
    parentOptions.value = (res?.items ?? []).filter((item: Organization) => item.id !== currentId)
  } catch (error) {
    logger.error('加载上级组织失败:', error)
    ElMessage.error(getErrorMessage(error, '加载上级组织失败，请稍后重试'))
  }
}

const loadData = async () => {
  const id = safeRouteParam(route.params.id)
  if (!id) return

  loading.value = true
  try {
    const data: any = await getOrganization(id as number)
    Object.assign(formData, {
      name: data.name || '',
      // 响应信封的顶层 `code` 是 HTTP 状态码（200），响应拦截器展平 data 载荷时
      // 会跳过已存在的键 → 组织自身的业务 code 不会提到顶层。必须从载荷里取，
      // 否则"组织编码"输入框会显示 200。
      code: data?.data?.code || '',
      parent_id: data.parent_id ?? null,
      org_type: data.org_type || 'department',
      is_active: data.is_active !== false,
      contact_person: data.contact_person || '',
      contact_phone: data.contact_phone || '',
      contact_email: data.contact_email || '',
      address: data.address || '',
      description: data.description || '',
    })
  } catch (error) {
    logger.error('加载组织信息失败:', error)
    ElMessage.error('加载组织信息失败')
    pushSafe('/organizations')
  } finally {
    loading.value = false
  }
}

const handleBack = () => {
  pushSafe('/organizations')
}

const handleSubmit = async () => {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (!valid) return

    submitLoading.value = true
    try {
      if (isEdit.value) {
        await updateOrganization(safeRouteParam(route.params.id) as number, {
          name: formData.name,
          // 显式传 null 才能在编辑时把组织"置为顶级"：
          // 后端 update 用 exclude_unset，传 undefined 等于不提交该字段 → 父级不变。
          parent_id: formData.parent_id ?? null,
          org_type: formData.org_type,
          description: formData.description || undefined,
          contact_person: formData.contact_person || undefined,
          contact_phone: formData.contact_phone || undefined,
          contact_email: formData.contact_email || undefined,
          address: formData.address || undefined,
          is_active: formData.is_active,
        })
        ElMessage.success('更新成功')
      } else {
        await createOrganization({
          name: formData.name,
          // 必填字段不做 `|| undefined` 兜底：那会把校验已通过的编码静默丢弃，
          // 让用户收到后端的 422「组织编码不能为空」（rules 已保证 6 位数字）。
          code: formData.code.trim(),
          parent_id: formData.parent_id,
          org_type: formData.org_type,
          description: formData.description || undefined,
          contact_person: formData.contact_person || undefined,
          contact_phone: formData.contact_phone || undefined,
          contact_email: formData.contact_email || undefined,
          address: formData.address || undefined,
        })
        ElMessage.success('创建成功')
      }
      // 提交成功：清掉草稿并复位脏标记（否则下次进来会"复活"已提交的数据）
      clearDraft()
      isDirty.value = false
      pushSafe('/organizations')
    } catch (error) {
      logger.error('保存失败:', error)
      ElMessage.error('保存失败')
    } finally {
      submitLoading.value = false
    }
  })
}

onMounted(async () => {
  loadParentOptions()
  if (isEdit.value) {
    await loadData()
  }

  // ③ 有未提交草稿时先问再恢复：不静默覆盖后端刚拉回来的数据
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

  isDirty.value = false
})

onBeforeUnmount(() => {
  stopDirtyWatch()
  // 离开前立刻落盘一次（防抖窗口内离开也不能丢）
  flushDraft()
})
</script>

<style lang="scss" scoped>
.organization-edit {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.title {
  font-size: 16px;
  font-weight: bold;
}
</style>

<style scoped>
.form-hint {
  margin-top: 4px;
  font-size: 12px;
  color: var(--color-text-secondary);
}
</style>
