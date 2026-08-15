<template>
  <div class="batch-import-page">
    <div class="page-header">
      <div class="header-info">
        <h2 class="page-title">数据批量导入</h2>
        <p class="page-desc">
          通过Excel模板批量导入帮扶项目数据，支持基本信息、组织管理、资金管理、进度管理、成效评估五大板块
        </p>
      </div>
      <div class="header-actions">
        <el-button @click="pushSafe('/projects')">
          <el-icon><Back /></el-icon>返回项目列表
        </el-button>
      </div>
    </div>

    <el-steps :active="step" finish-status="success" align-center class="steps-card">
      <el-step title="选择模板" description="选择并下载导入模板" />
      <el-step title="上传文件" description="上传填写好的Excel" />
      <el-step title="数据校验" description="校验格式与逻辑" />
      <el-step title="预览确认" description="确认导入数据" />
      <el-step title="导入执行" description="执行导入" />
      <el-step title="导入报告" description="查看结果" />
    </el-steps>

    <div class="step-content">
      <!-- ========== 步骤1: 选择模板 ========== -->
      <div v-if="step === 0" class="step-panel">
        <!-- 顶部表单：填报日期 + 年度选择 -->
        <div class="template-form-bar">
          <div class="form-item">
            <label>填报日期</label>
            <span class="form-value">{{ currentDate }}</span>
          </div>
          <div class="form-item">
            <label>帮扶项目年度</label>
            <el-input-number
              v-model="selectedYear"
              :min="2000"
              :max="2099"
              :step="1"
              controls-position="right"
              style="width: 160px"
            />
            <span style="margin-left: 4px; color: #666; font-size: 13px">年</span>
          </div>
        </div>

        <!-- 模板选择表格 -->
        <div class="template-table-wrapper">
          <h3 class="section-title">选择导入模板</h3>
          <el-table
            :data="templates"
            border
            stripe
            highlight-current-row
            :current-row-key="selectedTemplate"
            row-key="type"
            class="template-table"
            @current-change="handleTemplateSelect"
          >
            <el-table-column width="55" align="center">
              <template #default="{ row }">
                <el-radio
                  :value="row.type"
                  :model-value="selectedTemplate"
                  @change="selectedTemplate = row.type"
                >
                  <span></span>
                </el-radio>
              </template>
            </el-table-column>
            <el-table-column prop="name" label="模板名称" width="180">
              <template #default="{ row }">
                <span class="tmpl-name">
                  <el-icon class="tmpl-icon-inline"><component :is="row.icon" /></el-icon>
                  {{ row.name }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="description" label="说明" min-width="260" />
            <el-table-column label="涵盖板块" width="200">
              <template #default="{ row }">
                <div class="section-tags">
                  <el-tag
                    v-for="s in row.sections"
                    :key="s"
                    size="small"
                    type="info"
                    effect="plain"
                    >{{ s }}</el-tag
                  >
                </div>
              </template>
            </el-table-column>
            <el-table-column label="字段数" width="80" align="center">
              <template #default="{ row }">
                <span class="field-count">{{ row.fieldCount }}</span>
              </template>
            </el-table-column>
            <el-table-column label="适用场景" width="180">
              <template #default="{ row }">
                <span class="scenario-text">{{ row.scenario }}</span>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <!-- 模板内容预览 -->
        <div v-if="selectedTemplate" class="template-preview">
          <h3 class="section-title">
            模板字段预览
            <span class="preview-hint">（<span class="required-mark">*</span>为必填字段）</span>
          </h3>
          <div class="preview-sections">
            <div v-for="sec in previewSections" :key="sec.label" class="preview-section">
              <div class="preview-section-title">{{ sec.label }}</div>
              <div class="preview-fields">
                <span
                  v-for="f in sec.fields"
                  :key="f.col"
                  class="preview-field"
                  :class="{ required: f.required }"
                >
                  <span v-if="f.required" class="required-mark">*</span>{{ f.col }}
                </span>
              </div>
            </div>
          </div>
        </div>

        <div class="step-actions">
          <el-button type="success" :disabled="!selectedTemplate" @click="handleDownloadTemplate">
            <el-icon><Download /></el-icon>下载模板（{{ selectedYear }}年度）
          </el-button>
          <el-button type="primary" :disabled="!selectedTemplate" @click="step++">
            下一步：上传文件
          </el-button>
        </div>
      </div>

      <!-- ========== 步骤2: 上传文件 ========== -->
      <div v-if="step === 1" class="step-panel">
        <div class="upload-info-bar">
          <el-descriptions :column="3" border size="small">
            <el-descriptions-item label="模板类型">{{ currentTemplateName }}</el-descriptions-item>
            <el-descriptions-item label="帮扶年度">{{ selectedYear }}年</el-descriptions-item>
            <el-descriptions-item label="填报日期">{{ currentDate }}</el-descriptions-item>
          </el-descriptions>
        </div>
        <el-upload
          ref="uploadRef"
          drag
          :auto-upload="false"
          accept=".xlsx,.xls"
          :limit="1"
          :on-change="handleFileSelect"
          :on-exceed="() => ElMessage.warning('只能上传一个文件')"
          class="upload-area"
        >
          <el-icon class="el-icon--upload" :size="48"><UploadFilled /></el-icon>
          <div class="el-upload__text">将文件拖到此处，或<em>点击选择</em></div>
          <template #tip
            ><div class="el-upload__tip">仅支持 .xlsx/.xls 格式，最大10MB</div></template
          >
        </el-upload>
        <el-form label-width="120px" style="margin-top: 24px">
          <el-form-item label="导入模式">
            <el-radio-group v-model="importMode">
              <el-radio value="incremental">
                <span>增量导入</span>
                <span class="mode-hint">仅新增，不影响已有数据</span>
              </el-radio>
              <el-radio value="overwrite">
                <span>全量覆盖</span>
                <span class="mode-hint">清空后重新导入</span>
              </el-radio>
            </el-radio-group>
          </el-form-item>
        </el-form>
        <div class="step-actions">
          <el-button @click="step--">上一步</el-button>
          <el-button
            type="primary"
            :disabled="!selectedFile"
            :loading="validating"
            @click="handleValidate"
            >开始校验</el-button
          >
        </div>
      </div>

      <!-- ========== 步骤3: 校验结果 ========== -->
      <div v-if="step === 2" class="step-panel">
        <el-result
          v-if="!validating && validationErrors.length === 0"
          icon="success"
          title="校验通过"
          sub-title="数据格式和逻辑验证通过，可以继续导入"
        />
        <el-result
          v-if="!validating && validationErrors.length > 0"
          icon="warning"
          :title="`发现 ${validationErrors.length} 个问题`"
          sub-title="请修正以下问题后重新上传"
        />
        <div v-if="validating" style="text-align: center; padding: 40px">
          <el-icon class="is-loading" :size="32"><Loading /></el-icon>
          <p>正在校验数据...</p>
        </div>
        <el-table
          v-if="validationErrors.length > 0"
          :data="validationErrors"
          max-height="300"
          border
          style="margin-top: 16px"
        >
          <el-table-column prop="row" label="行号" width="80" align="center" />
          <el-table-column prop="field" label="字段" width="140" />
          <el-table-column prop="message" label="问题描述" />
        </el-table>
        <div class="step-actions">
          <el-button @click="step = 1">返回修改</el-button>
          <el-button
            type="primary"
            :disabled="validating || validationErrors.length > 0"
            @click="step++"
            >继续导入</el-button
          >
        </div>
      </div>

      <!-- ========== 步骤4: 预览 ========== -->
      <div v-if="step === 3" class="step-panel">
        <el-descriptions title="导入数据预览" :column="3" border>
          <el-descriptions-item label="模板类型">{{ currentTemplateName }}</el-descriptions-item>
          <el-descriptions-item label="帮扶年度">{{ selectedYear }}年</el-descriptions-item>
          <el-descriptions-item label="导入模式">{{
            importMode === 'incremental' ? '增量导入' : '全量覆盖'
          }}</el-descriptions-item>
          <el-descriptions-item label="数据总行数">{{ previewCount }} 条</el-descriptions-item>
          <el-descriptions-item label="填报日期">{{ currentDate }}</el-descriptions-item>
        </el-descriptions>
        <div class="step-actions" style="margin-top: 24px">
          <el-button @click="step--">上一步</el-button>
          <el-button type="primary" @click="handleImport">确认导入</el-button>
        </div>
      </div>

      <!-- ========== 步骤5: 导入中 ========== -->
      <div v-if="step === 4" class="step-panel" style="text-align: center; padding: 60px">
        <el-progress
          type="circle"
          :percentage="importProgress"
          :status="importProgress >= 100 ? 'success' : undefined"
        />
        <p style="margin-top: 16px">
          {{ importProgress >= 100 ? '导入完成' : '正在导入数据...' }}
        </p>
      </div>

      <!-- ========== 步骤6: 结果 ========== -->
      <div v-if="step === 5" class="step-panel">
        <el-result
          icon="success"
          title="导入完成"
          :sub-title="`成功导入 ${importResult.success} 条，失败 ${importResult.failed} 条`"
        >
          <template #extra>
            <el-button type="primary" @click="handleReset">继续导入</el-button>
            <el-button @click="pushSafe('/projects')">查看项目列表</el-button>
          </template>
        </el-result>
        <div v-if="importResult.errors && importResult.errors.length > 0" style="margin-top: 20px">
          <h4 style="margin-bottom: 8px; color: var(--color-danger)">失败记录</h4>
          <el-table :data="importResult.errors" border size="small" max-height="200">
            <el-table-column prop="row" label="行号" width="80" align="center" />
            <el-table-column prop="name" label="项目名称" width="200" />
            <el-table-column prop="error" label="失败原因" />
          </el-table>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouterSafe } from '@/composables/useRouterSafe'
