#!/usr/bin/env node
/**
 * sync-version.js — 版本号统一校验/同步工具
 *
 * 以根目录 package.json 的 `version` 字段为唯一版本源，校验/同步以下文件中的版本号：
 *   - backend/app/core/config.py        PROJECT_VERSION
 *   - backend/version.txt (若存在) / version.txt
 *   - README.md                          badge + 文末版本
 *   - Dockerfile                         echo 版本
 *   - Dockerfile.runtime                 LABEL version
 *   - docker-compose.yml                 BUILD_VERSION / image tag / PROJECT_VERSION / 头注释
 *   - build.ps1                          $Version 默认值
 *   - build-kylin.sh                     产物文件名版本
 *   - build-with-check.ps1               $PACKAGE_VERSION
 *   - electron/main.js                   回退默认版本
 *   - launch.py                          启动横幅版本
 *
 * 用法:
 *   node scripts/sync-version.js --check   # 仅校验，不一致退出码 1
 *   node scripts/sync-version.js --write   # 自动同步所有文件到 package.json 版本
 *
 * 退出码: 0 = 一致/已同步; 1 = 存在不一致（--check 模式）
 */

"use strict";

const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const PKG_PATH = path.join(ROOT, "package.json");

// ── 读取唯一版本源 ──
function readSourceVersion() {
  const pkg = JSON.parse(fs.readFileSync(PKG_PATH, "utf-8"));
  if (!pkg.version || !/^\d+\.\d+\.\d+/.test(pkg.version)) {
    console.error(`[sync-version] package.json version 无效: ${pkg.version}`);
    process.exit(1);
  }
  return pkg.version;
}

