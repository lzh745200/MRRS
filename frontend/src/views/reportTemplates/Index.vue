<template>
  <div class="report-templates-page">
    <div class="page-header">
      <div>
        <h2 class="page-title">报表模板管理</h2>
        <p class="page-desc">管理数据导入导出模板和报表格式</p>
      </div>
      <el-button type="primary" @click="openCreateDialog">+ 新建模板</el-button>
    </div>

    <!-- 搜索与筛选 -->
    <div class="filter-bar">
      <el-input
        v-model="searchText"
        placeholder="搜索模板名称或描述"
        clearable
        style="width: 260px"
        @clear="onFilterChange"
        @keyup.enter="onFilterChange"
      >
        <template #prefix
          ><el-icon><Search /></el-icon
        ></template>
      </el-input>
      <el-select
        v-model="filterModule"
        placeholder="关联模块"
        clearable
        style="width: 160px"
        @change="onFilterChange"
      >
        <el-option label="全部模块" value="" />
        <el-option label="帮扶村" value="village" />
        <el-option label="帮扶学校" value="school" />
        <el-option label="经费管理" value="fund" />
        <el-option label="帮扶项目" value="project" />
        <el-option label="乡村工作" value="rural_work" />
        <el-option label="综合报表" value="comprehensive" />
      </el-select>
    </div>

    <el-tabs v-model="activeTab" type="border-card" @tab-change="onFilterChange">
      <el-tab-pane label="导入模板" name="import">
        <div v-loading="loading" class="template-grid">
          <EmptyState
            v-if="displayTemplates.length === 0 && !loading"
            text="暂无导入模板，点击右上角创建"
          />
          <div v-for="t in displayTemplates" :key="t.id" class="template-item">
            <el-icon class="t-icon"><component :is="moduleIcon(t.module)" /></el-icon>
            <div class="t-info">
              <div class="t-name-row">
                <h4>{{ t.name }}</h4>
                <el-tag v-if="t.is_active" type="success" size="small" effect="plain">启用</el-tag>
                <el-tag v-else type="info" size="small" effect="plain">停用</el-tag>
              </div>
              <p>{{ t.description || moduleLabel(t.module) }}</p>
              <span class="t-meta"
                >{{ moduleLabel(t.module) }} · 创建: {{ formatDate(t.created_at) }} · 更新:
                {{ formatDate(t.updated_at) }}</span
              >
            </div>
            <div class="t-actions">
              <el-button type="primary" link @click="handlePreview(t)">预览</el-button>
              <el-button type="primary" link @click="handleDownload(t)">下载</el-button>
              <el-button type="success" link @click="openFillDialog(t)">在线填报</el-button>
              <el-button link @click="openUploadDialog(t)">上传填报</el-button>
              <el-button link @click="handleEdit(t)">编辑</el-button>
              <el-button link type="danger" @click="handleDelete(t)">删除</el-button>
            </div>
          </div>
        </div>
      </el-tab-pane>
      <el-tab-pane label="导出模板" name="export">
        <div v-loading="loading" class="template-grid">
          <EmptyState
            v-if="displayTemplates.length === 0 && !loading"
            text="暂无导出模板，点击右上角创建"
          />
          <div v-for="t in displayTemplates" :key="t.id" class="template-item">
            <el-icon class="t-icon"><component :is="moduleIcon(t.module)" /></el-icon>
            <div class="t-info">
              <div class="t-name-row">
                <h4>{{ t.name }}</h4>
                <el-tag v-if="t.is_active" type="success" size="small" effect="plain">启用</el-tag>
                <el-tag v-else type="info" size="small" effect="plain">停用</el-tag>
              </div>
              <p>{{ t.description || moduleLabel(t.module) }}</p>
              <span class="t-meta"
                >{{ moduleLabel(t.module) }} · 创建: {{ formatDate(t.created_at) }} · 更新:
                {{ formatDate(t.updated_at) }}</span
              >
            </div>
            <div class="t-actions">
              <el-button type="primary" link @click="handlePreview(t)">预览</el-button>
              <el-button type="primary" link @click="handleDownload(t)">下载</el-button>
              <el-button type="success" link @click="openFillDialog(t)">在线填报</el-button>
              <el-button link @click="handleEdit(t)">编辑</el-button>
              <el-button link type="danger" @click="handleDelete(t)">删除</el-button>
            </div>
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- 新建模板对话框 -->
    <el-dialog
      v-model="showCreateDialog"
      title="新建模板"
      :width="DIALOG_SM"
      @closed="resetCreateForm"
    >
      <el-form ref="createFormRef" :model="newTemplate" :rules="createRules" label-width="100px">
        <el-form-item label="模板名称" prop="name">
          <el-input
            v-model="newTemplate.name"
            placeholder="如：帮扶村数据导入模板"
            maxlength="50"
            show-word-limit
          />
        </el-form-item>
        <el-form-item label="模板类型" prop="type">
          <el-select
            v-model="newTemplate.type"
            placeholder="请选择模板类型"
            clearable
            style="width: 100%"
          >
            <el-option label="导入模板" value="import" />
            <el-option label="导出模板" value="export" />
          </el-select>
        </el-form-item>
        <el-form-item label="关联模块" prop="module">
          <el-select
            v-model="newTemplate.module"
            placeholder="请选择关联模块"
            clearable
            style="width: 100%"
            @change="loadAvailableFields"
          >
            <el-option label="帮扶村" value="village" />
            <el-option label="帮扶学校" value="school" />
            <el-option label="经费管理" value="fund" />
            <el-option label="帮扶项目" value="project" />
            <el-option label="乡村工作" value="rural_work" />
            <el-option label="综合报表" value="comprehensive" />
          </el-select>
        </el-form-item>
        <el-form-item label="选择字段">
          <el-checkbox-group v-model="newTemplate.selectedFields" class="field-checkbox-group">
            <el-checkbox v-for="f in availableFields" :key="f.key" :label="f.key">
              {{ f.label }}
            </el-checkbox>
          </el-checkbox-group>
          <div v-if="availableFields.length === 0" class="field-empty-tip">
            选择模块后加载可选字段；不勾选则使用系统默认字段
          </div>
        </el-form-item>
        <el-form-item label="描述">
          <el-input
            v-model="newTemplate.description"
            type="textarea"
            :rows="2"
            maxlength="200"
            show-word-limit
            placeholder="请输入模板描述（可选）"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="handleCreate">创建</el-button>
      </template>
    </el-dialog>

    <!-- 编辑模板对话框 -->
    <el-dialog v-model="showEditDialog" title="编辑模板" :width="DIALOG_SM">
      <el-form
        v-if="editTemplate"
        ref="editFormRef"
        :model="editTemplate"
        :rules="editRules"
        label-width="100px"
      >
        <el-form-item label="模板名称" prop="name">
          <el-input v-model="editTemplate.name" maxlength="50" show-word-limit />
        </el-form-item>
        <el-form-item label="描述">
          <el-input
            v-model="editTemplate.description"
            type="textarea"
            :rows="2"
            maxlength="200"
            show-word-limit
          />
        </el-form-item>
        <el-form-item label="是否启用">
          <el-switch v-model="editTemplate.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEditDialog = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="handleSaveEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 在线填报对话框 -->
    <el-dialog
      v-model="showFillDialog"
      :title="`在线填报 — ${fillTemplate?.name || ''}`"
      :width="DIALOG_MD"
    >
      <el-alert
        title="按模板字段填写数据，支持多行记录，填写完成后点击「导出 Excel」保存"
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 16px"
      />
      <el-form label-width="100px">
        <el-form-item
          v-for="(field, idx) in fillFields"
          :key="field.key + '-' + idx"
          :label="field.label"
        >
          <el-input v-model="fillRow[field.key]" :placeholder="`请输入${field.label}`" />
        </el-form-item>
        <el-form-item v-if="fillFields.length === 0" label="提示">
          该模板未配置字段，可直接导出空白模板
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showFillDialog = false">取消</el-button>
        <el-button type="primary" @click="handleFillExport">导出 Excel</el-button>
      </template>
    </el-dialog>

    <!-- 预览对话框 -->
    <el-dialog v-model="showPreviewDialog" title="模板预览" :width="DIALOG_MD">
      <div v-if="previewTemplate" class="preview-content">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="模板名称">{{ previewTemplate.name }}</el-descriptions-item>
          <el-descriptions-item label="模板类型">{{
            previewTemplate.type === 'import' ? '导入模板' : '导出模板'
          }}</el-descriptions-item>
          <el-descriptions-item label="关联模块">
            <span style="display: inline-flex; align-items: center; gap: 4px">
              <el-icon><component :is="moduleIcon(previewTemplate.module)" /></el-icon>
              {{ moduleLabel(previewTemplate.module) }}
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="previewTemplate.is_active ? 'success' : 'info'" size="small">{{
              previewTemplate.is_active ? '启用' : '停用'
            }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="描述" :span="2">{{
            previewTemplate.description || '暂无描述'
          }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{
            formatDate(previewTemplate.created_at)
          }}</el-descriptions-item>
          <el-descriptions-item label="更新时间">{{
            formatDate(previewTemplate.updated_at)
          }}</el-descriptions-item>
        </el-descriptions>
        <div v-if="previewTemplate.fields" class="preview-fields">
          <h4>字段配置</h4>
          <el-tag
            v-for="(field, idx) in parseFields(previewTemplate.fields)"
            :key="idx"
            style="margin: 4px"
            >{{ field }}</el-tag
          >
        </div>
      </div>
      <template #footer>
        <el-button @click="showPreviewDialog = false">关闭</el-button>
        <el-button type="primary" @click="handleDownload(previewTemplate!)">下载模板</el-button>
      </template>
    </el-dialog>

    <!-- 上传填报对话框（两阶段） -->
    <el-dialog
      v-model="showUploadDialog"
      :title="`上传填报 — ${currentUploadTemplate?.name || ''}`"
      :width="DIALOG_MD"
      @closed="onUploadDialogClosed"
    >
      <!-- 第一步：选择文件和模式 -->
      <div v-if="!previewResult">
        <el-alert
          title="上传说明"
          type="info"
          :closable="false"
          show-icon
          style="margin-bottom: 16px"
        >
          请先选择填写好的 Excel 文件，点击"预览数据"查看解析结果，确认无误后再点击"确认导入"。
        </el-alert>

        <el-upload
          ref="uploadRef"
          :auto-upload="false"
          :limit="1"
          :on-change="onFileChange"
          :on-remove="onFileRemove"
          accept=".xlsx,.xls"
          style="margin-bottom: 16px"
        >
          <el-button type="primary">
            <el-icon><Upload /></el-icon>
            选择 Excel 文件
          </el-button>
          <template #tip>
            <div style="font-size: 12px; color: var(--color-text-placeholder); margin-top: 8px">
              支持 .xlsx / .xls 格式，文件大小不超过 10MB
            </div>
          </template>
        </el-upload>

        <el-form label-width="100px">
          <el-form-item label="导入模式">
            <el-radio-group v-model="importMode">
              <el-radio value="incremental"> 增量导入（跳过已有重复数据） </el-radio>
              <el-radio value="overwrite"> 全量覆盖（清空后重新导入） </el-radio>
            </el-radio-group>
          </el-form-item>
        </el-form>
      </div>

      <!-- 第二步：预览结果 -->
      <div v-else>
        <el-descriptions :column="3" border style="margin-bottom: 16px">
          <el-descriptions-item label="关联模块">
            {{ moduleLabel(previewResult.module) }}
          </el-descriptions-item>
          <el-descriptions-item label="总行数">
            {{ previewResult.total_rows }}
          </el-descriptions-item>
          <el-descriptions-item label="导入模式">
            {{ importMode === 'incremental' ? '增量导入' : '全量覆盖' }}
          </el-descriptions-item>
          <el-descriptions-item label="有效数据">
            <el-tag type="success">{{ previewResult.success_count }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="失败/错误">
            <el-tag :type="previewResult.error_count > 0 ? 'danger' : 'info'">
              {{ previewResult.error_count }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="预览条数">
            <el-tag type="info">{{ previewResult.parsed_data?.length || 0 }}</el-tag>
          </el-descriptions-item>
        </el-descriptions>

        <!-- 预览数据表格 -->
        <div v-if="previewResult.parsed_data?.length" style="margin-bottom: 16px">
          <h4 style="margin: 0 0 8px; font-size: 14px; color: var(--color-primary)">
            数据预览（前 {{ previewResult.parsed_data.length }} 条）
          </h4>
          <el-table :data="previewResult.parsed_data" border size="small" max-height="220">
            <el-table-column
              v-for="col in previewColumns"
              :key="col"
              :prop="col"
              :label="col"
              min-width="100"
              show-overflow-tooltip
            />
          </el-table>
        </div>

        <!-- 错误列表 -->
        <div v-if="previewResult.errors?.length" style="margin-bottom: 8px">
          <h4 style="margin: 0 0 8px; font-size: 14px; color: var(----color-danger)">
            错误详情（共 {{ previewResult.errors.length }} 条）
          </h4>
          <el-table :data="previewResult.errors" border size="small" max-height="160">
            <el-table-column prop="row" label="位置" width="70" />
            <el-table-column prop="message" label="错误信息" />
          </el-table>
        </div>
      </div>

      <template #footer>
        <el-button @click="showUploadDialog = false">取消</el-button>
        <!-- 预览按钮 -->
        <el-button
          v-if="!previewResult"
          type="primary"
          :loading="previewing"
          :disabled="!selectedFile"
          @click="handleFilePreview"
        >
          预览数据
        </el-button>
        <!-- 返回预览 -->
        <el-button v-else @click="previewResult = null"> 重新选择文件 </el-button>
        <!-- 确认导入 -->
        <el-button
          v-if="previewResult"
          type="success"
          :loading="importing"
          @click="handleConfirmImport"
        >
          确认导入
        </el-button>
      </template>
    </el-dialog>

    <!-- 导入结果对话框 -->
    <el-dialog v-model="showImportResult" title="导入结果" :width="DIALOG_MD">
      <div v-if="importResult">
        <el-result v-if="importResult.success" icon="success" :title="importResult.message">
          <template #sub-title>
            <el-descriptions :column="2" border style="margin-top: 16px">
              <el-descriptions-item label="导入成功">
                <el-tag type="success">{{ importResult.imported }}</el-tag> 条
              </el-descriptions-item>
              <el-descriptions-item v-if="importResult.skipped" label="跳过重复">
                <el-tag type="info">{{ importResult.skipped }}</el-tag> 条
              </el-descriptions-item>
              <el-descriptions-item v-if="importResult.deleted" label="删除旧记录">
                <el-tag type="warning">{{ importResult.deleted }}</el-tag> 条
              </el-descriptions-item>
              <el-descriptions-item label="导入失败">
                <el-tag :type="importResult.failed > 0 ? 'danger' : 'info'">
                  {{ importResult.failed }}
                </el-tag>
                条
              </el-descriptions-item>
            </el-descriptions>
          </template>
        </el-result>

        <el-result v-else icon="error" title="导入失败">
          <template #sub-title>
            <p>{{ importResult.message || importResult.detail }}</p>
          </template>
        </el-result>

        <!-- 错误详情 -->
        <div v-if="importResult.errors?.length" style="margin-top: 12px">
          <h4 style="color: var(----color-danger)">失败详情</h4>
          <el-table :data="importResult.errors" border size="small" max-height="180">
            <el-table-column prop="row" label="行号" width="70" />
            <el-table-column prop="message" label="错误信息" />
          </el-table>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { DIALOG_SM, DIALOG_MD } from '@/config/dialog'
import EmptyState from '@/components/business/EmptyState/EmptyState.vue'
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Search,
  Upload,
  House,
  School,
  Money,
  Folder,
  Crop,
  DataAnalysis,
  Document,
} from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'
import { get, post, put, del, apiRequest } from '@/api/request'

interface Template {
  id: number
  name: string
  type: string
  module: string
  fields?: string
  description?: string
  is_active: boolean
  created_at?: string
  updated_at?: string
}

// 状态
const activeTab = ref('import')
const loading = ref(false)
const creating = ref(false)
const templates = ref<Template[]>([])
const showCreateDialog = ref(false)
const showEditDialog = ref(false)
const showPreviewDialog = ref(false)
const showUploadDialog = ref(false)
const showImportResult = ref(false)
const editTemplate = ref<Template | null>(null)
const previewTemplate = ref<Template | null>(null)
const searchText = ref('')
const filterModule = ref('')

// 上传相关
const uploadRef = ref()
const selectedFile = ref<File | null>(null)
const previewResult = ref<any>(null)
const previewColumns = ref<string[]>([])
const importing = ref(false)
const previewing = ref(false)
const importMode = ref('incremental')
const currentUploadTemplate = ref<Template | null>(null)
const importResult = ref<any>(null)

// 表单
const createFormRef = ref<FormInstance>()
const editFormRef = ref<FormInstance>()
const newTemplate = reactive({
  name: '',
  type: 'import',
  module: 'village',
  description: '',
  selectedFields: [] as string[],
})

// 字段组合生成（available-fields）
const availableFields = ref<Array<{ key: string; label: string }>>([])

async function loadAvailableFields() {
  availableFields.value = []
  if (!newTemplate.module) return
  try {
    const { get } = await import('@/api/request')
    const res: any = await get('/report-templates/available-fields', { module: newTemplate.module })
    const list = res?.data?.data ?? res?.data ?? res ?? []
    availableFields.value = Array.isArray(list) ? list : []
  } catch {
    availableFields.value = []
  }
}

// 在线填报
const showFillDialog = ref(false)
const fillTemplate = ref<Template | null>(null)
const fillFields = ref<Array<{ key: string; label: string }>>([])
const fillRow = ref<Record<string, any>>({})

function openFillDialog(t: Template) {
  fillTemplate.value = t
  showFillDialog.value = true
  fillRow.value = {}
  // 解析模板字段（兼容对象/字符串数组）
  const keys = parseFields(t.fields)
  fillFields.value = keys.map((k: string) => ({ key: k, label: k }))
  // 若模板无字段配置，加载模块默认字段
  if (fillFields.value.length === 0 && t.module) {
    loadModuleFieldsForFill(t.module)
  }
}

async function loadModuleFieldsForFill(module: string) {
  try {
    const { get } = await import('@/api/request')
    const res: any = await get('/report-templates/available-fields', { module })
    const list = res?.data?.data ?? res?.data ?? res ?? []
    fillFields.value = Array.isArray(list) ? list : []
  } catch {
    fillFields.value = []
  }
}

async function handleFillExport() {
  const XLSX = (await import('xlsx')) as any
  const header = fillFields.value.map((f) => f.label || f.key)
  const row = fillFields.value.map((f) => fillRow.value[f.key] ?? '')
  const ws = XLSX.utils.aoa_to_sheet([header, row])
  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, ws, 'Sheet1')
  XLSX.writeFile(wb, `${fillTemplate.value?.name || '填报'}_填报.xlsx`)
  ElMessage.success('已导出 Excel 文件')
}

const createRules: FormRules = {
  name: [{ required: true, message: '请输入模板名称', trigger: 'blur' }],
  type: [{ required: true, message: '请选择模板类型', trigger: 'change' }],
  module: [{ required: true, message: '请选择关联模块', trigger: 'change' }],
}
const editRules: FormRules = {
  name: [{ required: true, message: '请输入模板名称', trigger: 'blur' }],
}

const moduleIcon = (m: string) =>
  (
    ({
      village: House,
      school: School,
      fund: Money,
      project: Folder,
      rural_work: Crop,
      comprehensive: DataAnalysis,
    }) as Record<string, any>
  )[m] || Document
const moduleLabel = (m: string) =>
  ({
    village: '帮扶村',
    school: '帮扶学校',
    fund: '经费管理',
    project: '帮扶项目',
    rural_work: '乡村工作',
    comprehensive: '综合报表',
  })[m] || m

const formatDate = (dateStr?: string) => {
  if (!dateStr) return '-'
  return dateStr.slice(0, 10)
}

const parseFields = (fields?: string): string[] => {
  if (!fields) return []
  try {
    const parsed = JSON.parse(fields)
    if (!Array.isArray(parsed)) return []
    // 字段可能是对象（含 excel_header）或纯字符串
    return parsed
      .map((f: any) =>
        typeof f === 'object' && f !== null
          ? f.excel_header || f.db_field || JSON.stringify(f)
          : String(f)
      )
      .filter(Boolean)
  } catch {
    return fields
      .split(',')
      .map((f) => f.trim())
      .filter(Boolean)
  }
}

// 过滤逻辑：类型 + 搜索 + 模块
const displayTemplates = computed(() => {
  let data = templates.value.filter((t) => t.type === activeTab.value)
  if (searchText.value) {
    const q = searchText.value.toLowerCase()
    data = data.filter(
      (t) =>
        (t.name && t.name.toLowerCase().includes(q)) ||
        (t.description && t.description.toLowerCase().includes(q))
    )
  }
  if (filterModule.value) {
    data = data.filter((t) => t.module === filterModule.value)
  }
  return data
})

function onFilterChange() {
  // displayTemplates 是 computed，自动响应
}

// API
async function loadTemplates() {
  loading.value = true
  try {
    const data = await get('/report-templates')
    // 兼容多种后端响应格式: 直接数组 / { data: [...] } / { items: [...] }
    const list = Array.isArray(data)
      ? data
      : Array.isArray((data as any)?.data)
        ? (data as any).data
        : (data as any)?.items || []
    templates.value = list as Template[]
  } catch {
    templates.value = []
  } finally {
    loading.value = false
  }
}

function openCreateDialog() {
  showCreateDialog.value = true
}

function resetCreateForm() {
  newTemplate.name = ''
  newTemplate.description = ''
  newTemplate.type = 'import'
  newTemplate.module = 'village'
  createFormRef.value?.resetFields()
}

async function handleCreate() {
  if (!createFormRef.value) return
  try {
    await createFormRef.value.validate()
  } catch {
    return
  }
  creating.value = true
  try {
    const payload: any = {
      name: newTemplate.name,
      type: newTemplate.type,
      module: newTemplate.module,
      description: newTemplate.description || undefined,
    }
    if (newTemplate.selectedFields.length > 0) {
      // 后端 fields 期望字段映射对象数组 [{excel_col, excel_header, db_field, required}]，
      // 仅发送 key 数组会导致下载/填报解析时 field.get 崩溃（500）
      const labelMap = new Map(availableFields.value.map((f) => [f.key, f.label]))
      payload.fields = JSON.stringify(
        newTemplate.selectedFields.map((key: string, i: number) => ({
          excel_col: String.fromCharCode(65 + i),
          excel_header: labelMap.get(key) || key,
          db_field: key,
          required: i === 0,
        }))
      )
    }
    await post('/report-templates', payload)
    ElMessage.success('模板创建成功')
    showCreateDialog.value = false
    activeTab.value = newTemplate.type
    loadTemplates()
  } catch {
    ElMessage.error('创建失败')
  } finally {
    creating.value = false
  }
}

async function handleDownload(t: Template) {
  try {
    const res = await apiRequest({
      method: 'GET',
      url: `/report-templates/${t.id}/download`,
      responseType: 'blob',
    })
    // apiRequest 在 responseType:'blob' 下直接返回 Blob 本身（不要再取 .data）
    const url = window.URL.createObjectURL(res)
    const link = document.createElement('a')
    link.href = url
    link.download = `${t.name}.xlsx`
    link.click()
    window.URL.revokeObjectURL(url)
    ElMessage.success(`下载模板: ${t.name}`)
  } catch {
    ElMessage.error('下载失败')
  }
}

function handleEdit(t: Template) {
  editTemplate.value = { ...t }
  showEditDialog.value = true
}

async function handleSaveEdit() {
  if (!editTemplate.value) return
  if (editFormRef.value) {
    try {
      await editFormRef.value.validate()
    } catch {
      return
    }
  } else if (!editTemplate.value.name?.trim()) {
    ElMessage.warning('请输入模板名称')
    return
  }
  creating.value = true
  try {
    await put(`/report-templates/${editTemplate.value.id}`, {
      name: editTemplate.value.name,
      description: editTemplate.value.description,
      is_active: editTemplate.value.is_active,
    })
    ElMessage.success('保存成功')
    showEditDialog.value = false
    loadTemplates()
  } catch {
    ElMessage.error('保存失败')
  } finally {
    creating.value = false
  }
}

function handlePreview(t: Template) {
  previewTemplate.value = { ...t }
  showPreviewDialog.value = true
}

async function handleDelete(t: Template) {
  try {
    await ElMessageBox.confirm(`确定删除模板“${t.name}”？此操作不可恢复。`, '提示', {
      type: 'warning',
    })
    await del(`/report-templates/${t.id}`)
    ElMessage.success('删除成功')
    loadTemplates()
  } catch {
    // cancelled
  }
}

// 上传填报相关方法
function openUploadDialog(t: Template) {
  selectedFile.value = null
  previewResult.value = null
  previewColumns.value = []
  importMode.value = 'incremental'
  currentUploadTemplate.value = t
  if (uploadRef.value) {
    uploadRef.value.clearFiles()
  }
  showUploadDialog.value = true
}

function onUploadDialogClosed() {
  selectedFile.value = null
  previewResult.value = null
  previewColumns.value = []
  if (uploadRef.value) {
    uploadRef.value.clearFiles()
  }
}

function onFileChange(file: any) {
  selectedFile.value = file.raw || file
}

function onFileRemove() {
  selectedFile.value = null
  previewResult.value = null
}

async function handleFilePreview() {
  if (!selectedFile.value || !currentUploadTemplate.value) return
  previewing.value = true
  try {
    const formData = new FormData()
    formData.append('file', selectedFile.value)
    const res = await post(
      `/report-templates/${currentUploadTemplate.value!.id}/upload?mode=preview`,
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' } }
    )
    previewResult.value = res.data
    // 提取预览列名
    if (res.data.parsed_data?.length) {
      previewColumns.value = Object.keys(res.data.parsed_data[0] || {})
    }
  } catch (err: any) {
    const msg = err?.response?.data?.detail || err?.message || '预览失败'
    ElMessage.error(msg)
    previewResult.value = null
  } finally {
    previewing.value = false
  }
}

async function handleConfirmImport() {
  if (!selectedFile.value || !currentUploadTemplate.value) return

  // 增量覆盖模式需要二次确认
  if (importMode.value === 'overwrite') {
    try {
      await ElMessageBox.confirm(
        '全量覆盖将删除现有所有记录后重新导入，确定继续？',
        '危险操作确认',
        { type: 'warning', confirmButtonText: '确定全量覆盖' }
      )
    } catch {
      return
    }
  }

  importing.value = true
  try {
    const formData = new FormData()
    formData.append('file', selectedFile.value)
    const res = await post(
      `/report-templates/${currentUploadTemplate.value!.id}/upload?mode=confirm&import_mode=${importMode.value}`,
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' } }
    )
    importResult.value = res.data
    showUploadDialog.value = false
    showImportResult.value = true
    loadTemplates()
  } catch (err: any) {
    const msg = err?.response?.data?.detail || err?.message || '导入失败'
    ElMessage.error(msg)
  } finally {
    importing.value = false
  }
}

onMounted(loadTemplates)
</script>

<style lang="scss" scoped>
.report-templates-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.page-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--color-primary-dark-1);
  margin: 0 0 4px;
}
.page-desc {
  font-size: 14px;
  color: var(--color-text-secondary);
  margin: 0;
}

