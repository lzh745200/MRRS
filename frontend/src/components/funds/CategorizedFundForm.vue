<template>
  <div class="categorized-fund-form">
    <el-form
      ref="formRef"
      :model="formData"
      :rules="rules"
      label-width="140px"
      label-position="top"
    >
      <!-- 年份选择 -->
      <el-form-item label="数据年份" prop="year">
        <el-select v-model="formData.year" placeholder="选择年份" style="width: 200px">
          <el-option v-for="year in yearOptions" :key="year" :label="`${year}年`" :value="year" />
        </el-select>
      </el-form-item>

      <!-- 资金分类 -->
      <el-divider content-position="left">资金信息</el-divider>

      <el-row :gutter="16">
        <el-col :span="8">
          <el-form-item label="资金总额 (万元)" prop="totalAmount">
            <el-input-number
              v-model="formData.totalAmount"
              :min="0"
              :precision="2"
              style="width: 100%"
            />
          </el-form-item>
        </el-col>
        <el-col :span="8">
          <el-form-item label="已使用 (万元)" prop="usedAmount">
            <el-input-number
              v-model="formData.usedAmount"
              :min="0"
              :precision="2"
              style="width: 100%"
            />
          </el-form-item>
        </el-col>
        <el-col :span="8">
          <el-form-item label="剩余 (万元)" prop="remainingAmount">
            <el-input-number
              v-model="formData.remainingAmount"
              :min="0"
              :precision="2"
              disabled
              style="width: 100%"
            />
          </el-form-item>
        </el-col>
      </el-row>

      <!-- 备注 -->
      <el-form-item label="备注" prop="remark">
        <el-input
          v-model="formData.remark"
          type="textarea"
          :rows="3"
          placeholder="请输入备注信息"
        />
      </el-form-item>

      <el-form-item>
        <el-button type="primary" @click="handleSubmit">提交</el-button>
        <el-button @click="handleReset">重置</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { getYearOptions } from '@/utils/yearOptions'

const props = defineProps<{
  initialData?: Record<string, any>
}>()

const emit = defineEmits<{
  (e: 'submit', data: Record<string, any>): void
}>()

const formRef = ref<FormInstance>()
const currentYear = new Date().getFullYear()
// 数据年份范围：当前年-10 ~ 当前年+10（滚动窗口，见 utils/yearOptions）
const yearOptions = computed(() => getYearOptions({ start: currentYear - 10 }))

const formData = reactive<Record<string, any>>({
  year: props.initialData?.year ?? currentYear,
  totalAmount: props.initialData?.totalAmount ?? 0,
  usedAmount: props.initialData?.usedAmount ?? 0,
  remainingAmount: (props.initialData?.totalAmount ?? 0) - (props.initialData?.usedAmount ?? 0),
  remark: props.initialData?.remark ?? '',
})

watch(
  () => [formData.totalAmount, formData.usedAmount],
  () => {
    formData.remainingAmount = formData.totalAmount - formData.usedAmount
  }
)

const rules: FormRules = {
  year: [{ required: true, message: '请选择年份', trigger: 'change' }],
  totalAmount: [{ required: true, message: '请输入资金总额', trigger: 'blur' }],
}

async function handleSubmit() {
  /* c8 ignore next */ // formRef 由模板 ref 绑定, 渲染后恒存在
  if (!formRef.value) return
  await formRef.value.validate((valid) => {
    if (valid) {
      emit('submit', { ...formData })
    }
  })
}

function handleReset() {
  formRef.value?.resetFields()
}
</script>

<style scoped>
.categorized-fund-form {
  padding: 16px;
}
</style>
