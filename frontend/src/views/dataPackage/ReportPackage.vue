<template>
  <div class="report-package-page">
    <div class="page-header">
      <div class="header-info">
        <h2 class="page-title">数据上报</h2>
        <p class="page-desc">选择数据范围，生成并导出上报数据包</p>
      </div>
      <div class="header-actions">
        <el-button
          type="success"
          :loading="oneClickLoading"
          size="large"
          @click="handleOneClickReport"
        >
          <el-icon><Cpu /></el-icon> 一键上报
        </el-button>
      </div>
    </div>

    <!-- 步骤条 -->
    <el-steps :active="currentStep" align-center style="margin-bottom: 24px">
      <el-step title="选择范围" />
      <el-step title="预览数据" />
      <el-step title="生成导出" />
    </el-steps>

    <!-- 非管理员仅导出本人录入数据（后端 export_scope=self） -->
    <el-alert v-if="!isAdmin" type="info" show-icon :closable="false" class="self-scope-alert"
      >仅导出您本人录入的数据</el-alert
    >

    <!-- 步骤1：选择数据范围 -->
    <el-card v-if="currentStep === 0">
      <el-form label-width="120px" style="max-width: 600px">
        <el-form-item label="上报年度">
          <el-date-picker
            v-model="form.year"
            type="year"
            placeholder="选择年度"
            value-format="YYYY"
          />
        </el-form-item>
        <el-form-item label="数据类型">
          <el-checkbox-group v-model="form.dataTypes">
            <el-checkbox :value="DATA_TYPES.VILLAGES">{{
              DATA_TYPE_LABELS[DATA_TYPES.VILLAGES]
            }}</el-checkbox>
            <el-checkbox :value="DATA_TYPES.PROJECTS">{{
              DATA_TYPE_LABELS[DATA_TYPES.PROJECTS]
            }}</el-checkbox>
            <el-checkbox :value="DATA_TYPES.FUNDS">经费数据</el-checkbox>
            <el-checkbox :value="DATA_TYPES.SCHOOLS">{{
              DATA_TYPE_LABELS[DATA_TYPES.SCHOOLS]
            }}</el-checkbox>
            <el-checkbox value="rural_works">乡村工作</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="备注说明">
          <el-input v-model="form.remarks" type="textarea" :rows="3" placeholder="可选填写备注" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="previewing" @click="previewData">
            下一步：预览数据
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 步骤2：预览数据 -->
    <el-card v-if="currentStep === 1">
      <div class="preview-summary">
        <h4>数据预览</h4>
        <!-- 数据完整性警告 -->
        <el-alert
          v-if="emptyDataTypes.length > 0"
          :title="`以下数据类型记录数为0: ${emptyDataTypes.map((t) => typeLabels[t] || t).join('、')}`"
          type="warning"
          show-icon
          :closable="false"
          style="margin-bottom: 12px"
        />
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="上报年度">{{ form.year }}</el-descriptions-item>
          <el-descriptions-item label="数据类型">{{
            form.dataTypes.map((t) => typeLabels[t] || t).join('、')
          }}</el-descriptions-item>
          <el-descriptions-item
            v-for="(count, key) in previewCounts"
            :key="key"
            :label="typeLabels[key] || key"
          >
            <span
              :style="{
                color: count === 0 ? 'var(--color-warning)' : '#1b4332',
                fontWeight: '600',
              }"
            >
              {{ count }} 条记录
            </span>
          </el-descriptions-item>
        </el-descriptions>
      </div>
      <div style="margin-top: 16px; display: flex; gap: 12px">
        <el-button @click="currentStep = 0">上一步</el-button>
        <el-button type="primary" :loading="generating" @click="generatePackage">
          生成数据包
        </el-button>
      </div>
    </el-card>

    <!-- 步骤3：生成导出 -->
    <el-card v-if="currentStep === 2">
      <el-result
        icon="success"
        title="数据包已生成"
        sub-title="数据包已自动开始下载，如未开始请手动点击下载"
      >
        <template #extra>
          <el-button type="primary" :loading="downloading" @click="downloadPackage">
            下载数据包 (ZIP)
          </el-button>
          <el-button @click="resetForm">重新上报</el-button>
        </template>
      </el-result>
    </el-card>

    <!-- 组件异常回退 -->
    <el-card v-if="componentError" class="error-fallback">
      <el-result icon="warning" title="页面加载异常" :sub-title="componentError">
        <template #extra>
          <el-button type="primary" @click="handleRetry">重试</el-button>
          <el-button @click="resetForm">返回首步</el-button>
        </template>
      </el-result>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { logger } from '@/utils/logger'
import { getErrorMessage } from '@/utils/getErrorMessage'

import { ref, reactive, computed, onErrorCaptured } from 'vue'
import { ElMessage } from 'element-plus'
import { Cpu } from '@element-plus/icons-vue'
import { post, apiRequest } from '@/api/request'
import { useAuthStore } from '@/stores/auth'
import { DATA_TYPES, DATA_TYPE_LABELS } from '@/constants/dataTypes'

defineOptions({ name: 'ReportPackage' })

const authStore = useAuthStore()
// 非管理员导出走后端 export_scope=self（仅本人录入数据），前端仅做提示
const isAdmin = computed(() => authStore.isAdmin)

