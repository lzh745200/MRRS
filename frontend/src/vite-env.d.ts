/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}

declare module '*.json' {
  const value: any
  export default value
}

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string
  readonly VITE_APP_TITLE: string
  readonly VITE_APP_VERSION: string
  readonly VITE_WS_BASE_URL: string
  readonly VITE_APP_MODE: string
  readonly VITE_DEBUG: string
  readonly VITE_ENABLE_PERFORMANCE_MONITOR: string
  readonly VITE_ENABLE_ERROR_TRACKING: string
  readonly VITE_REQUEST_TIMEOUT: string
  readonly VITE_TOKEN_KEY: string
  readonly VITE_REFRESH_TOKEN_KEY: string
  readonly VITE_TOKEN_REFRESH_THRESHOLD: string
  readonly VITE_CSRF_ENABLED: string
  readonly VITE_OFFLINE_MODE: string
  readonly VITE_MAP_TILE_DIR: string
  readonly VITE_MAP_CENTER: string
  readonly VITE_MAP_ZOOM: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

/**
 * 构建时由 vite.config.ts / vitest.config.ts 的 `define` 注入，
 * 值等于根 `package.json` 的 `version`（版本号单一事实源）。
 */
declare const __APP_VERSION__: string
