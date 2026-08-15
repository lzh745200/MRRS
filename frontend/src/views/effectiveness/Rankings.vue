<template>
  <div class="rankings-page">
    <div class="page-header">
      <div class="header-info">
        <h2 class="page-title">成效排名</h2>
        <p class="page-desc">查看帮扶村庄综合成效评分排名</p>
      </div>
    </div>

    <!-- 筛选 -->
    <div class="filter-card">
      <el-form :model="filterForm" inline>
        <el-form-item label="评估年度">
          <el-select v-model="filterForm.year" style="width: 140px" @change="handleSearch">
            <el-option v-for="y in yearOptions" :key="y" :label="String(y)" :value="y" />
          </el-select>
        </el-form-item>
        <el-form-item label="显示数量">
          <el-select v-model="filterForm.limit" style="width: 120px" @change="handleSearch">
            <el-option label="前10名" :value="10" />
            <el-option label="前20名" :value="20" />
            <el-option label="前50名" :value="50" />
            <el-option label="全部" :value="100" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">
            <el-icon><Search /></el-icon>查询
          </el-button>
        </el-form-item>
      </el-form>
    </div>

    <!-- 加载/错误/空 -->
    <div v-if="loading" class="state-container">
      <el-icon class="is-loading" :size="32"><Loading /></el-icon>
      <p>加载中...</p>
    </div>

    <div v-else-if="loadError" class="state-container">
      <el-empty description="加载失败">
        <el-button type="primary" @click="fetchRankings">重新加载</el-button>
      </el-empty>
    </div>

    <div v-else-if="rankings.length === 0" class="state-container">
      <el-empty description="暂无排名数据" />
    </div>

    <!-- 排名表格 -->
    <div v-else class="table-card">
      <el-table :data="rankings" stripe>
        <el-table-column label="排名" width="80" align="center">
          <template #default="scope">
            <span class="rank-badge" :class="rankClass(scope.row.rank)">
              {{ scope.row.rank }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="village_name" label="村庄名称" min-width="160">
          <template #default="scope">
            <el-link type="primary" @click="goToEvaluate(scope.row.village_id)">
              {{ scope.row.village_name || scope.row.name || '-' }}
            </el-link>
          </template>
        </el-table-column>
        <el-table-column
          prop="support_unit"
          label="帮扶单位"
          min-width="140"
          show-overflow-tooltip
        />
        <el-table-column label="总分" width="120" align="center">
          <template #default="scope">
            <div class="score-bar-wrapper">
              <div class="score-bar">
                <div
                  class="score-bar-fill"
                  :style="{ width: scorePercent(scope.row.total_score) + '%' }"
                />
              </div>
              <span class="score-text">{{ formatScore(scope.row.total_score) }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="等级" width="100" align="center">
          <template #default="scope">
            <el-tag :type="levelTagType(scope.row.level)" size="small">
              {{ levelLabel(scope.row.level) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="经济" width="90" align="right">
          <template #default="scope">
            {{ scope.row.scores?.economic ?? '-' }}
          </template>
        </el-table-column>
        <el-table-column label="社会" width="90" align="right">
          <template #default="scope">
            {{ scope.row.scores?.social ?? '-' }}
          </template>
        </el-table-column>
        <el-table-column label="生态" width="90" align="right">
          <template #default="scope">
            {{ scope.row.scores?.ecological ?? '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right" align="center">
          <template #default="scope">
            <el-button type="primary" link size="small" @click="goToEvaluate(scope.row.village_id)">
              {{ isAdmin ? '评估' : '查看' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouterSafe } from '@/composables/useRouterSafe'
import { Loading, Search } from '@element-plus/icons-vue'
import { getRankings } from '@/api/effectiveness'
import { useUserStore } from '@/stores/user'

const { pushSafe } = useRouterSafe()
const userStore = useUserStore()
// 仅管理员可发起评估；其余角色（viewer/user）入口降级为"查看"
const isAdmin = computed(
  () =>
    ['admin', 'super_admin'].includes(userStore.currentUser?.role || '') ||
    !!userStore.currentUser?.is_superuser
)

const currentYear = new Date().getFullYear()
const yearOptions = Array.from({ length: 5 }, (_, i) => currentYear - i)

const filterForm = reactive({
  year: currentYear,
  limit: 20,
})

const rankings = ref<any[]>([])
const loading = ref(false)
const loadError = ref(false)

function rankClass(rank: number) {
  if (rank === 1) return 'rank-gold'
  if (rank === 2) return 'rank-silver'
  if (rank === 3) return 'rank-bronze'
  return ''
}

function scorePercent(score: number) {
  const maxScore = 100
  return Math.min(Math.max((score / maxScore) * 100, 0), 100)
}

function formatScore(score: number) {
  if (score == null) return '-'
  return Number(score).toFixed(1)
}

function levelLabel(level: string) {
  const map: Record<string, string> = {
    excellent: '优秀',
    good: '良好',
    average: '一般',
    poor: '较差',
    A: 'A级',
    B: 'B级',
    C: 'C级',
    D: 'D级',
  }
  return map[level] || level || '-'
}

function levelTagType(level: string) {
  if (!level) return 'info'
  const l = level.toLowerCase()
  if (l === 'excellent' || l === 'a') return 'success'
  if (l === 'good' || l === 'b') return 'primary'
  if (l === 'average' || l === 'c') return 'warning'
  return 'danger'
}

function goToEvaluate(villageId: number) {
  pushSafe(`/effectiveness/evaluate?villageId=${villageId}&year=${filterForm.year}`)
}

async function fetchRankings() {
  loading.value = true
  loadError.value = false
  try {
    const response = await getRankings(filterForm.year, filterForm.limit)
    const data = response?.data ?? response
    const list = data?.rankings ?? data?.items ?? (Array.isArray(data) ? data : [])
    // 后端字段适配：grade → level、support_unit 兼容
    rankings.value = (Array.isArray(list) ? list : []).map((r: any) => ({
      ...r,
      level: r.level ?? r.grade ?? null,
      support_unit: r.support_unit ?? r.support_unit_name ?? null,
      scores: r.scores || {},
    }))
  } catch {
    loadError.value = true
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  fetchRankings()
}

onMounted(() => {
  fetchRankings()
})
</script>

<style scoped>
.rankings-page {
  padding: 20px;
}

.page-header {
  margin-bottom: 20px;
}

.page-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.page-desc {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--color-text-secondary);
}

.filter-card {
  background: white;
  border-radius: 8px;
  padding: 16px 20px 4px;
  margin-bottom: 20px;
  border: 1px solid var(--color-border);
}

.state-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 0;
  color: var(--color-text-secondary);
}

.table-card {
  background: white;
  border-radius: 8px;
  padding: 20px;
  border: 1px solid var(--color-border);
}

.rank-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  font-weight: 700;
  font-size: 13px;
  background: var(--color-border-lighter);
  color: var(--color-text-secondary);
}

.rank-gold {
  background: linear-gradient(135deg, var(--color-warning-lighter), var(--color-warning));
  color: #fff;
}

.rank-silver {
  background: linear-gradient(135deg, var(--color-border), var(--color-text-secondary));
  color: #fff;
}

.rank-bronze {
  background: linear-gradient(135deg, var(--color-danger-lighter), var(--color-danger));
  color: #fff;
}

.score-bar-wrapper {
  display: flex;
  align-items: center;
  gap: 8px;
}

.score-bar {
  flex: 1;
  height: 8px;
  background: var(--color-border-lighter);
  border-radius: 4px;
  overflow: hidden;
}

.score-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--color-success-dark), var(--color-success));
  border-radius: 4px;
  transition: width 0.5s ease;
}

.score-text {
  font-weight: 600;
  color: var(--color-text-primary);
  min-width: 42px;
  text-align: right;
  font-size: 13px;
}
</style>
