<template>
  <div class="grant-import">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>导入单位授权包</span>
          <el-tag type="info" size="small">下级单位专用</el-tag>
        </div>
      </template>

      <el-alert
        type="warning"
        :closable="false"
        show-icon
        title="导入后本机授权将按包内容覆盖，且不提供本机编辑入口。"
        description="授权包由上级单位生成，包含组织编码、版本号与数字签名。版本号必须大于本机当前版本。"
      />

      <el-upload
        class="uploader"
        drag
        action="#"
        accept=".json"
        :auto-upload="false"
        :limit="1"
        :file-list="fileList"
        :on-change="onChange"
        :on-remove="onRemove"
      >
        <div class="uploader-tip">将授权包（.json）拖到此处，或点击选择</div>
      </el-upload>

      <div class="actions">
        <el-button type="primary" :loading="submitting" @click="submit">导入并应用</el-button>
        <el-button :disabled="submitting" @click="onRemove">清空</el-button>
      </div>

      <el-alert
        v-if="errorMsg"
        class="feedback"
        type="error"
        :closable="false"
        show-icon
        :title="errorMsg"
      />

      <el-descriptions v-if="result" class="feedback" :column="2" border>
        <el-descriptions-item label="单位编码">{{ result.org_code }}</el-descriptions-item>
        <el-descriptions-item label="授权版本">{{ result.version }}</el-descriptions-item>
        <el-descriptions-item label="模块数量">{{ result.modules }}</el-descriptions-item>
        <el-descriptions-item label="签名校验">
          <el-tag :type="result.signed ? 'success' : 'warning'" size="small">
            {{ result.signed ? '已签名' : '未签名' }}
          </el-tag>
        </el-descriptions-item>
      </el-descriptions>
    </el-card>
  </div>
  <!-- P2：重复授权包导入确认（后端 409 → 显式允许 force） -->
  <ImportPreviewDialog
    v-model:visible="duplicateVisible"
    title="该授权包已导入过"
    :info="{ type: '授权包', fileName: fileList[0]?.name }"
    :duplicate="duplicateInfo"
    allow-force
    @confirm="onDuplicateConfirm"
    @cancel="onDuplicateCancel"
  />
</template>

<script setup lang="ts">
/**
 * 导入单位授权包（R33，下级单位专用）。
 *
 * 下级单位没有超级管理员且完全离线：授权只能由上级生成授权包、经离线介质送达，
 * 本页负责把包交给后端校验并应用。导入成功后矩阵只读，本机不提供编辑入口。
 */
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { importGrantPackage, type GrantImportResult } from '@/api/orgGrants'
import ImportPreviewDialog from '@/components/import/ImportPreviewDialog.vue'

const fileList = ref<any[]>([])
const submitting = ref(false)
const result = ref<GrantImportResult | null>(null)
const errorMsg = ref('')

/** 只保留最后选择的那个文件（limit=1 时浏览器仍可能塞入多个） */
function onChange(_file: any, files: any[]): void {
  fileList.value = files.slice(-1)
  errorMsg.value = ''
}

function onRemove(): void {
  fileList.value = []
  errorMsg.value = ''
}

// P2：重复包确认（后端按内容哈希查重，重复时 409，由用户显式允许）
const duplicateVisible = ref(false)
const duplicateInfo = ref<{ createdAt?: string; username?: string } | null>(null)
let pendingDuplicateFile: File | null = null

/** 从后端 409 文案里解析「已于 X 由 Y 导入过」 */
function parseDuplicateDetail(detail: unknown): { createdAt?: string; username?: string } {
  const text = typeof detail === 'string' ? detail : ''
  const matched = text.match(/已于\s*(.*?)\s*由\s*(.*?)\s*导入过/)
  return matched ? { createdAt: matched[1], username: matched[2] } : {}
}

/** 真正执行导入（force=true 时允许重复导入） */
async function doImport(file: File, force = false): Promise<void> {
  submitting.value = true
  try {
    result.value = await importGrantPackage(file, force)
    errorMsg.value = ''
    ElMessage.success('授权包已应用')
  } catch (e: any) {
    result.value = null
    if (e?.response?.status === 409) {
      pendingDuplicateFile = file
      duplicateInfo.value = parseDuplicateDetail(e?.response?.data?.detail)
      duplicateVisible.value = true
      return
    }
    // 后端把不可读原因放在 detail 里；取不到时逐级回退
    errorMsg.value = e?.response?.data?.detail || e?.message || '导入失败'
  } finally {
    submitting.value = false
  }
}

async function submit(): Promise<void> {
  const raw = fileList.value[0]?.raw
  if (!raw) {
    errorMsg.value = '请先选择授权包文件'
    return
  }
  await doImport(raw as File)
}

/** 重复包确认：带 force=true 重新导入 */
async function onDuplicateConfirm(): Promise<void> {
  duplicateVisible.value = false
  const file = pendingDuplicateFile
  pendingDuplicateFile = null
  if (!file) return
  await doImport(file, true)
}

function onDuplicateCancel(): void {
  duplicateVisible.value = false
  pendingDuplicateFile = null
}

// 暴露给单测驱动（jsdom 下 el-upload 的 change 事件不稳定）。
// 仅用于测试，生产无副作用：外部调用方不会拿到组件实例。
defineExpose({
  submit,
  onChange,
  onRemove,
  onDuplicateConfirm,
  onDuplicateCancel,
  parseDuplicateDetail,
})
</script>

<style scoped>
.grant-import {
  padding: 16px;
}
.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
}
.uploader {
  margin: 16px 0;
}
.uploader-tip {
  padding: 24px 0;
  color: var(--el-text-color-secondary);
}
.actions {
  display: flex;
  gap: 8px;
}
.feedback {
  margin-top: 16px;
}
</style>
