<template>
  <div class="handover-page">
    <div class="page-header">
      <h2>工作移交</h2>
      <el-button :loading="inventoryLoading" @click="loadAll">刷新</el-button>
    </div>

    <el-tabs v-model="activeTab" @tab-change="handleTabChange">
      <el-tab-pane label="发起移交" name="execute">
        <el-card v-loading="inventoryLoading" class="handover-card">
          <div class="inventory-total">
            可移交工作共 <strong>{{ inventory.total }}</strong> 项
            <span class="selected-total">已勾选 {{ selectedTotal }} 项</span>
          </div>

          <EmptyState v-if="inventory.total === 0" description="当前没有可移交的工作" />

          <template v-else>
            <div v-for="group in inventory.groups" :key="group.type" class="asset-group">
              <el-checkbox
                class="group-checkbox"
                :model-value="isGroupChecked(group)"
                :indeterminate="isGroupIndeterminate(group)"
                @change="toggleGroup(group, Boolean($event))"
              >
                {{ group.label }}（{{ group.count }}）
              </el-checkbox>
              <div v-for="item in group.items" :key="item.type + '-' + item.id" class="asset-item">
                <el-checkbox
                  :model-value="isItemSelected(item)"
                  @change="toggleItem(item, Boolean($event))"
                >
                  {{ item.title }}
                  <span v-if="item.subtitle" class="asset-subtitle">{{ item.subtitle }}</span>
                </el-checkbox>
              </div>
            </div>
          </template>
        </el-card>

        <el-card class="handover-card">
          <el-form label-width="90px">
            <el-form-item label="接任人">
              <el-select
                v-model="toUserId"
                filterable
                clearable
                placeholder="选择接任人"
                class="successor-select"
              >
                <el-option
                  v-for="candidate in candidates"
                  :key="candidate.id"
                  :label="candidateLabel(candidate)"
                  :value="candidate.id"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="移交备注">
              <el-input
                v-model="note"
                type="textarea"
                :rows="2"
                maxlength="500"
                placeholder="选填：轮岗原因 / 交接要求"
              />
            </el-form-item>
          </el-form>
          <div class="execute-actions">
            <el-button type="primary" :loading="submitting" @click="handleExecute">
              确认移交
            </el-button>
          </div>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="移交历史" name="history">
        <el-card v-loading="historyLoading" class="handover-card">
          <EmptyState v-if="historyItems.length === 0" description="暂无移交记录" />
          <template v-else>
            <el-table :data="historyItems" stripe>
              <el-table-column prop="record_no" label="交接单号" min-width="200" />
              <el-table-column label="交接双方" min-width="180">
                <template #default="{ row }">
                  {{ row.from_username }} → {{ row.to_username }}
                </template>
              </el-table-column>
              <el-table-column prop="total" label="项数" width="80" />
              <el-table-column prop="log_date" label="移交日期" width="120" />
              <el-table-column label="操作" width="130" fixed="right">
                <template #default="{ row }">
                  <el-button link type="primary" @click="exportReceipt(row as HandoverHistoryItem)">
                    导出交接单
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
            <el-pagination
              class="pager"
              background
              layout="total, prev, pager, next"
              :total="historyTotal"
              :current-page="historyQuery.page"
              :page-size="historyQuery.page_size"
              @current-change="handleHistoryPageChange"
            />
          </template>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="receiptVisible" title="工作交接单" width="760px">
      <div v-if="receipt" class="receipt">
        <div class="receipt-meta">
          <span>交接单号：{{ receipt.record_no }}</span>
          <span>移交人：{{ receipt.from_user?.username }}</span>
          <span>接任人：{{ receipt.to_user?.username }}</span>
          <span>移交时间：{{ receipt.created_at }}</span>
        </div>
        <div v-if="receipt.note" class="receipt-note">备注：{{ receipt.note }}</div>
        <el-table :data="receipt.items" stripe>
          <el-table-column label="资产类型" width="120">
            <template #default="{ row }">{{ assetTypeLabel(row.type) }}</template>
          </el-table-column>
          <el-table-column prop="title" label="名称" min-width="200" />
          <el-table-column label="归属角色" width="150">
            <template #default="{ row }">{{ roleLabel(row.role) }}</template>
          </el-table-column>
        </el-table>
      </div>
      <template #footer>
        <el-button @click="receiptVisible = false">关闭</el-button>
        <el-button type="primary" @click="exportReceipt(receipt)">导出交接单</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
