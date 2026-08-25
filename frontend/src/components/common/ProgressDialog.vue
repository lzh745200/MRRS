<template>
  <el-dialog
    :model-value="visible"
    :title="`项目进度汇报 - ${projectName}`"
    width="720px"
    :before-close="handleClose"
    @update:model-value="$emit('update:visible', $event)"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
      <el-form-item label="进度百分比" prop="progress_percentage">
        <el-input-number
          v-model="form.progress_percentage"
          :min="0"
          :max="100"
          controls-position="right"
          style="width: 200px"
        >
          <template #append>%</template>
        </el-input-number>
      </el-form-item>

      <el-form-item label="进度描述" prop="description">
        <el-input
          v-model="form.description"
          type="textarea"
          :rows="4"
          placeholder="请描述当前项目进展情况"
        />
      </el-form-item>

      <el-form-item label="面临困难">
        <el-input
          v-model="form.challenges"
          type="textarea"
          :rows="3"
          placeholder="请描述项目推进中遇到的困难"
        />
      </el-form-item>

      <el-form-item label="下一步计划">
        <el-input
          v-model="form.next_steps"
          type="textarea"
          :rows="3"
          placeholder="请描述下一步的工作计划"
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button type="primary" :loading="loading" @click="handleSubmit"> 提交 </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, watch } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { useProjectStore } from '@/stores/project'

// 定义项目进度创建接口
interface ProjectProgressCreate {
  project_id: number
  progress_percentage: number
  description: string
  challenges?: string
  next_steps?: string
}

interface Props {
  projectId: number
  projectName?: string
  visible: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{
  'update:visible': [value: boolean]
  close: []
  success: []
}>()

const projectStore = useProjectStore()
const formRef = ref<FormInstance>()
const loading = ref(false)

const form = reactive<Omit<ProjectProgressCreate, 'project_id'>>({
  progress_percentage: 0,
  description: '',
  challenges: '',
  next_steps: '',
})

const rules: FormRules = {
  progress_percentage: [
    { required: true, message: '请输入进度百分比', trigger: 'blur' },
    {
      type: 'number',
      min: 0,
      max: 100,
      message: '进度必须在 0-100 之间',
      trigger: 'blur',
    },
  ],
  description: [
    { required: true, message: '请输入进度描述', trigger: 'blur' },
    { min: 10, message: '进度描述至少10个字符', trigger: 'blur' },
  ],
}

watch(
  () => props.visible,
  (newVal) => {
    if (newVal) {
      // 重置表单
      Object.assign(form, {
        progress_percentage: 0,
        description: '',
        challenges: '',
        next_steps: '',
      })
    }
  }
)

const handleClose = () => {
  emit('close')
}

const handleSubmit = async () => {
  /* c8 ignore next */ // formRef 由模板 ref 绑定, 渲染后恒存在
  if (!formRef.value) return

  const valid = await formRef.value.validate()
  if (!valid) return

  loading.value = true
  try {
    await (projectStore as any).addProjectProgress({
      project_id: props.projectId,
      ...form,
    })
    ElMessage.success('进度汇报成功')
    emit('success')
    handleClose()
  } catch (error) {
    // 错误已在store中处理
  } finally {
    loading.value = false
  }
}
</script>
