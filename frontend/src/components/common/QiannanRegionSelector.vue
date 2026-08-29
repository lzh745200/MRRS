<template>
  <div class="qiannan-region-selector">
    <el-row :gutter="12">
      <!-- 省份 (固定值) -->
      <el-col :span="8">
        <el-form-item
          :label="showLabels ? '省份' : ''"
          :label-width="showLabels ? labelWidth : '0'"
        >
          <el-input :model-value="province" disabled :placeholder="provincePlaceholder" />
        </el-form-item>
      </el-col>

      <!-- 州/市 (固定值) -->
      <el-col :span="8">
        <el-form-item
          :label="showLabels ? '州/市' : ''"
          :label-width="showLabels ? labelWidth : '0'"
        >
          <el-input :model-value="city" disabled :placeholder="cityPlaceholder" />
        </el-form-item>
      </el-col>

      <!-- 县/市 (可选择) -->
      <el-col :span="8">
        <el-form-item
          :label="showLabels ? '县/市' : ''"
          :label-width="showLabels ? labelWidth : '0'"
        >
          <el-select
            :model-value="modelValue"
            :disabled="disabled"
            :placeholder="countyPlaceholder"
            :clearable="clearable"
            style="width: 100%"
            @update:model-value="handleCountyChange"
          >
            <el-option
              v-for="county in QIANNAN_COUNTIES"
              :key="county"
              :label="county"
              :value="county"
            />
          </el-select>
        </el-form-item>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
/**
 * 黔南州地区选择器组件
 *
 * 限定地区范围为贵州省黔南布依族苗族自治州的12个县市
 *
 * Feature: supported-village-enhancement
 * Requirements: 16.1, 16.2, 16.3
 */

import { QIANNAN_COUNTIES, DEFAULT_PROVINCE, DEFAULT_PREFECTURE } from '@/data/guizhouRegion'

interface Props {
  /** 选中的县/市值 */
  modelValue?: string
  /** 是否禁用 */
  disabled?: boolean
  /** 是否可清空 */
  clearable?: boolean
  /** 是否显示标签 */
  showLabels?: boolean
  /** 标签宽度 */
  labelWidth?: string
  /** 省份占位符 */
  provincePlaceholder?: string
  /** 州/市占位符 */
  cityPlaceholder?: string
  /** 县/市占位符 */
  countyPlaceholder?: string
}

withDefaults(defineProps<Props>(), {
  modelValue: '',
  disabled: false,
  clearable: true,
  showLabels: true,
  labelWidth: '60px',
  provincePlaceholder: '贵州省',
  cityPlaceholder: '黔南布依族苗族自治州',
  countyPlaceholder: '请选择县/市',
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'change', value: string): void
}>()

/** 固定的省份值 */
const province = DEFAULT_PROVINCE

/** 固定的州/市值 */
const city = DEFAULT_PREFECTURE

/**
 * 处理县/市选择变化
 * Requirements: 16.3
 */
function handleCountyChange(value: string) {
  emit('update:modelValue', value)
  emit('change', value)
}
</script>

<style scoped lang="scss">
.qiannan-region-selector {
  width: 100%;

  :deep(.el-form-item) {
    margin-bottom: 0;
  }

  :deep(.el-input.is-disabled .el-input__inner) {
    background-color: var(--el-fill-color-light);
    color: var(--el-text-color-regular);
  }
}
</style>
