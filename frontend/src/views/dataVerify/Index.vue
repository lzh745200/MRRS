<template>
  <div class="data-verify-page">
    <div class="page-header">
      <div>
        <h2 class="page-title">数据校验</h2>
        <p class="page-desc">
          校验执行 / 规则管理 / 字段说明
          三合一：一键查出问题数据、按规则维护校验策略、查阅字段中文说明
        </p>
      </div>
    </div>

    <!-- 页内 Tab（不依赖 el-tabs，便于键盘/测试与打印） -->
    <div class="dv-tabs" role="tablist">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        type="button"
        role="tab"
        class="dv-tab"
        :class="{ 'is-active': activeTab === tab.key }"
        :aria-selected="activeTab === tab.key"
        @click="switchTab(tab.key)"
      >
        {{ tab.label }}
      </button>
    </div>

    <!-- ① 校验执行 -->
    <section v-if="activeTab === 'verify'" class="dv-panel">
      <div class="dv-toolbar">
        <label class="dv-field">
          <span class="dv-field-label">校验模块</span>
          <select v-model="module" class="dv-input" @change="onModuleChange">
            <option v-for="m in moduleOptions" :key="m.value" :value="m.value">
              {{ m.label }}
            </option>
          </select>
        </label>
        <label class="dv-field">
          <span class="dv-field-label">条件逻辑</span>
          <select v-model="logic" class="dv-input">
            <option value="and">全部满足（且）</option>
            <option value="or">任一满足（或）</option>
          </select>
        </label>
        <button type="button" class="dv-btn" @click="addCondition">+ 添加条件</button>
        <button type="button" class="dv-btn dv-btn-primary" :disabled="running" @click="runCheck">
          {{ running ? '校验中…' : '一键校验' }}
        </button>
        <button type="button" class="dv-btn" @click="resetCheck">重置</button>
        <button type="button" class="dv-btn" @click="exportIssues">导出问题清单</button>
      </div>

      <div v-if="conditions.length" class="dv-conditions">
        <div v-for="(cond, idx) in conditions" :key="idx" class="dv-condition-row">
          <select v-model="cond.field" class="dv-input dv-field-select">
            <option value="" disabled>选择字段</option>
            <option v-for="f in fields" :key="f.key" :value="f.key">
              {{ f.label }}（{{ f.key }}）
            </option>
          </select>
          <select v-model="cond.operator" class="dv-input dv-op-select">
            <option v-for="op in operatorOptions" :key="op.value" :value="op.value">
              {{ op.label }}
            </option>
          </select>
          <input
            v-if="needValue(cond.operator)"
            v-model="cond.value"
            class="dv-input dv-value-input"
            placeholder="比较值"
          />
          <button type="button" class="dv-btn dv-btn-danger" @click="removeCondition(idx)">
            删除
          </button>
        </div>
      </div>
      <p v-else class="dv-empty">
        请先添加至少一个校验条件（如：字段「帮扶村名称」为空 = 查出缺失项）
      </p>

      <div v-if="result" class="dv-result">
        <p class="dv-summary">
          共校验 <strong>{{ result.total ?? 0 }}</strong> 条，满足条件
          <strong>{{ result.matched ?? 0 }}</strong> 条，问题记录
          <strong class="dv-danger-text">{{ issueRows.length }}</strong> 条
          <span v-if="result.message" class="dv-message">（{{ result.message }}）</span>
        </p>

        <table v-if="issueRows.length" class="dv-table">
          <thead>
            <tr>
              <th>记录ID</th>
              <th v-for="cond in submittedConditions" :key="cond.field">
                {{ fieldLabel(cond.field) }}
              </th>
              <th>状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in issueRows" :key="String(row.id)" class="dv-issue-row">
              <td>{{ row.id ?? '-' }}</td>
              <td v-for="cond in submittedConditions" :key="cond.field">
                {{ row.values?.[cond.field] ?? '-' }}
              </td>
              <td><span class="dv-tag dv-tag-danger">问题</span></td>
              <td>
                <button type="button" class="dv-link" @click="locateFix(row)">定位修复</button>
              </td>
            </tr>
          </tbody>
        </table>
        <p v-else class="dv-empty">未发现问题记录，数据通过当前条件校验 🎉</p>
      </div>
      <p v-else class="dv-empty">尚未执行校验。选择模块与条件后点击「一键校验」。</p>
    </section>

    <!-- ② 规则管理（原 RulesManagement 独立页逻辑，迁移为组件内嵌） -->
    <section v-else-if="activeTab === 'rules'" class="dv-panel">
      <RulesPanel />
    </section>

    <!-- ③ 字段说明（原 i18n 字段中文映射并入，只读） -->
    <section v-else class="dv-panel">
      <div class="dv-toolbar">
        <label class="dv-field">
          <span class="dv-field-label">字段所属模块</span>
          <select v-model="fieldsModule" class="dv-input" @change="loadFields">
            <option v-for="m in moduleOptions" :key="m.value" :value="m.value">
              {{ m.label }}
            </option>
          </select>
        </label>
        <span class="dv-hint"
          >字段中文名用于校验提示与导出表头；由后端 /validation/fields 提供。</span
        >
      </div>

      <div v-if="fieldsLoading" class="dv-empty">字段加载中…</div>
      <table v-else-if="fields.length" class="dv-table">
        <thead>
          <tr>
            <th>字段名（key）</th>
            <th>中文说明</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="f in fields" :key="f.key">
            <td>
              <code>{{ f.key }}</code>
            </td>
            <td>{{ f.label }}</td>
          </tr>
        </tbody>
      </table>
      <p v-else class="dv-empty">该模块暂无字段说明（加载失败或模块不支持）</p>

      <h3 class="dv-subtitle">校验规则类型说明</h3>
      <table class="dv-table">
        <thead>
          <tr>
            <th>规则类型</th>
            <th>中文名</th>
            <th>说明</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="rule in ruleDescriptions" :key="rule.type">
            <td>
              <code>{{ rule.type }}</code>
            </td>
            <td>{{ rule.label }}</td>
            <td>{{ rule.description }}</td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<script setup lang="ts">
