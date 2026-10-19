<template>
  <div class="org-grant">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>单位授权配置</span>
          <el-tag type="info" size="small">上级单位</el-tag>
        </div>
      </template>

      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="按单位为粒度配置「模块 × 级别」，保存后导出授权包，经离线介质下发给下级导入。"
        description="级别：可操作=可见且可写；只读=可见但写接口 403；不开放=菜单不下发。"
      />

      <div class="toolbar">
        <el-input
          :model-value="orgIdText"
          placeholder="单位 ID"
          class="org-input"
          @update:model-value="onOrgIdInput"
        />
        <el-button type="primary" :loading="loading" @click="load">加载</el-button>
        <el-button :disabled="!meta" :loading="saving" @click="save">保存矩阵</el-button>
        <el-button :disabled="!meta" @click="exportPkg">导出授权包</el-button>
      </div>

      <el-alert
        v-if="errorMsg"
        class="feedback"
        type="error"
        :closable="false"
        show-icon
        :title="errorMsg"
      />

      <el-descriptions v-if="meta" class="feedback" :column="2" border>
        <el-descriptions-item label="单位编码">{{
          meta.org_code || '（未填写）'
        }}</el-descriptions-item>
        <el-descriptions-item label="授权版本">{{ meta.grant_version }}</el-descriptions-item>
        <el-descriptions-item label="授权来源">{{
          meta.grant_source || '未授权'
        }}</el-descriptions-item>
        <el-descriptions-item label="签名校验">
          <el-tag :type="meta.signed ? 'success' : 'info'" size="small">
            {{ meta.signed ? '已签名' : '未签名' }}
          </el-tag>
        </el-descriptions-item>
      </el-descriptions>

      <div v-if="meta" class="matrix">
        <div v-for="row in rows" :key="row.key" class="row">
          <span class="label" :title="row.key">{{ row.label }}</span>
          <el-select v-model="row.level" class="level">
            <el-option label="可操作" value="edit" />
            <el-option label="只读" value="view" />
            <el-option label="不开放" value="none" />
          </el-select>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
/**
 * 单位授权配置（R33，上级单位）。
 *
 * 上级按单位为粒度配置「模块 × 级别」，保存后导出授权包，经离线介质下发给下级；
 * 下级导入后只读执行（本页在下级侧没有意义，故仅在上级使用）。
 *
 * 模块清单来自全局菜单 store（应用启动时已加载），并与当前授权矩阵取并集 ——
 * 这样即使菜单尚未加载完，已授权的模块也不会从界面上消失。
 */
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  exportGrantPackage,
  getOrgGrants,
  setOrgGrants,
  type GrantLevel,
  type OrgGrantMatrix,
} from '@/api/orgGrants'
import { useMenuStore } from '@/stores/menu'

interface MatrixRow {
  key: string
  label: string
  level: GrantLevel
}

const menuStore = useMenuStore()

const orgIdText = ref('')
const loading = ref(false)
const saving = ref(false)
const meta = ref<OrgGrantMatrix | null>(null)
const rows = ref<MatrixRow[]>([])
const errorMsg = ref('')

/** 输入框只收数字，空串表示未填 */
function onOrgIdInput(value: string): void {
  orgIdText.value = String(value ?? '').trim()
}

/** 统一的错误文案：后端 detail → Error.message → 兜底 */
function errText(e: any): string {
  return e?.response?.data?.detail || e?.message || '操作失败'
}

function parseOrgId(): number {
  const parsed = Number(orgIdText.value)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : 0
}

/** 菜单项与已授权 key 取并集，保证未在菜单里的授权模块仍可见可改 */
function buildRows(grants: Record<string, GrantLevel>): MatrixRow[] {
  const seen = new Set<string>()
  const out: MatrixRow[] = []
  for (const entry of menuStore.flatEntries) {
    if (seen.has(entry.key)) continue
    seen.add(entry.key)
    out.push({ key: entry.key, label: entry.label, level: grants[entry.key] ?? 'none' })
  }
  for (const key of Object.keys(grants)) {
    if (seen.has(key)) continue
    seen.add(key)
    out.push({ key, label: key, level: grants[key] })
  }
  return out
}

async function load(): Promise<void> {
  const orgId = parseOrgId()
  if (!orgId) {
    errorMsg.value = '请先填写有效的单位 ID'
    return
  }
  loading.value = true
  try {
    const data = await getOrgGrants(orgId)
    meta.value = data
    rows.value = buildRows(data.grants || {})
    errorMsg.value = ''
  } catch (e: any) {
    meta.value = null
    rows.value = []
    errorMsg.value = errText(e)
  } finally {
    loading.value = false
  }
}

async function save(): Promise<void> {
  const orgId = parseOrgId()
  if (!orgId) {
    errorMsg.value = '请先填写有效的单位 ID'
    return
  }
  saving.value = true
  try {
    // 只提交非 none 的模块：应用语义是"替换"，缺失即等于不开放
    const grants: Record<string, GrantLevel> = {}
    for (const row of rows.value) {
      if (row.level !== 'none') grants[row.key] = row.level
    }
    const result = await setOrgGrants(orgId, grants)
    if (meta.value) meta.value.grant_version = result.grant_version
    errorMsg.value = ''
    ElMessage.success('授权矩阵已保存')
  } catch (e: any) {
    errorMsg.value = errText(e)
  } finally {
    saving.value = false
  }
}

async function exportPkg(): Promise<void> {
  const orgId = parseOrgId()
  if (!orgId) {
    errorMsg.value = '请先填写有效的单位 ID'
    return
  }
  try {
    const filename = await exportGrantPackage(orgId)
    errorMsg.value = ''
    ElMessage.success('已导出 ' + filename)
  } catch (e: any) {
    errorMsg.value = errText(e)
  }
}

// 供单测驱动（jsdom 下 el-select 的交互不稳定），生产无副作用
defineExpose({ load, save, exportPkg, onOrgIdInput, buildRows })
</script>

<style scoped>
.org-grant {
  padding: 16px;
}
.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
}
.toolbar {
  display: flex;
  gap: 8px;
  align-items: center;
  margin: 16px 0;
}
.org-input {
  width: 160px;
}
.feedback {
  margin-top: 16px;
}
.matrix {
  margin-top: 16px;
  max-height: 480px;
  overflow: auto;
}
.row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 4px 0;
}
.label {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.level {
  width: 120px;
}
</style>
