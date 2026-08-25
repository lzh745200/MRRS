<template>
  <el-dialog
    v-model="visible"
    :title="mode === 'backup' ? '数据备份' : '数据恢复'"
    width="720px"
    destroy-on-close
  >
    <!-- 备份模式 -->
    <div v-if="mode === 'backup'" class="backup-section">
      <el-alert type="info" :closable="false" show-icon>
        <template #title> 备份将导出当前所有数据为 SQL 文件，可用于数据恢复或迁移。 </template>
      </el-alert>
      <el-form label-width="100px" style="margin-top: 16px">
        <el-form-item label="备份名称">
          <el-input v-model="backupName" placeholder="输入备份名称（可选）" />
        </el-form-item>
        <el-form-item label="包含数据">
          <el-checkbox-group v-model="backupOptions">
            <el-checkbox label="projects">项目数据</el-checkbox>
            <el-checkbox label="funds">资金数据</el-checkbox>
            <el-checkbox label="villages">帮扶村数据</el-checkbox>
            <el-checkbox label="users">用户数据</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
      </el-form>
    </div>

    <!-- 恢复模式 -->
    <div v-else class="restore-section">
      <el-alert type="warning" :closable="false" show-icon>
        <template #title> 恢复操作将覆盖当前数据，请确保已做好当前数据备份。 </template>
      </el-alert>
      <el-upload
        ref="uploadRef"
        class="upload-area"
        drag
        accept=".sql,.db,.bak"
        :auto-upload="false"
        :limit="1"
        :on-change="onFileChange"
      >
        <el-icon style="font-size: 48px; color: var(--color-info)">
          <UploadFilled />
        </el-icon>
        <div class="el-upload__text">将备份文件拖到此处，或<em>点击上传</em></div>
      </el-upload>
      <div v-if="selectedFile" class="file-info">
        <p>已选择: {{ selectedFile.name }} ({{ formatSize(selectedFile.size) }})</p>
      </div>
    </div>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button
        :type="mode === 'backup' ? 'primary' : 'danger'"
        :loading="loading"
        @click="handleAction"
      >
        {{ mode === 'backup' ? '开始备份' : '开始恢复' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import type { UploadFile } from 'element-plus'

const props = defineProps<{
  modelValue: boolean
  mode: 'backup' | 'restore'
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void
  (e: 'backup', options: { name: string; tables: string[] }): void
  (e: 'restore', file: File): void
}>()

const visible = ref(props.modelValue)
const loading = ref(false)
const backupName = ref('')
const backupOptions = ref(['projects', 'funds', 'villages', 'users'])
const selectedFile = ref<File | null>(null)
const uploadRef = ref()

function onFileChange(file: UploadFile) {
  selectedFile.value = file.raw ?? null
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

async function handleAction() {
  if (props.mode === 'backup') {
    loading.value = true
    try {
      emit('backup', { name: backupName.value, tables: backupOptions.value })
      ElMessage.success('备份任务已提交')
      visible.value = false
    } finally {
      loading.value = false
    }
  } else {
    if (!selectedFile.value) {
      ElMessage.warning('请选择备份文件')
      return
    }
    try {
      await ElMessageBox.confirm(
        '恢复操作将覆盖当前所有数据，此操作不可逆。确认继续？',
        '确认恢复',
        { type: 'warning' }
      )
      loading.value = true
      emit('restore', selectedFile.value)
      ElMessage.success('恢复任务已提交')
      visible.value = false
    } catch {
      // user cancelled
    } finally {
      loading.value = false
    }
  }
}
</script>

<style scoped>
.backup-section,
.restore-section {
  padding: 8px 0;
}
.upload-area {
  margin-top: 16px;
}
.file-info {
  margin-top: 12px;
  color: var(--color-text-regular);
}
</style>