/**
 * 工作移交页（w17-004）
 *
 * 流程：勾选「我负责/我发起」的资产 → 选择接任人 → 确认移交（不可撤销）→
 * 展示交接单并支持导出 PDF。历史页由后端 WorkLog 审计快照回放。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import EmptyState from '@/components/business/EmptyState/EmptyState.vue'
import {
  ASSET_ROLE_LABELS,
  ASSET_TYPE_LABELS,
  executeHandover,
  getHandoverCandidates,
  getHandoverHistory,
  getHandoverInventory,
} from '@/api/handover'
import type {
  HandoverAssetItem,
  HandoverAssetType,
  HandoverCandidate,
  HandoverGroup,
  HandoverHistoryItem,
  HandoverInventory,
  HandoverReceipt,
} from '@/api/handover'
import exportUtil from '@/utils/exportUtil'

const ASSET_TYPES: HandoverAssetType[] = ['village', 'project', 'todo', 'approval']

function emptyInventory(): HandoverInventory {
  return { groups: [], total: 0 }
}

function emptySelection(): Record<HandoverAssetType, number[]> {
  return { village: [], project: [], todo: [], approval: [] }
}

const activeTab = ref('execute')
const inventory = ref<HandoverInventory>(emptyInventory())
const inventoryLoading = ref(false)
const candidates = ref<HandoverCandidate[]>([])
const toUserId = ref<number | null>(null)
const note = ref('')
const submitting = ref(false)
const receipt = ref<HandoverReceipt | null>(null)
const receiptVisible = ref(false)

const historyItems = ref<HandoverHistoryItem[]>([])
const historyTotal = ref(0)
const historyLoading = ref(false)
const historyQuery = reactive({ page: 1, page_size: 10 })

const selection = ref<Record<HandoverAssetType, number[]>>(emptySelection())

const selectedTotal = computed(() =>
  ASSET_TYPES.reduce((sum, type) => sum + selection.value[type].length, 0)
)

/** 资产类型中文标签（未知类型原样返回，便于历史脏数据展示） */
function assetTypeLabel(type: string): string {
  return ASSET_TYPE_LABELS[type as HandoverAssetType] || type
}

/** 归属角色中文标签（空值显示 '-'） */
function roleLabel(role?: string | null): string {
  if (!role) return '-'
  return ASSET_ROLE_LABELS[role] || role
}

/** 接任人下拉文案：有姓名显示「姓名（账号）」 */
function candidateLabel(candidate: HandoverCandidate): string {
  return candidate.full_name
    ? candidate.full_name + '（' + candidate.username + '）'
    : candidate.username
}

function isItemSelected(item: HandoverAssetItem): boolean {
  return selection.value[item.type].includes(item.id)
}

function toggleItem(item: HandoverAssetItem, checked: boolean): void {
  const current = selection.value[item.type]
  selection.value[item.type] = checked
    ? [...current.filter((id) => id !== item.id), item.id]
    : current.filter((id) => id !== item.id)
}

function isGroupChecked(group: HandoverGroup): boolean {
  return group.items.length > 0 && group.items.every((item) => isItemSelected(item))
}

function isGroupIndeterminate(group: HandoverGroup): boolean {
  return !isGroupChecked(group) && group.items.some((item) => isItemSelected(item))
}

function toggleGroup(group: HandoverGroup, checked: boolean): void {
  selection.value[group.type] = checked ? group.items.map((item) => item.id) : []
}

async function loadInventory(): Promise<void> {
  inventoryLoading.value = true
  try {
    const data = await getHandoverInventory()
    inventory.value = data || emptyInventory()
    selection.value = emptySelection()
  } catch (error: any) {
    ElMessage.error(error?.userMessage || '加载可移交清单失败')
  } finally {
    inventoryLoading.value = false
  }
}

async function loadCandidates(): Promise<void> {
  try {
    const data = await getHandoverCandidates({ limit: 200 })
    candidates.value = data?.items || []
  } catch (error: any) {
    ElMessage.error(error?.userMessage || '加载接任人列表失败')
  }
}

