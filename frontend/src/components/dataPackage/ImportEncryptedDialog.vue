<template>
  <el-dialog
    append-to-body
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

/**
 * 加密数据包导入：严格按后端三步契约串联。
 * 后端 upload-encrypted 只落盘并建 pending 记录（不导入数据），
 * 真正落库必须再走 decrypt-preview（带密码校验）与 confirm-import，
 * 因此任一步失败都必须如实报错，绝不能提示"导入成功"。
 */
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
    // 第一步：上传加密包（后端仅登记 pending 记录）
    const fd = new FormData()
    fd.append('file', selectedFile.value)
    fd.append('password', form.password)
    const upload: any = await post('/data-packages/upload-encrypted', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    const uploadData = upload?.data ?? upload
    const packageId = uploadData?.id
    if (!packageId) {
      throw new Error('上传加密数据包失败：服务端未返回数据包 ID')
    }

    // 第二步：携带密码解密预览（密码经请求体传输，后端校验密码与包结构）
    await post(`/data-packages/decrypt-preview/${packageId}`, { password: form.password })

    // 第三步：确认导入（后端在单一事务内完成冲突处理与落库）
    const confirm: any = await post(`/data-packages/confirm-import/${packageId}`, {
      conflict_strategy: 'KEEP_BOTH',
      // 加密包必须同时提交解密口令（后端 confirm-import 自行解密后导入）
      password: form.password,
    })
    // 后端该端点以 HTTP 200 + {success, message} 表达业务成败，必须显式判定
    const confirmData = confirm?.data ?? confirm
    if (!confirmData || confirmData.success !== true) {
      throw new Error(confirmData?.message || '确认导入失败')
    }

    ElMessage.success(confirmData.message || '加密数据包导入成功')
    emit('success')
    emit('update:modelValue', false)
    selectedFile.value = null
    fileList.value = []
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || err?.message || '导入失败')
  } finally {
    submitting.value = false
  }
}
</script>
