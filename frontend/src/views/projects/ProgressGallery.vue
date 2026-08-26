<template>
  <div class="progress-gallery">
    <el-page-header title="返回" @back="goBack">
      <template #content>
        <span class="page-title">项目进度画廊</span>
      </template>
    </el-page-header>

    <el-card class="main-card" shadow="never">
      <!-- Loading -->
      <el-skeleton v-if="loading" :rows="6" animated />

      <template v-else>
        <!-- 项目基本信息 -->
        <div class="project-info">
          <h2>{{ project?.name ?? '项目进度' }}</h2>
          <el-descriptions :column="3" border>
            <el-descriptions-item label="项目编号">{{ project?.code ?? '-' }}</el-descriptions-item>
            <el-descriptions-item label="开始时间">{{
              project?.start_date ?? '-'
            }}</el-descriptions-item>
            <el-descriptions-item label="当前状态">
              <el-tag :type="getStatusType(project?.status)">{{
                getStatusText(project?.status)
              }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="负责单位" :span="2">{{
              project?.responsible_unit ?? '-'
            }}</el-descriptions-item>
            <el-descriptions-item label="预算金额">{{
              project?.budget != null ? `${project.budget} 万元` : '-'
            }}</el-descriptions-item>
          </el-descriptions>
        </div>

        <el-divider content-position="left">
          <h3>项目进度照片</h3>
        </el-divider>

        <!-- Upload toolbar -->
        <div class="gallery-toolbar">
          <el-upload :show-file-list="false" accept="image/*" :http-request="handleUpload" multiple>
            <el-button type="primary">
              <el-icon><Upload /></el-icon> 上传进度照片
            </el-button>
          </el-upload>
        </div>

        <!-- Empty state -->
        <EmptyState text="暂无进度照片，请在附件管理中上传进度照片" v-if="!progressFiles.length" />

        <!-- Photo gallery -->
        <div v-else class="photo-grid">
          <el-card
            v-for="file in progressFiles"
            :key="file.id"
            shadow="hover"
            class="photo-card"
            :body-style="{ padding: '0' }"
          >
            <el-image
              :src="blobUrls[file.id] || ''"
              :preview-src-list="previewList"
              :initial-index="progressFiles.indexOf(file)"
              fit="cover"
              class="photo-img"
            >
              <template #error>
                <div class="image-error">
                  <el-icon :size="32"><Picture /></el-icon>
                  <span>加载失败</span>
                </div>
              </template>
            </el-image>
            <div class="photo-meta">
              <span class="photo-name" :title="file.filename ?? file.name">{{
                file.filename ?? file.name
              }}</span>
              <span class="photo-date">{{ file.created_at ?? '' }}</span>
            </div>
            <div class="photo-actions">
              <el-button link type="danger" size="small" @click="handleDelete(file.id)"
                >删除</el-button
              >
            </div>
          </el-card>
        </div>

        <!-- Before/After comparison section -->
        <template v-if="comparisonPairs.length">
          <el-divider content-position="left">
            <h3>前后对比</h3>
          </el-divider>
          <div class="comparison-list">
            <div v-for="pair in comparisonPairs" :key="pair.label" class="comparison-item">
              <h4>{{ pair.label }}</h4>
              <div class="comparison-images">
                <div class="comparison-side">
                  <el-tag type="info" size="small" class="comparison-label">之前</el-tag>
                  <el-image
                    :src="pair.beforeUrl"
                    fit="contain"
                    class="comparison-img"
                    :preview-src-list="[pair.beforeUrl]"
                  />
                </div>
                <div class="comparison-arrow">
                  <el-icon :size="24"><Right /></el-icon>
                </div>
                <div class="comparison-side">
                  <el-tag type="success" size="small" class="comparison-label">之后</el-tag>
                  <el-image
                    :src="pair.afterUrl"
                    fit="contain"
                    class="comparison-img"
                    :preview-src-list="[pair.afterUrl]"
                  />
                </div>
              </div>
            </div>
          </div>
        </template>
      </template>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import EmptyState from '@/components/business/EmptyState/EmptyState.vue'
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Upload, Picture, Right } from '@element-plus/icons-vue'
import { logger } from '@/utils/logger'
import { projectsApi } from '@/api/projects'
import { safeRouteParam } from '@/composables/useRouterSafe'
import { AuthStorage } from '@/utils/authStorage'