// ── 文件目标定义 ──
// 每个目标: { file, describe(relativePath), apply(content, ver) -> newContent }
// describe 返回当前文件中提取的版本号（用于 --check）；找不到返回 null。
const TARGETS = [
  {
    name: "frontend/package.json (version)",
    file: "frontend/package.json",
    describe(c) {
      try {
        return JSON.parse(c).version || null;
      } catch (_) {
        return null;
      }
    },
    apply(c, v) {
      const pkg = JSON.parse(c);
      pkg.version = v;
      return JSON.stringify(pkg, null, 2) + "\n";
    },
  },
  {
    name: "backend/app/core/config.py (PROJECT_VERSION)",
    file: "backend/app/core/config.py",
    describe(c) {
      const m = c.match(/PROJECT_VERSION:\s*str\s*=\s*"([^"]+)"/);
      return m ? m[1] : null;
    },
    apply(c, v) {
      return c.replace(
        /(PROJECT_VERSION:\s*str\s*=\s*")([^"]+)(")/,
        `$1${v}$3`,
      );
    },
  },
  {
    name: "backend/version.txt",
    file: "backend/version.txt",
    optional: true,
    describe(c) {
      const m = c.trim().match(/^(\d+\.\d+\.\d+.*)$/);
      return m ? m[1] : null;
    },
    apply(_c, v) {
      return `${v}\n`;
    },
  },
  {
    name: "version.txt (root)",
    file: "version.txt",
    optional: true,
    describe(c) {
      const m = c.trim().match(/^(\d+\.\d+\.\d+.*)$/);
      return m ? m[1] : null;
    },
    apply(_c, v) {
      return `${v}\n`;
    },
  },
  {
    name: "README.md (badge)",
    file: "README.md",
    describe(c) {
      const m = c.match(/version-(\d+\.\d+\.\d+)-blue/);
      return m ? m[1] : null;
    },
    apply(c, v) {
      return c.replace(/(version-)(\d+\.\d+\.\d+)(-blue)/, `$1${v}$3`);
    },
  },
  {
    name: "Dockerfile (echo banner)",
    file: "Dockerfile",
    optional: true,
    describe(c) {
      const m = c.match(/帮扶管理信息系统 v(\d+\.\d+\.\d+)/);
      return m ? m[1] : null;
    },
    apply(c, v) {
      return c.replace(/(帮扶管理信息系统 v)(\d+\.\d+\.\d+)/, `$1${v}`);
    },
  },
  {
    name: "Dockerfile.runtime (LABEL version)",
    file: "Dockerfile.runtime",
    optional: true,
    describe(c) {
      const m = c.match(/image\.version="([^"]+)"/);
      return m ? m[1] : null;
    },
    apply(c, v) {
      return c.replace(/(image\.version=")([^"]+)(")/, `$1${v}$3`);
    },
  },
  {
    name: "docker-compose.yml (BUILD_VERSION)",
    file: "docker-compose.yml",
    describe(c) {
      const m = c.match(/BUILD_VERSION=(\d+\.\d+\.\d+)/);
      return m ? m[1] : null;
    },
    apply(c, v) {
      return c
        .replace(/(BUILD_VERSION=)(\d+\.\d+\.\d+)/g, `$1${v}`)
        .replace(/(\$\{VERSION:-)(\d+\.\d+\.\d+)(\})/g, `$1${v}$3`)
        .replace(/(PROJECT_VERSION=)(\d+\.\d+\.\d+)/g, `$1${v}`)
        .replace(/(版本:\s*v)(\d+\.\d+\.\d+)/, `$1${v}`);
    },
  },
  {
    name: "scripts/docker/build.ps1 ($Version)",
    file: "scripts/docker/build.ps1",
    describe(c) {
      const m = c.match(/\$Version\s*=\s*"([^"]+)"/);
      return m ? m[1] : null;
    },
    apply(c, v) {
      return c.replace(/(\$Version\s*=\s*")([^"]+)(")/, `$1${v}$3`);
    },
  },
  {
    name: "build-kylin.sh (config.py 读取失败时的兜底字面量)",
    file: "scripts/legacy/build-kylin.sh",
    optional: true,
    // 2026-09-12：原目标匹配 `arm64-vX.Y.Z.tar.gz`（历史产物命名），该命名已不存在
    // → 目标恒不命中、只在输出里留一条 warn 噪声（死目标）。现改为对准文件里
    // 真实存在的版本字面量：VERSION 从 config.py 提取，失败时兜底 `|| echo "1.2.0"`
    // —— 那正是会随发版漂移的地方（2026-09-12 实测仍停在 1.2.0）。
    describe(c) {
      const m = c.match(/\|\|\s*echo\s*"(\d+\.\d+\.\d+)"/);
      return m ? m[1] : null;
    },
    apply(c, v) {
      return c.replace(
        /(\|\|\s*echo\s*")(\d+\.\d+\.\d+)(")/,
        `$1${v}$3`,
      );
    },
  },
  {
    name: "build-with-check.ps1 ($PACKAGE_VERSION)",
    file: "build-with-check.ps1",
    optional: true,
    describe(c) {
      const m = c.match(/\$PACKAGE_VERSION\s*=\s*"([^"]+)"/);
      return m ? m[1] : null;
    },
    apply(c, v) {
      return c.replace(/(\$PACKAGE_VERSION\s*=\s*")([^"]+)(")/, `$1${v}$3`);
    },
  },
  {
    name: "frontend/src/config/constants.ts (SYSTEM_VERSION fallback)",
    file: "frontend/src/config/constants.ts",
    describe(c) {
      const m = c.match(/VITE_APP_VERSION \|\|\s*'([^']+)'/);
      return m ? m[1] : null;
    },
    apply(c, v) {
      return c.replace(
        /(VITE_APP_VERSION \|\|\s*')(\d+\.\d+\.\d+)(')/g,
        `$1${v}$3`,
      );
    },
  },
  {
    name: "frontend/package-lock.json (version + packages[\"\"].version)",
    file: "frontend/package-lock.json",
    // 2026-09-12 新增：lock 根部两处 version 长期靠手工对齐（v1.12.3 发版时实测
    // 仍停在 1.12.2）。纳入单一版本源管理，避免"package.json 已升、lock 没升"。
    describe(c) {
      try {
        const d = JSON.parse(c);
        return d.version || null;
      } catch {
        return null;
      }
    },
    apply(c, v) {
      const d = JSON.parse(c);
      d.version = v;
      if (d.packages && d.packages[""]) {
        d.packages[""].version = v;
      }
      return JSON.stringify(d, null, 2) + "\n";
    },
  },
  {
    name: "electron/splash.html (不得含静态版本字面量)",
    file: "electron/splash.html",
    // F3 单一来源契约：splash 的版本号由 main.js 用 app.getVersion() 注入，
    // 静态 HTML 里出现 `V1.2.3` 就说明又埋了一处会漂移的第二来源（2026-09-12
    // 实测残留 V1.12.2）。契约满足时返回源版本 → [ok]；否则哨兵 → --check 退出 1。
    describe(c) {
      const m = c.match(/V(\d+\.\d+\.\d+)/);
      if (m) {
        return `静态字面量 V${m[1]}（应由 main.js 注入）`;
      }
      return readSourceVersion();
    },
    apply(c) {
      // 删除静态字面量属人工判断（可能连带注释），禁止自动改写。
      return c;
    },
  },
  {
    name: "backend/version.json (version)",
    file: "backend/version.json",
    describe(c) {
      try {
        return JSON.parse(c).version || null;
      } catch {
        return null;
      }
    },
    apply(c, v) {
      const data = JSON.parse(c);
      data.version = v;
      return JSON.stringify(data, null, 2) + "\n";
    },
  },
  {
    name: "docker/Dockerfile.kylin-standalone (ARG VERSION)",
    file: "docker/Dockerfile.kylin-standalone",
    describe(c) {
      const m = c.match(/ARG VERSION=(\d+\.\d+\.\d+)/);
      return m ? m[1] : null;
    },
    apply(c, v) {
      return c.replace(/(ARG VERSION=)(\d+\.\d+\.\d+)/, `$1${v}`);
    },
  },
  {
    name: "electron/main.js (版本单一来源: app.getVersion)",
    file: "electron/main.js",
    // 2026-09-12（F3 整改副作用修复）：F3 删除了 `|| '1.2.3'` 硬编码回退，版本改为
    // 由打包元数据（根 package.json）经 `app.getVersion()` 单一提供。原目标只认
    // 字面量正则 → 永远匹配不到，成为死目标并每次输出 warn 噪声。
    // 现改为**契约检查**：仍在使用 app.getVersion() 且未重新引入硬编码版本字面量
    // 时视为一致（返回源版本）；契约被破坏则返回哨兵串 → 触发 [diff]，--check 退出 1。
    describe(c) {
      const usesPackedVersion = /app\.getVersion\(\)/.test(c);
      const hasHardcoded = /(\|\|\s*'|return\s*')\d+\.\d+\.\d+'/.test(c);
      if (!usesPackedVersion || hasHardcoded) {
        return "契约破坏: 需 app.getVersion() 且无硬编码版本";
      }
      return readSourceVersion();
    },
    apply(c) {
      // 没有可同步的字面量：契约不满足只能人工修复，禁止自动改写。
      return c;
    },
  },
  {
    name: "launch.py (banner version)",
    file: "launch.py",
    optional: true,
    describe(c) {
      const m = c.match(/帮扶管理信息系统 v(\d+\.\d+\.\d+)/);
      return m ? m[1] : null;
    },
    apply(c, v) {
      return c.replace(/(帮扶管理信息系统 v)(\d+\.\d+\.\d+)/, `$1${v}`);
    },
  },
];

