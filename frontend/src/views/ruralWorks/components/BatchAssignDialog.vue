<template>
  <el-dialog
    :model-value="modelValue"
    append-to-body
    title="批量分配任务"
    :width="DIALOG_SM"
    class="batch-assign-dialog"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <div class="batch-assign-content">
      <p class="batch-assign-count">已选择 {{ selectedCount }} 个任务</p>
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="100px"
        class="batch-assign-form"
      >
        <el-form-item label="负责人" prop="assigneeId">
          <el-select
            :model-value="form.assigneeId"
            placeholder="请选择负责人"
            @update:model-value="emit('update:assigneeId', $event)"
          >
            <el-option
              v-for="person in staff"
              :key="person.id"
              :label="person.name"
              :value="person.id"
            >
              <div class="select-assignee-item">
                <el-avatar :size="24" :src="person.avatar" :alt="person.name">
                  {{ person.name[0] }}
                </el-avatar>
                <span>{{ person.name }} - {{ person.position }}</span>
              </div>
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="分配说明">
          <el-input
            :model-value="form.note"
            type="textarea"
            placeholder="请输入分配说明（可选）"
            :rows="3"
            maxlength="200"
            show-word-limit
            @update:model-value="emit('update:note', $event)"
          />
        </el-form-item>
      </el-form>
    </div>
    <template #footer>
      <span class="dialog-footer">
        <el-button @click="emit('update:modelValue', false)">取消</el-button>
        <el-button type="primary" :disabled="selectedCount === 0" @click="emit('confirm')"
          >确认分配</el-button
        >
      </span>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
/**
 * 批量分配对话框（W5-T10 自 ruralWorks/Task.vue 拆出）。
 *
 * 搬走的只有模板与 el-form 实例：勾选集合 `selectedTasks`、人员列表、表单对象
 * `batchAssignForm`、批量改写任务负责人的逻辑（`confirmBatchAssign`）全部留在父组件。
 * 子组件通过 `defineExpose({ validate })` 把 el-form 校验转发给父组件，父组件里
 * `if (!batchAssignFormRef.value) return` + `await batchAssignFormRef.value.validate()`
 * 与拆分前逐字一致（ref 现在指向本组件）。
 */
import { ref } from 'vue'
import type { FormInstance } from 'element-plus'
import { DIALOG_SM } from '@/config/dialog'

interface Staff {
  id: string
  name: string
  position: string
  avatar?: string
}

interface AssignForm {
  assigneeId: string
  note: string
}

defineProps<{
  modelValue: boolean
  selectedCount: number
  staff: Staff[]
  form: AssignForm
  rules: Record<string, any[]>
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', visible: boolean): void
  (e: 'update:assigneeId', value: string): void
  (e: 'update:note', value: string): void
  (e: 'confirm'): void
}>()

const formRef = ref<FormInstance>()

/** 校验转发（无分支：el-form 由本组件模板固定渲染，实例必然存在） */
function validate() {
  return (formRef.value as FormInstance).validate()
}

defineExpose({ validate })
</script>

<style lang="scss" scoped>
.dialog-footer {
  text-align: right;
}

.batch-assign-form {
  .select-assignee-item {
    display: flex;
    align-items: center;
    gap: 8px;
  }
}

.batch-assign-content {
  .batch-assign-count {
    margin-bottom: 20px;
    font-size: 16px;
    color: $military-dark;
    font-weight: 500;
  }
}
</style>