.filter-bar {
  display: flex;
  gap: 12px;
  align-items: center;
}

.template-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 100px;
}
.template-item {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px;
  background: var(--color-bg-hover);
  border-radius: 8px;
  border: 1px solid #eee;
  transition:
    border-color 0.2s,
    box-shadow 0.2s;
}
.template-item:hover {
  border-color: var(--color-primary-light-1);
  box-shadow: 0 2px 8px rgba(64, 145, 108, 0.1);
}
.t-icon {
  font-size: 32px;
  color: var(--color-primary);
  flex-shrink: 0;
}
.t-info {
  flex: 1;
}
.t-name-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.t-info h4 {
  margin: 0;
  font-size: 15px;
  color: var(--color-primary-dark-1);
}
.t-info p {
  margin: 0 0 4px;
  font-size: 13px;
  color: var(--color-text-secondary);
}
.t-meta {
  font-size: 12px;
  color: var(--color-text-secondary);
}
.t-actions {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-shrink: 0;
}

.preview-content {
  padding: 0;
}
.preview-fields {
  margin-top: 16px;
}
.preview-fields h4 {
  margin: 0 0 8px;
  font-size: 14px;
  color: var(--color-primary-dark-1);
}

.error-list {
  max-height: 200px;
  overflow-y: auto;
  padding-left: 20px;
  color: var(----color-danger);
  font-size: 13px;
}
.error-list li {
  margin-bottom: 4px;
}

@media (max-width: 768px) {
  .filter-bar {
    flex-direction: column;
    align-items: stretch;
  }
  .template-item {
    flex-direction: column;
    align-items: flex-start;
  }
  .t-actions {
    width: 100%;
    justify-content: flex-end;
  }
}
</style>
