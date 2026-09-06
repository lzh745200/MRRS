<template>
  <div class="permission-tree-panel">
    <el-alert type="info" :closable="false" style="margin-bottom: 16px">
      为当前用户配置各功能模块的查看和编辑权限。 无查看权限则模块不可见；仅有查看权限则为只读模式。
    </el-alert>

    <el-table :data="moduleList" border style="width: 100%">
      <el-table-column label="功能模块" width="160">
        <template #default="{ row }">{{ row.label }}</template>
      </el-table-column>
      <el-table-column label="查看权限" width="100" align="center">
        <template #default="{ row }">
          <el-checkbox
            :model-value="row.view"
            :disabled="disabled"
            @change="(val: any) => togglePermission(row.module, 'view', !!val)"
          />
        </template>
      </el-table-column>
      <el-table-column label="编辑权限" width="100" align="center">
        <template #default="{ row }">
          <el-checkbox
            :model-value="row.edit"
            :disabled="disabled || !row.view"
            @change="(val: any) => togglePermission(row.module, 'edit', !!val)"
          />
        </template>
      </el-table-column>
      <el-table-column label="说明" min-width="200">
        <template #default="{ row }">
          <span v-if="!row.view" class="text-danger">模块不可见</span>
          <span v-else-if="!row.edit" class="text-warning">只读访问</span>
          <span v-else class="text-success">完全访问</span>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'

interface ModulePermissionRow {
  module: string
  label: string
  view: boolean
  edit: boolean
}

const props = defineProps<{
  permissions: string[]
  disabled?: boolean
  userId?: number
}>()

const emit = defineEmits<{
  change: [permissions: string[]]
}>()

const MODULE_DEFINITIONS: { module: string; label: string }[] = [
  { module: 'user', label: '用户管理' },
  { module: 'village', label: '帮扶村管理' },
  { module: 'project', label: '项目管理' },
  { module: 'fund', label: '经费管理' },
  { module: 'policy', label: '政策管理' },
  { module: 'school', label: '学校管理' },
  { module: 'org', label: '组织管理' },
  { module: 'analytics', label: '数据分析' },
  { module: 'audit', label: '审计日志' },
  { module: 'backup', label: '备份管理' },
  { module: 'system', label: '系统设置' },
]

const moduleList = ref<ModulePermissionRow[]>([])

function buildModuleList(perms: string[]) {
  moduleList.value = MODULE_DEFINITIONS.map((def) => {
    const hasRead = perms.includes(`${def.module}:read`)
    const hasWrite = perms.includes(`${def.module}:write`)
    return {
      module: def.module,
      label: def.label,
      view: hasRead || hasWrite,
      edit: hasWrite,
    }
  })
}

function togglePermission(module: string, level: 'view' | 'edit', value: boolean) {
  const codes = new Set(props.permissions)

  if (level === 'view') {
    if (value) {
      codes.add(`${module}:read`)
    } else {
      codes.delete(`${module}:read`)
      // 如果取消查看，编辑也自动取消
      codes.delete(`${module}:write`)
    }
  } else {
    if (value) {
      codes.add(`${module}:write`)
    } else {
      codes.delete(`${module}:write`)
    }
  }

  const newPerms = Array.from(codes)
  buildModuleList(newPerms)
  emit('change', newPerms)
}

watch(
  () => props.permissions,
  (perms) => buildModuleList(perms || []),
  { immediate: true }
)

onMounted(() => buildModuleList(props.permissions || []))
</script>

<style scoped lang="scss">
.text-danger {
  color: var(--el-color-danger);
}
.text-warning {
  color: var(--el-color-warning);
}
.text-success {
  color: var(--el-color-success);
}
</style>
