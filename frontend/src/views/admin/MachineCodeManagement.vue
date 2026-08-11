<template>
  <!-- 单根包裹：避免 transition 内多根导致 setAttribute('0') 崩溃 -->
  <div style="display: contents">
    <template v-if="isAdmin">
      <div class="machine-code-management">
        <el-tabs v-model="activeTab">
          <!-- 页签1：机器码管理 -->
          <el-tab-pane label="机器码管理" name="machineCodes">
            <el-card>
              <template #header>
                <div class="card-header">
                  <h2>机器码管理</h2>
                  <el-button type="primary" @click="showCreateDialog">
                    <el-icon><Plus /></el-icon>
                    录入机器码
                  </el-button>
                </div>
              </template>

              <!-- 筛选条件 -->
              <el-form :inline="true" :model="queryForm" class="query-form">
                <el-form-item label="状态">
                  <el-select
                    v-model="queryForm.status"
                    placeholder="全部状态"
                    clearable
                    style="width: 150px"
                    @change="handleQuery"
                  >
                    <el-option label="待使用" value="pending" />
                    <el-option label="已激活" value="active" />
                    <el-option label="已撤销" value="revoked" />
                  </el-select>
                </el-form-item>
                <el-form-item>
                  <el-button type="primary" @click="handleQuery">查询</el-button>
                  <el-button @click="handleReset">重置</el-button>
                </el-form-item>
              </el-form>

              <!-- 机器码列表 -->
              <el-table
                v-loading="loading"
                :data="machineCodeList"
                border
                stripe
                style="width: 100%"
              >
                <el-table-column type="index" label="序号" width="60" />
                <el-table-column prop="machine_code" label="机器码" min-width="200">
                  <template #default="{ row }">
                    <el-tooltip :content="row.machine_code" placement="top">
                      <span class="machine-code-text">
                        {{ row.machine_code.substring(0, 16) }}...
                      </span>
                    </el-tooltip>
                    <el-button
                      link
                      type="primary"
                      size="small"
                      @click="copyToClipboard(row.machine_code)"
                    >
                      <el-icon><CopyDocument /></el-icon>
                    </el-button>
                  </template>
                </el-table-column>
                <el-table-column prop="pass_code" label="通行码" min-width="250">
                  <template #default="{ row }">
                    <el-tooltip :content="row.pass_code" placement="top">
                      <span class="pass-code-text">{{ row.pass_code }}</span>
                    </el-tooltip>
                    <el-button
                      link
                      type="primary"
                      size="small"
                      @click="copyToClipboard(row.pass_code)"
                    >
                      <el-icon><CopyDocument /></el-icon>
                    </el-button>
                  </template>
                </el-table-column>
                <el-table-column prop="status" label="状态" width="100">
                  <template #default="{ row }">
                    <el-tag :type="getStatusType(row.status)" size="small">
                      {{ getStatusText(row.status) }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="username" label="绑定用户" width="120">
                  <template #default="{ row }">
                    <span v-if="row.username">{{ row.username }}</span>
                    <span v-else class="text-muted">未绑定</span>
                  </template>
                </el-table-column>
                <el-table-column
                  prop="description"
                  label="备注"
                  min-width="150"
                  show-overflow-tooltip
                />
                <el-table-column prop="created_at" label="创建时间" width="180">
                  <template #default="{ row }">
                    {{ format.formatDateTime(row.created_at) }}
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="120" fixed="right">
                  <template #default="{ row }">
                    <el-button
                      v-if="row.status === 'pending' || row.status === 'active'"
                      link
                      type="danger"
                      size="small"
                      @click="handleRevoke(row as MachineCodeRecord)"
                    >
                      撤销
                    </el-button>
                    <span v-else class="text-muted">-</span>
                  </template>
                </el-table-column>
              </el-table>

              <!-- 分页 -->
              <el-pagination
                v-model:current-page="pagination.page"
                v-model:page-size="pagination.pageSize"
                :total="pagination.total"
                :page-sizes="[10, 20, 50, 100]"
                layout="total, sizes, prev, pager, next, jumper"
                style="margin-top: 20px; justify-content: flex-end"
                @size-change="handleQuery"
                @current-change="handleQuery"
              />
            </el-card>

            <!-- 录入机器码对话框 -->
            <el-dialog
              v-model="createDialogVisible"
              title="录入机器码"
              width="600px"
              @close="resetCreateForm"
            >
              <el-form
                ref="createFormRef"
                :model="createForm"
                :rules="createRules"
                label-width="100px"
              >
                <el-form-item label="机器码" prop="machine_code">
                  <el-input
                    v-model="createForm.machine_code"
                    type="textarea"
                    :rows="3"
                    placeholder="请输入用户提供的机器码"
                  />
                </el-form-item>
                <el-form-item label="通行码" prop="pass_code">
                  <div class="pass-code-input-wrapper">
                    <el-input
                      v-model="createForm.pass_code"
                      placeholder="留空则自动生成"
                      maxlength="4"
                      style="width: 200px"
                    />
                    <div class="pass-code-hint">
                      输入4位数字手动设置通行码，不填则系统自动生成32位通行码
                    </div>
                  </div>
                </el-form-item>
                <el-form-item label="备注" prop="description">
                  <el-input
                    v-model="createForm.description"
                    type="textarea"
                    :rows="2"
                    placeholder="请输入备注信息（可选）"
                  />
                </el-form-item>
              </el-form>
              <template #footer>
                <el-button @click="createDialogVisible = false">取消</el-button>
                <el-button type="primary" :loading="submitting" @click="handleCreate">
                  确定
                </el-button>
              </template>
            </el-dialog>

            <!-- 通行码显示对话框 -->
            <el-dialog v-model="passCodeDialogVisible" title="通行码已生成" width="500px">
              <el-alert type="success" :closable="false" style="margin-bottom: 20px">
                <template #title>
                  <strong>请将以下通行码提供给用户</strong>
                </template>
              </el-alert>
              <div class="pass-code-display">
                <div class="pass-code-value">{{ generatedPassCode }}</div>
                <el-button type="primary" @click="copyToClipboard(generatedPassCode, '通行码')">
                  <el-icon><CopyDocument /></el-icon>
                  复制通行码
                </el-button>
              </div>
              <el-alert type="warning" :closable="false" style="margin-top: 20px">
                通行码仅显示一次，请妥善保管并及时提供给用户
              </el-alert>
              <template #footer>
                <el-button type="primary" @click="passCodeDialogVisible = false">
                  我已复制
                </el-button>
              </template>
            </el-dialog>
          </el-tab-pane>

          <!-- 页签2：组织通行码（整合原通行码管理板块，功能完整保留） -->
          <el-tab-pane label="组织通行码" name="orgPassCodes">
            <PassCodeManagement />
          </el-tab-pane>
        </el-tabs>
      </div>
    </template>
    <el-empty v-else description="无权限访问此页面" />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { logger } from '@/utils/logger'
import { Plus, CopyDocument } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { ADMIN_ROLES, normalizeRole } from '@/utils/roleAccess'
import PassCodeManagement from '@/views/organization/PassCodeManagement.vue'
import {
  listMachineCodes,
  createMachineCode,
  revokeMachineCode,
  type MachineCodeRecord,
} from '@/api/machineCode'
import { format } from '@/utils'
import { copyToClipboard } from '@/utils/clipboard'

const userStore = useUserStore()
const isAdmin = computed(() => {
  const role = normalizeRole(userStore.currentUser?.role)
  return ADMIN_ROLES.includes(role)
})

const activeTab = ref('machineCodes')
const loading = ref(false)
const submitting = ref(false)
const createDialogVisible = ref(false)
const passCodeDialogVisible = ref(false)
const generatedPassCode = ref('')

const machineCodeList = ref<MachineCodeRecord[]>([])

const queryForm = reactive({
  status: '',
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0,
})

const createFormRef = ref<FormInstance>()
const createForm = reactive({
  machine_code: '',
  description: '',
  pass_code: '',
})

const createRules: FormRules = {
  machine_code: [
    { required: true, message: '请输入机器码', trigger: 'blur' },
    { min: 32, message: '机器码长度不能少于32个字符', trigger: 'blur' },
  ],
  pass_code: [
    {
      pattern: /^\d{4}$/,
      message: '通行码必须为4位数字',
      trigger: 'blur',
    },
  ],
}

// 获取机器码列表
const fetchMachineCodeList = async () => {
  try {
    loading.value = true
    const response = await listMachineCodes({
      status_filter: queryForm.status || undefined,
      skip: (pagination.page - 1) * pagination.pageSize,
      limit: pagination.pageSize,
    })

    // 响应结构: { data: { data: MachineCodeListResponse } }
    // 拦截器已将 data.data 字段展开到顶层，但 data 键保留以兼容旧代码
    const data = response as any
    if (data.data) {
      machineCodeList.value = data.data.items
      pagination.total = data.data.total
    }
  } catch (error: any) {
    logger.error('获取机器码列表失败', error)
    ElMessage.error(error.response?.data?.detail || '获取机器码列表失败')
  } finally {
    loading.value = false
  }
}

// 查询
const handleQuery = () => {
  pagination.page = 1
  fetchMachineCodeList()
}

// 重置
const handleReset = () => {
  queryForm.status = ''
  handleQuery()
}

// 显示创建对话框
const showCreateDialog = () => {
  createForm.pass_code = ''
  createDialogVisible.value = true
}

// 重置创建表单
const resetCreateForm = () => {
  createFormRef.value?.resetFields()
  createForm.machine_code = ''
  createForm.description = ''
  createForm.pass_code = ''
}

// 创建机器码
const handleCreate = async () => {
  if (!createFormRef.value) return

  try {
    await createFormRef.value.validate()
    submitting.value = true

    const response = await createMachineCode({
      machine_code: createForm.machine_code.trim(),
      description: createForm.description.trim() || undefined,
      pass_code: createForm.pass_code || undefined,
    })

    // 机器码录入成功
    if (response?.code === 200) {
      ElMessage.success('机器码录入成功')

      // 显示生成的通行码
      generatedPassCode.value = response.pass_code
      passCodeDialogVisible.value = true

      // 刷新列表
      pagination.page = 1 // 重置到第1页，确保新建/编辑后的数据可见
      fetchMachineCodeList()

      // 仅在成功时关闭对话框
      createDialogVisible.value = false
    }
  } catch (error: any) {
    logger.error('录入机器码失败', error)
    ElMessage.error(error.response?.data?.detail || '录入机器码失败')
  } finally {
    submitting.value = false
  }
}

// 撤销机器码
const handleRevoke = async (row: MachineCodeRecord) => {
  try {
    await ElMessageBox.confirm(
      `确定要撤销该机器码吗？${row.username ? `用户 ${row.username} 将无法登录。` : ''}`,
      '撤销确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )

    await revokeMachineCode(row.id)
    ElMessage.success('机器码已撤销')
    pagination.page = 1 // 重置到第1页，确保新建/编辑后的数据可见
    fetchMachineCodeList()
  } catch (error: any) {
    if (error !== 'cancel') {
      logger.error('撤销机器码失败', error)
      ElMessage.error(error.response?.data?.detail || '撤销机器码失败')
    }
  }
}

// 获取状态类型
const getStatusType = (status: string) => {
  const typeMap: Record<string, any> = {
    pending: 'warning',
    active: 'success',
    revoked: 'info',
  }
  return typeMap[status] || 'info'
}

// 获取状态文本
const getStatusText = (status: string) => {
  const textMap: Record<string, string> = {
    pending: '待使用',
    active: '已激活',
    revoked: '已撤销',
  }
  return textMap[status] || status
}

onMounted(() => {
  fetchMachineCodeList()
})
</script>

<style scoped lang="scss">
.machine-code-management {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;

  h2 {
    margin: 0;
    font-size: 18px;
    font-weight: 600;
  }
}

.query-form {
  margin-bottom: 20px;
}

.machine-code-text,
.pass-code-text {
  font-family: 'Courier New', monospace;
  font-size: 13px;
  color: #606266;
}

.text-muted {
  color: #909399;
}

.pass-code-input-wrapper {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.pass-code-hint {
  font-size: 12px;
  color: #999;
}

.pass-code-display {
  text-align: center;
  padding: 20px;

  .pass-code-value {
    font-family: 'Courier New', monospace;
    font-size: 18px;
    font-weight: 600;
    color: var(--color-primary);
    padding: 20px;
    background: #f5f7fa;
    border-radius: 8px;
    margin-bottom: 20px;
    word-break: break-all;
  }
}
</style>
