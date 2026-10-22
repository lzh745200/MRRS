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
        title="先在下方选择要授权的单位（可按名称/编码搜索），再按「模块 × 级别」配置；保存后导出授权包，经离线介质下发给下级导入。"
        description="级别：可操作=可见且可写；只读=可见但写接口 403；不开放=菜单不下发。"
      />

      <div class="toolbar">
        <!-- 主路径：单位选择器（名称/编码可搜索，内部仍用 organizations.id） -->
        <el-select
          v-if="!manualMode"
          :model-value="orgIdText"
          filterable
          clearable
          :loading="orgLoading"
          placeholder="选择单位（可按名称或编码搜索）"
          class="org-input"
          data-testid="org-grant-org-select"
          @update:model-value="onOrgSelect"
        >
          <el-option
            v-for="opt in orgOptions"
            :key="opt.id"
            :label="opt.label"
            :value="String(opt.id)"
          />
        </el-select>
        <!-- 兜底：手工输入数字 ID（老操作习惯 / 自动化脚本） -->
        <el-input
          v-else
          :model-value="orgIdText"
          placeholder="单位 ID（数字）"
          class="org-input"
          data-testid="org-grant-org-input"
          @update:model-value="onOrgIdInput"
        />
        <el-button link type="primary" data-testid="org-grant-toggle-manual" @click="toggleManual">
          {{ manualMode ? '改用单位选择' : '手工输入 ID' }}
        </el-button>
        <el-button type="primary" :loading="loading" @click="load">加载</el-button>
        <el-button :disabled="!meta" :loading="saving" @click="save">保存矩阵</el-button>
        <el-button :disabled="!meta" @click="exportPkg">导出授权包</el-button>
      </div>

      <el-alert
        v-if="orgLoadFailed"
        class="feedback"
        type="warning"
        :closable="false"
        show-icon
        title="未能加载单位列表，可点「手工输入 ID」后直接填写数字 ID"
        data-testid="org-grant-org-load-failed"
      />

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
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  exportGrantPackage,
  getOrgGrants,
  setOrgGrants,
  type GrantLevel,
  type OrgGrantMatrix,
} from '@/api/orgGrants'
import { getOrganizationTree } from '@/api/organization'
import { useMenuStore } from '@/stores/menu'

interface MatrixRow {
  key: string
  label: string
  level: GrantLevel
}

const menuStore = useMenuStore()

/** 单位下拉选项（树形拍平后带层级缩进） */
interface OrgOption {
  id: number
  label: string
}

const orgIdText = ref('')
/** 单位下拉数据；加载失败时置 orgLoadFailed 并提示改用手工输入 */
const orgOptions = ref<OrgOption[]>([])
const orgLoading = ref(false)
const orgLoadFailed = ref(false)
/** 手工输入数字 ID 的兜底模式（默认走单位选择器） */
const manualMode = ref(false)
const loading = ref(false)
const saving = ref(false)
const meta = ref<OrgGrantMatrix | null>(null)
const rows = ref<MatrixRow[]>([])
const errorMsg = ref('')

/** 输入框只收数字，空串表示未填 */
function onOrgIdInput(value: string): void {
  orgIdText.value = String(value ?? '').trim()
}

/** 把组织树拍平成「缩进名称（编码）」的下拉项；缺失字段做安全兜底 */
function flattenOrgs(nodes: any[], depth = 0): OrgOption[] {
  const out: OrgOption[] = []
  for (const node of Array.isArray(nodes) ? nodes : []) {
    const id = Number(node?.id)
    if (!Number.isInteger(id) || id <= 0) continue
    const name = String(node?.name ?? '').trim() || '未命名单位'
    const code = String(node?.code ?? '').trim()
    const label = '　'.repeat(depth) + (code ? name + '（' + code + '）' : name)
    out.push({ id, label })
    if (Array.isArray(node?.children) && node.children.length > 0) {
      out.push(...flattenOrgs(node.children, depth + 1))
    }
  }
  return out
}

/** 拉取可选单位（后端按调用者组织子树过滤，与 assert_org_reachable 口径一致） */
async function loadOrgOptions(): Promise<void> {
  orgLoading.value = true
  try {
    const tree = await getOrganizationTree()
    orgOptions.value = flattenOrgs(tree as any[])
    orgLoadFailed.value = orgOptions.value.length === 0
  } catch {
    orgOptions.value = []
    orgLoadFailed.value = true
  } finally {
    orgLoading.value = false
  }
}

/** 选择单位：写入 ID，并清空上一个单位的矩阵，避免把 A 的矩阵存到 B 名下 */
function onOrgSelect(value: string | number | null): void {
  orgIdText.value = value === null || value === undefined ? '' : String(value)
  meta.value = null
  rows.value = []
  errorMsg.value = ''
}

/** 切换「单位选择 / 手工输入 ID」；切到手工时若当前值非正整数则清空，避免误操作 */
function toggleManual(): void {
  manualMode.value = !manualMode.value
  if (manualMode.value && !parseOrgId()) orgIdText.value = ''
  errorMsg.value = ''
}

onMounted(() => {
  void loadOrgOptions()
})

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
defineExpose({
  load,
  save,
  exportPkg,
  onOrgIdInput,
  buildRows,
  loadOrgOptions,
  flattenOrgs,
  onOrgSelect,
  toggleManual,
})
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
