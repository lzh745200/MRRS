<template>
  <div class="not-found">
    <div class="error-content">
      <div class="error-code">404</div>
      <div class="error-message">页面未找到</div>
      <div class="error-description">抱歉，您访问的页面不存在或已被移除</div>
      <el-button type="primary" @click="goHome"> 返回首页 </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouterSafe } from '@/composables/useRouterSafe'

const { pushSafe } = useRouterSafe()

const goHome = () => {
  pushSafe('/')
}
</script>

<style scoped>
.not-found {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 20px;
}

.error-content {
  text-align: center;
  color: white;
}

.error-code {
  font-size: 120px;
  font-weight: bold;
  margin-bottom: 20px;
  text-shadow: 2px 2px 4px var(--color-black-30);
}

.error-message {
  font-size: 32px;
  margin-bottom: 16px;
  font-weight: 500;
}

.error-description {
  font-size: 18px;
  margin-bottom: 32px;
  opacity: 0.9;
}
</style>
