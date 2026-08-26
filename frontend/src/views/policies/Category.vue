<template>
  <div class="policy-category">
    <!-- 专项政策分类 -->
    <el-card v-loading="loading" class="category-card">
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <el-icon class="category-icon military"><Aim /></el-icon>
            <span class="title">专项政策</span>
            <el-tag type="danger" size="small">{{ statistics.military.total }} 条</el-tag>
          </div>
        </div>
      </template>

      <el-row :gutter="20">
        <el-col v-for="level in militaryLevels" :key="level.value" :xs="24" :sm="12" :md="6">
          <div class="level-card" @click="handleLevelClick('military', level.value)">
            <div class="level-icon">
              <el-icon><Flag /></el-icon>
            </div>
            <div class="level-info">
              <div class="level-name">{{ level.label }}</div>
              <div class="level-count">
                {{ statistics.military.levels[level.value] || 0 }} 条政策
              </div>
            </div>
            <el-icon class="arrow-icon"><ArrowRight /></el-icon>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <!-- 地方政策分类 -->
    <el-card v-loading="loading" class="category-card">
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <el-icon class="category-icon local"><OfficeBuilding /></el-icon>
            <span class="title">地方政策</span>
            <el-tag type="primary" size="small">{{ statistics.local.total }} 条</el-tag>
          </div>
        </div>
      </template>

      <el-row :gutter="20">
        <el-col v-for="level in localLevels" :key="level.value" :xs="24" :sm="12" :md="6">
          <div class="level-card local" @click="handleLevelClick('local', level.value)">
            <div class="level-icon">
              <el-icon><Location /></el-icon>
            </div>
            <div class="level-info">
              <div class="level-name">{{ level.label }}</div>
              <div class="level-count">{{ statistics.local.levels[level.value] || 0 }} 条政策</div>
            </div>
            <el-icon class="arrow-icon"><ArrowRight /></el-icon>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <!-- 快捷操作 -->
    <el-card class="action-card">
      <template #header>
        <div class="card-header">
          <span class="title">快捷操作</span>
        </div>
      </template>

      <el-row :gutter="20">
        <el-col :xs="24" :sm="8">
          <el-button type="primary" size="large" class="action-btn" @click="handleViewAll">
            <el-icon><List /></el-icon>
            查看全部政策
          </el-button>
        </el-col>
        <el-col :xs="24" :sm="8">
          <el-button type="success" size="large" class="action-btn" @click="handleViewMilitary">
            <el-icon><Aim /></el-icon>
            查看专项政策
          </el-button>
        </el-col>
        <el-col :xs="24" :sm="8">
          <el-button type="warning" size="large" class="action-btn" @click="handleViewLocal">
            <el-icon><OfficeBuilding /></el-icon>
            查看地方政策
          </el-button>
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { logger } from '@/utils/logger'

import { ref, reactive, onMounted } from 'vue'
import { useRouterSafe } from '@/composables/useRouterSafe'
import { Aim, OfficeBuilding, Flag, Location, ArrowRight, List } from '@element-plus/icons-vue'
import { usePolicyStore } from '@/stores/policy'
import { getLevelOptions, type PolicyCategory, type LevelConfig } from '@/api/policy'

type OrganizationLevel = string

const { pushSafe } = useRouterSafe()
const policyStore = usePolicyStore()

const loading = ref(false)

// 统计数据
const statistics = reactive({
  military: {
    total: 0,
    levels: {} as Record<string, number>,
  },
  local: {
    total: 0,
    levels: {} as Record<string, number>,
  },
})

// 层级配置（异步加载：接口返回全部层级，前端按「专项/地方」拆分）
const militaryLevels = ref<LevelConfig[]>([])
const localLevels = ref<LevelConfig[]>([])