async function loadHistory(): Promise<void> {
  historyLoading.value = true
  try {
    const data = await getHandoverHistory({
      page: historyQuery.page,
      page_size: historyQuery.page_size,
    })
    historyItems.value = data?.items || []
    historyTotal.value = data?.total || 0
  } catch (error: any) {
    ElMessage.error(error?.userMessage || '加载移交历史失败')
  } finally {
    historyLoading.value = false
  }
}

async function loadAll(): Promise<void> {
  await Promise.all([loadInventory(), loadCandidates()])
}

async function handleTabChange(name: string | number): Promise<void> {
  if (name === 'history') {
    await loadHistory()
  }
}

async function handleHistoryPageChange(page: number): Promise<void> {
  historyQuery.page = page
  await loadHistory()
}

function buildPayload(target: number) {
  const scope: HandoverAssetType[] = []
  const itemIds: Partial<Record<HandoverAssetType, number[]>> = {}
  for (const type of ASSET_TYPES) {
    const ids = selection.value[type]
    if (ids.length > 0) {
      scope.push(type)
      itemIds[type] = [...ids]
    }
  }
  return {
    to_user_id: target,
    scope,
    item_ids: itemIds,
    note: note.value.trim() || null,
  }
}

/** 导出交接单 PDF（即时交接单与历史记录共用） */
function exportReceipt(target: HandoverReceipt | HandoverHistoryItem | null): void {
  if (!target) return
  const rows = (target.items || []).map((item) => ({
    type: assetTypeLabel(item.type),
    title: item.title,
    role: roleLabel(item.role),
  }))
  const fromUsername =
    (target as HandoverReceipt).from_user?.username ||
    (target as HandoverHistoryItem).from_username ||
    '-'
  const toUsername =
    (target as HandoverReceipt).to_user?.username ||
    (target as HandoverHistoryItem).to_username ||
    '-'
  const recordNo = target.record_no || '未编号'
  exportUtil.exportToPDF(
    '工作交接单 ' + recordNo + '（' + fromUsername + ' → ' + toUsername + '）',
    rows,
    { type: '资产类型', title: '名称', role: '归属角色' }
  )
  ElMessage.success('交接单已生成')
}

async function handleExecute(): Promise<void> {
  if (selectedTotal.value === 0) {
    ElMessage.warning('请先勾选要移交的工作项')
    return
  }
  const target = toUserId.value
  if (!target) {
    ElMessage.warning('请选择接任人')
    return
  }
  try {
    await ElMessageBox.confirm(
      '确认将选中的 ' + selectedTotal.value + ' 项工作移交给该接任人？移交后不可撤销。',
      '确认工作移交',
      { type: 'warning', confirmButtonText: '确认移交', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  submitting.value = true
  try {
    const result = await executeHandover(buildPayload(target))
    receipt.value = result
    receiptVisible.value = true
    selection.value = emptySelection()
    note.value = ''
    toUserId.value = null
    await Promise.all([loadInventory(), loadHistory()])
    ElMessage.success('工作移交完成')
  } catch (error: any) {
    ElMessage.error(error?.userMessage || '工作移交失败')
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  loadAll()
})
</script>

<style scoped>
.handover-page {
  padding: 16px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.handover-card {
  margin-bottom: 16px;
}

.inventory-total {
  margin-bottom: 12px;
  color: var(--color-text-regular);
}

.selected-total {
  margin-left: 16px;
  color: var(--color-primary-dark-1);
  font-weight: 600;
}

.asset-group {
  margin-bottom: 12px;
  padding: 8px 12px;
  border: 1px solid var(--color-border-light);
  border-radius: 6px;
}

.group-checkbox {
  font-weight: 600;
}

.asset-item {
  padding-left: 24px;
}

.asset-subtitle {
  margin-left: 8px;
  color: var(--color-text-placeholder);
  font-size: 12px;
}

.successor-select {
  width: 320px;
}

.execute-actions {
  display: flex;
  justify-content: flex-end;
}

.receipt-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  margin-bottom: 12px;
  color: var(--color-text-regular);
}

.receipt-note {
  margin-bottom: 12px;
  color: var(--color-warning-dark);
}

.pager {
  margin-top: 12px;
  justify-content: flex-end;
}
</style>
