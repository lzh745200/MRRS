<template>
  <div class="page-header">
    <div class="header-left">
      <h1 class="welcome-text">
        欢迎回来，<span class="welcome-name">{{ displayName }}</span>
      </h1>
      <p class="current-date">{{ formattedDate }}</p>
    </div>
    <div class="header-actions">
      <!-- 全局搜索 -->
      <GlobalSearch class="header-search" />
      <el-button
        data-test="btn-new-project"
        type="primary"
        :icon="Plus"
        @click="pushSafe('/projects/create')"
      >
        新建项目
      </el-button>
      <el-button data-test="btn-analysis" :icon="TrendCharts" @click="pushSafe('/data-analysis')">
        数据分析
      </el-button>
      <el-button
        v-if="isAdmin"
        data-test="btn-backup"
        :icon="Upload"
        :loading="backingUp"
        @click="handleBackup"
      >
        {{ backingUp ? '备份中...' : '一键备份' }}
      </el-button>
      <!-- 更多菜单 -->
      <el-dropdown trigger="click" @command="handleMoreCommand">
        <el-button :icon="MoreFilled" />
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="layout">
              <el-icon><Grid /></el-icon> 自定义布局
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouterSafe } from '@/composables/useRouterSafe'
import { useAuthStore } from '@/stores/auth'
import { Plus, TrendCharts, Upload, MoreFilled, Grid } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { post } from '@/api/request'
import GlobalSearch from './components/GlobalSearch.vue'

const emit = defineEmits<{
  (e: 'toggle-layout'): void
  (e: 'backup-complete'): void
}>()

const { pushSafe } = useRouterSafe()
const authStore = useAuthStore()
const backingUp = ref(false)

const displayName = computed(
  () => authStore.user?.full_name || authStore.user?.username || '管理员'
)

const isAdmin = computed(() => authStore.user?.role === 'admin' || authStore.user?.is_superuser)

const formattedDate = computed(() => {
  const now = new Date()
  const weekDays = ['日', '一', '二', '三', '四', '五', '六']
  return `${now.getFullYear()}年${now.getMonth() + 1}月${now.getDate()}日 周${weekDays[now.getDay()]}`
})

async function handleBackup() {
  backingUp.value = true
  try {
    await post('/system/backup', {
      description: '主页手动备份',
      include_uploads: true,
    })
    ElMessage.success('备份创建成功')
    emit('backup-complete')
  } catch {
    ElMessage.error('备份失败')
  } finally {
    backingUp.value = false
  }
}

function handleMoreCommand(cmd: string) {
  if (cmd === 'layout') {
    emit('toggle-layout')
  }
}
</script>

<style scoped lang="scss">
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 0 16px 0;
}

.header-left {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.welcome-text {
  font-size: 22px;
  font-weight: 700;
  color: #1e293b;
  margin: 0;
}

.welcome-name {
  color: #d4af37;
}

.current-date {
  font-size: 14px;
  color: #64748b;
  margin: 0;
}

.header-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.header-search {
  width: 320px;
  flex-shrink: 0;
}

@media (max-width: 768px) {
  .header-search {
    display: none;
  }
}
</style>
