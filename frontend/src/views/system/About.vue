<template>
  <div class="about-page">
    <div class="about-container">
      <!-- 系统标识 -->
      <div class="about-hero">
        <div class="app-logo">
          <el-icon :size="32"><Platform /></el-icon>
        </div>
        <h2 class="app-name">帮扶管理信息系统</h2>
        <p class="app-name-en">Assistance Management Information System</p>
        <el-tag type="success" effect="dark" round>v{{ systemVersion }}</el-tag>
      </div>

      <!-- 系统信息 -->
      <el-card class="about-card">
        <template #header>
          <span class="card-title"
            ><el-icon><InfoFilled /></el-icon> 系统信息</span
          >
        </template>
        <el-descriptions :column="1" border>
          <el-descriptions-item label="系统名称">帮扶管理信息系统</el-descriptions-item>
          <el-descriptions-item label="英文名"
            >Assistance Management Information System</el-descriptions-item
          >
          <el-descriptions-item label="版本">
            <el-tag type="success" size="small">v{{ systemVersion }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="技术栈">
            <div class="tag-list">
              <el-tag v-for="tech in techStack" :key="tech" size="small" effect="plain">
                {{ tech }}
              </el-tag>
            </div>
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <!-- 系统要求 -->
      <el-card class="about-card">
        <template #header>
          <span class="card-title"
            ><el-icon><Monitor /></el-icon> 系统要求</span
          >
        </template>
        <el-descriptions :column="1" border>
          <el-descriptions-item label="操作系统"
            >Windows 10/11 64-bit / 麒麟 V10 ARM64</el-descriptions-item
          >
          <el-descriptions-item label="内存">4GB 最低 / 8GB 推荐</el-descriptions-item>
          <el-descriptions-item label="硬盘">2GB 最低 / 5GB 推荐</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <!-- 许可与致谢 -->
      <el-card class="about-card">
        <template #header>
          <span class="card-title"
            ><el-icon><Stamp /></el-icon> 许可与致谢</span
          >
        </template>
        <el-descriptions :column="1" border>
          <el-descriptions-item label="许可">
            <span class="license-text">UNLICENSED</span>
            <el-tag type="warning" size="small" style="margin-left: 8px">内部使用</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="开发单位">（待补充）</el-descriptions-item>
          <el-descriptions-item label="主要开源组件">
            <div class="tag-list">
              <el-tag
                v-for="lib in openSourceLibs"
                :key="lib"
                size="small"
                type="info"
                effect="plain"
              >
                {{ lib }}
              </el-tag>
            </div>
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <!-- 运行时信息 -->
      <el-card v-loading="envLoading" class="about-card">
        <template #header>
          <div class="card-header">
            <span class="card-title"
              ><el-icon><Cpu /></el-icon> 运行时信息</span
            >
            <el-button :icon="Refresh" size="small" :loading="envLoading" @click="fetchEnv">
              重新检测
            </el-button>
          </div>
        </template>
        <el-alert
          v-if="envError"
          title="运行时信息获取失败，请确认后端服务已启动"
          type="warning"
          :closable="false"
          show-icon
          style="margin-bottom: 12px"
        />
        <el-descriptions :column="1" border>
          <el-descriptions-item label="Python 版本">
            <el-tag v-if="envData?.system?.python_version" type="primary" size="small">
              {{ envData.system.python_version }}
            </el-tag>
            <span v-else>-</span>
          </el-descriptions-item>
          <el-descriptions-item label="操作系统">
            {{ envData?.system?.platform || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="运行模式">
            <el-tag :type="envModeTagType" size="small">{{
              envData?.system?.env_mode || '-'
            }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="依赖完整性">
            <template v-if="envData">
              <el-tag type="success" size="small">已安装 {{ installedCount }}</el-tag>
              <el-tag v-if="missingCount > 0" type="danger" size="small" style="margin-left: 8px">
                缺失 {{ missingCount }}
              </el-tag>
              <el-tag v-else type="success" size="small" effect="plain" style="margin-left: 8px">
                无缺失
              </el-tag>
            </template>
            <span v-else>-</span>
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <!-- 页脚 -->
      <div class="about-footer">
        <span>© 2026 帮扶管理信息系统 · 内部系统，未经授权禁止外传</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Platform, InfoFilled, Monitor, Stamp, Cpu, Refresh } from '@element-plus/icons-vue'
import { get } from '@/api/request'
import { SYSTEM_VERSION } from '@/config/constants'

// ── 类型定义 ──
interface RuntimeSystemInfo {
  python_version?: string
  platform?: string
  env_mode?: string
}

/** /env/check 响应 */
interface EnvCheckResponse {
  system?: RuntimeSystemInfo
  packages?: Record<string, string>
  missing_packages?: string[]
}

// ── 静态信息 ──
const systemVersion = SYSTEM_VERSION
const techStack = ['Vue 3', 'TypeScript', 'FastAPI', 'Electron', 'SQLite']

const openSourceLibs = ['Vue 3', 'Element Plus', 'ECharts', 'FastAPI', 'SQLAlchemy', 'Electron']

// ── 运行时信息 ──
const envLoading = ref(false)
const envError = ref(false)
const envData = ref<EnvCheckResponse | null>(null)

const missingCount = computed(() => envData.value?.missing_packages?.length ?? 0)

const installedCount = computed(() => {
  const total = envData.value?.packages ? Object.keys(envData.value.packages).length : 0
  return Math.max(0, total - missingCount.value)
})

const envModeTagType = computed<'success' | 'warning' | 'info'>(() => {
  const mode = envData.value?.system?.env_mode || ''
  if (mode === 'production') return 'success'
  if (mode === 'development') return 'warning'
  return 'info'
})

async function fetchEnv(): Promise<void> {
  envLoading.value = true
  envError.value = false
  try {
    envData.value = await get<EnvCheckResponse>('/env/check')
  } catch {
    envData.value = null
    envError.value = true
  } finally {
    envLoading.value = false
  }
}

onMounted(() => {
  fetchEnv()
})
</script>

<style scoped>
.about-page {
  padding: 20px;
}
.about-container {
  max-width: 800px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* ── 系统标识 ── */
.about-hero {
  text-align: center;
  padding: 28px 20px 8px;
}
.app-logo {
  width: 64px;
  height: 64px;
  margin: 0 auto 14px;
  border-radius: 14px;
  background: linear-gradient(135deg, var(--color-primary-dark-1), var(--color-primary-light-1));
  color: var(--color-text-inverse);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8px 20px rgba(27, 67, 50, 0.25);
}
.app-name {
  font-size: 26px;
  font-weight: 700;
  color: var(--color-primary-dark-1);
  letter-spacing: 2px;
  margin: 0 0 6px;
}
.app-name-en {
  font-size: 13px;
  color: var(--color-info);
  letter-spacing: 0.5px;
  margin: 0 0 12px;
}

/* ── 卡片 ── */
.about-card {
  transition: box-shadow 0.25s ease;
}
.about-card:hover {
  box-shadow: 0 6px 18px rgba(27, 67, 50, 0.1);
}
.card-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
  color: var(--color-primary-dark-1);
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.license-text {
  font-family: monospace;
  font-weight: 600;
  color: var(--color-warning);
}

/* ── 页脚 ── */
.about-footer {
  text-align: center;
  font-size: 12px;
  color: var(--color-text-placeholder, var(--color-text-disabled));
  padding: 4px 0 12px;
}
</style>
