<template>
  <a href="#main-content" class="skip-link" @click.prevent="handleSkip"> 跳转到主要内容 </a>
</template>

<script setup lang="ts">
import { useSkipLink } from '@/composables/useAccessibility'

const { skipToMainContent } = useSkipLink()

const handleSkip = () => {
  skipToMainContent()
}
</script>

<style scoped>
.skip-link {
  position: absolute;
  top: -40px;
  left: 0;
  background: var(--color-primary);
  color: white;
  padding: 8px 16px;
  text-decoration: none;
  font-size: 14px;
  z-index: 10000;
  border-radius: 0 0 4px 0;
  transition: top 0.2s;
}

.skip-link:focus {
  top: 0;
  outline: 2px solid var(--color-bg-card);
  outline-offset: 2px;
}
</style>
