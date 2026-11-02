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
        title="按组织树选择单位：父级配置的模块会被下级继承，下级只需配置差异；「不开放」会显式压住继承。"
        description="四态：继承=沿用上级（未配置则不开放）；可操作=可见且可写；只读=可见但写接口 403；不开放=显式禁用（菜单不下发）。"
      />

      <div class="toolbar">
        <!-- 主路径：组织树（名称/编码可搜索，默认展开根节点） -->
        <template v-if="!manualMode">
          <el-input
            :model-value="searchText"
            placeholder="搜索名称/编码"
            class="search-input"
            data-testid="org-grant-search"
            @update:model-value="onSearch"
          />
          <el-tree
            :data="visibleTree"
            node-key="id"
            :props="treeProps"
            :default-expanded-keys="[treeRootId]"
            highlight-current
            class="org-tree"
            data-testid="org-grant-tree"
            @node-click="onTreeSelect"
          />
        </template>
        <!-- 兜底：手工输入数字 ID（组织树加载失败 / 自动化脚本） -->
        <el-input
          v-else
          :model-value="orgIdText"
          placeholder="单位 ID（数字）"
          class="org-input"
          data-testid="org-grant-org-input"
          @update:model-value="onOrgIdInput"
        />
        <el-button link type="primary" data-testid="org-grant-toggle-manual" @click="toggleManual">
          {{ manualMode ? '改用组织树' : '手工输入 ID' }}
        </el-button>
        <el-button type="primary" :loading="loading" @click="load">加载</el-button>
        <el-button :disabled="!meta" :loading="saving" @click="save">保存矩阵</el-button>
        <el-button :disabled="!meta" @click="exportPkg">导出授权包</el-button>
        <el-button :disabled="!meta" @click="exportBranch">导出本子树</el-button>
      </div>

      <el-alert
        v-if="treeLoadFailed"
        class="feedback"
        type="warning"
        :closable="false"
        show-icon
        title="未能加载组织树，可点「手工输入 ID」后直接填写数字 ID"
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
          <span class="hint" data-testid="org-grant-row-hint">{{ row.effectiveLabel }}</span>
          <el-select v-model="row.state" class="level">
            <el-option label="继承" value="inherit" />
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
 * 单位授权配置（R33/R48，上级单位）。
 *
 * 上级在组织树上选单位，按「模块 × 四态」配置显式覆盖；未配置的模块继承上级
 * （与 effective_grant_service 的裁决完全一致）。保存后可按单位导出单包，
 * 或「导出本子树」由服务端把每个单位的**有效矩阵**分别打成 v1 包再合并为 zip。
 *
 * 四态之所以必要：引入继承后「缺失」等于「继承」，不能再拿它表示「不开放」；
 * 显式 none 必须被提交，否则下级无法压住父级下发的可写权限。
 */
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  exportGrantBranch,
  exportGrantPackage,
  getOrgGrantTree,
  getOrgGrants,
  setOrgGrants,
  type GrantLevel,
  type OrgGrantMatrix,
  type OrgGrantTreeNode,
} from '@/api/orgGrants'
import { useMenuStore } from '@/stores/menu'

/** 行状态：inherit=沿用上级；其余为显式覆盖 */
type RowState = 'inherit' | GrantLevel

interface MatrixRow {
  key: string
  label: string
  state: RowState
  /** 继承来的有效值说明；显式覆盖时为空串 */
  effectiveLabel: string
}

interface TreeItem {
  id: number
  label: string
  children: TreeItem[]
}

const menuStore = useMenuStore()

const treeProps = { label: 'label', children: 'children' }
const searchText = ref('')
const treeRootId = ref(0)
const treeData = ref<TreeItem[]>([])
const treeLoadFailed = ref(false)
const orgIdText = ref('')
const manualMode = ref(false)
const loading = ref(false)
const saving = ref(false)
const meta = ref<OrgGrantMatrix | null>(null)
const rows = ref<MatrixRow[]>([])
const errorMsg = ref('')

/** 组织树节点 → 带「名称（编码）」标签的树数据；编码缺失时只显示名称 */
function buildTreeItem(node: OrgGrantTreeNode): TreeItem {
  const name = String(node?.name ?? '').trim() || '未命名单位'
  const code = String(node?.code ?? '').trim()
  const children = Array.isArray(node?.children) ? node.children : []
  return {
    id: Number(node?.id),
    label: code ? `${name}（${code}）` : name,
    children: children.map((child) => buildTreeItem(child)),
  }
}

/** 名称/编码过滤：命中的节点连同其祖先一起保留；空关键字返回原树 */
function filterTree(nodes: TreeItem[], keyword: string): TreeItem[] {
  const kw = keyword.trim().toLowerCase()
  if (!kw) return nodes
  const out: TreeItem[] = []
  for (const node of nodes) {
    const children = filterTree(node.children, keyword)
    if (node.label.toLowerCase().includes(kw) || children.length > 0) {
      out.push({ ...node, children })
    }
  }
  return out
}