const route = useRoute()
const router = useRouter()

const projectId = safeRouteParam(route.params.id)

const loading = ref(true)
const project = ref<any>(null)
const allFiles = ref<any[]>([])

// 图片 Blob URL 映射（key = file.id），用于认证模式下 <img :src> / <el-image :src> 加载
const blobUrls = ref<Record<number | string, string>>({})

// --- Computed ---
const progressFiles = computed(() =>
  allFiles.value.filter((f) => (f.category ?? '').toLowerCase() === 'progress')
)

const previewList = computed(() =>
  progressFiles.value.map((f) => blobUrls.value[f.id]).filter(Boolean)
)

/**
 * Pair up progress images for before/after comparison.
 * Groups by filename prefix (e.g. "before_xxx" / "after_xxx") or
 * falls back to sequential pairing (1st vs 2nd, 3rd vs 4th, …).
 */
const comparisonPairs = computed(() => {
  const imgs = progressFiles.value
  if (imgs.length < 2) return []

  const pairs: { label: string; beforeUrl: string; afterUrl: string }[] = []

  // Try name-based pairing: files whose names contain "before"/"前" matched with "after"/"后"
  const beforeFiles = imgs.filter((f) => /before|前/i.test(f.filename ?? f.name ?? ''))
  const afterFiles = imgs.filter((f) => /after|后/i.test(f.filename ?? f.name ?? ''))

  if (beforeFiles.length && afterFiles.length) {
    const count = Math.min(beforeFiles.length, afterFiles.length)
    for (let i = 0; i < count; i++) {
      pairs.push({
        label: `对比 ${i + 1}`,
        beforeUrl: blobUrls.value[beforeFiles[i].id] || '',
        afterUrl: blobUrls.value[afterFiles[i].id] || '',
      })
    }
  } else if (imgs.length >= 2) {
    // Sequential pairing fallback
    for (let i = 0; i + 1 < imgs.length; i += 2) {
      pairs.push({
        label: `对比 ${Math.floor(i / 2) + 1}`,
        beforeUrl: blobUrls.value[imgs[i].id] || '',
        afterUrl: blobUrls.value[imgs[i + 1].id] || '',
      })
    }
  }

  return pairs
})

// --- Helpers ---

/**
 * 异步加载单个文件的 Blob URL（带认证头）
 */
async function loadBlobUrl(file: any): Promise<void> {
  try {
    const url = projectsApi.getFileDownloadUrl(projectId, file.id)
    const token = AuthStorage.getToken()
    const response = await fetch(url, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!response.ok) return
    const blob = await response.blob()
    // 释放旧的 Blob URL
    if (blobUrls.value[file.id]) URL.revokeObjectURL(blobUrls.value[file.id])
    blobUrls.value[file.id] = URL.createObjectURL(blob)
  } catch {
    // 静默处理，el-image 会显示 error 占位
  }
}

/**
 * 为所有进度照片加载 Blob URL
 */
async function loadAllBlobUrls() {
  await Promise.all(progressFiles.value.map((f) => loadBlobUrl(f)))
}

/**
 * 释放所有 Blob URL
 */
function revokeAllBlobUrls() {
  for (const key of Object.keys(blobUrls.value)) {
    URL.revokeObjectURL(blobUrls.value[key])
  }
  blobUrls.value = {}
}

type ElTagType = 'primary' | 'success' | 'warning' | 'info' | 'danger'
function getStatusType(status?: string): ElTagType {
  const map: Record<string, string> = {
    draft: 'info',
    pending: 'info',
    approved: 'primary',
    planning: 'info',
    in_progress: 'warning',
    completed: 'success',
    cancelled: 'danger',
    suspended: 'danger',
  }
  return (map[status ?? ''] ?? 'info') as ElTagType
}

function getStatusText(status?: string) {
  const map: Record<string, string> = {
    draft: '草稿',
    pending: '待审批',
    approved: '已审批',
    planning: '规划中',
    in_progress: '进行中',
    completed: '已完成',
    cancelled: '已取消',
    suspended: '已暂停',
  }
  return map[status ?? ''] ?? status ?? '-'
}

const goBack = () => router.back()

