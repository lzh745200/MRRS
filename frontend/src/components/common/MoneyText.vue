<template>
  <span class="money-text">{{ displayText }}</span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { formatMoneyText, MONEY_PLACEHOLDER } from '@/utils/money'

interface Props {
  /** 金额数值（null / undefined / 空串显示占位符） */
  value?: number | string | null
  /** 单位后缀，如 `万元` */
  unit?: string
  /** 空值占位文案 */
  placeholder?: string
  /** 是否展示人民币大写 */
  uppercase?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  value: null,
  unit: '',
  placeholder: MONEY_PLACEHOLDER,
  uppercase: false,
})

const displayText = computed(() =>
  formatMoneyText(props.value, {
    unit: props.unit,
    placeholder: props.placeholder,
    uppercase: props.uppercase,
  })
)
</script>
