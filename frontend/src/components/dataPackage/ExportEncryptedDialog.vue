<template>
  <el-dialog
    append-to-body
    :model-value="modelValue"
    title="加密导出数据包"
    width="480px"
    :close-on-click-modal="false"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="110px">
      <el-form-item label="数据类型">
        <el-checkbox-group v-model="form.data_types">
          <el-checkbox label="villages">帮扶村</el-checkbox>
          <el-checkbox label="projects">帮扶项目</el-checkbox>
          <el-checkbox label="funds">帮扶经费</el-checkbox>
          <el-checkbox label="schools">帮扶学校</el-checkbox>
        </el-checkbox-group>
      </el-form-item>
      <el-form-item label="加密密码" prop="password">
        <el-input
          v-model="form.password"
          type="password"
          show-password
          placeholder="请输入至少8位密码"
        />
      </el-form-item>
      <el-form-item label="备注说明">
        <el-input
          v-model="form.description"
          type="textarea"
          :rows="2"
          placeholder="导出备注（可选）"
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleExport">加密导出</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, watch } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { post } from '@/api/request'

const props = defineProps<{
  modelValue: boolean
  orgId?: number
}>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  success: []
}>()

const formRef = ref<FormInstance | null>(null)
const submitting = ref(false)

const form = reactive({
  data_types: ['villages', 'projects', 'funds', 'schools'],
  password: '',
  description: '',
})

const rules: FormRules = {
  data_types: [
    { required: true, type: 'array', min: 1, message: '请至少选择一种数据类型', trigger: 'change' },
  ],
  password: [
    { required: true, message: '请输入加密密码', trigger: 'blur' },
    { min: 8, message: '密码长度至少8位', trigger: 'blur' },
  ],
}

watch(
  () => props.modelValue,
  (v) => {
    if (v) {
      form.data_types = ['villages', 'projects', 'funds', 'schools']
      form.password = ''
      form.description = ''
    }
  }
)

async function handleExport() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch {
    return
  }
  submitting.value = true
  try {
    const result: any = await post('/data-packages/export-encrypted', {
      data_types: form.data_types,
      password: form.password,
      description: form.description || undefined,
      package_type: 'report',
    })
    ElMessage.success(result?.message || '加密导出成功')
    emit('success')
    emit('update:modelValue', false)
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '加密导出失败')
  } finally {
    submitting.value = false
  }
}
</script>