// --- Data loading ---
async function loadData() {
  loading.value = true
  try {
    const [proj, filesRes] = await Promise.all([
      projectsApi.get(projectId),
      projectsApi.listFiles(projectId),
    ])
    project.value = proj
    // 后端返回 {files: [...], grouped: {...}}——兼容两种结构，防止对象被当数组
    allFiles.value = Array.isArray(filesRes) ? filesRes : (filesRes?.files ?? filesRes?.items ?? [])
    // 异步加载所有进度照片的 Blob URL
    await loadAllBlobUrls()
  } catch (e: any) {
    logger.error('加载进度画廊数据失败', e)
    ElMessage.error('加载数据失败，请返回重试')
  } finally {
    loading.value = false
  }
}

// --- Upload ---
async function handleUpload(options: any) {
  try {
    await projectsApi.uploadFiles(projectId, 'progress', [options.file])
    ElMessage.success('上传成功')
    // Refresh file list
    const filesRes = await projectsApi.listFiles(projectId)
    // 后端返回 {files: [...], grouped: {...}}——兼容两种结构，防止对象被当数组
    allFiles.value = Array.isArray(filesRes) ? filesRes : (filesRes?.files ?? filesRes?.items ?? [])
    // 加载新照片的 Blob URL
    await loadAllBlobUrls()
  } catch (e: any) {
    logger.error('上传进度照片失败', e)
    ElMessage.error(e?.message || '上传失败')
  }
}

// --- Delete ---
async function handleDelete(fileId: number) {
  try {
    await ElMessageBox.confirm('确定删除该进度照片？', '提示', { type: 'warning' })
    await projectsApi.deleteFile(projectId, fileId)
    // 释放被删除文件的 Blob URL
    if (blobUrls.value[fileId]) {
      URL.revokeObjectURL(blobUrls.value[fileId])
      delete blobUrls.value[fileId]
    }
    ElMessage.success('已删除')
    const filesRes = await projectsApi.listFiles(projectId)
    // 后端返回 {files: [...], grouped: {...}}——兼容两种结构，防止对象被当数组
    allFiles.value = Array.isArray(filesRes) ? filesRes : (filesRes?.files ?? filesRes?.items ?? [])
  } catch (e: any) {
    if (e === 'cancel' || e?.toString?.().includes('cancel')) return
    logger.error('删除进度照片失败', e)
    ElMessage.error(e?.message || '删除失败')
  }
}

// --- Init ---
onMounted(() => loadData())

// --- Cleanup ---
onUnmounted(() => {
  revokeAllBlobUrls()
})
</script>

<style scoped lang="scss">
.progress-gallery {
  padding: 20px;

  .page-title {
    font-size: 18px;
    font-weight: 600;
  }

  .main-card {
    margin-top: 20px;

    .project-info {
      margin-bottom: 24px;

      h2 {
        margin: 0 0 16px 0;
        font-size: 22px;
        color: var(--color-text-primary);
      }
    }
  }

  .gallery-toolbar {
    display: flex;
    justify-content: flex-end;
    margin-bottom: 16px;
  }

  .photo-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 16px;

    .photo-card {
      border-radius: 8px;
      overflow: hidden;

      .photo-img {
        width: 100%;
        height: 180px;
        display: block;
      }

      .image-error {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        height: 180px;
        color: #c0c4cc;
        gap: 8px;
        background: var(--color-bg-hover);
      }

      .photo-meta {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px 12px 4px;
        font-size: 12px;
        color: var(--color-info);

        .photo-name {
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
          max-width: 140px;
          color: var(--color-text-regular);
        }
      }

      .photo-actions {
        padding: 0 12px 8px;
        text-align: right;
      }
    }
  }

  .comparison-list {
    .comparison-item {
      margin-bottom: 24px;

      h4 {
        margin: 0 0 12px;
        color: var(--color-text-primary);
      }

      .comparison-images {
        display: flex;
        align-items: center;
        gap: 16px;

        .comparison-side {
          flex: 1;
          text-align: center;

          .comparison-label {
            margin-bottom: 8px;
          }

          .comparison-img {
            width: 100%;
            height: 240px;
            border-radius: 6px;
            border: 1px solid var(--color-border-light);
          }
        }

        .comparison-arrow {
          color: #c0c4cc;
          flex-shrink: 0;
        }
      }
    }
  }
}
</style>
