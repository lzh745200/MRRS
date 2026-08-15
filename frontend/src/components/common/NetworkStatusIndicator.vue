<template>
  <span
    class="net-dot"
    :class="{ online, offline: !online }"
    :title="online ? '在线' : '离线'"
  ></span>
</template>
<script setup lang="ts">
defineProps<{ online?: boolean }>()
</script>
<style scoped>
.net-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.online {
  background: var(--color-success);
}
.offline {
  background: var(--color-danger);
}
</style>