function main() {
  const argv = process.argv.slice(2);
  const mode = argv.includes("--write")
    ? "write"
    : argv.includes("--check")
      ? "check"
      : "check"; // 默认 check

  const sourceVer = readSourceVersion();
  console.log(`[sync-version] 源版本 (package.json): ${sourceVer}`);
  console.log(`[sync-version] 模式: ${mode}`);
  console.log("");

  let mismatches = 0;
  let missing = 0;
  let synced = 0;

  for (const t of TARGETS) {
    const fullPath = path.join(ROOT, t.file);
    if (!fs.existsSync(fullPath)) {
      if (t.optional) {
        console.log(`  - [skip] ${t.name} (文件不存在，可选)`);
      } else {
        console.log(`  - [MISSING] ${t.name} -> ${t.file}`);
        missing++;
      }
      continue;
    }
    const content = fs.readFileSync(fullPath, "utf-8");
    const current = t.describe(content);
    if (current === null) {
      console.log(`  - [warn] ${t.name}: 未匹配到版本号（可能格式已变）`);
      continue;
    }
    if (current === sourceVer) {
      console.log(`  - [ok]    ${t.name}: ${current}`);
    } else {
      console.log(
        `  - [diff]  ${t.name}: ${current} 期望 ${sourceVer}`,
      );
      mismatches++;
      if (mode === "write") {
        const newContent = t.apply(content, sourceVer);
        if (newContent !== content) {
          fs.writeFileSync(fullPath, newContent, "utf-8");
          console.log(`           已同步 -> ${sourceVer}`);
          synced++;
        }
      }
    }
  }

  console.log("");
  if (mode === "write") {
    console.log(
      `[sync-version] 同步完成: ${synced} 个文件已更新，${mismatches - synced} 个仍不一致。`,
    );
  }

  if (missing > 0) {
    console.error(`[sync-version] ${missing} 个必需文件缺失`);
    process.exit(1);
  }

  // --check 模式下，重新校验一次以确认 write 结果
  if (mode === "check" && mismatches > 0) {
    console.error(
      `[sync-version] 发现 ${mismatches} 处版本不一致。运行 \`node scripts/sync-version.js --write\` 自动同步。`,
    );
    process.exit(1);
  }

  console.log("[sync-version] 校验通过 ✅");
  process.exit(0);
}

main();
