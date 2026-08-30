<template>
  <el-dialog
    append-to-body
    :model-value="modelValue"
    title="导出数据包"
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
      <el-form-item label="备注说明">
        <el-input
          v-model="form.description"
          type="textarea"
          :rows="3"
          placeholder="导出备注（可选）"
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleExport">导出</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, watch } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { exportDataPackage } from '@/api/dataPackage'

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
  description: '',
})

const rules: FormRules = {
  data_types: [
    { required: true, type: 'array', min: 1, message: '请至少选择一种数据类型', trigger: 'change' },
  ],
}

watch(
  () => props.modelValue,
  (v) => {
    if (v) {
      form.data_types = ['villages', 'projects', 'funds', 'schools']
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
    const result = await exportDataPackage({
      data_types: form.data_types,
      description: form.description || undefined,
      org_id: props.orgId,
    })
    const data: any = result
    const packageId = data?.package_id ?? data?.id
    if (packageId) {
      ElMessage.success(`数据包已导出（ID: ${packageId}），正在下载文件...`)
      // 导出成功立即触发下载，避免"提示成功却看不到文件"
      try {
        const { useDataPackageStore } = await import('@/stores/dataPackage')
        await useDataPackageStore().downloadPackage(packageId)
      } catch {
        /* 下载失败不阻塞（可到列表手动下载） */
      }
      emit('success')
      emit('update:modelValue', false)
    } else {
      ElMessage.success('数据包导出成功')
      emit('success')
      emit('update:modelValue', false)
    }
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '导出失败')
  } finally {
    submitting.value = false
  }
}
</script>
