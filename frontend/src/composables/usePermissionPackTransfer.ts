/**
 * 权限包导入/导出（W5-T10 自 views/system/UserManagement.vue 拆出）。
 *
 * 为什么是 composable 而不是子组件：这段逻辑没有可供渲染的独立 UI（文件选择框由
 * `document.createElement('input')` 动态创建，导入模式选择走 ElMessageBox），
 * 拆成组件反而要在父/子之间来回搬 8 个 ref。抽成 composable 后
 * UserManagement.vue 只保留一行调用，测试仍通过 `vm.xxx` 访问同一批 ref
 * （`<script setup>` 解构出的 ref 依旧在 setupState 上，读写语义不变）。
 *
 * 边界：本模块只管“权限包文件”的导入导出与提示；用户列表刷新由调用方通过
 * `hooks` 注入（`reload` / `resetPage`），避免把分页与列表状态耦合进来。
 */
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request, { get, post } from '@/api/request'
import { downloadBlobAsFile } from '@/api/helpers/blobDownload'

export interface PermissionPackTransferHooks {
  /** 导入成功后刷新用户列表 */
  reload: () => void | Promise<void>
  /** 刷新列表前把分页重置到第 1 页（否则新数据落在用户看不到的页码上） */
  resetPage: () => void
}

export function usePermissionPackTransfer(hooks: PermissionPackTransferHooks) {
  // ── 权限包导入/导出 ──
  const exportingPermPackage = ref(false)
  const importingPermPackage = ref(false)

  // ── 导出：角色选择对话框（P1 选择性导出） ──
  const permExportDialogVisible = ref(false)
  const permRolesLoading = ref(false)
  const permExportRoleOptions = ref<{ name: string; label?: string }[]>([])
  const permExportRoleNames = ref<string[]>([])
  const permExportPassword = ref('')
  const permBindMachineCode = ref(false)

  async function openPermExportDialog() {
    permExportDialogVisible.value = true
    permExportRoleNames.value = []
    permExportPassword.value = ''
    permBindMachineCode.value = false
    if (permExportRoleOptions.value.length > 0) return
    permRolesLoading.value = true
    try {
      const res: any = await get('/rbac/roles', { limit: 200 })
      const data = res?.data || res || {}
      const roles = Array.isArray(data) ? data : data.data || data.items || []
      permExportRoleOptions.value = roles.map((r: any) => ({
        name: r.name,
        label: r.label || r.description || r.name,
      }))
    } catch {
      // 角色列表获取失败不阻断导出，仍可全量导出
      permExportRoleOptions.value = []
    } finally {
      permRolesLoading.value = false
    }
  }

  const doExportPermissionPackage = async () => {
    exportingPermPackage.value = true
    try {
      const payload: Record<string, unknown> = {}
      if (permExportRoleNames.value.length > 0) {
        payload.role_names = permExportRoleNames.value
      }
      if (permExportPassword.value) {
        payload.password = permExportPassword.value
      }
      if (permBindMachineCode.value) {
        payload.bind_machine_code = true
      }
      const res = await post('/permission-packages/export', payload)
      const data = res.data || res
      if (!data.file_name) {
        throw new Error('导出响应缺少 file_name')
      }
      // 必须走带 Authorization 拦截器的 axios 实例：/permission-packages/download
      // 依赖 get_current_user，裸 <a> 导航不带认证头会恒 401（表现为“提示成功却没有文件”）。
      // await 下载真正完成后才提示成功；失败会抛出并由下方 catch 提示真实原因。
      await downloadBlobAsFile(
        () =>
          request.get(`/permission-packages/download/${encodeURIComponent(data.file_name)}`, {
            responseType: 'blob',
          }),
        { fallbackFileName: data.file_name }
      )
      ElMessage.success(`权限包导出成功 (${data.role_count} 个角色, ${data.user_count} 个用户)`)
      permExportDialogVisible.value = false
    } catch (err: any) {
      ElMessage.error(err?.userMessage || err?.response?.data?.detail || err?.message || '导出失败')
    } finally {
      exportingPermPackage.value = false
    }
  }

  const handleImportPermissionPackage = () => {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = '.zip'

    // 清理函数：移除 input 元素 + 重置状态
    const cleanup = () => {
      importingPermPackage.value = false
      input.remove()
      window.removeEventListener('focus', cleanup)
    }

    // 用户取消文件对话框时 change 事件不触发，用 window focus 代理清理
    window.addEventListener('focus', cleanup, { once: true })

    input.addEventListener('change', async (e: Event) => {
      // 用户已选择文件 → 取消 focus 清理（change 事件先于 focus）
      window.removeEventListener('focus', cleanup)

      importingPermPackage.value = true
      try {
        const file = (e.target as HTMLInputElement).files?.[0]
        if (!file) {
          cleanup()
          return
        }
        const fd = new FormData()
        fd.append('file', file)
        const res = await post('/permission-packages/import', fd, {
          headers: { 'Content-Type': 'multipart/form-data' },
        })
        const result = res.data || res
        // Phase E：加密包需要密码；预览失败且标记加密时提示输入并重传
        let importPassword = ''
        if (!result.success && /加密/.test(result.message || '')) {
          try {
            const { value } = await ElMessageBox.prompt(
              '该权限包已加密，请输入导出时设置的密码：',
              '解密密码',
              {
                inputType: 'password',
                inputValidator: (v: string) => (v ? true : '密码不能为空'),
              }
            )
            importPassword = value || ''
          } catch {
            cleanup()
            return
          }
          const fd2 = new FormData()
          fd2.append('file', file)
          fd2.append('password', importPassword)
          const res2 = await post('/permission-packages/import', fd2, {
            headers: { 'Content-Type': 'multipart/form-data' },
          })
          const merged = res2.data || res2
          Object.assign(result, merged)
          if (!result.success) {
            ElMessage.error(merged.message || result.message || '导入失败')
            return
          }
        }
        if (result.success) {
          const p = result.preview || {}
          let msg = `将导入 ${p.role_count || 0} 个角色, ${p.user_legacy_count || 0} 个用户权限`
          if (p.warnings?.length) msg += `\n警告: ${p.warnings.join('; ')}`
          // 选择导入模式：确定=合并（保留本机其他配置）；取消=完全替换；关闭=放弃
          msg +=
            '\n\n【合并导入】保留本机已有权限，仅追加包内配置\n【覆盖导入】清空本机现有配置后按包内容重建'
          let mode: 'merge' | 'overwrite' | null = null
          await ElMessageBox.confirm(msg, '选择导入模式', {
            type: 'warning',
            distinguishCancelAndClose: true,
            confirmButtonText: '合并导入',
            cancelButtonText: '覆盖导入',
          })
            .then(() => {
              mode = 'merge'
            })
            .catch(async (action: any) => {
              if (action === 'cancel') mode = 'overwrite'
            })
          if (!mode) return // 用户关闭 → 放弃导入
          const cRes = await post(`/permission-packages/confirm/${encodeURIComponent(file.name)}`, {
            overwrite_existing: mode === 'overwrite',
            mode,
          })
          ElMessage.success(cRes.data?.message || cRes.message || '导入完成')
          hooks.resetPage() // 重置到第1页，确保导入后的数据可见
          hooks.reload()
        } else {
          ElMessage.error(result.message || '导入失败')
        }
      } catch (err: any) {
        if (err === 'cancel') return
        ElMessage.error(err?.response?.data?.detail || err?.message || '导入失败')
      } finally {
        cleanup()
      }
    })

    input.click()
  }

  return {
    exportingPermPackage,
    importingPermPackage,
    permExportDialogVisible,
    permRolesLoading,
    permExportRoleOptions,
    permExportRoleNames,
    permExportPassword,
    permBindMachineCode,
    openPermExportDialog,
    doExportPermissionPackage,
    handleImportPermissionPackage,
  }
}
