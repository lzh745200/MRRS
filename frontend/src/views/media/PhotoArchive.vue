<template>
  <div class="photo-archive-page">
    <PageHeader
      title="影像库"
      subtitle="按帮扶村/学校/项目归档现场影像，支持标签筛选、拍摄点多期对比与对比图导出"
    >
      <template #extra>
        <div class="header-actions">
          <el-upload
            :action="uploadAction"
            :headers="uploadHeaders"
            :show-file-list="false"
            :before-upload="beforeUpload"
            :on-success="handleUploadSuccess"
            :on-error="handleUploadError"
            accept="image/*"
            data-testid="photo-upload"
          >
            <el-button type="primary" :loading="uploading" data-testid="upload-btn">
              <el-icon><Upload /></el-icon>上传照片
            </el-button>
          </el-upload>
          <el-button :loading="loading" data-testid="refresh-btn" @click="loadPhotos"
            >刷新</el-button
          >
        </div>
      </template>
    </PageHeader>

    <!-- 筛选条 -->
    <el-card class="filter-card" shadow="never">
      <div class="filter-row">
        <el-select
          v-model="filters.village_id"
          placeholder="帮扶村"
          clearable
          class="filter-select"
          data-testid="filter-village"
        >
          <el-option
            v-for="opt in villageOptions"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
        <el-select
          v-model="filters.school_id"
          placeholder="帮扶学校"
          clearable
          class="filter-select"
          data-testid="filter-school"
        >
          <el-option
            v-for="opt in schoolOptions"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
        <el-select
          v-model="filters.project_id"
          placeholder="帮扶项目"
          clearable
          class="filter-select"
          data-testid="filter-project"
        >
          <el-option
            v-for="opt in projectOptions"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
        <el-input
          v-model="filters.tag"
          placeholder="标签"
          clearable
          class="filter-tag"
          data-testid="filter-tag"
        />
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          value-format="YYYY-MM-DD"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          class="filter-date"
          data-testid="filter-date"
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

    <!-- 多选工具条 -->
    <div class="selection-bar">
      <span class="selection-info" data-testid="selection-info">
        {{ selectedIds.length ? `已选 ${selectedIds.length} 张` : '勾选至少 2 张可生成对比图' }}
      </span>
      <el-button
        type="primary"
        :disabled="selectedIds.length < 2"
        :loading="compareLoading"
        data-testid="compare-btn"
        @click="openCompare"
      >
        生成对比图
      </el-button>
      <el-button
        v-if="selectedIds.length"
        data-testid="clear-selection-btn"
        @click="clearSelection"
      >
        清空选择
      </el-button>
    </div>

    <!-- 影像卡片网格 -->
    <div v-loading="loading" class="photo-grid-wrap">
      <el-empty
        v-if="!loading && photos.length === 0"
        description="暂无影像，请先上传照片归档"
        data-testid="photo-empty"
      />
      <div v-else class="photo-grid" data-testid="photo-grid">
        <el-card
          v-for="photo in photos"
          :key="photo.id"
          class="photo-card"
          shadow="never"
          data-testid="photo-card"
        >
          <div class="photo-card-head">
            <el-checkbox
              :model-value="selectedIds.includes(photo.id)"
              data-testid="photo-checkbox"
              @change="toggleSelect(photo.id)"
            />
            <span v-if="photo.tag" class="photo-tag">{{ photo.tag }}</span>
          </div>
          <div class="photo-thumb">
            <img :src="photo.file_url" :alt="photo.file_name || '影像'" loading="lazy" />
          </div>
          <div class="photo-meta">
            <div class="photo-time">拍摄：{{ formatTakenAt(photo.taken_at) }}</div>
            <div class="photo-object">{{ objectLabel(photo) }}</div>
            <div v-if="photo.spot_key" class="photo-spot">拍摄点：{{ photo.spot_key }}</div>
          </div>
          <div class="photo-actions">
            <el-button text type="primary" data-testid="photo-edit" @click="openEdit(photo)">
              编辑
            </el-button>
            <el-button text type="danger" data-testid="photo-delete" @click="handleDelete(photo)">
              删除
            </el-button>
          </div>
        </el-card>
      </div>
    </div>

    <el-pagination
      v-if="total > 0"
      :current-page="page"
      :page-size="pageSize"
      :page-sizes="[12, 24, 48]"
      :total="total"
      layout="total, prev, pager, next, sizes"
      class="photo-pagination"
      data-testid="photo-pagination"
      @current-change="handlePageChange"
      @size-change="handlePageSizeChange"
    />

    <!-- 拍摄点多期分组 -->
    <el-card v-if="spotGroups.length" class="spot-groups-card" shadow="never">
      <template #header>
        <span class="card-title">拍摄点多期归档</span>
      </template>
      <div class="spot-group-list" data-testid="spot-group-list">
        <div
          v-for="group in spotGroups"
          :key="group.key"
          class="spot-group"
          data-testid="spot-group"
        >
          <div class="spot-group-info">
            <div class="spot-group-key">{{ group.key }}</div>
            <div class="spot-group-count">共 {{ group.count }} 期</div>
          </div>
          <div class="spot-group-thumbs">
            <img
              v-for="item in group.items.slice(0, 3)"
              :key="item.id"
              :src="item.file_url"
              class="spot-thumb"
              :alt="item.file_name || '多期影像'"
            />
          </div>
          <el-button
            type="primary"
            link
            data-testid="spot-compare-btn"
            @click="openSpotCompare(group.key)"
          >
            多期对比
          </el-button>
        </div>
      </div>
    </el-card>

    <!-- 编辑归档信息 -->
    <el-dialog v-model="editVisible" title="编辑归档信息" :width="DIALOG_MD">
      <el-form label-width="90px">
        <el-form-item label="关联村">
          <el-select v-model="editForm.village_id" placeholder="选择帮扶村" clearable>
            <el-option
              v-for="opt in villageOptions"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="关联学校">
          <el-select v-model="editForm.school_id" placeholder="选择帮扶学校" clearable>
            <el-option
              v-for="opt in schoolOptions"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="关联项目">
          <el-select v-model="editForm.project_id" placeholder="选择帮扶项目" clearable>
            <el-option
              v-for="opt in projectOptions"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="标签">
          <el-input v-model="editForm.tag" placeholder="如：村容村貌、产业基地" />
        </el-form-item>
        <el-form-item label="拍摄点">
          <el-input v-model="editForm.spot_key" placeholder="同拍摄点标识，用于多期对比" />
        </el-form-item>
        <el-form-item label="拍摄时间">
          <el-date-picker
            v-model="editForm.taken_at"
            type="datetime"
            value-format="YYYY-MM-DDTHH:mm:ss"
            placeholder="选择拍摄时间"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" data-testid="edit-save" @click="saveEdit">
          保存
        </el-button>
      </template>
    </el-dialog>

    <!-- 对比图弹窗 -->
    <el-dialog v-model="compareVisible" title="影像对比图" :width="DIALOG_LG">
      <div v-if="compareSeries.length" class="compare-series" data-testid="compare-series">
        <div v-for="item in compareSeries" :key="item.id" class="compare-series-item">
          <img :src="item.file_url" class="compare-series-thumb" :alt="`多期影像 ${item.id}`" />
          <span class="compare-series-time">{{ formatTakenAt(item.taken_at) }}</span>
        </div>
      </div>
      <el-alert
        v-if="compareError"
        type="error"
        :title="compareError"
        :closable="false"
        data-testid="compare-error"
      />
      <div v-else class="compare-preview">
        <img
          v-if="compareUrl"
          :src="compareUrl"
          alt="影像对比图"
          class="compare-image"
          data-testid="compare-image"
        />
        <el-empty v-else description="正在生成对比图" data-testid="compare-pending" />
      </div>
      <template #footer>
        <el-button @click="closeCompare">关闭</el-button>
        <el-button
          type="primary"
          :disabled="!compareUrl"
          :loading="downloading"
          data-testid="compare-download"
          @click="downloadCompare"
        >
          下载对比图
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Upload, Refresh, Search } from '@element-plus/icons-vue'
import { DIALOG_LG, DIALOG_MD } from '@/config/dialog'
import { formatDateTime } from '@/utils'
import { unwrapList } from '@/utils/unwrapList'
import { getErrorMessage } from '@/utils/getErrorMessage'
import { useUploadHeaders } from '@/composables/useUploadHeaders'
import { getSupportedVillages } from '@/api/supportedVillage'
import { schoolsApi } from '@/api/schools'
import { projectsApi } from '@/api/projects'
import {
  createPhoto,
  deletePhoto,
  downloadCompareImage,
  generateCompareImage,
  getPhotoCompare,
  getPhotos,
  updatePhoto,
} from '@/api/media'
import type { PhotoArchive, PhotoArchiveQuery, PhotoCompareItem } from '@/api/media'
import PageHeader from '@/components/common/PageHeader.vue'

