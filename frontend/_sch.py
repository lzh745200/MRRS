import pathlib

# ============ schools/List.vue：回收站开关 + 双模式操作列 + 恢复/彻底删除 ============
p = pathlib.Path('src/views/schools/List.vue')
t = p.read_text(encoding='utf-8')

# 1) 筛选表单尾部插入开关（在 搜索按钮 的 el-form-item 之后、</el-form> 之前）
anchor_search_btn = re.compile(
    r'(  <el-button type="primary" @click="handleSearch">[\s\S]*?</el-form-item>\n)(\s*</el-form>)'
)
m = anchor_search_btn.search(t)
assert m, 'schools search form anchor not found'
switch_block = (
    '  <el-form-item>\n'
    '    <el-tooltip v-if="canViewDeleted" content="切换显示已软删的学校（管理员可见）" placement="top">\n'
    '      <el-switch\n'
    '        v-model="showDeletedOnly"\n'
    '        inline-prompt\n'
    '        active-text="回收站"\n'
    '        inactive-text="正常"\n'
    '        @change="handleToggleDeleted"\n'
    '      />\n'
    '    </el-tooltip>\n'
    '  </el-form-item>\n'
)
t = t[: m.end(1)] + switch_block + t[m.end(1):]

# 2) 操作列双模式
old_ops = re.search(
    r'(<el-table-column label="操作"[^>]*>\s*<template #default="scope">\s*)'
    r'(<el-button[^>]*@click="handleView\(scope\.row\)"[\s\S]*?)'
    r'(<el-popconfirm title="确定删除该学校吗？[\s\S]*?</el-popconfirm>)',
    t,
)
assert old_ops, 'schools ops column not found'
new_ops = (
    old_ops.group(1)
    + '<el-button type="primary" link size="small" @click="handleView(scope.row)">查看</el-button>\n'
    '            <template v-if="showDeletedOnly">\n'
    '              <el-button type="success" link size="small" @click="handleRestore(scope.row)">恢复</el-button>\n'
    '              <el-button type="danger" link size="small" @click="handlePurge(scope.row)">彻底删除</el-button>\n'
    '            </template>\n'
    '            <template v-else>\n'
    + old_ops.group(2).replace('查看', '编辑', 1)
    + old_ops.group(3)
    + '\n            </template>'
)
t = t[: old_ops.start()] + new_ops + t[old_ops.end():]

# 3) script 追加逻辑
script_add = '''

// ── 回收站（Phase C 推广）──
const canViewDeleted = computed(() => authStore.canViewDeleted)
const showDeletedOnly = ref(false)

async function handleToggleDeleted() {
  currentPage.value = 1
  await fetchData()
}

async function handleRestore(row: any) {
  try {
    await ElMessageBox.confirm(
      `确定恢复学校【${row.name}】吗？`,
      '恢复确认',
      { confirmButtonText: '确认恢复', cancelButtonText: '取消', type: 'info' }
    )
  } catch {
    return
  }
  try {
    await restoreSchool(row.id)
    ElMessage.success('恢复成功')
    fetchData()
  } catch {
    ElMessage.error('恢复失败')
  }
}

async function handlePurge(row: any) {
  let totalRefs = 0
  let cascadeHint = ''
  try {
    const pv: any = await previewPurgeSchool(row.id)
    const d = pv?.data || pv || {}
    totalRefs = Number(d.total_references || 0)
    cascadeHint = d.total_references ? `（含关联 ${totalRefs} 条）` : ''
  } catch { /* 预览失败不阻断 */ }
  try {
    await ElMessageBox.confirm(
      `彻底删除后【${row.name}】及其关联的 ${totalRefs} 条数据将无法恢复${cascadeHint}！不可撤销。`,
      '彻底删除警告',
      { confirmButtonText: '继续', cancelButtonText: '取消', type: 'warning' }
    )
  } catch { return }
  let confirmPassword = ''
  try {
    const r = await ElMessageBox.prompt(
      `彻底删除【${row.name}】需二次确认，请输入登录密码：`, '二次确认',
      { confirmButtonText: '确认彻底删除', inputType: 'password',
        inputValidator: (v: string) => (v ? true : '密码不能为空') }
    )
    confirmPassword = r.value || ''
  } catch { return }
  loading.value = true
  try {
    const res: any = await purgeSchool(row.id, confirmPassword)
    ElMessage.success(res?.data?.message || `已清理 ${res?.data?.deleted_records ?? 0} 条关联数据`)
    fetchData()
  } catch {
    ElMessage.error('彻底删除失败')
  } finally {
    loading.value = false
  }
}
'''
t = t.rstrip() + script_add

# 4) imports：auth store / computed已有? 补齐
t = t.replace(
    "import { schoolApi } from '@/api/schools'",
    "import { schoolApi } from '@/api/schools'\n"
    "import {\n"
    "  restoreSchool,\n"
    "  previewPurgeSchool,\n"
    "  purgeSchool,\n"
    "} from '@/api/schoolsRecycle'\n"
    "import { useAuthStore } from '@/stores/auth'",
    1,
)

p.write_text(t, encoding='utf-8')
print('schools List.vue patched')