const visibleTree = computed(() => filterTree(treeData.value, searchText.value))

/** 拉取组织树（后端按调用者子树过滤，与 assert_org_reachable 同口径） */
async function loadTree(): Promise<void> {
  try {
    const data = await getOrgGrantTree()
    if (!data || !data.node) {
      treeData.value = []
      treeLoadFailed.value = true
      return
    }
    treeRootId.value = Number(data.root_id) || 0
    treeData.value = [buildTreeItem(data.node)]
    treeLoadFailed.value = false
  } catch {
    treeData.value = []
    treeLoadFailed.value = true
  }
}

onMounted(() => {
  void loadTree()
})

/** 选择树节点：写入 ID 并清空上一个单位的矩阵，避免把 A 的矩阵存到 B 名下 */
function onTreeSelect(item: TreeItem): void {
  orgIdText.value = String(item.id)
  meta.value = null
  rows.value = []
  errorMsg.value = ''
  void load()
}

function onSearch(value: string): void {
  searchText.value = String(value ?? '')
}

/** 输入框只收数字，空串表示未填 */
function onOrgIdInput(value: string | null): void {
  orgIdText.value = String(value ?? '').trim()
}

/** 切换「组织树 / 手工输入 ID」；切到手工时若当前值非正整数则清空，避免误操作 */
function toggleManual(): void {
  manualMode.value = !manualMode.value
  if (manualMode.value && !parseOrgId()) orgIdText.value = ''
  errorMsg.value = ''
}

/** 统一的错误文案：后端 detail → Error.message → 兜底 */
function errText(e: any): string {
  return e?.response?.data?.detail || e?.message || '操作失败'
}

function parseOrgId(): number {
  const parsed = Number(orgIdText.value)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : 0
}

function levelLabel(level: string): string {
  if (level === 'edit') return '可操作'
  if (level === 'view') return '只读'
  return '不开放'
}

/**
 * 菜单项与显式/有效矩阵的 key 取并集：
 * - 未显式配置 → inherit（显示继承来的有效值+来源）；
 * - 显式配置 → 对应级别（含显式 none）。
 */
function buildRows(data: Pick<OrgGrantMatrix, 'grants' | 'effective' | 'sources'>): MatrixRow[] {
  const grants = data.grants || {}
  const effective = data.effective || {}
  const sources = data.sources || {}
  const seen = new Set<string>()
  const out: MatrixRow[] = []
  const push = (key: string, label: string): void => {
    if (seen.has(key)) return
    seen.add(key)
    const explicit = grants[key]
    const effLabel = levelLabel(effective[key] ?? 'none')
    const source = sources[key]
    out.push({
      key,
      label,
      state: explicit ?? 'inherit',
      effectiveLabel:
        explicit === undefined
          ? source
            ? `继承：${effLabel}（来自 ${source}）`
            : `继承：${effLabel}`
          : '',
    })
  }
  for (const entry of menuStore.flatEntries) push(entry.key, entry.label)
  for (const key of Object.keys(grants)) push(key, key)
  for (const key of Object.keys(effective)) push(key, key)
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
    rows.value = buildRows(data)
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
    // 显式覆盖（含 none）才能真正压住继承；inherit 不提交，交给服务端裁决
    const grants: Record<string, GrantLevel> = {}
    for (const row of rows.value) {
      if (row.state !== 'inherit') grants[row.key] = row.state
    }
    const result = await setOrgGrants(orgId, grants)
    if (meta.value) meta.value.grant_version = result.grant_version
    errorMsg.value = ''
    ElMessage.success('授权矩阵已保存')
    // 保存后重新拉取：继承来的 effective/sources 会随父级变化，必须刷新
    if (meta.value) await load()
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

async function exportBranch(): Promise<void> {
  const orgId = parseOrgId()
  if (!orgId) {
    errorMsg.value = '请先填写有效的单位 ID'
    return
  }
  try {
    const filename = await exportGrantBranch(orgId)
    errorMsg.value = ''
    ElMessage.success('已导出发子树授权包 ' + filename)
  } catch (e: any) {
    errorMsg.value = errText(e)
  }
}

// 供单测驱动（jsdom 下 el-tree/el-select 的交互不稳定），生产无副作用
defineExpose({
  load,
  save,
  exportPkg,
  exportBranch,
  loadTree,
  onTreeSelect,
  onSearch,
  onOrgIdInput,
  toggleManual,
  buildRows,
  levelLabel,
  orgIdText,
  manualMode,
  meta,
  rows,
  treeData,
  treeLoadFailed,
  visibleTree,
  searchText,
  treeRootId,
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
  align-items: flex-start;
  margin: 16px 0;
}
.search-input {
  width: 200px;
}
.org-tree {
  min-width: 260px;
  max-height: 240px;
  overflow: auto;
  padding: 4px 8px;
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
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
.hint {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
.level {
  width: 120px;
}
</style>
