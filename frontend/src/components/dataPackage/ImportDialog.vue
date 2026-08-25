<template>
  <el-dialog
    :model-value="modelValue"
    title="导入数据包"
    width="480px"
    :close-on-click-modal="false"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <el-form label-width="110px">
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
            <div style="font-size: 12px; color: #999; margin-top: 8px">
              支持 .zip 数据包文件，导入后可在数据包列表查看
            </div>
          </template>
        </el-upload>
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
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { importDataPackage } from '@/api/dataPackage'

const props = defineProps<{
  modelValue: boolean
  orgId?: number
}>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  success: []
}>()

const uploadRef = ref()
const fileList = ref<any[]>([])
const selectedFile = ref<File | null>(null)
const submitting = ref(false)

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
  submitting.value = true
  try {
    const result: any = await importDataPackage(selectedFile.value, props.orgId)
    ElMessage.success(result?.message || '数据包导入成功')
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