/**
 * 数据校验合并页（W22）
 *
 * ① 校验执行：选模块 + 条件（字段/运算符/值 + 与或）→ 后端
 *    `/validation/query-check` 对存量数据做查询式校验 → 问题记录（不满足条件）
 *    可「定位修复」跳转对应详情页，可导出 CSV 问题清单。
 * ② 规则管理：原 `views/dataVerify/RulesManagement.vue` 独立页逻辑迁移为
 *    `components/RulesPanel.vue` 内嵌（独立路由删除，`/data-verify?tab=rules` 兼容）。
 * ③ 字段说明：后端 `/validation/fields` 的字段中文标签 + 规则类型静态说明
 *    （原「国际化」页的字段中文映射职能并入，不再依赖 i18n 页面）。
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { get, post } from '@/api/request'
import { useRouterSafe } from '@/composables/useRouterSafe'
import RulesPanel from './components/RulesPanel.vue'

/** 页内 Tab */
type TabKey = 'verify' | 'rules' | 'fields'

interface TabOption {
  key: TabKey
  label: string
}

interface ModuleOption {
  value: string
  label: string
}

interface FieldOption {
  key: string
  label: string
}

interface Condition {
  field: string
  operator: string
  value: string
}

interface QueryCheckRow {
  id?: number | null
  matched?: boolean
  values?: Record<string, string>
}

interface QueryCheckResult {
  module?: string
  logic?: string
  total?: number
  matched?: number
  unmatched?: number
  results: QueryCheckRow[]
  message?: string
}

const TABS: TabOption[] = [
  { key: 'verify', label: '校验执行' },
  { key: 'rules', label: '规则管理' },
  { key: 'fields', label: '字段说明' },
]

const MODULE_OPTIONS: ModuleOption[] = [
  { value: 'village', label: '帮扶村' },
  { value: 'school', label: '帮扶学校' },
  { value: 'project', label: '帮扶项目' },
  { value: 'fund', label: '经费管理' },
]

const OPERATOR_OPTIONS = [
  { value: 'eq', label: '等于' },
  { value: 'ne', label: '不等于' },
  { value: 'gt', label: '大于' },
  { value: 'gte', label: '大于等于' },
  { value: 'lt', label: '小于' },
  { value: 'lte', label: '小于等于' },
  { value: 'contains', label: '包含' },
  { value: 'not_contains', label: '不包含' },
  { value: 'empty', label: '为空' },
  { value: 'not_empty', label: '不为空' },
]

/** 规则类型说明（静态，只读；与后端 validation.py 支持类型一致） */
const RULE_DESCRIPTIONS = [
  { type: 'required', label: '非空检查', description: '字段值不能为空' },
  { type: 'positive', label: '正数', description: '字段值必须大于 0' },
  { type: 'non_negative', label: '非负数', description: '字段值必须大于等于 0' },
  { type: 'date_format', label: '日期格式', description: '符合 YYYY-MM-DD 日期格式' },
  { type: 'max_length', label: '最大长度', description: '字符串长度不超过 params.max' },
  { type: 'min_length', label: '最小长度', description: '字符串长度不小于 params.min' },
  { type: 'range', label: '数值范围', description: '数值位于 params.min~params.max 之间' },
  { type: 'regex', label: '正则匹配', description: '匹配 params.pattern 正则表达式' },
  { type: 'enum_values', label: '枚举值', description: '取值属于 params.values 枚举清单' },
  { type: 'cross_field', label: '跨字段逻辑', description: '与其他字段做大小/相等比较' },
]