const loadLevels = async () => {
  try {
    const res: any = await getLevelOptions()
    // 兼容信封（items）/裸数组/data 数组三种形态
    let list: any = []
    if (Array.isArray(res)) list = res
    else if (res?.items) list = res.items
    else if (Array.isArray(res?.data)) list = res.data
    const items: LevelConfig[] = Array.isArray(list) ? list : []
    militaryLevels.value = items.filter((l) => l.value === 'military')
    localLevels.value = items.filter((l) => l.value !== 'military')
  } catch {
    // 层级加载失败静默，使用空列表
    militaryLevels.value = []
    localLevels.value = []
  }
}

// 加载统计数据
const loadStatistics = async () => {
  loading.value = true
  try {
    const data = await (policyStore as any).fetchStatistics()
    statistics.military = data.military
    statistics.local = data.local
  } catch (error: any) {
    logger.error('加载统计数据失败:', error)
    // 静默处理错误，使用默认值
  } finally {
    loading.value = false
  }
}

// 点击层级卡片
const handleLevelClick = (category: PolicyCategory, level: OrganizationLevel) => {
  pushSafe({
    path: '/policies',
    query: { category, level },
  })
}

// 查看全部政策
const handleViewAll = () => {
  pushSafe('/policies')
}

// 查看专项政策
const handleViewMilitary = () => {
  pushSafe({
    path: '/policies',
    query: { category: 'military' },
  })
}

// 查看地方政策
const handleViewLocal = () => {
  pushSafe({
    path: '/policies',
    query: { category: 'local' },
  })
}

// 初始化
onMounted(() => {
  loadStatistics()
  loadLevels()
})
</script>

<style scoped lang="scss">
.policy-category {
  padding: 20px;
}

.category-card,
.action-card {
  margin-bottom: 20px;
  background: rgba(10, 30, 20, 0.5);
  border: 1px solid rgba(64, 145, 108, 0.3);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.category-icon {
  font-size: 24px;

  &.military {
    color: var(--color-danger);
  }

  &.local {
    color: var(--color-primary);
  }
}

.title {
  font-size: 18px;
  font-weight: bold;
  color: var(--color-text-inverse);
}

.level-card {
  display: flex;
  align-items: center;
  padding: 16px;
  margin-bottom: 16px;
  background: color-mix(in srgb, var(--color-danger) 10%, transparent);
  border: 1px solid color-mix(in srgb, var(--color-danger) 30%, transparent);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s ease;

  &:hover {
    background: color-mix(in srgb, var(--color-danger) 20%, transparent);
    transform: translateY(-2px);
    box-shadow: 0 4px 12px color-mix(in srgb, var(--color-danger) 20%, transparent);
  }

  &.local {
    background: rgba(45, 106, 79, 0.1);
    border-color: rgba(45, 106, 79, 0.3);

    &:hover {
      background: rgba(45, 106, 79, 0.2);
      box-shadow: 0 4px 12px rgba(45, 106, 79, 0.2);
    }

    .level-icon {
      background: rgba(45, 106, 79, 0.2);
      color: var(--color-primary);
    }
  }
}

.level-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  background: color-mix(in srgb, var(--color-danger) 20%, transparent);
  border-radius: 8px;
  color: var(--color-danger);
  font-size: 24px;
  margin-right: 16px;
}

.level-info {
  flex: 1;
}

.level-name {
  font-size: 16px;
  font-weight: 500;
  color: var(--color-text-inverse);
  margin-bottom: 4px;
}

.level-count {
  font-size: 14px;
  color: var(--color-text-secondary);
}

.arrow-icon {
  color: var(--color-text-secondary);
  font-size: 20px;
}

.action-card {
  .action-btn {
    width: 100%;
    height: 60px;
    font-size: 16px;
    margin-bottom: 10px;

    .el-icon {
      margin-right: 8px;
    }
  }
}

@media (max-width: 768px) {
  .level-card {
    margin-bottom: 12px;
  }

  .action-card .action-btn {
    margin-bottom: 12px;
  }
}
</style>
