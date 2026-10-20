<template>
  <div class="consumption-page">
    <PageHeader
      title="消费帮扶台账"
      subtitle="登记农产品/畜禽/手工等消费帮扶采购记录，按年度与品类统计采购金额与覆盖村"
    >
      <div class="header-actions">
        <el-button type="primary" data-testid="create-btn" @click="openCreate">新建记录</el-button>
        <el-button :loading="exporting" data-testid="export-xlsx-btn" @click="exportData('xlsx')">
          导出 Excel
        </el-button>
        <el-button :loading="exporting" data-testid="export-csv-btn" @click="exportData('csv')">
          导出 CSV
        </el-button>
      </div>
    </PageHeader>

    <!-- 统计卡 -->
    <div v-loading="statsLoading" class="stats-row" data-testid="stats-row">
      <div class="stat-card">
        <div class="stat-value" data-testid="stat-total">
          {{ formatCurrency(stats.total_amount) }}
        </div>
        <div class="stat-label">年度采购总额</div>
      </div>
      <div class="stat-card">
        <div class="stat-value" data-testid="stat-count">{{ stats.record_count ?? 0 }}</div>
        <div class="stat-label">采购记录笔数</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">品类分布</div>
        <div class="stat-tags">
          <el-tag
            v-for="item in categoryStats"
            :key="item.label"
            :type="categoryTagType(item.category)"
            class="stat-tag"
            data-testid="category-stat"
          >
            {{ item.label }} {{ formatCurrency(item.amount) }}（{{ item.count }}）
          </el-tag>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-label">村分布</div>
        <div class="stat-tags">
          <el-tag
            v-for="item in villageStats"
            :key="item.label"
            type="info"
            class="stat-tag"
            data-testid="village-stat"
          >
            {{ item.label }} {{ formatCurrency(item.amount) }}（{{ item.count }}）
          </el-tag>
        </div>
      </div>
    </div>

    <!-- 筛选条 -->
    <el-card class="filter-card" shadow="never">
      <div class="filter-row">
        <el-select
          v-model="yearFilter"
          placeholder="年度"
          clearable
          class="filter-year"
          data-testid="filter-year"
          @change="handleYearChange"
        >
          <el-option v-for="year in YEAR_OPTIONS" :key="year" :label="`${year}年`" :value="year" />
        </el-select>
        <el-select
          v-model="categoryFilter"
          placeholder="品类"
          clearable
          class="filter-category"
          data-testid="filter-category"
        >
          <el-option
            v-for="(label, value) in CONSUMPTION_CATEGORY_LABELS"
            :key="value"
            :label="label"
            :value="value"
          />
        </el-select>
        <el-select
          v-model="villageFilter"
          placeholder="帮扶村"
          clearable
          class="filter-village"
          data-testid="filter-village"
        >
          <el-option
            v-for="opt in villageOptions"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
        <el-input
          v-model="keyword"
          placeholder="品名/采购方/供货方"
          clearable
          class="filter-keyword"
          data-testid="filter-keyword"
        />
        <el-button type="primary" data-testid="search-btn" @click="handleSearch">
          <el-icon><Search /></el-icon>
          查询
        </el-button>
        <el-button data-testid="reset-btn" @click="handleReset">
          <el-icon><Refresh /></el-icon>
          重置
        </el-button>
      </div>
    </el-card>

    <el-table v-loading="loading" :data="records" border stripe data-testid="record-table">
      <el-table-column prop="year" label="年度" width="90" align="center" />
      <el-table-column label="记录日期" width="120" align="center">
        <template #default="{ row }">{{ formatDateText(row.record_date) }}</template>
      </el-table-column>
      <el-table-column label="帮扶村" min-width="140">
        <template #default="{ row }">{{ row.village_name || '-' }}</template>
      </el-table-column>
      <el-table-column label="品类" width="100" align="center">
        <template #default="{ row }">
          <el-tag :type="categoryTagType(row.category)">{{ categoryLabel(row.category) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="item_name" label="品名" min-width="150" show-overflow-tooltip />
      <el-table-column label="数量" width="110" align="right">
        <template #default="{ row }">{{ quantityText(row) }}</template>
      </el-table-column>
      <el-table-column label="金额（元）" width="130" align="right">
        <template #default="{ row }">{{ formatCurrency(row.amount) }}</template>
      </el-table-column>
      <el-table-column label="采购方" min-width="140" show-overflow-tooltip>
        <template #default="{ row }">{{ row.buyer || '-' }}</template>
      </el-table-column>
      <el-table-column label="供货方" min-width="160">
        <template #default="{ row }">
          {{ row.seller || '-' }}
          <span v-if="row.seller_type" class="seller-type">
            （{{ sellerTypeLabel(row.seller_type) }}）
          </span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="130" fixed="right">
        <template #default="{ row }">
          <el-button text type="primary" data-testid="record-edit" @click="openEdit(row)">
            编辑
          </el-button>
          <el-button text type="danger" data-testid="record-delete" @click="handleDelete(row)">
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-if="total > 0"
      :current-page="page"
      :page-size="pageSize"
      :page-sizes="[20, 50, 100]"
      :total="total"
      layout="total, prev, pager, next, sizes"
      class="record-pagination"
      data-testid="record-pagination"
      @current-change="handlePageChange"
      @size-change="handlePageSizeChange"
    />

    <!-- 新建/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="editingId === null ? '新建消费帮扶记录' : '编辑消费帮扶记录'"
      :width="DIALOG_MD"
    >
      <el-form label-width="90px">
        <el-form-item label="年度" required>
          <el-select v-model="form.year" placeholder="选择年度">
            <el-option
              v-for="year in YEAR_OPTIONS"
              :key="year"
              :label="`${year}年`"
              :value="year"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="品类" required>
          <el-select v-model="form.category" placeholder="选择品类">
            <el-option
              v-for="(label, value) in CONSUMPTION_CATEGORY_LABELS"
              :key="value"
              :label="label"
              :value="value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="帮扶村">
          <el-select v-model="form.supported_village_id" placeholder="选择帮扶村" clearable>
            <el-option
              v-for="opt in villageOptions"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="品名" required>
          <el-input v-model="form.item_name" placeholder="如：土蜂蜜" />
        </el-form-item>
        <el-form-item label="数量">
          <el-input-number v-model="form.quantity" :min="0" :precision="2" />
        </el-form-item>
        <el-form-item label="单位">
          <el-input v-model="form.unit" placeholder="如：斤、箱" />
        </el-form-item>
        <el-form-item label="金额（元）" required>
          <el-input-number v-model="form.amount" :min="0" :precision="2" />
        </el-form-item>
        <el-form-item label="采购方">
          <el-input v-model="form.buyer" placeholder="采购单位" />
        </el-form-item>
        <el-form-item label="供货方">
          <el-input v-model="form.seller" placeholder="农户/合作社/企业名称" />
        </el-form-item>
        <el-form-item label="供货方类型">
          <el-select v-model="form.seller_type" placeholder="选择类型" clearable>
            <el-option
              v-for="(label, value) in CONSUMPTION_SELLER_TYPE_LABELS"
              :key="value"
              :label="label"
              :value="value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="记录日期">
          <el-date-picker
            v-model="form.record_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="选择日期"
          />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remarks" type="textarea" :rows="2" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" data-testid="record-save" @click="saveRecord">
          保存
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { DIALOG_MD } from '@/config/dialog'
import { formatCurrency, formatDateTime } from '@/utils'
import { getErrorMessage } from '@/utils/getErrorMessage'
import { getYearOptions } from '@/utils/yearOptions'
import { unwrapList } from '@/utils/unwrapList'
import { getSupportedVillages } from '@/api/supportedVillage'
import {
  CONSUMPTION_CATEGORY_LABELS,
  CONSUMPTION_SELLER_TYPE_LABELS,
  createConsumptionRecord,
  deleteConsumptionRecord,
  exportConsumption,
  getConsumptionRecords,
  getConsumptionStatistics,
  updateConsumptionRecord,
} from '@/api/consumption'
import type {
  ConsumptionCategory,
  ConsumptionExportFormat,
  ConsumptionQuery,
  ConsumptionRecord,
  ConsumptionRecordPayload,
  ConsumptionSellerType,
  ConsumptionStatistics,
} from '@/api/consumption'

import PageHeader from '@/components/common/PageHeader.vue'
import { Refresh, Search } from '@element-plus/icons-vue'
interface SelectOption {
  value: number
  label: string
}

const DEFAULT_PAGE_SIZE = 20
/** 年度下拉窗口：2021 ~ 当前年+10 */
const YEAR_OPTIONS = getYearOptions({ start: 2021 })
const CURRENT_YEAR = new Date().getFullYear()

// ── 列表与筛选 ──
const loading = ref(false)
const records = ref<ConsumptionRecord[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(DEFAULT_PAGE_SIZE)
const yearFilter = ref<number | null>(CURRENT_YEAR)
const categoryFilter = ref<ConsumptionCategory | ''>('')
const villageFilter = ref<number | null>(null)
const keyword = ref('')
const villageOptions = ref<SelectOption[]>([])

// ── 统计 ──
const statsLoading = ref(false)
const stats = ref<ConsumptionStatistics>({})

// ── 新建/编辑 ──
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const saving = ref(false)
const exporting = ref(false)
const form = reactive<{
  year: number
  category: ConsumptionCategory
  supported_village_id: number | null
  item_name: string
  quantity: number | null
  unit: string
  amount: number | null
  buyer: string
  seller: string
  seller_type: ConsumptionSellerType | ''
  record_date: string | null
  remarks: string
}>({
  year: CURRENT_YEAR,
  category: 'agriculture',
  supported_village_id: null,
  item_name: '',
  quantity: null,
  unit: '',
  amount: null,
  buyer: '',
  seller: '',
  seller_type: '',
  record_date: null,
  remarks: '',
})

/** 品类中文标签（未知值原样回显） */
function categoryLabel(category: string): string {
  return CONSUMPTION_CATEGORY_LABELS[category as ConsumptionCategory] ?? category
}

/** 品类标签颜色 */
function categoryTagType(category: string): 'success' | 'warning' | 'info' | 'danger' {
  const types: Record<string, 'success' | 'warning' | 'info' | 'danger'> = {
    agriculture: 'success',
    livestock: 'warning',
    handicraft: 'info',
    other: 'danger',
  }
  return types[category] ?? 'info'
}

/** 供货方类型标签（空值显示 -） */
function sellerTypeLabel(sellerType?: string | null): string {
  if (!sellerType) return '-'
  return CONSUMPTION_SELLER_TYPE_LABELS[sellerType as ConsumptionSellerType] ?? sellerType
}

/** 数量展示（数量+单位，缺数量显示 -） */
function quantityText(row: any): string {
  if (row.quantity === null || row.quantity === undefined) return '-'
  return `${row.quantity}${row.unit ?? ''}`
}

function formatDateText(value?: string | null): string {
  return formatDateTime(value, 'YYYY-MM-DD', '-')
}

/** 统计卡：品类分布（兼容 amount/total_amount 两种后端字段） */
const categoryStats = computed(() =>
  (stats.value.by_category ?? []).map((item) => ({
    category: item.category,
    label: categoryLabel(item.category),
    amount: item.amount ?? item.total_amount ?? 0,
    count: item.count ?? 0,
  }))
)

/** 统计卡：村分布（兼容 amount/total_amount 与 village 两种 id 字段） */
const villageStats = computed(() =>
  (stats.value.by_village ?? []).map((item) => ({
    label: item.village_name ?? `#${item.supported_village_id ?? item.village_id}`,
    amount: item.amount ?? item.total_amount ?? 0,
    count: item.count ?? 0,
  }))
)

/** 村下拉选项 */
async function loadVillageOptions(): Promise<void> {
  try {
    const res = await getSupportedVillages({ page: 1, page_size: 200 })
    villageOptions.value = unwrapList<any>(res).items.map((item) => ({
      value: Number(item.id),
      label: String(item.village_name ?? `#${item.id}`),
    }))
  } catch {
    // 村下拉是辅助筛选：失败不阻断台账浏览
  }
}

/** 构建列表查询参数 */
function buildQuery(): ConsumptionQuery {
  const query: ConsumptionQuery = { page: page.value, page_size: pageSize.value }
  if (yearFilter.value !== null) query.year = yearFilter.value
  if (categoryFilter.value) query.category = categoryFilter.value
  if (villageFilter.value !== null) query.village_id = villageFilter.value
  if (keyword.value.trim()) query.keyword = keyword.value.trim()
  return query
}

/** 加载台账列表 */
async function loadRecords(): Promise<void> {
  loading.value = true
  try {
    const res = await getConsumptionRecords(buildQuery())
    const { items, total: count } = unwrapList<ConsumptionRecord>(res)
    records.value = items
    total.value = count
  } catch (err) {
    ElMessage.error(getErrorMessage(err, '加载消费帮扶台账失败'))
    records.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

/** 加载年度统计 */
async function loadStatistics(): Promise<void> {
  statsLoading.value = true
  try {
    stats.value = await getConsumptionStatistics(yearFilter.value)
  } catch (err) {
    ElMessage.error(getErrorMessage(err, '加载统计数据失败'))
    stats.value = {}
  } finally {
    statsLoading.value = false
  }
}

function handleSearch(): void {
  page.value = 1
  void loadRecords()
}

function handleReset(): void {
  yearFilter.value = CURRENT_YEAR
  categoryFilter.value = ''
  villageFilter.value = null
  keyword.value = ''
  page.value = 1
  void loadRecords()
  void loadStatistics()
}

/** 年度变化：列表与统计都按新年份刷新 */
function handleYearChange(): void {
  page.value = 1
  void loadRecords()
  void loadStatistics()
}

function handlePageChange(next: number): void {
  page.value = next
  void loadRecords()
}

function handlePageSizeChange(size: number): void {
  pageSize.value = size
  page.value = 1
  void loadRecords()
}

// ── 新建/编辑 ──
function resetForm(): void {
  form.year = CURRENT_YEAR
  form.category = 'agriculture'
  form.supported_village_id = null
  form.item_name = ''
  form.quantity = null
  form.unit = ''
  form.amount = null
  form.buyer = ''
  form.seller = ''
  form.seller_type = ''
  form.record_date = null
  form.remarks = ''
}

function openCreate(): void {
  editingId.value = null
  resetForm()
  dialogVisible.value = true
}

function openEdit(row: any): void {
  editingId.value = row.id
  form.year = row.year
  form.category = row.category
  form.supported_village_id = row.supported_village_id ?? null
  form.item_name = row.item_name
  form.quantity = row.quantity ?? null
  form.unit = row.unit ?? ''
  form.amount = row.amount ?? null
  form.buyer = row.buyer ?? ''
  form.seller = row.seller ?? ''
  form.seller_type = row.seller_type ?? ''
  form.record_date = row.record_date ?? null
  form.remarks = row.remarks ?? ''
  dialogVisible.value = true
}

/** 表单 → 提交载荷（可选文本统一空串转 null） */
function buildPayload(): ConsumptionRecordPayload {
  return {
    supported_village_id: form.supported_village_id,
    category: form.category,
    item_name: form.item_name.trim(),
    quantity: form.quantity,
    unit: form.unit || null,
    amount: Number(form.amount),
    buyer: form.buyer || null,
    seller: form.seller || null,
    seller_type: form.seller_type || null,
    year: form.year,
    record_date: form.record_date,
    remarks: form.remarks || null,
  }
}

async function saveRecord(): Promise<void> {
  if (!form.item_name.trim()) {
    ElMessage.error('请输入品名')
    return
  }
  if (form.amount === null || Number(form.amount) <= 0) {
    ElMessage.error('请输入正确的金额')
    return
  }
  saving.value = true
  try {
    if (editingId.value === null) {
      await createConsumptionRecord(buildPayload())
      ElMessage.success('消费帮扶记录已创建')
    } else {
      await updateConsumptionRecord(editingId.value, buildPayload())
      ElMessage.success('消费帮扶记录已更新')
    }
    dialogVisible.value = false
    page.value = 1
    await loadRecords()
    await loadStatistics()
  } catch (err) {
    ElMessage.error(getErrorMessage(err, '保存失败'))
  } finally {
    saving.value = false
  }
}

// ── 删除 ──
async function handleDelete(row: any): Promise<void> {
  try {
    await ElMessageBox.confirm(`确定删除「${row.item_name}」这条消费帮扶记录吗？`, '删除确认', {
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await deleteConsumptionRecord(row.id)
    ElMessage.success('消费帮扶记录已删除')
    page.value = 1
    await loadRecords()
    await loadStatistics()
  } catch (err) {
    ElMessage.error(getErrorMessage(err, '删除失败'))
  }
}

// ── 导出 ──
async function exportData(format: ConsumptionExportFormat): Promise<void> {
  exporting.value = true
  try {
    await exportConsumption({
      format,
      year: yearFilter.value,
      category: categoryFilter.value,
      village_id: villageFilter.value,
      keyword: keyword.value.trim(),
    })
    ElMessage.success('导出任务已开始')
  } catch (err) {
    ElMessage.error(getErrorMessage(err, '导出台账失败'))
  } finally {
    exporting.value = false
  }
}

onMounted(() => {
  void loadVillageOptions()
  void loadRecords()
  void loadStatistics()
})
</script>

<style scoped lang="scss">
.consumption-page {
  padding: 20px;

  .page-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 16px;
  }

  .page-title {
    margin: 0;
    font-size: 20px;
    font-weight: 600;
    color: var(--color-primary-dark-1);
  }

  .page-desc {
    margin: 4px 0 0;
    font-size: 13px;
    color: var(--color-text-secondary);
  }

  .header-actions {
    display: flex;
    gap: 10px;
    align-items: center;
  }

  .stats-row {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 16px;
    margin-bottom: 16px;
  }

  .stat-card {
    background: var(--color-bg-card);
    border: 1px solid var(--color-border-light);
    border-radius: 8px;
    padding: 16px 20px;
    min-height: 84px;
  }

  .stat-value {
    font-size: 24px;
    font-weight: 700;
    color: var(--color-primary-dark-1);
    line-height: 1.3;
  }

  .stat-label {
    font-size: 13px;
    color: var(--color-text-secondary);
  }

  .stat-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 6px;
  }

  .stat-tag {
    max-width: 100%;
  }

  .filter-card {
    margin-bottom: 12px;
  }

  .filter-row {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    align-items: center;
  }

  .filter-year,
  .filter-category {
    width: 130px;
  }

  .filter-village {
    width: 170px;
  }

  .filter-keyword {
    width: 220px;
  }

  .seller-type {
    color: var(--color-text-secondary);
    font-size: 12px;
  }

  .record-pagination {
    margin-top: 16px;
    justify-content: flex-end;
  }
}
</style>