/** 模块 → 详情/编辑路由前缀（「定位修复」跳转目标） */
const ROUTE_PREFIX: Record<string, string> = {
  village: '/supported-villages',
  school: '/schools',
  project: '/projects',
  fund: '/funds',
}

const route = useRoute()
const router = useRouter()
const { pushSafe } = useRouterSafe()

const tabs = TABS
const moduleOptions = MODULE_OPTIONS
const operatorOptions = OPERATOR_OPTIONS
const ruleDescriptions = RULE_DESCRIPTIONS

function resolveTab(value: unknown): TabKey {
  const matched = TABS.find((tab) => tab.key === value)
  return matched ? matched.key : 'verify'
}

const activeTab = ref<TabKey>(resolveTab(route.query.tab))
const module = ref('village')
const fieldsModule = ref('village')
const logic = ref<'and' | 'or'>('and')
const conditions = ref<Condition[]>([{ field: '', operator: 'not_empty', value: '' }])
const fields = ref<FieldOption[]>([])
const fieldsLoading = ref(false)
const running = ref(false)
const result = ref<QueryCheckResult | null>(null)
const submittedConditions = ref<Condition[]>([])

const issueRows = computed<QueryCheckRow[]>(() =>
  result.value ? result.value.results.filter((row) => row.matched !== true) : []
)

/** 字段中文名（字段说明未加载时回退字段 key） */
function fieldLabel(key: string): string {
  const matched = fields.value.find((field) => field.key === key)
  return matched ? matched.label : key
}

/** empty/not_empty 不需要比较值 */
function needValue(operator: string): boolean {
  return operator !== 'empty' && operator !== 'not_empty'
}

/** Tab 切换并同步到路由 query（?tab=rules 兼容旧独立规则页链接） */
function switchTab(key: TabKey): void {
  activeTab.value = key
  router.replace({ query: { ...route.query, tab: key } })
}

/** 字段说明/条件构建共用：按模块加载字段中文标签 */
async function loadFields(): Promise<void> {
  fieldsLoading.value = true
  try {
    const res: any = await get('/validation/fields', { module: fieldsModule.value })
    const data = res?.data ?? res ?? {}
    const list = Array.isArray(data) ? data : (data.fields ?? [])
    fields.value = Array.isArray(list) ? list : []
  } catch {
    fields.value = []
    ElMessage.error('字段说明加载失败')
  } finally {
    fieldsLoading.value = false
  }
}

/** 切换模块：条件与校验结果重置，字段清单重新加载 */
function onModuleChange(): void {
  fieldsModule.value = module.value
  conditions.value = [{ field: '', operator: 'not_empty', value: '' }]
  result.value = null
  submittedConditions.value = []
  void loadFields()
}

function addCondition(): void {
  conditions.value.push({ field: '', operator: 'not_empty', value: '' })
}

function removeCondition(index: number): void {
  conditions.value.splice(index, 1)
}

function resetCheck(): void {
  conditions.value = [{ field: '', operator: 'not_empty', value: '' }]
  result.value = null
  submittedConditions.value = []
}

/** 规整后端返回（兼容 {data:...} 信封与扁平结构、results 缺失） */
function normalizeResult(res: any): QueryCheckResult {
  const data = res?.data ?? res ?? {}
  const list = Array.isArray(data.results) ? data.results : []
  return {
    module: data.module,
    logic: data.logic,
    total: data.total,
    matched: data.matched,
    unmatched: data.unmatched,
    message: data.message,
    results: list,
  }
}

async function runCheck(): Promise<void> {
  const usable = conditions.value.filter((cond) => cond.field && cond.operator)
  if (usable.length === 0) {
    ElMessage.warning('请至少添加一个有效条件（字段 + 运算符）')
    return
  }
  running.value = true
  try {
    const res = await post('/validation/query-check', {
      module: module.value,
      conditions: usable,
      logic: logic.value,
      limit: 200,
    })
    result.value = normalizeResult(res)
    submittedConditions.value = usable
  } catch (error: any) {
    result.value = null
    ElMessage.error(error?.response?.data?.detail || '校验执行失败')
  } finally {
    running.value = false
  }
}

/** CSV 单元格转义（引号翻倍后整体加引号，兼容逗号/换行） */
function csvCell(value: unknown): string {
  return `"${String(value ?? '').replace(/"/g, '""')}"`
}

