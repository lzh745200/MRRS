<template>
  <div class="rules-management">
    <div class="page-header">
      <h2 class="page-title">校验规则管理</h2>
      <p class="page-desc">配置数据校验规则，对提交数据执行实时校验</p>
    </div>

    <!-- 工具栏 -->
    <el-card class="toolbar-card">
      <div class="toolbar">
        <div class="toolbar-left">
          <el-select
            v-model="filterModule"
            placeholder="筛选模块"
            clearable
            style="width: 160px"
            @change="loadRules"
          >
            <el-option label="全部模块" value="" />
            <el-option label="帮扶村" value="supported_villages" />
            <el-option label="学校" value="schools" />
            <el-option label="项目" value="projects" />
            <el-option label="资金" value="funds" />
            <el-option label="政策" value="policies" />
          </el-select>
          <el-select
            v-model="filterActive"
            placeholder="筛选状态"
            clearable
            style="width: 140px; margin-left: 10px"
            @change="loadRules"
          >
            <el-option label="全部" value="" />
            <el-option label="启用" value="true" />
            <el-option label="禁用" value="false" />
          </el-select>
        </div>
        <div class="toolbar-right">
          <el-button type="primary" :icon="Plus" @click="handleCreate">新增规则</el-button>
          <el-button
            type="success"
            :icon="VideoPlay"
            :loading="runningValidation"
            @click="showRunDialog"
          >
            执行校验
          </el-button>
          <el-button :icon="Refresh" :loading="loading" @click="loadRules">刷新</el-button>
        </div>
      </div>
    </el-card>

    <!-- 规则表格 -->
    <el-card class="table-card">
      <el-table v-loading="loading" :data="rules" stripe border>
        <el-table-column type="index" label="序号" width="60" align="center" />
        <el-table-column
          prop="description"
          label="规则名称"
          min-width="160"
          show-overflow-tooltip
        />
        <el-table-column prop="module" label="目标模块" width="120">
          <template #default="{ row }">
            <el-tag type="primary" size="small">{{ moduleLabel(row.module) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="field" label="校验字段" width="140" />
        <el-table-column prop="rule_type" label="规则类型" width="130">
          <template #default="{ row }">
            <el-tag size="small">{{ ruleTypeLabel(row.rule_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="priority" label="优先级" width="80" align="center" sortable />
        <el-table-column prop="is_active" label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
              {{ row.is_active ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column
          prop="error_message"
          label="错误提示"
          min-width="180"
          show-overflow-tooltip
        />
        <el-table-column label="操作" width="200" align="center" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" size="small" link @click="handleEdit(row)">编辑</el-button>
            <el-button type="success" size="small" link @click="runSingleValidation(row)"
              >校验</el-button
            >
            <el-button type="danger" size="small" link @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <EmptyState v-if="!loading && rules.length === 0" text="暂无校验规则，点击新增规则创建" />
    </el-card>

    <!-- 创建/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEditing ? '编辑校验规则' : '新增校验规则'"
      :width="DIALOG_MD"
      @close="resetForm"
    >
      <el-form ref="formRef" :model="formData" :rules="formRules" label-width="100px">
        <el-form-item label="规则描述" prop="description">
          <el-input v-model="formData.description" placeholder="规则描述（如：帮扶村名不能为空）" />
        </el-form-item>
        <el-form-item label="目标模块" prop="module">
          <el-select v-model="formData.module" placeholder="选择模块" style="width: 100%">
            <el-option label="帮扶村" value="supported_villages" />
            <el-option label="学校" value="schools" />
            <el-option label="项目" value="projects" />
            <el-option label="资金" value="funds" />
            <el-option label="政策" value="policies" />
          </el-select>
        </el-form-item>
        <el-form-item label="校验字段" prop="field">
          <el-input v-model="formData.field" placeholder="如：village_name, income, population" />
        </el-form-item>
        <el-form-item label="规则类型" prop="rule_type">
          <el-select v-model="formData.rule_type" placeholder="选择规则类型" style="width: 100%">
            <el-option label="非空检查" value="required" />
            <el-option label="正数" value="positive" />
            <el-option label="非负数" value="non_negative" />
            <el-option label="日期格式" value="date_format" />
            <el-option label="最大长度" value="max_length" />
            <el-option label="最小长度" value="min_length" />
            <el-option label="数值范围" value="range" />
            <el-option label="正则匹配" value="regex" />
            <el-option label="枚举值" value="enum_values" />
            <el-option label="跨字段逻辑" value="cross_field" />
          </el-select>
        </el-form-item>
        <el-form-item label="规则参数" prop="params">
          <el-input
            v-model="formData.params"
            type="textarea"
            :rows="2"
            placeholder='JSON格式参数，如：{"min": 0, "max": 100000} 或 {"pattern": "^[一-龥]+$"}'
          />
          <div class="form-item-tip">规则类型为range时可设min/max，regex时可设pattern</div>
        </el-form-item>
        <el-form-item label="错误提示">
          <el-input v-model="formData.error_message" placeholder="校验失败时的提示信息" />
        </el-form-item>
        <el-form-item label="优先级">
          <el-input-number v-model="formData.priority" :min="0" :max="100" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="formData.is_active" active-text="启用" inactive-text="禁用" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 执行校验对话框 -->
    <el-dialog v-model="runDialogVisible" title="执行校验" :width="DIALOG_SM">
      <el-form label-width="100px">
        <el-form-item label="目标模块">
          <el-select v-model="runModule" placeholder="选择校验目标模块" style="width: 100%">
            <el-option label="帮扶村" value="supported_villages" />
            <el-option label="学校" value="schools" />
            <el-option label="项目" value="projects" />
            <el-option label="资金" value="funds" />
            <el-option label="政策" value="policies" />
          </el-select>
        </el-form-item>
        <el-form-item label="测试数据">
          <el-input
            v-model="runDataInput"
            type="textarea"
            :rows="6"
            placeholder='输入测试JSON数据，如：{"village_name": "测试村", "income": 5000}'
          />
        </el-form-item>
      </el-form>
      <div v-if="validationResult" class="validation-result">
        <el-divider />
        <h4>校验结果</h4>
        <el-alert
          :title="validationResult.valid ? '校验通过' : '校验未通过'"
          :type="validationResult.valid ? 'success' : 'error'"
          :closable="false"
          show-icon
        />
        <div v-if="validationResult.errors?.length" style="margin-top: 12px">
          <el-tag
            v-for="(err, idx) in validationResult.errors"
            :key="idx"
            type="danger"
            style="margin: 4px; display: block"
          >
            {{ err }}
          </el-tag>
        </div>
      </div>
      <template #footer>
        <el-button @click="runDialogVisible = false">关闭</el-button>
        <el-button type="primary" :loading="runningValidation" @click="executeValidation">
          执行
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { DIALOG_SM, DIALOG_MD } from '@/config/dialog'
import EmptyState from '@/components/business/EmptyState/EmptyState.vue'
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance } from 'element-plus'
import { Plus, Refresh, VideoPlay } from '@element-plus/icons-vue'
import { listRules, createRule, updateRule, deleteRule, runValidation } from '@/api/validationRules'

const loading = ref(false)
const submitting = ref(false)
const runningValidation = ref(false)
const dialogVisible = ref(false)
const runDialogVisible = ref(false)
const isEditing = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref<FormInstance>()

const rules = ref<any[]>([])
const filterModule = ref('')
const filterActive = ref('')

const runModule = ref('supported_villages')
const runDataInput = ref('')
const validationResult = ref<any>(null)

interface RuleForm {
  description: string
  module: string
  field: string
  rule_type: string
  params: string
  error_message: string
  priority: number
  is_active: boolean
}

const formData = reactive<RuleForm>({
  description: '',
  module: 'supported_villages',
  field: '',
  rule_type: 'required',
  params: '',
  error_message: '',
  priority: 0,
  is_active: true,
})

const formRules = {
  description: [{ required: true, message: '请输入规则描述', trigger: 'blur' }],
  module: [{ required: true, message: '请选择目标模块', trigger: 'change' }],
  field: [{ required: true, message: '请输入校验字段', trigger: 'blur' }],
  rule_type: [{ required: true, message: '请选择规则类型', trigger: 'change' }],
}

function moduleLabel(m: string): string {
  const map: Record<string, string> = {
    supported_villages: '帮扶村',
    schools: '学校',
    projects: '项目',
    funds: '资金',
    policies: '政策',
  }
  return map[m] || m
}

function ruleTypeLabel(t: string): string {
  const map: Record<string, string> = {
    required: '非空检查',
    positive: '正数',
    non_negative: '非负数',
    date_format: '日期格式',
    max_length: '最大长度',
    min_length: '最小长度',
    range: '数值范围',
    regex: '正则匹配',
    enum_values: '枚举值',
    cross_field: '跨字段逻辑',
  }
  return map[t] || t
}

async function loadRules() {
  loading.value = true
  try {
    const params: any = {}
    if (filterModule.value) params.module = filterModule.value
    if (filterActive.value !== '') params.is_active = filterActive.value === 'true'
    const res = await listRules(params)
    // 后端裸返回数组（response_model=List[ValidationRuleOut]）
    const list = (res as any)?.data || (res as any)?.items || res
    rules.value = Array.isArray(list) ? list : []
  } catch {
    ElMessage.error('加载校验规则失败')
  } finally {
    loading.value = false
  }
}

function handleCreate() {
  isEditing.value = false
  editingId.value = null
  resetForm()
  dialogVisible.value = true
}

function handleEdit(row: any) {
  isEditing.value = true
  editingId.value = row.id
  Object.assign(formData, {
    description: row.description || '',
    module: row.module || 'supported_villages',
    field: row.field || '',
    rule_type: row.rule_type || 'required',
    params: row.params || '',
    error_message: row.error_message || '',
    priority: row.priority || 0,
    is_active: row.is_active !== false,
  })
  dialogVisible.value = true
}

function resetForm() {
  Object.assign(formData, {
    description: '',
    module: 'supported_villages',
    field: '',
    rule_type: 'required',
    params: '',
    error_message: '',
    priority: 0,
    is_active: true,
  })
  formRef.value?.resetFields()
}

async function handleSubmit() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    submitting.value = true
    try {
      const payload = {
        module: formData.module,
        field: formData.field,
        rule_type: formData.rule_type,
        params: formData.params || undefined,
        error_message: formData.error_message || undefined,
        description: formData.description,
        is_active: formData.is_active,
        priority: formData.priority,
      }
      if (isEditing.value && editingId.value) {
        await updateRule(editingId.value, payload)
        ElMessage.success('已保存')
      } else {
        await createRule(payload)
        ElMessage.success('已创建')
      }
      dialogVisible.value = false
      await loadRules()
    } catch (err: any) {
      const msg = err?.response?.data?.detail || '操作失败'
      ElMessage.error(msg)
    } finally {
      submitting.value = false
    }
  })
}

async function handleDelete(row: any) {
  try {
    await ElMessageBox.confirm(`确定删除规则 "${row.description || row.field}" 吗？`, '确认删除', {
      type: 'warning',
    })
    await deleteRule(row.id)
    ElMessage.success('规则已删除')
    await loadRules()
  } catch (err: any) {
    if (err !== 'cancel' && err?.toString() !== 'cancel') {
      ElMessage.error(err?.response?.data?.detail || '删除失败')
    }
  }
}

async function runSingleValidation(row: any) {
  try {
    runningValidation.value = true
    await runValidation(row.module, {})
    ElMessage.success(`规则 "${row.description}" 校验完成`)
    // 可以在此处理返回结果
  } catch {
    ElMessage.error(`规则 "${row.description}" 校验失败`)
  } finally {
    runningValidation.value = false
  }
}

function showRunDialog() {
  runModule.value = 'supported_villages'
  runDataInput.value = ''
  validationResult.value = null
  runDialogVisible.value = true
}

async function executeValidation() {
  if (!runDataInput.value) {
    ElMessage.warning('请输入测试数据')
    return
  }
  let parsedData: any
  try {
    parsedData = JSON.parse(runDataInput.value)
  } catch {
    ElMessage.error('测试数据格式错误，请输入有效的JSON')
    return
  }

  runningValidation.value = true
  validationResult.value = null
  try {
    const res = await runValidation(runModule.value, parsedData)
    validationResult.value = (res as any)?.data || res
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '校验执行失败')
  } finally {
    runningValidation.value = false
  }
}

onMounted(() => {
  loadRules()
})
</script>

<style scoped>
.rules-management {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 20px;
}
.page-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--color-primary-dark-1);
  margin: 0 0 4px;
}
.page-desc {
  font-size: 14px;
  color: var(--color-text-secondary);
  margin: 0;
}
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}
.toolbar-left,
.toolbar-right {
  display: flex;
  align-items: center;
}
.table-card {
  background: var(--color-bg-card);
}
.form-item-tip {
  font-size: 12px;
  color: var(--color-info);
  line-height: 1.4;
  margin-top: 4px;
}
.validation-result {
  margin-top: 12px;
}
.validation-result h4 {
  margin: 0 0 8px;
  font-size: 14px;
}
</style>
