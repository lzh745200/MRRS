<template>
  <div class="control-package-view">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>管控配置包</span>
          <el-tag type="info" size="small">离线管控</el-tag>
        </div>
      </template>

      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="管控配置包用于上级单位向下级单机系统下发模块可见性、编辑权限和系统配置。通过USB/光盘等离线方式传递。"
        style="margin-bottom: 20px"
      />

      <!-- 导入区域 -->
      <el-divider content-position="left">导入管控包</el-divider>
      <el-upload
        ref="uploadRef"
        :auto-upload="false"
        :limit="1"
        accept=".zip"
        :on-change="handleFileChange"
        :on-remove="handleFileRemove"
        drag
      >
        <el-icon class="el-icon--upload"><upload-filled /></el-icon>
        <div class="el-upload__text">拖拽管控配置包到此处，或 <em>点击选择</em></div>
        <template #tip>
          <div class="el-upload__tip">仅支持 .zip 格式的管控配置包</div>
        </template>
      </el-upload>

      <!-- 预览区域 -->
      <div v-if="preview" class="preview-section">
        <el-divider content-position="left">包内容预览</el-divider>
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="包类型">{{
            preview.manifest?.package_type
          }}</el-descriptions-item>
          <el-descriptions-item label="包版本">{{
            preview.manifest?.package_version
          }}</el-descriptions-item>
          <el-descriptions-item label="目标组织ID">{{
            preview.manifest?.target_organization_id
          }}</el-descriptions-item>
          <el-descriptions-item label="生成时间">{{
            preview.manifest?.generated_at
          }}</el-descriptions-item>
          <el-descriptions-item label="模块策略数"
            >{{ preview.module_policy_count }} 项</el-descriptions-item
          >
          <el-descriptions-item label="用户数">{{ preview.user_count }} 个</el-descriptions-item>
        </el-descriptions>

        <el-alert
          v-if="!preview.valid"
          type="error"
          :title="preview.error || '无效的管控包'"
          :closable="false"
          style="margin-top: 12px"
        />

        <div v-if="preview.valid" style="margin-top: 16px; text-align: right">
          <el-button type="primary" :loading="importing" @click="handleImport">
            确认导入并执行
          </el-button>
        </div>
      </div>

      <!-- 导入结果 -->
      <el-result
        v-if="importResult"
        icon="success"
        title="管控配置包导入成功"
        :sub-title="`已应用 ${importResult.applied_policies} 项模块策略，${importResult.applied_configs} 项系统配置`"
      >
        <template #extra>
          <el-button type="primary" @click="resetState">完成</el-button>
        </template>
      </el-result>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import { post } from '@/api/request'
import type { UploadFile } from 'element-plus'

interface PreviewResult {
  valid: boolean
  manifest: Record<string, unknown> | null
  module_policy_count: number
  user_count: number
  error: string | null
}

interface ImportResult {
  applied_policies: number
  applied_configs: number
  package_hash: string
}

const uploadRef = ref()
const selectedFile = ref<File | null>(null)
const preview = ref<PreviewResult | null>(null)
const importing = ref(false)
const importResult = ref<ImportResult | null>(null)

async function handleFileChange(file: UploadFile) {
  if (!file.raw) return
  selectedFile.value = file.raw
  importResult.value = null

  const formData = new FormData()
  formData.append('file', file.raw)

  try {
    const res = await post('/control-packages/import-preview', formData)
    preview.value = res.data || res
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : '预览失败'
    ElMessage.error(msg)
    preview.value = null
  }
}

function handleFileRemove() {
  selectedFile.value = null
  preview.value = null
}

async function handleImport() {
  if (!selectedFile.value) return
  importing.value = true

  const formData = new FormData()
  formData.append('file', selectedFile.value)

  try {
    const res = await post('/control-packages/import', formData)
    importResult.value = res.data || res
    ElMessage.success('管控配置包导入成功')
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : '导入失败'
    ElMessage.error(msg)
  } finally {
    importing.value = false
  }
}

function resetState() {
  selectedFile.value = null
  preview.value = null
  importResult.value = null
  uploadRef.value?.clearFiles()
}
</script>

<style lang="scss" scoped>
.control-package-view {
  padding: 20px;
  max-width: 800px;
}
.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
}
.preview-section {
  margin-top: 16px;
}
</style>
