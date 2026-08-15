/**
 * Vite 构建配置
 *
 * 包含：
 * - Gzip/Brotli 压缩
 * - 代码分割策略
 * - Element Plus 按需引入
 * - ECharts 按需引入
 * - 构建优化
 * - 路由懒加载优化
 * - 资源预加载
 *
 * 需求: 4.1, 4.2, 4.3, 10.5
 */

import { defineConfig, type PluginOption } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'
import viteCompression from 'vite-plugin-compression'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

/**
 * SPA 回退插件 - 确保所有非文件请求都返回 index.html
 * 解决 Vite 5 中 SPA history fallback 不生效的问题
 */
function spaFallbackPlugin(): PluginOption {
  return {
    name: 'spa-fallback',
    configureServer(server) {
      // 在其他中间件之前注册，确保 SPA 路由正常工作
      server.middlewares.use((req, res, next) => {
        const url = req.url || ''
        // 仅处理 HTML 请求（非静态资源）
        if (
          req.method === 'GET' &&
          !url.includes('.') &&
          !url.startsWith('/@') &&
          !url.startsWith('/__') &&
          !url.startsWith('/api') &&
          !url.startsWith('/src') &&
          !url.startsWith('/node_modules') &&
          req.headers.accept?.includes('text/html')
        ) {
          req.url = '/index.html'
        }
        next()
      })
    },
  }
}

