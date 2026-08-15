<template>
  <div class="data-import-page">
    <div class="page-header">
      <h2>数据导入</h2>
      <p class="page-desc">下载模板填写数据后上传，支持帮扶村、项目、资金、学校四种类型</p>
    </div>

    <!-- 模板下载区 -->
    <el-card class="template-section" shadow="never">
      <template #header>
        <span
          ><el-icon><Download /></el-icon> 第一步：下载导入模板</span
        >
      </template>
      <el-row :gutter="16">
        <el-col v-for="tpl in templates" :key="tpl.type" :span="6">
          <el-card
            shadow="hover"
            :body-style="{ padding: '20px', textAlign: 'center' }"
            class="template-card"
          >
            <el-icon :size="32" color="var(--color-primary)"><Document /></el-icon>
            <h4 style="margin: 12px 0 4px">{{ tpl.label }}模板</h4>
            <p style="color: var(--color-info); font-size: 12px; margin-bottom: 16px">
              {{ tpl.desc }}
            </p>
            <el-button
              type="primary"
              :loading="downloadingType === tpl.type"
              @click="handleDownloadTemplate(tpl.type)"
            >
              <el-icon><Download /></el-icon> 下载模板
            </el-button>
          </el-card>
        </el-col>
      </el-row>
    </el-card>

    <!-- 上传区 -->
    <el-card class="upload-section" shadow="never">
      <template #header>
        <span
          ><el-icon><Upload /></el-icon> 第二步：上传数据文件</span
        >
      </template>
      <el-form :model="importForm" label-width="100px">
        <el-form-item label="导入类型">
          <el-select v-model="importForm.entityType" placeholder="选择数据类型">
            <el-option
              v-for="tpl in templates"
              :key="tpl.type"
              :label="tpl.label"
              :value="tpl.type"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="导入模式">
          <el-radio-group v-model="importForm.mode">
            <el-radio value="incremental">增量导入（不覆盖已有数据）</el-radio>
            <el-radio value="overwrite">全量覆盖（删除旧数据后导入）</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="选择文件">
          <el-upload
            ref="uploadRef"
            drag
            :auto-upload="false"
            :limit="1"
            accept=".xlsx,.xls"
            :on-change="handleFileChange"
            :on-remove="handleFileRemove"
          >
            <el-icon :size="48"><Upload /></el-icon>
            <div class="upload-text">
              <p>拖拽文件到此处或<em>点击上传</em></p>
              <p class="upload-hint">仅支持 .xlsx / .xls 格式，单次最多 1000 条</p>
            </div>
          </el-upload>
        </el-form-item>
        <el-form-item>
          <el-button
            type="primary"
            :loading="previewing"
            :disabled="!selectedFile"
            @click="handlePreview"
          >
            <el-icon><View /></el-icon> 预览数据
          </el-button>
          <el-button
            type="success"
            :loading="importing"
            :disabled="!previewData"
            @click="handleImport"
          >
            <el-icon><Upload /></el-icon> 确认导入
          </el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>

      <!-- 数据预览 -->
      <div v-if="previewData" class="preview-section">
        <el-alert type="info" :closable="false" style="margin-bottom: 12px">
          共 {{ previewData.total }} 条数据，请确认无误后点击"确认导入"
        </el-alert>
        <el-table :data="previewData.rows.slice(0, 10)" border stripe max-height="300" size="small">
          <el-table-column
            v-for="col in previewData.columns"
            :key="col"
            :prop="col"
            :label="col"
            min-width="120"
            show-overflow-tooltip
          />
        </el-table>
        <p
          v-if="previewData.total > 10"
          style="text-align: center; color: var(--color-info); margin-top: 8px"
        >
          （仅显示前 10 条，共 {{ previewData.total }} 条）
        </p>
      </div>

      <!-- 导入结果 -->
      <el-alert
        v-if="importResult"
        :title="importResult.success ? '导入成功' : '导入失败'"
        :type="importResult.success ? 'success' : 'error'"
        :closable="true"
        show-icon
        style="margin-top: 16px"
      >
        <template v-if="importResult.success">
          总 {{ importResult.total_rows }} 条，成功 {{ importResult.success_rows }} 条
          <span v-if="importResult.skipped_rows">，跳过 {{ importResult.skipped_rows }} 条</span>
          <span v-if="importResult.failed_rows">，失败 {{ importResult.failed_rows }} 条</span>
        </template>
        <div v-if="importResult.errors?.length" style="margin-top: 8px">
          <p
            v-for="(e, i) in importResult.errors.slice(0, 10)"
            :key="i"
            style="margin: 0; font-size: 12px"
          >
            行{{ e.row_number }}: {{ e.message || e.field_name }}
          </p>
        </div>
      </el-alert>
    </el-card>

    <!-- 导入历史 -->
    <el-card class="history-section" shadow="never">
      <template #header>
        <span
          ><el-icon><Clock /></el-icon> 导入历史</span
        >
      </template>
      <el-table v-loading="historyLoading" :data="history" stripe>
        <el-table-column prop="id" label="编号" width="70" />
        <el-table-column prop="file_name" label="文件名" min-width="180" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="total_rows" label="总行数" width="80" />
        <el-table-column prop="success_rows" label="成功" width="70" />
        <el-table-column prop="failed_rows" label="失败" width="70" />
        <el-table-column prop="created_at" label="导入时间" width="170">
          <template #default="{ row }">
            {{ row.created_at?.slice(0, 19) || '-' }}
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-if="historyTotal > 10"
        v-model:current-page="historyPage"
        :page-size="10"
        :total="historyTotal"
        layout="prev, pager, next"
        style="margin-top: 16px; justify-content: center"
        @current-change="loadHistory"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Download, Upload, Document, Clock, View } from '@element-plus/icons-vue'