interface SelectOption {
  value: number
  label: string
}

/** 每页卡片数（12 的倍数便于 3 列网格） */
const DEFAULT_PAGE_SIZE = 12
/** 上传大小上限（与 /files/upload 后端限制一致） */
const MAX_UPLOAD_SIZE = 20 * 1024 * 1024

const uploadAction = `${import.meta.env.VITE_API_BASE_URL || '/api/v1'}/files/upload`
const { uploadHeaders, ensureCsrf } = useUploadHeaders()

// ── 列表与筛选 ──
const loading = ref(false)
const photos = ref<PhotoArchive[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(DEFAULT_PAGE_SIZE)
const filters = reactive<{
  village_id: number | null
  school_id: number | null
  project_id: number | null
  tag: string
}>({ village_id: null, school_id: null, project_id: null, tag: '' })
const dateRange = ref<[string, string] | null>(null)

// ── 下拉选项 ──
const villageOptions = ref<SelectOption[]>([])
const schoolOptions = ref<SelectOption[]>([])
const projectOptions = ref<SelectOption[]>([])

// ── 多选与对比图 ──
const selectedIds = ref<number[]>([])
const compareVisible = ref(false)
const compareLoading = ref(false)
const downloading = ref(false)
const compareUrl = ref('')
const compareError = ref('')
const compareSeries = ref<PhotoCompareItem[]>([])
const compareIds = ref<number[]>([])

// ── 上传/编辑 ──
const uploading = ref(false)
const saving = ref(false)
const editVisible = ref(false)
const editingId = ref<number | null>(null)
const editForm = reactive<{
  village_id: number | null
  school_id: number | null
  project_id: number | null
  tag: string
  spot_key: string
  taken_at: string | null
}>({ village_id: null, school_id: null, project_id: null, tag: '', spot_key: '', taken_at: null })

/** 表单格式化拍摄时间（空值显示 -） */
function formatTakenAt(value?: string | null): string {
  return formatDateTime(value, 'YYYY-MM-DD HH:mm', '-')
}

/** 归档对象展示：按 村 → 学校 → 项目 的顺序取第一个已关联对象 */
function objectLabel(photo: PhotoArchive): string {
  const targets: Array<[number | null | undefined, SelectOption[], string]> = [
    [photo.village_id, villageOptions.value, '村'],
    [photo.school_id, schoolOptions.value, '学校'],
    [photo.project_id, projectOptions.value, '项目'],
  ]
  for (const [id, options, prefix] of targets) {
    if (id === null || id === undefined) continue
    const hit = options.find((option) => option.value === id)
    return `${prefix}：${hit ? hit.label : `#${id}`}`
  }
  return '未关联'
}

/** 当前页按 spot_key 分组（仅展示带拍摄点的影像，多期对比入口） */
const spotGroups = computed(() => {
  const groups = new Map<string, PhotoArchive[]>()
  for (const photo of photos.value) {
    const key = (photo.spot_key ?? '').trim()
    if (!key) continue
    const list = groups.get(key)
    if (list) {
      list.push(photo)
    } else {
      groups.set(key, [photo])
    }
  }
  return Array.from(groups.entries()).map(([key, items]) => ({
    key,
    count: items.length,
    items,
  }))
})

/** 加载村/学校/项目下拉选项（失败不阻断影像列表） */
async function loadFilterOptions(): Promise<void> {
  try {
    const [villages, schools, projects] = await Promise.all([
      getSupportedVillages({ page: 1, page_size: 200 }),
      schoolsApi.list({ page: 1, page_size: 200 }),
      projectsApi.list({ page: 1, page_size: 200 }),
    ])
    villageOptions.value = unwrapList<any>(villages).items.map((item) => ({
      value: Number(item.id),
      label: String(item.village_name ?? `#${item.id}`),
    }))
    schoolOptions.value = unwrapList<any>(schools).items.map((item) => ({
      value: Number(item.id),
      label: String(item.name ?? `#${item.id}`),
    }))
    projectOptions.value = unwrapList<any>(projects).items.map((item) => ({
      value: Number(item.id),
      label: String(item.name ?? `#${item.id}`),
    }))
  } catch {
    // 下拉选项是辅助信息：失败时不阻断影像浏览
  }
}

/** 根据筛选条件构建查询参数（可选字段为空时不传） */
function buildQuery(): PhotoArchiveQuery {
  const query: PhotoArchiveQuery = { page: page.value, page_size: pageSize.value }
  if (filters.village_id !== null) query.village_id = filters.village_id
  if (filters.school_id !== null) query.school_id = filters.school_id
  if (filters.project_id !== null) query.project_id = filters.project_id
  if (filters.tag.trim()) query.tag = filters.tag.trim()
  if (dateRange.value) {
    query.date_from = dateRange.value[0]
    query.date_to = dateRange.value[1]
  }
  return query
}

/** 加载影像列表 */
async function loadPhotos(): Promise<void> {
  loading.value = true
  try {
    const res = await getPhotos(buildQuery())
    const { items, total: count } = unwrapList<PhotoArchive>(res)
    photos.value = items
    total.value = count
  } catch (err) {
    ElMessage.error(getErrorMessage(err, '加载影像列表失败'))
    photos.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function handleSearch(): void {
  page.value = 1
  void loadPhotos()
}

function handleReset(): void {
  filters.village_id = null
  filters.school_id = null
  filters.project_id = null
  filters.tag = ''
  dateRange.value = null
  page.value = 1
  void loadPhotos()
}

function handlePageChange(next: number): void {
  page.value = next
  void loadPhotos()
}

function handlePageSizeChange(size: number): void {
  pageSize.value = size
  page.value = 1
  void loadPhotos()
}

// ── 多选 ──
function toggleSelect(id: number): void {
  const index = selectedIds.value.indexOf(id)
  if (index >= 0) {
    selectedIds.value.splice(index, 1)
  } else {
    selectedIds.value.push(id)
  }
}

function clearSelection(): void {
  selectedIds.value = []
}

// ── 上传归档 ──
async function beforeUpload(file: File): Promise<boolean> {
  if (!file.type.startsWith('image/')) {
    ElMessage.error('只能上传图片文件')
    return false
  }
  if (file.size > MAX_UPLOAD_SIZE) {
    ElMessage.error('图片大小不能超过 20MB')
    return false
  }
  await ensureCsrf()
  uploading.value = true
  return true
}

function handleUploadSuccess(response: any, file: any): void {
  const url = response?.data?.url ?? response?.url
  if (!url) {
    uploading.value = false
    ElMessage.error('上传响应缺少文件地址')
    return
  }
  void createArchiveFromUpload(String(url), file)
}

/** 上传成功后注册归档记录（关联当前筛选对象，便于归档后立即在列表中看到） */
async function createArchiveFromUpload(url: string, file: any): Promise<void> {
  try {
    await createPhoto({
      file_url: url,
      file_name: file?.name,
      file_size: file?.size,
      mime_type: file?.raw?.type ?? file?.type,
      village_id: filters.village_id,
      school_id: filters.school_id,
      project_id: filters.project_id,
      tag: filters.tag.trim() || null,
    })
    ElMessage.success('影像已归档')
    page.value = 1
    await loadPhotos()
  } catch (err) {
    ElMessage.error(getErrorMessage(err, '影像归档失败'))
  } finally {
    uploading.value = false
  }
}

function handleUploadError(): void {
  uploading.value = false
  ElMessage.error('上传失败，请重试')
}

// ── 编辑 ──
function openEdit(photo: PhotoArchive): void {
  editingId.value = photo.id
  editForm.village_id = photo.village_id ?? null
  editForm.school_id = photo.school_id ?? null
  editForm.project_id = photo.project_id ?? null
  editForm.tag = photo.tag ?? ''
  editForm.spot_key = photo.spot_key ?? ''
  editForm.taken_at = photo.taken_at ?? null
  editVisible.value = true
}

async function saveEdit(): Promise<void> {
  if (editingId.value === null) return
  saving.value = true
  try {
    await updatePhoto(editingId.value, {
      village_id: editForm.village_id,
      school_id: editForm.school_id,
      project_id: editForm.project_id,
      tag: editForm.tag.trim() || null,
      spot_key: editForm.spot_key.trim() || null,
      taken_at: editForm.taken_at,
    })
    ElMessage.success('归档信息已保存')
    editVisible.value = false
    await loadPhotos()
  } catch (err) {
    ElMessage.error(getErrorMessage(err, '保存归档信息失败'))
  } finally {
    saving.value = false
  }
}

// ── 删除 ──
async function handleDelete(photo: PhotoArchive): Promise<void> {
  try {
    await ElMessageBox.confirm(`确定删除影像「${photo.file_name || photo.id}」吗？`, '删除确认', {
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await deletePhoto(photo.id)
    ElMessage.success('影像已删除')
    selectedIds.value = selectedIds.value.filter((id) => id !== photo.id)
    if (page.value > 1 && photos.value.length === 1) page.value -= 1
    await loadPhotos()
  } catch (err) {
    ElMessage.error(getErrorMessage(err, '删除影像失败'))
  }
}

// ── 对比图 ──
function revokeCompareUrl(): void {
  if (compareUrl.value) {
    URL.revokeObjectURL(compareUrl.value)
    compareUrl.value = ''
  }
}

/** 生成对比图（POST 合成 PNG，弹窗预览） */
async function generateCompare(ids: number[]): Promise<void> {
  compareVisible.value = true
  compareLoading.value = true
  compareError.value = ''
  revokeCompareUrl()
  compareIds.value = ids
  try {
    const blob = await generateCompareImage(ids)
    compareUrl.value = URL.createObjectURL(blob)
  } catch (err) {
    compareError.value = getErrorMessage(err, '对比图生成失败')
    ElMessage.error(compareError.value)
  } finally {
    compareLoading.value = false
  }
}

/** 选中照片生成对比图 */
async function openCompare(): Promise<void> {
  if (selectedIds.value.length < 2) {
    ElMessage.info('请至少选择 2 张影像')
    return
  }
  compareSeries.value = []
  await generateCompare([...selectedIds.value])
}

/** 按拍摄点加载多期照片并生成对比图 */
async function openSpotCompare(spotKey: string): Promise<void> {
  try {
    const res = await getPhotoCompare(spotKey)
    compareSeries.value = unwrapList<PhotoCompareItem>(res).items
    const ids = compareSeries.value.map((item) => item.id)
    if (ids.length < 2) {
      ElMessage.info('该拍摄点不足 2 期，无法生成对比图')
      return
    }
    await generateCompare(ids)
  } catch (err) {
    ElMessage.error(getErrorMessage(err, '加载拍摄点多期失败'))
  }
}

/** 下载对比图（GET 版本，服务端按 Content-Disposition 命名） */
async function downloadCompare(): Promise<void> {
  if (!compareIds.value.length) return
  downloading.value = true
  try {
    await downloadCompareImage([...compareIds.value])
    ElMessage.success('对比图下载已开始')
  } catch (err) {
    ElMessage.error(getErrorMessage(err, '下载对比图失败'))
  } finally {
    downloading.value = false
  }
}

function closeCompare(): void {
  compareVisible.value = false
  compareError.value = ''
  compareSeries.value = []
  revokeCompareUrl()
}

onBeforeUnmount(revokeCompareUrl)

onMounted(() => {
  void loadFilterOptions()
  void loadPhotos()
})
</script>

<style scoped lang="scss">
.photo-archive-page {
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

  .filter-card {
    margin-bottom: 12px;
  }

  .filter-row {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    align-items: center;
  }

  .filter-select {
    width: 160px;
  }

  .filter-tag {
    width: 140px;
  }

  .filter-date {
    width: 260px;
  }

  .selection-bar {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 8px 0 12px;
  }

  .selection-info {
    font-size: 13px;
    color: var(--color-text-secondary);
  }

  .photo-grid-wrap {
    min-height: 180px;
  }

  .photo-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: 16px;
  }

  .photo-card {
    .photo-card-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 8px;
    }

    .photo-tag {
      font-size: 12px;
      color: var(--color-primary);
    }

    .photo-thumb {
      height: 150px;
      overflow: hidden;
      border-radius: 6px;
      background: var(--color-bg-hover);

      img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        display: block;
      }
    }

    .photo-meta {
      margin-top: 10px;
      font-size: 13px;
      color: var(--color-text-secondary);
      line-height: 1.6;
    }

    .photo-object {
      color: var(--color-text-primary);
    }

    .photo-actions {
      margin-top: 6px;
      display: flex;
      justify-content: flex-end;
    }
  }

  .photo-pagination {
    margin-top: 16px;
    justify-content: flex-end;
  }

  .spot-groups-card {
    margin-top: 16px;

    .card-title {
      font-weight: 600;
      color: var(--color-text-primary);
    }
  }

  .spot-group-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .spot-group {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 10px 12px;
    border: 1px solid var(--color-border-light);
    border-radius: 8px;
  }

  .spot-group-info {
    min-width: 180px;

    .spot-group-key {
      font-weight: 600;
      color: var(--color-text-primary);
    }

    .spot-group-count {
      font-size: 12px;
      color: var(--color-text-secondary);
      margin-top: 2px;
    }
  }

  .spot-group-thumbs {
    display: flex;
    gap: 8px;
    flex: 1;
  }

  .spot-thumb {
    width: 72px;
    height: 48px;
    object-fit: cover;
    border-radius: 4px;
    background: var(--color-bg-hover);
  }

  .compare-series {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
    margin-bottom: 16px;
  }

  .compare-series-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    font-size: 12px;
    color: var(--color-text-secondary);
  }

  .compare-series-thumb {
    width: 120px;
    height: 80px;
    object-fit: cover;
    border-radius: 6px;
    background: var(--color-bg-hover);
  }

  .compare-preview {
    text-align: center;
  }

  .compare-image {
    max-width: 100%;
    border-radius: 6px;
  }
}
</style>
