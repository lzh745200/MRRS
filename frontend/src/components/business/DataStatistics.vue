<template>
  <div class="data-statistics">
    <el-row :gutter="20">
      <el-col v-for="item in items" :key="item.label" :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value">{{ item.value }}</div>
          <div class="stat-label">{{ item.label }}</div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  items: { label: string; value: string | number }[]
}>()
</script>

<style scoped>
.stat-card {
  text-align: center;
}
.stat-value {
  font-size: 28px;
  font-weight: bold;
  color: var(--color-primary-light-1);
}
.stat-label {
  font-size: 14px;
  color: var(--color-text-secondary);
  margin-top: 8px;
}
</style>
