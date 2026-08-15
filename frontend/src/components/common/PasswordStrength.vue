<template>
  <div class="password-strength">
    <span :class="['strength-badge', `strength-${level}`]">
      {{ text }}
    </span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  passwordStrength?: string
}

const props = defineProps<Props>()

const level = computed(() => {
  const strength = (props.passwordStrength ?? '').toLowerCase()
  if (strength === 'weak' || strength === '弱') return 'weak'
  if (strength === 'medium' || strength === '中') return 'medium'
  if (strength === 'strong' || strength === '强') return 'strong'
  return 'none'
})

const text = computed(() => {
  switch (level.value) {
    case 'weak':
      return '弱'
    case 'medium':
      return '中'
    case 'strong':
      return '强'
    default:
      return '未设置'
  }
})
</script>

<style scoped>
.password-strength {
  display: inline-block;
}

.strength-badge {
  padding: 4px 12px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.strength-none {
  background-color: #f0f0f0;
  color: #999;
}

.strength-weak {
  background-color: var(--color-danger-lightest);
  color: var(--color-danger);
}

.strength-medium {
  background-color: var(--color-warning-lightest);
  color: var(--color-warning);
}

.strength-strong {
  background-color: var(--color-primary-light-8);
  color: var(--color-success);
}
</style>
