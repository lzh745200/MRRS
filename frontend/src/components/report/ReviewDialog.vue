<template>
  <el-dialog :model-value="visible" title="审核" width="480px" @update:model-value="$emit('close')"
    ><el-form
      ><el-form-item label="审核意见"
        ><el-input v-model="comment" type="textarea" /></el-form-item></el-form
    ><template #footer
      ><el-button @click="$emit('close')">取消</el-button
      ><el-button type="primary" @click="$emit('approve', comment)">通过</el-button
      ><el-button type="danger" @click="$emit('reject', comment)">驳回</el-button></template
    ></el-dialog
  >
</template>
<script setup lang="ts">
import { ref } from 'vue'
defineProps<{ visible: boolean }>()
defineEmits<{
  (e: 'close'): void
  (e: 'approve', c: string): void
  (e: 'reject', c: string): void
}>()
const comment = ref('')
</script>