const currentStep = ref(0)
const previewing = ref(false)
const generating = ref(false)
const downloading = ref(false)
const oneClickLoading = ref(false)
const packageId = ref('')
const componentError = ref('')

// 错误边界：捕获子组件异常，避免白屏
onErrorCaptured((err: Error) => {
  logger.error('[ReportPackage] 组件异常:', err)
  componentError.value = err?.message || '未知错误，请重试'
  return false // 阻止向上传播
})

function handleRetry() {
  componentError.value = ''
}

const form = reactive({
  year: new Date().getFullYear().toString(),
  dataTypes: [
    DATA_TYPES.VILLAGES,
    DATA_TYPES.PROJECTS,
    'funds',
    'schools',
    'rural_works',
  ] as string[],
  remarks: '',
})

const previewCounts = ref<Record<string, number>>({})

// 记录数为0的数据类型
const emptyDataTypes = computed(() => {
  return Object.entries(previewCounts.value)
    .filter(([_, count]) => count === 0)
    .map(([key]) => key)
})

const typeLabels: Record<string, string> = {
  villages: '帮扶村',
  projects: '项目',
  funds: '经费',
  schools: '学校',
  rural_works: '乡村工作',
}

function validateForm(): boolean {
  if (!form.year) {
    ElMessage.warning('请选择上报年度')
    return false
  }
  if (form.dataTypes.length === 0) {
    ElMessage.warning('请至少选择一种数据类型')
    return false
  }
  return true
}

async function previewData() {
  if (!validateForm()) return
  previewing.value = true
  try {
    const data = await post('/data-packages/preview', {
      year: form.year,
      data_types: form.dataTypes,
    })
    previewCounts.value = data?.counts || data?.data?.counts || {}
    currentStep.value = 1
  } catch {
    // 预览失败时用模拟数据让流程可继续
    previewCounts.value = {}
    for (const t of form.dataTypes) {
      previewCounts.value[t] = 0
    }
    currentStep.value = 1
  } finally {
    previewing.value = false
  }
}

async function generatePackage() {
  if (!validateForm()) return

  generating.value = true
  try {
    const data = await post('/data-packages/export', {
      data_types: form.dataTypes,
      description: form.remarks || `${form.year}年度数据上报`,
      type: 'report',
    })
    packageId.value = data?.package_id || data?.id || data?.data?.id || ''
    currentStep.value = 2
    ElMessage.success('数据包生成成功')
    // 自动触发下载
    if (packageId.value) {
      await downloadPackage()
    }
  } catch (error: any) {
    const errorMsg = error?.response?.data?.detail || error?.message || '数据包生成失败'
    ElMessage.error(errorMsg)
  } finally {
    generating.value = false
  }
}

async function downloadPackage() {
  if (!packageId.value) {
    ElMessage.warning('数据包 ID 不存在')
    return
  }
  downloading.value = true
  try {
    const response = await apiRequest({
      method: 'GET',
      url: `/data-packages/${packageId.value}/download`,
      responseType: 'blob',
    })
    // apiRequest 在 responseType:'blob' 下直接返回 Blob 本身
    const blob = new Blob([response])
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `上报数据包_${form.year}.zip`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  } catch {
    ElMessage.error('下载失败')
  } finally {
    downloading.value = false
  }
}

/** 一键上报：使用默认配置自动完成 生成 → 下载 */
async function handleOneClickReport() {
  if (!validateForm()) return

  oneClickLoading.value = true
  try {
    const response = await post('/data-packages/one-click-report', {
      year: form.year,
      data_types: form.dataTypes,
      remarks: form.remarks || `一键上报 ${form.year}年度数据`,
    })

    // 检查响应类型：可能是文件流或 JSON
    // apiRequest 已解包：responseType:'blob' 时 response 即 Blob，否则为响应体对象
    const isBlobResp = response instanceof Blob
    const data = isBlobResp ? null : (response?.data ?? response)
    if (isBlobResp) {
      // 直接下载文件流
      const url = URL.createObjectURL(response)
      const link = document.createElement('a')
      link.href = url
      link.download = `上报数据包_${form.year}.zip`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(url)
    } else if (data?.download_url) {
      // JSON 响应带下载链接
      const dlRes = await apiRequest({
        method: 'GET',
        url: data.download_url,
        responseType: 'blob',
      })
      // dlRes 已是 Blob 本身（apiRequest responseType:'blob' 直接返回）
      const blob = new Blob([dlRes as BlobPart])
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = data.file_name || `上报数据包_${form.year}.zip`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(url)
    }

    ElMessage.success('数据包已生成并开始下载')
    currentStep.value = 2
  } catch (e: any) {
    ElMessage.error('一键上报失败：' + getErrorMessage(e, '请稍后重试'))
  } finally {
    oneClickLoading.value = false
  }
}

function resetForm() {
  currentStep.value = 0
  packageId.value = ''
  previewCounts.value = {}
  componentError.value = ''
}
</script>

<style scoped>
.report-package-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
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
.preview-summary h4 {
  margin: 0 0 12px;
  color: var(--color-primary-dark-1);
}
.error-fallback {
  border: 1px solid var(--color-warning);
}
.self-scope-alert {
  margin-bottom: 16px;
}
</style>
