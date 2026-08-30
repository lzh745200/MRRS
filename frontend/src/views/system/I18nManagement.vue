<template>
  <div class="i18n-management">
    <div class="page-header">
      <h2 class="page-title">国际化管理</h2>
      <p class="page-desc">管理系统多语言翻译资源，确保前端文本覆盖完整</p>
    </div>

    <!-- 工具栏 -->
    <el-card class="toolbar-card">
      <div class="toolbar">
        <div class="toolbar-left">
          <span class="toolbar-label">当前语言：</span>
          <el-tag v-if="currentLang" type="success" size="large">
            {{ currentLang.name }} ({{ currentLang.language }})
          </el-tag>
          <el-tag v-else type="info" size="large">加载中...</el-tag>
        </div>
        <div class="toolbar-right">
          <el-select
            v-model="selectedLanguage"
            placeholder="选择目标语言"
            style="width: 200px"
            @change="onLanguageChange"
          >
            <el-option
              v-for="lang in languages"
              :key="lang.code"
              :label="`${lang.flag || ''} ${lang.name} (${lang.code})`"
              :value="lang.code"
            />
          </el-select>
          <el-button type="warning" :loading="checkingMissing" @click="checkMissingKeys">
            检查缺失键
          </el-button>
          <el-button type="primary" :icon="Refresh" :loading="loading" @click="loadTranslations">
            刷新
          </el-button>
        </div>
      </div>
    </el-card>

    <!-- 缺失键报告 -->
    <el-card v-if="missingReport" class="missing-card">
      <template #header>
        <div class="card-header">
          <span>缺失翻译键报告</span>
          <el-tag type="danger">
            完成率: {{ (missingReport.completion_rate * 100).toFixed(1) }}%
          </el-tag>
        </div>
      </template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="源语言">{{
          missingReport.source_language
        }}</el-descriptions-item>
        <el-descriptions-item label="目标语言">{{
          missingReport.target_language
        }}</el-descriptions-item>
        <el-descriptions-item label="源语言键数">{{
          missingReport.source_count
        }}</el-descriptions-item>
        <el-descriptions-item label="目标语言键数">{{
          missingReport.target_count
        }}</el-descriptions-item>
        <el-descriptions-item label="缺失数量">
          <el-tag type="danger">{{ missingReport.missing_count }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="多余键数">{{
          missingReport.extra_keys?.length || 0
        }}</el-descriptions-item>
      </el-descriptions>
      <div v-if="missingReport.missing_keys?.length" class="missing-keys-section">
        <h4>缺失的翻译键 ({{ missingReport.missing_keys.length }})</h4>
        <div class="missing-keys-list">
          <el-tag
            v-for="key in missingReport.missing_keys"
            :key="key"
            type="danger"
            class="missing-key-tag"
            closable
            @close="addTranslationDialog(key)"
          >
            {{ key }}
          </el-tag>
        </div>
      </div>
    </el-card>

    <!-- 翻译表格 -->
    <el-card class="table-card">
      <template #header>
        <div class="card-header">
          <span>翻译资源 ({{ selectedLanguage }})</span>
          <el-input
            v-model="searchKeyword"
            placeholder="搜索翻译键或值..."
            clearable
            style="width: 300px"
            :prefix-icon="Search"
          />
        </div>
      </template>
      <el-table
        v-loading="loading"
        :data="filteredTranslations"
        max-height="600"
        empty-text="请选择语言并加载翻译资源"
      >
        <el-table-column prop="key" label="翻译键" min-width="200" sortable />
        <el-table-column label="翻译值" min-width="300">
          <template #default="{ row }">
            <span :class="{ 'missing-value': !row.value }">
              {{ row.value || '(缺失)' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.value" type="success" size="small">已翻译</el-tag>
            <el-tag v-else type="danger" size="small">缺失</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" align="center">
          <template #default="{ row }">
            <el-button size="small" type="primary" link @click="viewTranslationDetail(row.key)">
              详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 翻译详情对话框 -->
    <el-dialog v-model="detailDialogVisible" append-to-body title="翻译详情" :width="DIALOG_SM">
      <el-form label-width="80px">
        <el-form-item label="翻译键">
          <el-input :value="detailKey" readonly />
        </el-form-item>
        <el-form-item label="语言">
          <el-tag>{{ selectedLanguage }}</el-tag>
        </el-form-item>
        <el-form-item label="翻译值">
          <el-input :value="detailValue" readonly type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item v-if="detailFallback" label="注意">
          <el-alert type="warning" :closable="false" title="此翻译为回退值（使用默认语言结果）" />
        </el-form-item>
      </el-form>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { DIALOG_SM } from '@/config/dialog'
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Search } from '@element-plus/icons-vue'
import { i18nApi } from '@/api/i18n'
import type { Language, MissingKeysReport } from '@/api/i18n'

const loading = ref(false)
const checkingMissing = ref(false)
const selectedLanguage = ref('en')
const languages = ref<Language[]>([])
const currentLang = ref<{ language: string; name: string } | null>(null)
const translations = ref<Record<string, string>>({})
const missingReport = ref<MissingKeysReport | null>(null)
const searchKeyword = ref('')

const detailDialogVisible = ref(false)
const detailKey = ref('')
const detailValue = ref('')
const detailFallback = ref(false)

const filteredTranslations = computed(() => {
  const entries = Object.entries(translations.value).map(([key, value]) => ({
    key,
    value,
  }))
  if (!searchKeyword.value) return entries
  const kw = searchKeyword.value.toLowerCase()
  return entries.filter(
    (e) => e.key.toLowerCase().includes(kw) || (e.value || '').toLowerCase().includes(kw)
  )
})

async function loadLanguages() {
  try {
    const res = await i18nApi.getLanguages()
    languages.value = res.data || []
  } catch {
    ElMessage.error('加载语言列表失败')
  }
}

async function loadCurrentLanguage() {
  try {
    const res = await i18nApi.getCurrentLanguage()
    currentLang.value = res.data || null
  } catch {
    // 忽略
  }
}

async function loadTranslations() {
  if (!selectedLanguage.value) return
  loading.value = true
  try {
    const res = await i18nApi.getTranslations(selectedLanguage.value)
    translations.value = res.data?.translations || {}
    ElMessage.success(`已加载 ${Object.keys(translations.value).length} 条翻译`)
  } catch {
    ElMessage.error('加载翻译资源失败')
  } finally {
    loading.value = false
  }
}

async function checkMissingKeys() {
  checkingMissing.value = true
  try {
    const res = await i18nApi.getMissingKeys('zh-CN', selectedLanguage.value)
    missingReport.value = res.data || null
    if (missingReport.value?.missing_count) {
      ElMessage.warning(`发现 ${missingReport.value.missing_count} 个缺失翻译键`)
    } else {
      ElMessage.success('翻译覆盖完整！')
    }
  } catch {
    ElMessage.error('检查缺失键失败')
  } finally {
    checkingMissing.value = false
  }
}

async function viewTranslationDetail(key: string) {
  detailKey.value = key
  detailDialogVisible.value = true
  try {
    const res = await i18nApi.translate(key, selectedLanguage.value)
    detailValue.value = res.data?.value || ''
    detailFallback.value = res.data?.fallback || false
  } catch {
    detailValue.value = translations.value[key] || '(未找到)'
    detailFallback.value = false
  }
}

function addTranslationDialog(key: string) {
  ElMessage.info(`翻译键 "${key}" 需要添加翻译值 - 请通过后端接口添加`)
}

function onLanguageChange() {
  searchKeyword.value = ''
  missingReport.value = null
  loadTranslations()
}

onMounted(() => {
  loadLanguages()
  loadCurrentLanguage()
})
</script>

<style lang="scss" scoped>
.i18n-management {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 20px;
}
.page-header {
  margin-bottom: 0;
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
.toolbar-card {
  background: var(--color-bg-card);
}
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}
.toolbar-left,
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 10px;
}
.toolbar-label {
  font-weight: 500;
  color: var(--color-text-primary);
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.missing-card {
  border-left: 4px solid var(--color-danger);
}
.missing-keys-section {
  margin-top: 16px;
}
.missing-keys-section h4 {
  margin: 0 0 8px;
  font-size: 14px;
  color: var(--color-text-primary);
}
.missing-keys-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.missing-key-tag {
  cursor: pointer;
}
.missing-value {
  color: var(--color-danger);
  font-style: italic;
}
.table-card {
  background: var(--color-bg-card);
}
</style>
