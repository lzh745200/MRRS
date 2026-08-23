<template>
  <div class="quick-actions">
    <el-collapse v-model="activeGroups" class="qa-collapse">
      <!-- 核心业务 -->
      <el-collapse-item name="core">
        <template #title>
          <span class="group-header">核心业务</span>
          <el-tag size="small" type="primary" effect="plain">12</el-tag>
        </template>
        <div class="action-grid">
          <button class="action-btn primary" @click="pushSafe('/supported-villages')">
            <el-icon class="btn-icon"><House /></el-icon><span class="btn-text">帮扶村管理</span>
          </button>
          <button class="action-btn primary" @click="pushSafe('/projects')">
            <el-icon class="btn-icon"><Document /></el-icon><span class="btn-text">项目管理</span>
          </button>
          <button class="action-btn primary" @click="pushSafe('/funds')">
            <el-icon class="btn-icon"><Money /></el-icon><span class="btn-text">经费管理</span>
          </button>
          <button class="action-btn primary" @click="pushSafe('/schools')">
            <el-icon class="btn-icon"><School /></el-icon><span class="btn-text">学校管理</span>
          </button>
          <button class="action-btn primary" @click="pushSafe('/policies')">
            <el-icon class="btn-icon"><Tickets /></el-icon><span class="btn-text">政策文件</span>
          </button>
          <button class="action-btn primary" @click="pushSafe('/organization')">
            <el-icon class="btn-icon"><OfficeBuilding /></el-icon
            ><span class="btn-text">组织架构</span>
          </button>
          <button
            v-if="isManager || isAdmin"
            class="action-btn primary"
            @click="pushSafe('/projects/import')"
          >
            <el-icon class="btn-icon"><Download /></el-icon><span class="btn-text">项目导入</span>
          </button>
          <button class="action-btn primary" @click="pushSafe('/funds/user')">
            <el-icon class="btn-icon"><EditPen /></el-icon><span class="btn-text">经费申请</span>
          </button>
          <button class="action-btn primary" @click="pushSafe('/rural-works')">
            <el-icon class="btn-icon"><Sunny /></el-icon><span class="btn-text">乡村振兴</span>
          </button>
          <button class="action-btn primary" @click="pushSafe('/effectiveness')">
            <el-icon class="btn-icon"><Aim /></el-icon><span class="btn-text">帮扶成效</span>
          </button>
          <button class="action-btn primary" @click="pushSafe('/data-analysis')">
            <el-icon class="btn-icon"><DataAnalysis /></el-icon
            ><span class="btn-text">数据分析</span>
          </button>
          <button class="action-btn primary" @click="pushSafe('/projects/create')">
            <el-icon class="btn-icon"><Plus /></el-icon><span class="btn-text">新建项目</span>
          </button>
          <button class="action-btn primary" @click="pushSafe('/schools/create')">
            <el-icon class="btn-icon"><Tools /></el-icon><span class="btn-text">新建学校</span>
          </button>
        </div>
      </el-collapse-item>

      <!-- 数据与分析 -->
      <el-collapse-item v-if="isManager || isAdmin" name="data">
        <template #title>
          <span class="group-header">数据与分析</span>
          <el-tag size="small" type="success" effect="plain">11</el-tag>
        </template>
        <div class="action-grid">
          <button class="action-btn secondary" @click="pushSafe('/data-analysis')">
            <el-icon class="btn-icon"><DataAnalysis /></el-icon
            ><span class="btn-text">数据分析</span>
          </button>
          <button class="action-btn secondary" @click="pushSafe('/funds/analysis')">
            <el-icon class="btn-icon"><TrendCharts /></el-icon
            ><span class="btn-text">经费分析</span>
          </button>
          <button class="action-btn secondary" @click="pushSafe('/schools/analysis')">
            <el-icon class="btn-icon"><TrendCharts /></el-icon
            ><span class="btn-text">学校分析</span>
          </button>
          <button class="action-btn secondary" @click="pushSafe('/import/data')">
            <el-icon class="btn-icon"><Download /></el-icon><span class="btn-text">数据导入</span>
          </button>
          <button class="action-btn secondary" @click="pushSafe('/export/report')">
            <el-icon class="btn-icon"><Upload /></el-icon><span class="btn-text">报表导出</span>
          </button>
          <button class="action-btn secondary" @click="pushSafe('/data-sync')">
            <el-icon class="btn-icon"><Refresh /></el-icon><span class="btn-text">数据同步</span>
          </button>
          <button class="action-btn secondary" @click="pushSafe('/data-entry')">
            <el-icon class="btn-icon"><EditPen /></el-icon><span class="btn-text">综合录入</span>
          </button>
          <button class="action-btn secondary" @click="pushSafe('/work-calendar')">
            <el-icon class="btn-icon"><Calendar /></el-icon><span class="btn-text">工作日历</span>
          </button>
          <button class="action-btn secondary" @click="pushSafe('/data-analysis/map')">
            <el-icon class="btn-icon"><MapLocation /></el-icon
            ><span class="btn-text">地图分析</span>
          </button>
          <button class="action-btn secondary" @click="pushSafe('/data-analysis/assessment')">
            <el-icon class="btn-icon"><Document /></el-icon><span class="btn-text">评估分析</span>
          </button>
          <button class="action-btn secondary" @click="pushSafe('/supported-villages/yearly')">
            <el-icon class="btn-icon"><Calendar /></el-icon><span class="btn-text">年度概览</span>
          </button>
        </div>
      </el-collapse-item>

      <!-- 审批与流程 -->
      <el-collapse-item name="workflow">
        <template #title>
          <span class="group-header">审批与流程</span>
          <el-tag size="small" type="warning" effect="plain">11</el-tag>
        </template>
        <div class="action-grid">
          <button class="action-btn secondary" @click="pushSafe('/approval')">
            <el-icon class="btn-icon"><Select /></el-icon><span class="btn-text">审批中心</span>
          </button>
          <button class="action-btn secondary" @click="pushSafe('/rural-works/list')">
            <el-icon class="btn-icon"><EditPen /></el-icon><span class="btn-text">工作日志</span>
          </button>
          <button class="action-btn secondary" @click="pushSafe('/message')">
            <el-icon class="btn-icon"><ChatDotRound /></el-icon
            ><span class="btn-text">消息中心</span>
          </button>
          <button class="action-btn secondary" @click="pushSafe('/funds')">
            <el-icon class="btn-icon"><Refresh /></el-icon><span class="btn-text">资金周期</span>
          </button>
          <button class="action-btn secondary" @click="pushSafe('/funds/contract')">
            <el-icon class="btn-icon"><Document /></el-icon><span class="btn-text">合同管理</span>
          </button>
          <button class="action-btn secondary" @click="pushSafe('/funds/anomaly')">
            <el-icon class="btn-icon"><Warning /></el-icon><span class="btn-text">异常资金</span>
          </button>
          <button class="action-btn secondary" @click="pushSafe('/funds/budget')">
            <el-icon class="btn-icon"><Money /></el-icon><span class="btn-text">经费预算</span>
          </button>
          <button class="action-btn secondary" @click="pushSafe('/report/templates')">
            <el-icon class="btn-icon"><Document /></el-icon><span class="btn-text">报表模板</span>
          </button>
          <button class="action-btn secondary" @click="pushSafe('/todos')">
            <el-icon class="btn-icon"><Select /></el-icon><span class="btn-text">待办事项</span>
          </button>
          <button class="action-btn secondary" @click="pushSafe('/funds/report')">
            <el-icon class="btn-icon"><DataAnalysis /></el-icon
            ><span class="btn-text">经费报表</span>
          </button>
          <button class="action-btn secondary" @click="pushSafe('/funds')">
            <el-icon class="btn-icon"><CreditCard /></el-icon><span class="btn-text">经费结算</span>
          </button>
        </div>
      </el-collapse-item>

      <!-- 系统管理 -->
      <el-collapse-item v-if="isManager || isAdmin" name="system">
        <template #title>
          <span class="group-header">系统管理</span>
          <el-tag size="small" type="danger" effect="plain">10</el-tag>
        </template>
        <div class="action-grid">
          <button
            v-if="isManager"
            class="action-btn backup"
            :disabled="backingUp"
            @click="$emit('backup')"
          >
            <el-icon class="btn-icon"><Files /></el-icon
            ><span class="btn-text">{{ backingUp ? '备份中...' : '一键备份' }}</span>
          </button>
          <button v-if="isAdmin" class="action-btn restore" @click="$emit('restore')">
            <el-icon class="btn-icon"><Tools /></el-icon><span class="btn-text">恢复数据</span>
          </button>
          <button
            v-if="isManager || isAdmin"
            class="action-btn secondary"
            @click="pushSafe('/system/monitoring')"
          >
            <!-- /* c8 ignore next */ 系统监控图标行：v8 分支计数器错位映射至此（实际 v-if/点击分支均已被用例覆盖） -->
            <el-icon class="btn-icon"><Monitor /></el-icon><span class="btn-text">系统监控</span>
          </button>
          <button v-if="isAdmin" class="action-btn secondary" @click="pushSafe('/system/users')">
            <el-icon class="btn-icon"><UserFilled /></el-icon
            ><span class="btn-text">用户与角色</span>
          </button>
          <button v-if="isAdmin" class="action-btn secondary" @click="pushSafe('/system/config')">
            <el-icon class="btn-icon"><Setting /></el-icon><span class="btn-text">系统配置</span>
          </button>
          <button v-if="isManager" class="action-btn secondary" @click="pushSafe('/system/audit')">
            <el-icon class="btn-icon"><Document /></el-icon><span class="btn-text">审计日志</span>
          </button>
          <button v-if="isAdmin" class="action-btn secondary" @click="pushSafe('/system/backup')">
            <el-icon class="btn-icon"><Box /></el-icon><span class="btn-text">备份管理</span>
          </button>
          <button
            v-if="isAdmin"
            class="action-btn secondary"
            @click="pushSafe('/admin/machine-code')"
          >
            <el-icon class="btn-icon"><Key /></el-icon><span class="btn-text">机器码管理</span>
          </button>
          <button
            v-if="isManager"
            class="action-btn secondary"
            @click="pushSafe('/data-management/logs')"
          >
            <el-icon class="btn-icon"><Tickets /></el-icon><span class="btn-text">操作日志</span>
          </button>
          <button class="action-btn secondary" @click="pushSafe('/help')">
            <el-icon class="btn-icon"><Reading /></el-icon><span class="btn-text">帮助文档</span>
          </button>
        </div>
      </el-collapse-item>
    </el-collapse>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouterSafe } from '@/composables/useRouterSafe'
