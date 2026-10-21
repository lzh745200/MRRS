<template>
  <div class="map-tile-manager">
    <PageHeader title="地图瓦片管理" subtitle="查看离线瓦片覆盖情况，导入运维生成的瓦片包" />

    <el-alert
      class="map-tile-tip"
      type="info"
      :closable="false"
      show-icon
      title="地图默认使用内置矢量地图；如需栅格瓦片底图，请由运维生成瓦片包后在此导入。"
    />

    <!-- 覆盖情况 -->
    <el-card class="map-tile-card">
      <h3 class="section-title">瓦片覆盖情况</h3>

      <el-descriptions v-loading="loading" :column="3" border>
        <el-descriptions-item label="是否可用">
          <el-tag :type="tileUsable ? 'success' : 'info'">
            {{ tileUsable ? '已预置' : '未预置' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="瓦片数量">{{ tileInfo.tileCount }}</el-descriptions-item>
        <el-descriptions-item label="占用空间">{{ sizeLabel }}</el-descriptions-item>
        <el-descriptions-item label="缩放级别">{{ zoomLabel }}</el-descriptions-item>
        <el-descriptions-item label="瓦片目录">{{ dirLabel }}</el-descriptions-item>
        <el-descriptions-item label="生成时间">{{ generatedAtLabel }}</el-descriptions-item>
      </el-descriptions>

      <div v-if="zoomLevels.length > 0" class="zoom-levels">
        <h4>已预置的缩放级别</h4>
        <div class="zoom-level-tags">
          <el-tag v-for="level in zoomLevels" :key="level" type="info" size="small">
            {{ level }}
          </el-tag>
        </div>
      </div>

      <el-alert
        v-if="unavailableHint"
        class="map-tile-hint"
        type="warning"
        :closable="false"
        :title="unavailableHint"
      />
      <el-alert
        v-if="gcj02"
        class="map-tile-hint"
        type="warning"
        :closable="false"
        :title="GCJ02_HINT"
      />

      <div class="actions">
        <el-button type="primary" :loading="loading" @click="loadTileInfo">刷新状态</el-button>
        <el-button type="danger" @click="handleClearTiles">清空瓦片缓存</el-button>
      </div>
    </el-card>

    <!-- 导入瓦片包 -->
    <el-card class="map-tile-card">
      <h3 class="section-title">导入瓦片包</h3>
      <p class="import-desc">
        瓦片包为 .zip（内部按 <code>{z}/{x}/{y}.png</code> 组织，最大
        512MB）。导入后在地图可视化页切换到「瓦片底图」即可查看，全程不联网。
      </p>

      <el-upload
        ref="uploadRef"
        class="tile-upload"
        accept=".zip"
        :auto-upload="false"
        :limit="1"
        :on-change="handleFileChange"
        :on-remove="handleFileRemove"
        :on-exceed="handleFileExceed"
      >
        <el-button>选择瓦片包</el-button>
        <template #tip>
          <div class="upload-tip">仅支持 .zip 格式；一次只能导入一个瓦片包</div>
        </template>
      </el-upload>

      <div class="actions">
        <el-button type="primary" :loading="importing" @click="handleImportTiles">
          导入瓦片包
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
/**
 * 地图瓦片管理（覆盖查看 + 导入瓦片包）
 *
 * 语义变更（离线部署）：
 * - 旧的「下载瓦片（需要网络连接）」已删除 —— 后端 POST /offline-map/download 改为显式失败，
 *   瓦片改由运维离线生成 .zip 瓦片包后在此导入（POST /map/tiles/import，管理员）。
 * - 状态数据源统一为 GET /map/tile-info（available/tileCount/zoomLevels/totalBytes/dir/manifest）。
 * - 清空缓存仍走后端 DELETE /offline-map/clear（整体清理，不支持按缩放级别）。
 */
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox, type UploadFile, type UploadInstance } from 'element-plus'
import { getTileInfo, type TileInfo } from '@/api/map'
import { clearTiles, importTiles } from '@/api/offlineMap'
import {
  GCJ02_HINT,
  formatManifestTime,
  formatTileBytes,
  formatZoomRange,
  isGcj02,
  isTileMapUsable,
  normalizeTileImportResult,
  normalizeTileInfo,
  tileInfoHint,
  validateTilePackage,
} from '@/utils/mapTiles'
import { getErrorMessage } from '@/utils/getErrorMessage'
import PageHeader from '@/components/common/PageHeader.vue'

const tileInfo = ref<TileInfo>(normalizeTileInfo(null))
const loading = ref(false)
const importing = ref(false)
/** 是否已完成一次状态读取（未读完时不展示"未预置"提示，避免闪烁） */
const loaded = ref(false)
const pendingFile = ref<File | null>(null)
const uploadRef = ref<UploadInstance>()

const tileUsable = computed(() => isTileMapUsable(tileInfo.value))
const sizeLabel = computed(() => formatTileBytes(tileInfo.value.totalBytes))
const zoomLabel = computed(() => formatZoomRange(tileInfo.value.zoomLevels))
const zoomLevels = computed(() => tileInfo.value.zoomLevels)
const dirLabel = computed(() => tileInfo.value.dir || '—')
const generatedAtLabel = computed(() => formatManifestTime(tileInfo.value.manifest))
const unavailableHint = computed(() => (loaded.value ? tileInfoHint(tileInfo.value) : ''))
const gcj02 = computed(() => isGcj02(tileInfo.value.manifest))

/** 读取本机瓦片覆盖情况（GET /map/tile-info） */
async function loadTileInfo() {
  loading.value = true
  try {
    tileInfo.value = normalizeTileInfo(await getTileInfo())
  } catch (error: any) {
    ElMessage.error(getErrorMessage(error, '读取瓦片信息失败'))
  } finally {
    loaded.value = true
    loading.value = false
  }
}

/** el-upload 选择文件后先做前端校验（.zip / 非空 / ≤512MB），再待用户点击导入 */
function handleFileChange(file: UploadFile) {
  const raw = (file?.raw ?? null) as File | null
  const validation = validateTilePackage(raw)
  if (!validation.ok) {
    pendingFile.value = null
    ElMessage.error(validation.message)
    uploadRef.value?.clearFiles()
    return
  }
  pendingFile.value = raw
}

function handleFileRemove() {
  pendingFile.value = null
}

/** limit=1：重复选择时提示先移除已选文件 */
function handleFileExceed() {
  ElMessage.warning('一次只能导入一个瓦片包，请先移除已选择的文件')
}

async function handleImportTiles() {
  if (!pendingFile.value) {
    ElMessage.warning('请先选择 .zip 瓦片包')
    return
  }
  importing.value = true
  try {
    const outcome = normalizeTileImportResult(await importTiles(pendingFile.value))
    if (!outcome.ok) {
      ElMessage.error(outcome.message)
      return
    }
    ElMessage.success(outcome.message)
    pendingFile.value = null
    uploadRef.value?.clearFiles()
    await loadTileInfo()
  } catch (error: any) {
    // 后端中文失败原因（detail/message）经拦截器挂到 userMessage，由 getErrorMessage 提取
    ElMessage.error(getErrorMessage(error, '导入瓦片包失败'))
  } finally {
    importing.value = false
  }
}

async function handleClearTiles() {
  try {
    await ElMessageBox.confirm(
      '将删除本机全部离线瓦片（含已导入的瓦片包），确定要继续吗？',
      '确认清空',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
  } catch {
    return
  }
  try {
    const response = await clearTiles()
    ElMessage.success(response?.message || '瓦片缓存已清空')
    await loadTileInfo()
  } catch (error: any) {
    ElMessage.error(getErrorMessage(error, '清空瓦片缓存失败'))
  }
}

onMounted(() => {
  loadTileInfo()
})
</script>

<style scoped lang="scss">
.map-tile-manager {
  padding: 20px;
}

.map-tile-tip {
  margin-bottom: 16px;
}

.map-tile-card {
  margin-bottom: 20px;
}

.section-title {
  margin: 0 0 20px 0;
  font-size: 18px;
  color: var(--color-text-primary);
  border-bottom: 2px solid var(--color-primary);
  padding-bottom: 10px;
}

.map-tile-hint {
  margin-top: 16px;
}

.zoom-levels {
  margin-top: 20px;

  h4 {
    margin: 0 0 10px 0;
    font-size: 16px;
    color: var(--color-text-primary);
  }
}

.zoom-level-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.import-desc {
  margin: 0 0 16px 0;
  color: var(--color-text-regular);
  font-size: 14px;

  code {
    padding: 0 4px;
    border-radius: 3px;
    background: var(--color-bg-hover);
    font-family: var(--font-family-mono);
  }
}

.upload-tip {
  margin-top: 8px;
  color: var(--color-info);
  font-size: 12px;
}

.actions {
  margin-top: 20px;
  display: flex;
  gap: 10px;
}
</style>
