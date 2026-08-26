<template>
  <div class="rural-works-index">
    <el-tabs
      v-model="activeTab"
      type="border-card"
      class="rural-works-tabs"
      @tab-change="handleTabChange"
    >
      <el-tab-pane label="工作列表" name="list">
        <RuralWorkList />
      </el-tab-pane>
      <el-tab-pane label="任务分配" name="task">
        <RuralWorkTask />
      </el-tab-pane>
      <el-tab-pane label="数据分析" name="analysis">
        <RuralWorkAnalysis v-if="tabLoaded.analysis" />
      </el-tab-pane>
      <el-tab-pane label="工作报告" name="report">
        <RuralWorkReport v-if="tabLoaded.report" />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRoute } from 'vue-router'
import RuralWorkList from './List.vue'
import RuralWorkTask from './Task.vue'
import RuralWorkAnalysis from './Analysis.vue'
import RuralWorkReport from './Report.vue'

const route = useRoute()

// 根据路由参数决定默认标签
const tabMap: Record<string, string> = {
  tasks: 'task',
  analysis: 'analysis',
  report: 'report',
}
const initialTab = (route.query.tab as string) || 'list'
const activeTab = ref(tabMap[initialTab] || initialTab)

// 懒加载标记：分析和报告含 Chart.js，切换到时才加载
const tabLoaded = reactive({
  analysis: activeTab.value === 'analysis',
  report: activeTab.value === 'report',
})

function handleTabChange(name: string | number) {
  const tab = String(name)
  if (tab === 'analysis') tabLoaded.analysis = true
  if (tab === 'report') tabLoaded.report = true
}
</script>

<style lang="scss" scoped>
.rural-works-index {
  padding: 16px;
}

.rural-works-tabs {
  border-radius: 4px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.rural-works-tabs :deep(.el-tabs__header) {
  background: linear-gradient(
    135deg,
    var(--color-primary-dark-2) 0%,
    var(----color-primary-dark-1) 100%
  );
  border-bottom: 2px solid var(--color-accent-gold);
  margin: 0;
}

.rural-works-tabs :deep(.el-tabs__item) {
  color: rgba(255, 255, 255, 0.7);
  font-size: 15px;
  font-weight: 500;
  padding: 0 24px;
  height: 48px;
  line-height: 48px;
}

.rural-works-tabs :deep(.el-tabs__item:hover) {
  color: var(--color-accent-gold);
}

.rural-works-tabs :deep(.el-tabs__item.is-active) {
  color: var(--color-accent-gold);
  background: rgba(212, 175, 55, 0.12);
}

.rural-works-tabs :deep(.el-tabs__content) {
  padding: 0;
}
</style>
