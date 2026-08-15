<template>
  <div class="config-package-page">
    <div class="page-header">
      <h2>配置包管理</h2>
      <p class="page-desc">系统配置导出、导入与版本管理</p>
    </div>

    <!-- 操作区 -->
    <el-card style="margin-bottom: 16px">
      <el-row :gutter="16">
        <el-col :span="8">
          <el-card shadow="hover" class="action-card" @click="exportConfig">
            <el-icon :size="32" color="#4a7c59"><Download /></el-icon>
            <h4>导出配置</h4>
            <p>导出当前系统配置为JSON文件</p>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card shadow="hover" class="action-card" @click="triggerImport">
            <el-icon :size="32" color="var(--color-primary)"><Upload /></el-icon>
            <h4>导入配置</h4>
            <p>从JSON文件恢复系统配置</p>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card shadow="hover" class="action-card" @click="resetConfig">
            <el-icon :size="32" color="var(--color-warning)"><RefreshRight /></el-icon>
            <h4>重置默认</h4>
            <p>恢复系统配置为出厂默认值</p>
          </el-card>
        </el-col>
      </el-row>
    </el-card>

    <!-- 外观主题 -->
    <el-card style="margin-bottom: 16px">
      <template #header>
        <span>外观主题</span>
      </template>
      <el-radio-group v-model="currentTheme" @change="applyTheme">
        <el-radio-button value="default">军绿</el-radio-button>
        <el-radio-button value="light">明亮</el-radio-button>
        <el-radio-button value="dark">深色</el-radio-button>
        <el-radio-button value="military">军旅</el-radio-button>
        <el-radio-button value="outdoor">户外</el-radio-button>
        <el-radio-button value="high-contrast">高对比</el-radio-button>
      </el-radio-group>
      <p class="theme-hint">主题实时切换并自动记忆，图表配色随主题联动。</p>
    </el-card>

    <!-- 配置列表 -->
    <el-card>
      <template #header>
        <span>当前系统配置</span>
        <el-button size="small" style="float: right" @click="loadConfig">
          <el-icon><Refresh /></el-icon> 刷新
        </el-button>
      </template>
      <el-table v-loading="loading" :data="configList" border stripe>
        <el-table-column prop="key" label="配置项" width="200" />
        <el-table-column prop="value" label="配置值" min-width="300">
          <template #default="{ row }">
            <span v-if="row.sensitive" style="color: var(--color-danger)">********</span>
            <span v-else>{{ row.value }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="说明" width="200" />
        <el-table-column label="操作" width="160">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click="editConfig(row as any)"
              >编辑</el-button
            >
            <el-button size="small" text type="danger" @click="deleteConfig(row as any)"
              >删除</el-button
            >
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 隐藏的文件上传 -->
    <input
      ref="fileInput"
      type="file"
      accept=".json"
      style="display: none"
      @change="handleFileImport"
    />

    <!-- 编辑对话框 -->
    <el-dialog
      :model-value="dialogVisible"
      title="编辑配置"
      width="500px"
      @update:model-value="dialogVisible = false"
    >
      <el-form v-if="editRow" :model="editRow" label-width="100px">
        <el-form-item label="配置项"><el-input :model-value="editRow.key" disabled /></el-form-item>
        <el-form-item label="配置值">
          <el-input v-if="!editRow.sensitive" v-model="editRow.value" />
          <el-input v-else v-model="editRow.value" type="password" show-password />
        </el-form-item>
        <el-form-item label="说明"><el-input v-model="editRow.description" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveConfig">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Download, Upload, RefreshRight, Refresh } from '@element-plus/icons-vue'
import { get, post, put, del } from '@/api/request'
import { useConfigStore } from '@/stores/config'

interface ConfigItem {
  key: string
  value: string
  description: string
  sensitive?: boolean
}

const loading = ref(false)

// ── 外观主题 ──
const configStore = useConfigStore()
const currentTheme = ref(configStore.theme || 'light')
const THEMES = ['default', 'light', 'dark', 'military', 'outdoor', 'high-contrast']

function applyTheme(t: string | number | boolean | undefined) {
  const theme = THEMES.includes(String(t)) ? String(t) : 'light'
  currentTheme.value = theme
  if (theme === 'default') {
    document.documentElement.removeAttribute('data-theme')
  } else {
    document.documentElement.setAttribute('data-theme', theme)
  }
  configStore.setTheme(theme)
}
const configList = ref<ConfigItem[]>([])
const dialogVisible = ref(false)
const editRow = ref<ConfigItem | null>(null)
const fileInput = ref<HTMLInputElement>()

const SENSITIVE_KEYS = ['SECRET_KEY', 'CSRF_SECRET_KEY', 'SMTP_PASSWORD', 'ENCRYPTION_KEY']

async function loadConfig() {
  loading.value = true
  try {
    const res = await get<any>('/system/config')
    // 兼容三种形态：旧扁平 {key:value} / 信封 data:{items,total} / 拦截器展开后的响应
    let payload: any = res ?? {}
    if (
      payload.data &&
      typeof payload.data === 'object' &&
      !Array.isArray(payload.data) &&
      Object.keys(payload.data).length > 0
    ) {
      payload = payload.data
    }
    if (payload.code !== undefined && payload.code !== 200 && !Array.isArray(payload.items)) {
      configList.value = []
      return
    }
    const items: any[] = Array.isArray(payload.items)
      ? payload.items
      : Object.entries(payload).map(([k, v]) => ({ key: k, value: v }))
    configList.value = items.map((it) => ({
      key: it.key,
      value: typeof it.value === 'string' ? it.value : JSON.stringify(it.value ?? ''),
      description: it.description || '',
      sensitive: SENSITIVE_KEYS.includes(it.key),
    }))
  } catch {
    configList.value = []
  } finally {
    loading.value = false
  }
}

function editConfig(row: ConfigItem) {
  editRow.value = { ...row }
  dialogVisible.value = true
}

async function saveConfig() {
  if (editRow.value) {
    try {
      // 后端批量更新端点契约：{ configs: [{ key, value }] }
      await put('/system/config', {
        configs: [{ key: editRow.value.key, value: editRow.value.value }],
      })
      ElMessage.success('已保存')
      dialogVisible.value = false
      loadConfig()
    } catch {
      ElMessage.error('保存失败')
    }
  }
}

async function deleteConfig(row: ConfigItem) {
  try {
    await ElMessageBox.confirm(
      `确定删除配置项 "${row.key}" 吗？删除后将回退使用系统默认值。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  try {
    await del(`/system/config/${encodeURIComponent(row.key)}`)
    ElMessage.success('配置已删除')
    loadConfig()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '删除失败')
  }
}

function exportConfig() {
  const data = JSON.stringify(
    Object.fromEntries(configList.value.map((c) => [c.key, c.value])),
    null,
    2
  )
  const blob = new Blob([data], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `system-config-${new Date().toISOString().slice(0, 10)}.json`
  a.click()
  URL.revokeObjectURL(url)
  ElMessage.success('配置已导出')
}

function triggerImport() {
  fileInput.value?.click()
}

async function handleFileImport(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  try {
    const text = await file.text()
    JSON.parse(text) // 先本地校验格式，避免把坏文件发给后端
    // 后端导入端点契约：{ data: "<JSON字符串>" }
    await post('/system/config/import/json', { data: text })
    ElMessage.success('配置已导入')
    loadConfig()
  } catch {
    ElMessage.error('导入失败，请检查文件格式')
  }
}

async function resetConfig() {
  try {
    await ElMessageBox.confirm('确认恢复为默认配置？此操作不可撤销。', '警告', {
      type: 'warning',
    })
    const defaults: any = await get('/system/config/defaults')
    const items = defaults?.data || defaults || {}
    const entries = Object.entries(items).map(([key, value]) => ({ key, value: String(value) }))
    if (entries.length > 0) {
      await put('/system/config', { configs: entries })
    }
    ElMessage.success('已恢复默认配置')
    loadConfig()
  } catch {
    /* cancelled */
  }
}

loadConfig()

// 应用已保存主题（页面级兜底，全局由布局负责）
applyTheme(currentTheme.value)
</script>

<style scoped>
.page-header {
  margin-bottom: 20px;
}
.page-header h2 {
  font-size: 24px;
  font-weight: 700;
  color: #1a3c2a;
  margin: 0 0 4px 0;
}
.page-desc {
  color: #606266;
  font-size: 14px;
  margin: 0;
}
.action-card {
  cursor: pointer;
  text-align: center;
  padding: 20px;
  transition: transform 0.2s;
}
.action-card:hover {
  transform: translateY(-2px);
}
.action-card h4 {
  margin: 12px 0 4px;
  font-size: 16px;
}
.action-card p {
  color: #909399;
  font-size: 13px;
  margin: 0;
}
.theme-hint {
  color: #909399;
  font-size: 13px;
  margin-top: 8px;
}
</style>
