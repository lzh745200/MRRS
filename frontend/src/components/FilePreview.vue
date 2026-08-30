<template>
  <el-dialog
    append-to-body
    :model-value="modelValue"
    :title="title || fileName || '文件预览'"
    width="80%"
    top="5vh"
    destroy-on-close
    @close="handleClose"
  >
    <div v-loading="loading" class="file-preview-body">
      <template v-if="objectUrl">
        <img v-if="isImage" :src="objectUrl" class="preview-image" :alt="fileName" />
        <iframe v-else :src="objectUrl" class="preview-frame" title="文件预览" />
      </template>
      <el-empty v-else-if="unsupported" description="该文件类型不支持在线预览，请下载查看">
        <el-button type="primary" @click="handleDownload">下载文件</el-button>
      </el-empty>
      <el-empty v-else-if="!loading" description="暂无可预览的文件" />
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { downloadBlob } from '@/api/request'

/**
 * 通用文件预览对话框（问题5/9/14 复用组件）。
 * - 图片 → <img> 直接渲染
 * - PDF / HTML / 文本 → iframe + Blob URL 内联预览
 * - Office 等其他类型 → 提示下载
 * 关闭时自动 revokeObjectURL，防止内存泄漏。
 */
const props = withDefaults(
  defineProps<{
    modelValue: boolean
    /** 认证 Blob 获取函数（由各业务 API 封装提供） */
    fetchBlob: () => Promise<Blob>
    fileName?: string
    title?: string
  }>(),
  { fileName: '', title: '' }
)

const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>()

const loading = ref(false)
const objectUrl = ref('')
const blobRef = ref<Blob | null>(null)
const unsupported = ref(false)

const isImage = computed(() => (blobRef.value?.type || '').startsWith('image/'))

watch(
  () => props.modelValue,
  async (visible) => {
    if (!visible) return
    loading.value = true
    unsupported.value = false
    try {
      const blob = await props.fetchBlob()
      if (!blob || blob.size === 0) return
      const type = blob.type || ''
      blobRef.value = blob
      if (
        type.startsWith('image/') ||
        type === 'application/pdf' ||
        type.includes('html') ||
        type.startsWith('text/')
      ) {
        objectUrl.value = URL.createObjectURL(blob)
      } else {
        unsupported.value = true
      }
    } catch {
      ElMessage.error('文件预览失败')
    } finally {
      loading.value = false
    }
  },
  // 初始即为可见时也要加载（父组件可能直接以 visible=true 挂载）
  { immediate: true }
)

function release() {
  if (objectUrl.value) {
    URL.revokeObjectURL(objectUrl.value)
    objectUrl.value = ''
  }
  blobRef.value = null
  unsupported.value = false
}

function handleClose() {
  release()
  emit('update:modelValue', false)
}

function handleDownload() {
  if (!blobRef.value) return
  downloadBlob(blobRef.value, props.fileName || 'download')
}
</script>

<style scoped>
.file-preview-body {
  min-height: 60vh;
}
.preview-frame {
  width: 100%;
  height: 65vh;
  border: none;
}
.preview-image {
  max-width: 100%;
  max-height: 70vh;
  display: block;
  margin: 0 auto;
}
</style>
