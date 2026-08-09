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
              <el-input v-model="formData.code" placeholder="留空自动生成" :disabled="isEdit" />
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
                <el-option label="无（顶级组织）" :value="null as any" />
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

import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useRouterSafe, safeRouteParam } from '@/composables/useRouterSafe'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
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

const rules: FormRules = {
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
    parentOptions.value = ((res as any).items || []).filter(
      (item: Organization) => item.id !== currentId
    )
  } catch (error) {
    logger.error('加载上级组织失败:', error)
    ElMessage.error('加载上级组织失败，请稍后重试')
  }
}

const loadData = async () => {
  const id = safeRouteParam(route.params.id)
  if (!id) return

  loading.value = true
  try {
    const data = await getOrganization(id as number)
    Object.assign(formData, {
      name: data.name || '',
      code: data.code || '',
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
          parent_id: formData.parent_id ?? undefined, // 编辑也必须提交上级组织（此前被丢弃）
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
          code: formData.code || undefined,
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
      pushSafe('/organizations')
    } catch (error) {
      logger.error('保存失败:', error)
      ElMessage.error('保存失败')
    } finally {
      submitLoading.value = false
    }
  })
}

onMounted(() => {
  loadParentOptions()
  if (isEdit.value) {
    loadData()
  }
})
</script>

<style scoped>
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