import { ref, computed } from 'vue'
import {
  UploadFilled,
  Loading,
  Download,
  Back,
  House,
  Document,
  Money,
  School,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { post } from '@/api/request'
import request from '@/api/request'
import { downloadBlobAsFile } from '@/api/helpers/blobDownload'

const { pushSafe } = useRouterSafe()

const step = ref(0)
const selectedTemplate = ref('')
const selectedFile = ref<File | null>(null)
const importMode = ref('incremental')
const validating = ref(false)
const validationErrors = ref<any[]>([])
const previewCount = ref(0)
const importProgress = ref(0)
const importResult = ref<{ success: number; failed: number; errors?: any[] }>({
  success: 0,
  failed: 0,
})

// 日期 & 年度
const now = new Date()
const currentDate = `${now.getFullYear()}年${String(now.getMonth() + 1).padStart(2, '0')}月${String(now.getDate()).padStart(2, '0')}日`
const selectedYear = ref(now.getFullYear())

// 实体类型模板定义
const entityPreviewFields: Record<
  string,
  { label: string; fields: { col: string; required: boolean }[] }[]
> = {
  supported_village: [
    {
      label: '基本信息',
      fields: [
        { col: '各部门各单位', required: true },
        { col: '具体帮扶单位', required: true },
        { col: '定点帮扶村', required: true },
        { col: '地区范围', required: false },
      ],
    },
    {
      label: '属性标识',
      fields: [
        { col: '是否属于三区三州', required: false },
        { col: '是否属于边疆地区', required: false },
        { col: '是否属于民族地区', required: false },
        { col: '是否属于160个国家乡村振兴重点帮扶县', required: false },
      ],
    },
  ],
  project: [
    {
      label: '基本信息',
      fields: [
        { col: '项目名称', required: true },
        { col: '项目编号', required: false },
        { col: '项目类型', required: true },
        { col: '项目描述', required: false },
      ],
    },
    {
      label: '组织与资金',
      fields: [
        { col: '预算金额', required: false },
        { col: '项目负责人', required: false },
        { col: '联系电话', required: false },
        { col: '负责单位', required: false },
        { col: '组织编码', required: false },
      ],
    },
  ],
  fund: [
    {
      label: '基本信息',
      fields: [
        { col: '资金名称', required: true },
        { col: '编号', required: false },
        { col: '金额', required: true },
        { col: '资金类型', required: false },
        { col: '资金来源', required: false },
      ],
    },
    {
      label: '关联信息',
      fields: [
        { col: '用途', required: false },
        { col: '状态', required: false },
        { col: '经办人', required: false },
        { col: '关联项目编号', required: false },
        { col: '日期', required: false },
      ],
    },
  ],
  school: [
    {
      label: '基本信息',
      fields: [
        { col: '学校名称', required: true },
        { col: '学校编码', required: false },
        { col: '学校类型', required: false },
        { col: '省份', required: false },
        { col: '城市', required: false },
        { col: '区县', required: false },
      ],
    },
    {
      label: '联系与规模',
      fields: [
        { col: '校长姓名', required: false },
        { col: '联系电话', required: false },
        { col: '学生人数', required: false },
        { col: '教师人数', required: false },
        { col: '帮扶单位', required: false },
        { col: '帮扶状态', required: false },
      ],
    },
  ],
}

const templates = [
  {
    type: 'supported_village',
    name: '帮扶村数据',
    icon: House,
    description: '导入帮扶村基础信息、属性标识、振兴发展梯队等数据',
    sections: ['基础信息', '属性标识'],
    fieldCount: 18,
    scenario: '村庄信息批量建档',
  },
  {
    type: 'project',
    name: '帮扶项目',
    icon: Document,
    description: '导入项目基础信息、预算金额、负责人、组织编码等',
    sections: ['基本信息', '组织与资金'],
    fieldCount: 13,
    scenario: '项目批量建档',
  },
  {
    type: 'fund',
    name: '资金台账',
    icon: Money,
    description: '导入资金名称、金额、类型、来源、关联项目等',
    sections: ['基本信息', '关联信息'],
    fieldCount: 12,
    scenario: '资金台账批量录入',
  },
  {
    type: 'school',
    name: '学校信息',
    icon: School,
    description: '导入学校基础信息、地理位置、师生规模、帮扶状态等',
    sections: ['基本信息', '联系与规模'],
    fieldCount: 14,
    scenario: '学校信息批量建档',
  },
]

const currentTemplateName = computed(
  () => templates.find((t) => t.type === selectedTemplate.value)?.name || ''
)

const previewSections = computed(() => {
  if (!selectedTemplate.value) return []
  return entityPreviewFields[selectedTemplate.value] || []
})

const handleTemplateSelect = (row: any) => {
  if (row) selectedTemplate.value = row.type
}

const handleDownloadTemplate = async () => {
  try {
    const tplName = templates.find((t) => t.type === selectedTemplate.value)?.name || '标准'
    await downloadBlobAsFile(
      () =>
        request.get('/import/template', {
          params: { entity_type: selectedTemplate.value },
          responseType: 'blob',
        }),
      { fallbackFileName: `${tplName}导入模板_${selectedYear.value}.xlsx` }
    )
  } catch {
    ElMessage.error('下载模板失败')
  }
}

const handleFileSelect = (file: any) => {
  selectedFile.value = file.raw
}

const handleValidate = async () => {
  if (!selectedFile.value) return
  validating.value = true
  validationErrors.value = []
  try {
    const formData = new FormData()
    formData.append('file', selectedFile.value)
    const res = await post('/import/validate', formData, {
      params: { entity_type: selectedTemplate.value },
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    // post() 已自动解包，后端裸返回校验结果对象
    const data = res?.data ?? res
    if (data.error_count > 0 && data.first_errors) {
      validationErrors.value = data.first_errors.map((e: any) => ({
        row: e.row_number || e.row || 0,
        field: e.field_name || e.field || '',
        message: e.message || '',
      }))
    }
    previewCount.value = data.total_rows || 0
    step.value = 2
  } catch (e: any) {
    // Bug#16 修复：校验请求失败时停留在当前步骤并明确报错，
    // 不得推进到步骤2（空 validationErrors 会渲染绿色"校验通过"成功页误导用户）
    previewCount.value = 0
    ElMessage.error(e?.response?.data?.detail || '校验请求失败，请检查网络后重试')
  } finally {
    validating.value = false
  }
}

const handleImport = async () => {
  if (!selectedFile.value) return
  step.value = 4
  importProgress.value = 10
  try {
    const formData = new FormData()
    formData.append('file', selectedFile.value)
    const res = await post(
      `/import/entities?mode=${importMode.value}&entity_type=${selectedTemplate.value}`,
      formData,
      {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 120000,
        onUploadProgress: (e: any) => {
          if (e.total) importProgress.value = Math.min(Math.round((e.loaded / e.total) * 80), 80)
        },
      }
    )
    importProgress.value = 100
    // post() 已自动解包，后端裸返回导入结果对象
    const data = res?.data ?? res
    importResult.value = {
      success: data.success_rows || 0,
      failed: data.failed_rows || 0,
      errors: data.errors || [],
    }
    setTimeout(() => {
      step.value = 5
    }, 500)
  } catch (e: any) {
    // Bug#17 修复：导入失败时返回预览确认页(step 3)并明确报错，
    // 不得进入步骤5（该页固定渲染 icon="success" 的"导入完成"成功结果页）
    importProgress.value = 0
    ElMessage.error(e?.response?.data?.detail || '导入失败')
    step.value = 3
  }
}

const handleReset = () => {
  step.value = 0
  selectedFile.value = null
  validationErrors.value = []
  previewCount.value = 0
  importProgress.value = 0
  importResult.value = { success: 0, failed: 0 }
}
</script>

<style scoped>
.batch-import-page {
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
  color: #1b4332;
  margin: 0 0 4px;
}
.page-desc {
  font-size: 14px;
  color: #666;
  margin: 0;
}

.steps-card {
  background: white;
  padding: 24px 32px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}
.step-content {
  background: white;
  padding: 32px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  min-height: 300px;
}

/* 模板表单条 */
.template-form-bar {
  display: flex;
  align-items: center;
  gap: 40px;
  padding: 16px 20px;
  background: #f0f7f4;
  border: 1px solid #d4e8dc;
  border-radius: 8px;
  margin-bottom: 24px;
}
.form-item {
  display: flex;
  align-items: center;
  gap: 10px;
}
.form-item label {
  font-size: 14px;
  font-weight: 500;
  color: #1b4332;
  white-space: nowrap;
}
.form-value {
  font-size: 14px;
  color: #333;
  font-weight: 500;
}

/* 模板选择表格 */
.section-title {
  font-size: 15px;
  font-weight: 600;
  color: #1b4332;
  margin: 0 0 12px;
}
.preview-hint {
  font-size: 12px;
  font-weight: 400;
  color: #999;
}
.template-table-wrapper {
  margin-bottom: 24px;
}
.template-table :deep(.el-table__row) {
  cursor: pointer;
}
.template-table :deep(.current-row > td) {
  background-color: rgba(64, 145, 108, 0.08) !important;
}
.tmpl-name {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 500;
  color: #1b4332;
}
.tmpl-icon-inline {
  font-size: 18px;
  display: flex;
  align-items: center;
}
.section-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.field-count {
  font-weight: 600;
  color: #40916c;
  font-size: 15px;
}
.scenario-text {
  font-size: 13px;
  color: #666;
}

/* 模板预览 */
.template-preview {
  margin-bottom: 20px;
}
.preview-sections {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 12px;
}
.preview-section {
  background: #fafcfb;
  border: 1px solid #e8efe8;
  border-radius: 6px;
  padding: 12px 14px;
}
.preview-section-title {
  font-size: 13px;
  font-weight: 600;
  color: #1b4332;
  margin-bottom: 8px;
  padding-bottom: 6px;
  border-bottom: 1px solid #e0e8e0;
}
.preview-fields {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.preview-field {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 4px;
  background: #f0f0f0;
  color: #555;
}
.preview-field.required {
  background: #fff0f0;
  color: #d32f2f;
  font-weight: 500;
}
.required-mark {
  color: var(--color-danger);
  margin-right: 2px;
}

/* 上传信息条 */
.upload-info-bar {
  margin-bottom: 20px;
}
.mode-hint {
  font-size: 12px;
  color: #999;
  margin-left: 6px;
}

/* 通用 */
.step-actions {
  display: flex;
  justify-content: center;
  gap: 16px;
  margin-top: 24px;
}
.upload-area {
  width: 100%;
}

@media (max-width: 768px) {
  .template-form-bar {
    flex-direction: column;
    gap: 12px;
    align-items: flex-start;
  }
  .preview-sections {
    grid-template-columns: 1fr;
  }
}
</style>