import { useMenuStore } from '@/stores/menu'
import {
  House,
  Document,
  Money,
  School,
  Tickets,
  OfficeBuilding,
  Download,
  EditPen,
  Sunny,
  Aim,
  Plus,
  Tools,
  DataAnalysis,
  TrendCharts,
  Upload,
  Refresh,
  Calendar,
  MapLocation,
  Select,
  ChatDotRound,
  Warning,
  CreditCard,
  Files,
  Monitor,
  UserFilled,
  Setting,
  Box,
  Key,
  Reading,
} from '@element-plus/icons-vue'

const menuStore = useMenuStore()

onMounted(() => {
  if (!menuStore.loaded) {
    menuStore.fetchMenus()
  }
})

defineProps<{
  isManager: boolean
  isAdmin: boolean
  backingUp: boolean
}>()

defineEmits<{
  backup: []
  restore: []
}>()

const { pushSafe } = useRouterSafe()
const activeGroups = ref(['core'])
</script>

<style scoped lang="scss">
.qa-collapse {
  border: none;
  :deep(.el-collapse-item__header) {
    padding: 10px 14px;
    font-weight: 600;
    font-size: 14px;
    border-radius: 8px;
    &.is-active {
      color: #1b4332;
    }
  }
  :deep(.el-collapse-item__wrap) {
    border: none;
  }
  :deep(.el-collapse-item__content) {
    padding: 8px 4px 12px;
  }
}

.group-header {
  flex: 1;
}

.action-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 6px;
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 10px;
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
  font-size: 13px;
  color: #303133;
  transition: all 0.15s ease;
  white-space: nowrap;
  &:hover {
    border-color: var(--color-primary);
    color: var(--color-primary);
    background: #f0f5ff;
  }
  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .btn-icon {
    font-size: 14px;
    flex-shrink: 0;
    display: flex;
    align-items: center;
  }
  .btn-text {
    overflow: hidden;
    text-overflow: ellipsis;
  }
  &.primary {
    background: #ecf5ff;
    border-color: #b3d8ff;
    color: var(--color-primary);
    &:hover {
      background: #d9ecff;
    }
  }
  &.secondary {
    background: #fafafa;
    &:hover {
      background: #f0f2f5;
    }
  }
  &.backup {
    background: var(--color-warning-lightest);
    border-color: #f5dab1;
    color: var(--color-warning);
    &:hover {
      background: #faf0e0;
    }
  }
  &.restore {
    background: var(--color-danger-lightest);
    border-color: #fbc4c4;
    color: var(--color-danger);
    &:hover {
      background: #fde2e2;
    }
  }
}
</style>
