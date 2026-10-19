/** * 外观设置面板（v1.15.0 / W23） * * 统一入口：字号档 / 密度档 / 高对比 / 简化模式（useUiPrefs）+
主题（configStore）。 * 顶栏用户下拉与系统设置均可打开；所有改动即时生效并持久化。 */
<script setup lang="ts">
import { computed } from 'vue'
import { ElMessage } from 'element-plus'

import { useUiPrefs } from '@/composables/useUiPrefs'
import { THEME_OPTIONS, DEFAULT_THEME, useConfigStore } from '@/stores/config'

const configStore = useConfigStore()
const { prefs, setPrefs, resetPrefs } = useUiPrefs()

const themeOptions = computed(() => THEME_OPTIONS)
const currentTheme = computed({
  get: () => configStore.theme,
  set: (value: string) => configStore.setTheme(value),
})

function onFontSize(value: string | number | boolean | undefined) {
  setPrefs({ fontSize: String(value) as 'compact' | 'standard' | 'large' })
}

function onDensity(value: string | number | boolean | undefined) {
  setPrefs({ density: String(value) as 'comfortable' | 'compact' })
}

function onContrast(value: boolean | string | number) {
  setPrefs({ contrast: value ? 'high' : 'normal' })
}

function onSimplify(value: boolean | string | number) {
  setPrefs({ simplify: Boolean(value) })
}

function onReset() {
  resetPrefs()
  configStore.setTheme(DEFAULT_THEME)
  ElMessage.success('已恢复默认外观')
}
</script>

<template>
  <div class="appearance-settings" data-testid="appearance-settings">
    <div class="appearance-row" data-testid="appearance-theme-row">
      <span class="appearance-label">主题</span>
      <el-select
        v-model="currentTheme"
        size="small"
        class="appearance-control"
        data-testid="appearance-theme"
      >
        <el-option v-for="t in themeOptions" :key="t.value" :label="t.label" :value="t.value" />
      </el-select>
    </div>

    <div class="appearance-row" data-testid="appearance-font-row">
      <span class="appearance-label">字号</span>
      <el-radio-group
        :model-value="prefs.fontSize"
        size="small"
        data-testid="appearance-font-size"
        @update:model-value="onFontSize"
      >
        <el-radio-button value="compact" data-testid="font-compact">紧凑</el-radio-button>
        <el-radio-button value="standard" data-testid="font-standard">标准</el-radio-button>
        <el-radio-button value="large" data-testid="font-large">大号</el-radio-button>
      </el-radio-group>
    </div>

    <div class="appearance-row" data-testid="appearance-density-row">
      <span class="appearance-label">密度</span>
      <el-radio-group
        :model-value="prefs.density"
        size="small"
        data-testid="appearance-density"
        @update:model-value="onDensity"
      >
        <el-radio-button value="comfortable" data-testid="density-comfortable">
          舒适
        </el-radio-button>
        <el-radio-button value="compact" data-testid="density-compact">紧凑</el-radio-button>
      </el-radio-group>
    </div>

    <div class="appearance-row" data-testid="appearance-contrast-row">
      <span class="appearance-label">高对比</span>
      <el-switch
        :model-value="prefs.contrast === 'high'"
        size="small"
        data-testid="appearance-contrast"
        @change="onContrast"
      />
    </div>

    <div class="appearance-row" data-testid="appearance-simplify-row">
      <span class="appearance-label">简化模式</span>
      <el-switch
        :model-value="prefs.simplify"
        size="small"
        data-testid="appearance-simplify"
        @change="onSimplify"
      />
      <span class="appearance-hint">隐藏趋势箭头/辅助说明/高级字段</span>
    </div>

    <div class="appearance-footer">
      <el-button size="small" data-testid="appearance-reset" @click="onReset">恢复默认</el-button>
    </div>
  </div>
</template>

<style scoped>
.appearance-settings {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
  padding: var(--spacing-xs) 0;
  min-width: 320px;
}

.appearance-row {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.appearance-label {
  width: 64px;
  flex: none;
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
}

.appearance-control {
  width: 160px;
}

.appearance-hint {
  color: var(--color-text-placeholder);
  font-size: var(--font-size-xs);
}

.appearance-footer {
  display: flex;
  justify-content: flex-end;
  padding-top: var(--spacing-xs);
  border-top: 1px solid var(--color-border-lighter);
}
</style>