import {
  downloadImportTemplateAndSave,
  importEntities,
  previewImportData,
  getImportHistory,
  formatImportStatus,
  type ImportResult,
  type ImportHistory,
  type ImportMode,
} from '@/api/import'

const templates = [
  {
    type: 'supported_village',
    label: '帮扶村',
    desc: '村名、县市、帮扶单位等字段',
  },
  { type: 'project', label: '项目', desc: '项目名称、类型、预算、日期等' },
  { type: 'fund', label: '资金', desc: '经费名称、金额、来源、用途等' },
  { type: 'school', label: '学校', desc: '学校名称、类型、学生数等' },
]

// ── Template download ──
const downloadingType = ref('')

async function handleDownloadTemplate(type: string) {
  downloadingType.value = type
  try {
    // 下载模板并解析 Content-Disposition 文件名
    await downloadImportTemplateAndSave(type, '模板')
  } catch (e: any) {
    const msg = e?.message || e?.response?.data?.detail || '模板下载失败，请重试'
    ElMessage.error(typeof msg === 'string' ? msg : '模板下载失败')
  } finally {
    downloadingType.value = ''
  }
}

// ── File upload ──
const uploadRef = ref()
const selectedFile = ref<File | null>(null)
const importForm = ref({
  entityType: 'supported_village',
  mode: 'incremental' as ImportMode,
})
const importing = ref(false)
const importResult = ref<ImportResult | null>(null)

function handleFileChange(file: any) {
  selectedFile.value = file.raw
}

function handleFileRemove() {
  selectedFile.value = null
}

function handleReset() {
  uploadRef.value?.clearFiles()
  selectedFile.value = null
  previewData.value = null
  importResult.value = null
}

// ── Preview ──
const previewing = ref(false)
const previewData = ref<{
  rows: any[]
  total: number
  columns: string[]
} | null>(null)

async function handlePreview() {
  if (!selectedFile.value) return
  previewing.value = true
  previewData.value = null
  try {
    const result = await previewImportData(selectedFile.value, importForm.value.entityType)
    previewData.value = result
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '数据预览失败，请检查文件格式')
  } finally {
    previewing.value = false
  }
}

async function handleImport() {
  if (!selectedFile.value) {
    ElMessage.warning('请先选择文件')
    return
  }
  if (!previewData.value) {
    ElMessage.warning('请先预览数据确认无误后再导入')
    return
  }
  importing.value = true
  importResult.value = null
  try {
    const result = await importEntities(
      selectedFile.value,
      importForm.value.entityType,
      importForm.value.mode
    )
    importResult.value = result
    if (result.success) {
      ElMessage.success(`导入完成：${result.success_rows} 条成功`)
    } else {
      ElMessage.error(`导入失败：${result.errors?.length || 0} 个错误`)
    }
    handleReset()
    loadHistory()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '导入失败')
  } finally {
    importing.value = false
  }
}

// ── History ──
const history = ref<ImportHistory[]>([])
const historyTotal = ref(0)
const historyPage = ref(1)
const historyLoading = ref(false)

async function loadHistory() {
  historyLoading.value = true
  try {
    const res = await getImportHistory(historyPage.value, 10)
    history.value = res.items || []
    historyTotal.value = res.total || 0
  } catch {
    history.value = []
  } finally {
    historyLoading.value = false
  }
}

function statusTagType(status: string): 'success' | 'warning' | 'danger' | 'info' | 'primary' {
  return formatImportStatus(status).type as 'success' | 'warning' | 'danger' | 'info' | 'primary'
}

function statusLabel(status: string): string {
  return formatImportStatus(status).text
}

onMounted(loadHistory)
</script>

<style scoped>
.data-import-page {
  padding: 16px;
}
.page-header {
  margin-bottom: 16px;
}
.page-header h2 {
  margin: 0 0 4px;
  font-size: 20px;
}
.page-desc {
  color: var(--color-info);
  font-size: 13px;
  margin: 0;
}
.template-section,
.upload-section,
.history-section {
  margin-bottom: 16px;
}
.template-card {
  cursor: pointer;
  transition: transform 0.2s;
}
.template-card:hover {
  transform: translateY(-2px);
}
.upload-text p {
  margin: 4px 0;
}
.upload-hint {
  color: var(--color-info);
  font-size: 12px;
}
</style>