export default defineConfig(({ mode }) => {
  const isProduction = mode === 'production'

  return {
    appType: 'spa',

    // 基础路径：绝对路径 `/` 适用于 FastAPI 根路径托管生产模式。
    // 注意：生产环境 FastAPI 在 http://host:port/ 根路径下挂载前端静态文件，
    // 使用绝对路径可确保所有资源（JS/CSS/字体/图片）和动态 import() 的
    // chunk 路径正确解析。如果部署在子目录下（如 /app/），请改为 '/app/'。
    // Electron file:// 协议场景则需改为 './'（相对路径）。
    base: '/',

    plugins: [
      // SPA 回退 - 必须在最前面
      spaFallbackPlugin(),

      // 构建时自动生成 version.json（供前端版本指纹校验）
      {
        name: 'generate-version-json',
        apply: 'build',
        generateBundle() {
          const versionJson = JSON.stringify(
            {
              version: process.env.npm_package_version || '1.5.0',
              buildTime: new Date().toISOString(),
            },
            null,
            2
          )
          this.emitFile({
            type: 'asset',
            fileName: 'version.json',
            source: versionJson,
          })
        },
      },

      vue({
        // 使用默认配置，避免编译问题
      }),

      // Element Plus 按需自动导入
      AutoImport({
        resolvers: [ElementPlusResolver()],
        imports: ['vue', 'vue-router', 'pinia'],
        dts: 'src/auto-imports.d.ts',
        eslintrc: {
          enabled: false,
        },
      }),

      // Element Plus 组件按需自动导入
      Components({
        resolvers: [
          ElementPlusResolver({
            importStyle: 'css',
          }),
        ],
        dts: 'src/components.d.ts',
        // 只扫描 src 目录
        dirs: ['src/components'],
        // 深度扫描子目录
        deep: true,
        // 使用目录作为命名空间，避免组件命名冲突
        directoryAsNamespace: true,
        // 忽略某些组件以避免冲突
        exclude: [/[\\/]node_modules[\\/]/, /[\\/]\.git[\\/]/, /[\\/]\.nuxt[\\/]/],
        // 组件名称转换函数，处理命名冲突
        extensions: ['vue'],
        // 允许覆盖已存在的组件
        allowOverrides: false,
      }),

      // Gzip 压缩 (生产环境)
      isProduction &&
        viteCompression({
          verbose: true,
          disable: false,
          threshold: 10240, // 10KB 以上才压缩
          algorithm: 'gzip',
          ext: '.gz',
          deleteOriginFile: false,
        }),

      // Brotli 压缩 (生产环境，压缩率更高)
      isProduction &&
        viteCompression({
          verbose: true,
          disable: false,
          threshold: 10240,
          algorithm: 'brotliCompress',
          ext: '.br',
          deleteOriginFile: false,
        }),
    ].filter(Boolean),

    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },

    // CSS 预处理器配置
    css: {
      preprocessorOptions: {
        scss: {
          api: 'modern-compiler',
          // 全局注入纯 SCSS 变量（实体 CSS 规则在 styles/index.scss 只加载一次，避免随 SFC 重复打包）
          additionalData: `@use "@/styles/tokens-vars.scss" as *;`,
        },
      },
      // 开发环境启用 source map
      devSourcemap: !isProduction,
    },

    server: {
      port: 5173,
      host: '127.0.0.1',
      strictPort: false, // 端口被占用时自动切换到下一个可用端口
      // 忽略对 dist_old 和 node_modules_garbage 目录的监听，防止 scandir 错误
      watch: {
        ignored: [
          '**/dist_old/**',
          '**/node_modules_garbage/**',
          '**/node_modules_corrupted/**',
          '**/node_modules_corrupted',
          path.resolve(__dirname, 'node_modules_corrupted') + '/**',
          path.resolve(__dirname, 'node_modules_corrupted'),
        ],
      },
      proxy: {
        '/api': {
          // E2E 运行时由 playwright.config.ts 注入 E2E_BACKEND_URL 指向隔离端口
          target: process.env.E2E_BACKEND_URL || 'http://127.0.0.1:8000',
          changeOrigin: true,
          secure: false,
          // 不重写路径，保持 /api/v1/xxx 格式
          // rewrite: (path) => path
        },
        // 后端 /uploads 静态文件（附件预览/下载）挂根路径，与 /api 并列代理
        '/uploads': {
          target: process.env.E2E_BACKEND_URL || 'http://127.0.0.1:8000',
          changeOrigin: true,
          secure: false,
        },
      },
    },

    // 跨过损坏的目录
    publicDir: 'public',

    build: {
      outDir: 'dist',
      // 生产环境禁用 source map
      sourcemap: !isProduction,
      // 复制 public 目录（含 images/badges 等静态资源）
      copyPublicDir: true,
      // 启用 CSS 代码分割
      cssCodeSplit: true,
      // 设置 chunk 大小警告阈值 (1500KB)
      chunkSizeWarningLimit: 1500,
      // 压缩选项
      minify: 'terser',
      terserOptions: {
        compress: {
          // 生产环境移除 console 和 debugger
          drop_console: isProduction,
          drop_debugger: isProduction,
          // 移除无用代码
          dead_code: true,
          // 优化条件表达式
          conditionals: true,
          // 优化布尔值
          booleans: true,
          // 移除未使用的变量
          unused: true,
          // 内联只使用一次的变量
          collapse_vars: true,
          // 优化 if-return 和 if-continue
          if_return: true,
          // 合并连续的 var 声明
          join_vars: true,
          // 移除 console 输出（生产环境静默）
          pure_funcs: isProduction
            ? ['console.log', 'console.info', 'console.debug', 'console.warn', 'console.error']
            : [],
        },
        mangle: {
          // 混淆顶级作用域变量名
          toplevel: true,
          // 保留类名（用于调试）
          keep_classnames: false,
          // 保留函数名（用于调试）
          keep_fnames: false,
          // Safari 10 兼容性
          safari10: true,
        },
        format: {
          // 移除注释
          comments: false,
          // 美化输出（开发环境）
          beautify: !isProduction,
          // ASCII 输出（避免编码问题）
          ascii_only: true,
        },
      },
      rollupOptions: {
        // 抑制 @vueuse/core 中 /* #__PURE__ */ 注释位置导致的 Rollup 警告
        // 该警告不影响功能，注释会被自动移除
        onwarn(warning, defaultHandler) {
          if (
            warning.code === 'INVALID_ANNOTATION' ||
            (warning.message && warning.message.includes('annotation that Rollup cannot interpret'))
          ) {
            return // 跳过此警告
          }
          defaultHandler(warning)
        },
        output: {
          // 代码分割策略 - 优化后的分割逻辑
          manualChunks: (id) => {
            // Vue 核心库 - 最高优先级，单独打包
            if (id.includes('node_modules/vue/') || id.includes('node_modules/@vue/')) {
              return 'vue-core'
            }

            // Vue Router - 路由库单独打包
            if (id.includes('node_modules/vue-router')) {
              return 'vue-router'
            }

            // Pinia - 状态管理单独打包
            if (id.includes('node_modules/pinia')) {
              return 'pinia'
            }

            // Element Plus - 统一打包以解决循环依赖警告
            if (id.includes('node_modules/element-plus')) {
              return 'element-plus'
            }

            // Element Plus 图标 - 单独打包
            if (id.includes('node_modules/@element-plus/icons-vue')) {
              return 'element-plus-icons'
            }

            // ECharts - 统一打包以解决循环依赖警告
            if (id.includes('node_modules/echarts') || id.includes('node_modules/zrender')) {
              return 'echarts'
            }

            // Chart.js - 图表库，仅在图表页面使用，单独分包
            if (id.includes('node_modules/chart.js')) {
              return 'chartjs'
            }

            // SortableJS - 拖拽库，单独分包
            if (id.includes('node_modules/sortablejs')) {
              return 'sortable'
            }

            // HTTP 客户端
            if (id.includes('node_modules/axios')) {
              return 'axios'
            }

            // 日期处理 - 合并到vendor避免空chunk
            // dayjs 如果未被直接使用会产生空chunk，合并到vendor

            // 安全相关
            if (id.includes('node_modules/dompurify')) {
              return 'security'
            }

            // 其他第三方库
            if (id.includes('node_modules')) {
              return 'vendor'
            }
          },
          // 入口文件命名
          entryFileNames: 'assets/js/[name]-[hash].js',
          // chunk 文件命名 - 按类型分目录
          chunkFileNames: (chunkInfo) => {
            const name = chunkInfo.name || 'chunk'
            // 视图组件
            if (name.includes('views') || name.includes('View')) {
              return 'assets/js/views/[name]-[hash].js'
            }
            // 第三方库
            if (
              [
                'vue-core',
                'vue-router',
                'pinia',
                'axios',
                'dayjs',
                'lodash',
                'el-',
                'echarts',
                'vendor',
                'security',
              ].some((prefix) => name.startsWith(prefix) || name.includes(prefix))
            ) {
              return 'assets/js/vendor/[name]-[hash].js'
            }
            return 'assets/js/[name]-[hash].js'
          },
          // 静态资源命名
          assetFileNames: (assetInfo) => {
            const name = assetInfo.name || ''

            // 图片资源
            if (/\.(png|jpe?g|gif|svg|webp|ico|avif)$/i.test(name)) {
              return 'assets/images/[name]-[hash][extname]'
            }

            // 字体资源
            if (/\.(woff2?|eot|ttf|otf)$/i.test(name)) {
              return 'assets/fonts/[name]-[hash][extname]'
            }

            // CSS 资源
            if (/\.css$/i.test(name)) {
              return 'assets/css/[name]-[hash][extname]'
            }

            // 其他资源
            return 'assets/[name]-[hash][extname]'
          },
        },
        // 外部化大型依赖（可选，用于 CDN）
        // external: ['vue', 'vue-router', 'pinia', 'element-plus', 'echarts']
      },
      // 报告压缩后的大小
      reportCompressedSize: true,
      // 启用 CSS 压缩
      cssMinify: true,
      // 启用模块预加载
      modulePreload: {
        polyfill: true,
      },
      // 资源内联阈值（4KB 以下的资源内联为 base64）
      assetsInlineLimit: 4096,
    },

    // 优化依赖预构建
    optimizeDeps: {
      include: ['vue', 'vue-router', 'pinia', 'axios', 'dayjs'],
      // 排除不需要预构建的依赖
      exclude: [
        // ECharts 按需加载，不预构建
      ],
      // 强制预构建这些依赖
      force: false,
      // 预构建入口
      entries: ['src/main.ts'],
    },

    // esbuild 配置
    esbuild: {
      // 开发环境移除 console（生产环境由 terser 处理，避免冲突）
      drop: isProduction ? [] : [],
      // 保留法律注释
      legalComments: 'none',
      // 目标环境 - 提升到 es2020 以支持 import.meta
      target: 'es2020',
    },

    // 预览服务器配置
    preview: {
      port: 4173,
      host: true,
      strictPort: true,
    },

    // JSON 处理
    json: {
      // 支持命名导入
      namedExports: true,
      // 字符串化（减小体积）
      stringify: false,
    },

    // Worker 配置
    worker: {
      format: 'es',
    },
  }
})
