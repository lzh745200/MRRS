/**
 * el-upload 原生上传请求头（统一 CSRF 修复）
 *
 * el-upload 的 :action 模式使用原生 XHR/FormData 直发,
 * 不经过 axios 拦截器 → 必须手动携带 Authorization + X-CSRF-Token。
 */
import { computed, onMounted, ref } from 'vue'
import { getCsrfToken } from '@/api/request'
import { AuthStorage } from '@/utils/authStorage'
import { logger } from '@/utils/logger'

export function useUploadHeaders() {
  const csrfToken = ref('')

  /**
   * 预取 CSRF token。
   * 必须返回 Promise 并在 resolve 后才算完成：调用方（before-upload）会
   * `await ensureCsrf()`，不返回则 await 立刻 resolve，上传带着空
   * X-CSRF-Token 发出 → 后端 CSRF 校验 403。
   */
  const ensureCsrf = async (): Promise<void> => {
    try {
      const t = await getCsrfToken()
      if (t) csrfToken.value = t
    } catch (err) {
      // 预取失败不阻塞上传流程，但必须可观测（否则只剩 403 现象）
      logger.warn('[useUploadHeaders] CSRF token 预取失败:', err)
    }
  }

  onMounted(ensureCsrf)

  const uploadHeaders = computed(() => {
    const token = AuthStorage.getToken() || ''
    const headers: Record<string, string> = {}
    if (token) headers.Authorization = `Bearer ${token}`
    if (csrfToken.value) headers['X-CSRF-Token'] = csrfToken.value
    return headers
  })

  return { uploadHeaders, ensureCsrf }
}