/** 导出问题清单（CSV，带 BOM，Excel 直接打开不乱码） */
function exportIssues(): void {
  if (issueRows.value.length === 0) {
    ElMessage.warning('当前没有问题记录可导出')
    return
  }
  const header = ['记录ID', ...submittedConditions.value.map((cond) => fieldLabel(cond.field))]
  const lines = [header.map(csvCell).join(',')]
  for (const row of issueRows.value) {
    const cells = [
      csvCell(row.id),
      ...submittedConditions.value.map((cond) => csvCell(row.values?.[cond.field])),
    ]
    lines.push(cells.join(','))
  }
  const blob = new Blob([`\ufeff${lines.join('\n')}`], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `数据校验问题清单_${new Date().toISOString().slice(0, 10)}.csv`
  link.click()
  URL.revokeObjectURL(url)
  ElMessage.success(`已导出 ${issueRows.value.length} 条问题记录`)
}

/** 定位修复：按模块跳转对应详情/编辑页 */
function locateFix(row: QueryCheckRow): void {
  // 模块选项与 ROUTE_PREFIX 一一对应，前缀必然存在
  const prefix = ROUTE_PREFIX[module.value] as string
  if (!row.id) {
    ElMessage.warning('该记录缺少唯一标识，无法定位')
    return
  }
  pushSafe(`${prefix}/${row.id}`)
}

watch(
  () => route.query.tab,
  (value) => {
    activeTab.value = resolveTab(value)
  }
)

onMounted(() => {
  void loadFields()
})
</script>

<style scoped>
.data-verify-page {
  padding: var(--spacing-lg, 20px);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md, 16px);
}

.page-title {
  margin: 0 0 4px;
  font-size: 20px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.page-desc {
  margin: 0;
  font-size: 13px;
  color: var(--color-text-secondary);
}

.dv-tabs {
  display: flex;
  gap: 8px;
  border-bottom: 1px solid var(--color-border-light);
}

.dv-tab {
  padding: 10px 18px;
  border: none;
  border-bottom: 2px solid transparent;
  background: transparent;
  color: var(--color-text-regular);
  font-size: 14px;
  cursor: pointer;
  transition: color 0.2s ease;
}

.dv-tab.is-active {
  color: var(--color-primary);
  border-bottom-color: var(--color-primary);
  font-weight: 600;
}

.dv-panel {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-height: 320px;
}

.dv-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 10px;
}

.dv-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.dv-field-label {
  font-size: 12px;
  color: var(--color-text-secondary);
}

.dv-input {
  height: 32px;
  padding: 0 10px;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  background: var(--color-bg-card);
  color: var(--color-text-primary);
  font-size: 13px;
}

.dv-btn {
  height: 32px;
  padding: 0 14px;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  background: var(--color-bg-card);
  color: var(--color-text-primary);
  font-size: 13px;
  cursor: pointer;
}

.dv-btn-primary {
  border-color: var(--color-primary);
  background: var(--color-primary);
  color: var(--color-text-inverse);
}

.dv-btn-danger {
  color: var(--color-danger);
  border-color: var(--color-danger-lightest);
}

.dv-conditions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.dv-condition-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.dv-field-select {
  min-width: 220px;
}

.dv-op-select {
  min-width: 120px;
}

.dv-value-input {
  min-width: 160px;
}

.dv-summary {
  margin: 0;
  font-size: 13px;
  color: var(--color-text-regular);
}

.dv-danger-text {
  color: var(--color-danger);
}

.dv-message {
  color: var(--color-text-secondary);
}

.dv-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.dv-table th,
.dv-table td {
  padding: 8px 10px;
  border-bottom: 1px solid var(--color-border-lighter);
  text-align: left;
  color: var(--color-text-regular);
}

.dv-table th {
  color: var(--color-text-secondary);
  font-weight: 600;
  background: var(--color-border-extra-light);
}

.dv-tag {
  display: inline-block;
  padding: 1px 8px;
  border-radius: 10px;
  font-size: 12px;
}

.dv-tag-danger {
  background: var(--color-danger-lightest);
  color: var(--color-danger);
}

.dv-link {
  padding: 0;
  border: none;
  background: transparent;
  color: var(--color-primary);
  font-size: 13px;
  cursor: pointer;
}

.dv-empty {
  margin: 0;
  padding: 26px 0;
  text-align: center;
  font-size: 13px;
  color: var(--color-text-placeholder);
}

.dv-hint {
  font-size: 12px;
  color: var(--color-text-placeholder);
}

.dv-subtitle {
  margin: 8px 0 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary);
}
</style>
