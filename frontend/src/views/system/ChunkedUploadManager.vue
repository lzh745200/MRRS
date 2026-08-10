<template>
  <div class="chunked-upload-page">
    <div class="page-header">
      <h2 class="page-title">分片上传管理</h2>
      <p class="page-desc">大文件分片上传演示，支持进度追踪和断点续传</p>
    </div>

    <!-- 文件选择区域 -->
    <el-card class="upload-card">
      <template #header>
        <span>选择文件</span>
      </template>
      <el-upload
        ref="uploadRef"
        :auto-upload="false"
        :limit="1"
        :on-change="onFileChange"
        :on-remove="onFileRemove"
        accept="*"
        drag
      >
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">将文件拖到此处，或 <em>点击上传</em></div>
        <template #tip>
          <div class="el-upload__tip">支持任意类型大文件，将使用分片上传</div>
        </template>
      </el-upload>
    </el-card>

    <!-- 上传会话信息 -->
    <el-card v-if="sessionInfo" class="info-card">
      <template #header>
        <div class="card-header">
          <span>上传会话</span>
          <el-tag :type="sessionStatusType">{{ sessionStatusText }}</el-tag>
        </div>
      </template>
      <el-descriptions :column="3" border size="small">
        <el-descriptions-item label="会话ID" :span="2">
          <code>{{ sessionInfo.session_id }}</code>
        </el-descriptions-item>
        <el-descriptions-item label="总块数">{{ sessionInfo.total_chunks }}</el-descriptions-item>
        <el-descriptions-item label="文件名">{{ sessionInfo.file_name }}</el-descriptions-item>
        <el-descriptions-item label="文件大小">{{
          formatSize(sessionInfo.file_size)
        }}</el-descriptions-item>
        <el-descriptions-item label="分片大小">{{
          formatSize(sessionInfo.chunk_size)
        }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <!-- 进度追踪 -->
    <el-card v-if="uploadState !== 'idle'" class="progress-card">
      <template #header>
        <div class="card-header">
          <span>上传进度</span>
          <span class="progress-text">
            {{ progressInfo?.uploaded_chunks || 0 }} / {{ progressInfo?.total_chunks || 0 }} 块 ({{
              (progressInfo?.progress || 0).toFixed(1)
            }}%)
          </span>
        </div>
      </template>

      <el-steps :active="currentStep" finish-status="success" align-center>
        <el-step title="初始化" />
        <el-step title="分片上传中" />
        <el-step title="合并文件" />
        <el-step title="完成" />
      </el-steps>

      <!-- 块级进度 -->
      <div
        v-if="uploadState === 'uploading' || uploadState === 'merging'"
        class="chunk-progress-bars"
      >
        <div
          v-for="chunk in chunkStatuses"
          :key="chunk.index"
          class="chunk-bar"
          :class="{
            'chunk-done': chunk.done,
            'chunk-current': chunk.current,
            'chunk-pending': chunk.pending,
          }"
          :title="`块 ${chunk.index + 1}: ${chunk.done ? '已完成' : chunk.current ? '上传中' : '待上传'}`"
        />
      </div>

      <el-progress
        :percentage="Math.round(progressInfo?.progress || 0)"
        :status="
          uploadState === 'done' ? 'success' : uploadState === 'error' ? 'exception' : undefined
        "
        :stroke-width="20"
        style="margin-top: 20px"
      />
    </el-card>

    <!-- 完成结果 -->
    <el-card v-if="mergeResult" class="result-card">
      <template #header>
        <span>上传完成</span>
      </template>
      <el-result icon="success" title="文件上传成功" :sub-title="mergeResult.file_name">
        <template #extra>
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="文件路径">{{
              mergeResult.file_path
            }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag type="success">{{ mergeResult.status }}</el-tag>
            </el-descriptions-item>
          </el-descriptions>
        </template>
      </el-result>
    </el-card>

    <!-- 操作按钮 -->
    <el-card v-if="selectedFile || sessionInfo" class="actions-card">
      <div class="action-buttons">
        <el-button
          v-if="uploadState === 'idle' || uploadState === 'error'"
          type="primary"
          :loading="initializing"
          @click="startUpload"
        >
          开始上传
        </el-button>
        <el-button
          v-if="uploadState === 'uploading'"
          type="danger"
          :loading="cancelling"
          @click="cancelUpload"
        >
          取消上传
        </el-button>
        <el-button v-if="uploadState === 'done' || uploadState === 'error'" @click="resetAll">
          重新上传
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import { chunkedUploadApi } from '@/api/chunkedUpload'
import type { InitUploadResult, UploadProgress, MergeResult } from '@/api/chunkedUpload'

type UploadState = 'idle' | 'initializing' | 'uploading' | 'merging' | 'done' | 'error'

const uploadState = ref<UploadState>('idle')
const initializing = ref(false)
const cancelling = ref(false)

const selectedFile = ref<File | null>(null)
const sessionInfo = ref<InitUploadResult | null>(null)
const progressInfo = ref<UploadProgress | null>(null)
const mergeResult = ref<MergeResult | null>(null)
const uploadRef = ref<any>(null)

const CHUNK_SIZE = 5 * 1024 * 1024 // 5MB

let pollingTimer: ReturnType<typeof setInterval> | null = null

const chunkStatuses = ref<
  Array<{ index: number; done: boolean; current: boolean; pending: boolean }>
>([])

const currentStep = ref(0)

const sessionStatusType = computed(() => {
  if (!sessionInfo.value) return 'info'
  if (uploadState.value === 'done') return 'success'
  if (uploadState.value === 'error') return 'danger'
  if (uploadState.value === 'uploading') return 'warning'
  return 'info'
})

const sessionStatusText = computed(() => {
  if (uploadState.value === 'done') return '已完成'
  if (uploadState.value === 'error') return '失败'
  if (uploadState.value === 'uploading') return '上传中'
  if (uploadState.value === 'merging') return '合并中'
  return '就绪'
})

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`
}

function onFileChange(file: any) {
  selectedFile.value = file.raw || file
  resetSession()
}

function onFileRemove() {
  selectedFile.value = null
  resetSession()
}

function resetSession() {
  stopPolling()
  sessionInfo.value = null
  progressInfo.value = null
  mergeResult.value = null
  uploadState.value = 'idle'
  currentStep.value = 0
  chunkStatuses.value = []
}

function resetAll() {
  selectedFile.value = null
  uploadRef.value?.clearFiles()
  resetSession()
}

function startPolling() {
  stopPolling()
  pollingTimer = setInterval(async () => {
    if (!sessionInfo.value) return
    try {
      const progress = await chunkedUploadApi.getProgress(sessionInfo.value.session_id)
      progressInfo.value = progress
      updateChunkStatuses(progress)
      if (progress.status === 'completed' || progress.status === 'merged') {
        // all chunks uploaded, trigger merge
        uploadState.value = 'merging'
        currentStep.value = 2
        stopPolling()
        await doMerge()
      } else if (progress.status === 'error') {
        uploadState.value = 'error'
        stopPolling()
        ElMessage.error('上传过程中出现错误')
      }
    } catch {
      // polling error, continue
    }
  }, 500)
}

function stopPolling() {
  if (pollingTimer) {
    clearInterval(pollingTimer)
    pollingTimer = null
  }
}

function updateChunkStatuses(progress: UploadProgress) {
  const total = progress.total_chunks
  const uploaded = progress.uploaded_chunks
  chunkStatuses.value = Array.from({ length: total }, (_, i) => ({
    index: i,
    done: i < uploaded,
    current: i === uploaded,
    pending: i > uploaded,
  }))
}

async function startUpload() {
  if (!selectedFile.value) {
    ElMessage.warning('请先选择文件')
    return
  }

  initializing.value = true
  try {
    // Step 1: Init
    uploadState.value = 'initializing'
    currentStep.value = 0
    const file = selectedFile.value
    const initResult = await chunkedUploadApi.initUpload({
      file_name: file.name,
      file_size: file.size,
      chunk_size: CHUNK_SIZE,
    })
    sessionInfo.value = initResult
    currentStep.value = 1

    // Step 2: Upload chunks
    uploadState.value = 'uploading'
    const chunks = splitFile(file, initResult.chunk_size)
    chunkStatuses.value = Array.from({ length: chunks.length }, (_, i) => ({
      index: i,
      done: false,
      current: false,
      pending: true,
    }))
    startPolling()

    for (let i = 0; i < chunks.length; i++) {
      if (uploadState.value !== 'uploading') break
      try {
        chunkStatuses.value[i] = {
          index: i,
          done: false,
          current: true,
          pending: false,
        }
        await chunkedUploadApi.uploadChunk(initResult.session_id, i, chunks[i])
        chunkStatuses.value[i] = {
          index: i,
          done: true,
          current: false,
          pending: false,
        }
      } catch {
        ElMessage.error(`块 ${i + 1} 上传失败`)
        uploadState.value = 'error'
        stopPolling()
        return
      }
    }

    if (uploadState.value === 'uploading') {
      // All chunks uploaded, wait for polling to detect completion and trigger merge
      stopPolling()
      // Check progress one more time
      const progress = await chunkedUploadApi.getProgress(initResult.session_id)
      progressInfo.value = progress
      if (progress.status === 'completed') {
        uploadState.value = 'merging'
        currentStep.value = 2
        await doMerge()
      }
    }
  } catch (err: any) {
    ElMessage.error(err?.message || '初始化上传失败')
    uploadState.value = 'error'
  } finally {
    initializing.value = false
  }
}

async function doMerge() {
  if (!sessionInfo.value) return
  try {
    uploadState.value = 'merging'
    const result = await chunkedUploadApi.mergeChunks(sessionInfo.value.session_id)
    mergeResult.value = result
    uploadState.value = 'done'
    currentStep.value = 3
    ElMessage.success('文件上传并合并成功！')
  } catch (err: any) {
    ElMessage.error(err?.message || '合并失败')
    uploadState.value = 'error'
  }
}

async function cancelUpload() {
  if (!sessionInfo.value) return
  try {
    await ElMessageBox.confirm('确定要取消上传吗？', '确认', {
      type: 'warning',
    })
  } catch {
    return
  }
  cancelling.value = true
  stopPolling()
  try {
    await chunkedUploadApi.cancelUpload(sessionInfo.value.session_id)
    ElMessage.success('上传已取消')
  } catch {
    ElMessage.error('取消失败')
  } finally {
    cancelling.value = false
    resetSession()
  }
}

function splitFile(file: File, chunkSize: number): Blob[] {
  const chunks: Blob[] = []
  let offset = 0
  while (offset < file.size) {
    chunks.push(file.slice(offset, offset + chunkSize))
    offset += chunkSize
  }
  return chunks
}

onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped>
.chunked-upload-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 20px;
}
.page-title {
  font-size: 20px;
  font-weight: 600;
  color: #1b4332;
  margin: 0 0 4px;
}
.page-desc {
  font-size: 14px;
  color: #666;
  margin: 0;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.progress-text {
  font-size: 14px;
  color: #666;
}
.chunk-progress-bars {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 16px;
}
.chunk-bar {
  width: 12px;
  height: 24px;
  border-radius: 2px;
  background: #e0e0e0;
  transition: background 0.3s;
}
.chunk-bar.chunk-done {
  background: #67c23a;
}
.chunk-bar.chunk-current {
  background: #409eff;
  animation: pulse 0.8s infinite;
}
.chunk-bar.chunk-pending {
  background: #e0e0e0;
}
@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}
.result-card {
  border-left: 4px solid #67c23a;
}
.actions-card {
  text-align: center;
  padding: 10px 0;
}
.action-buttons {
  display: flex;
  justify-content: center;
  gap: 10px;
}
</style>
