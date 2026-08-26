<template>
  <el-dialog
    :model-value="modelValue"
    title="导入加密数据包"
    width="480px"
    :close-on-click-modal="false"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="110px">
      <el-form-item label="选择数据包">
        <el-upload
          ref="uploadRef"
          :auto-upload="false"
          :limit="1"
          accept=".zip,.rrs"
          :on-change="handleFileChange"
          :on-remove="handleFileRemove"
          :file-list="fileList"
        >
          <el-button type="primary">选择文件</el-button>
          <template #tip>
            <div style="font-size: 12px; color: var(--color-text-placeholder); margin-top: 8px">
              支持加密数据包（.rrs / 加密 .zip）
            </div>
          </template>
        </el-upload>
      </el-form-item>
      <el-form-item label="解密密码" prop="password">
        <el-input
          v-model="form.password"
          type="password"
          show-password
          placeholder="输入导出时设置的密码"
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button
        type="primary"
        :loading="submitting"
        :disabled="!selectedFile"
        @click="handleImport"
      >
        导入
      </el-button>
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
const fileList = ref<any[]>([])
const selectedFile = ref<File | null>(null)
const submitting = ref(false)

const form = reactive({
  password: '',
})

const rules: FormRules = {
  password: [{ required: true, message: '请输入解密密码', trigger: 'blur' }],
}

watch(
  () => props.modelValue,
  (v) => {
    if (v) {
      form.password = ''
      selectedFile.value = null
      fileList.value = []
    }
  }
)

function handleFileChange(file: any) {
  selectedFile.value = file.raw || null
}
function handleFileRemove() {
  selectedFile.value = null
  fileList.value = []
}

async function handleImport() {
  if (!selectedFile.value) {
    ElMessage.warning('请先选择数据包文件')
    return
  }
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch {
    return
  }
  submitting.value = true
  try {
    const fd = new FormData()
    fd.append('file', selectedFile.value)
    fd.append('password', form.password)
    const result: any = await post('/data-packages/upload-encrypted', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    ElMessage.success(result?.message || '加密数据包导入成功')
    emit('success')
    emit('update:modelValue', false)
    selectedFile.value = null
    fileList.value = []
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '导入失败')
  } finally {
    submitting.value = false
  }
}
</script>
