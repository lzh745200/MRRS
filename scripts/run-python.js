#!/usr/bin/env node
/**
 * run-python.js — resolve the project Python interpreter and execute it.
 *
 * 根因（W24 构建缺陷）：本机 PATH 里的裸 python 指向已删除的 32 位安装
 * （C:\Users\...\Python311-32），npm run build:backend / Makefile / scripts/*.bat
 * 里的裸 python 调用因此不可复现甚至直接失败。
 *
 * 解析优先级（与 scripts/find-python.bat 保持同一口径）：
 *   1) 环境变量 MRRS_PYTHON（显式覆盖，供 CI / 特殊环境使用）
 *   2) backend/.venv（Windows: Scripts/python.exe；Linux/macOS: bin/python）
 *   3) Windows: py -3.11 启动器；其他平台: python3.11 -> python3
 *   4) 全部不可用 -> 打印可执行的修复指引并以非 0 退出（不静默回退到裸 python）
 *
 * 用法：
 *   node scripts/run-python.js -m PyInstaller assistance-backend.spec --clean --noconfirm
 *   node scripts/run-python.js --print          # 只打印解析到的解释器路径
 *   node scripts/run-python.js --version        # 打印解释器版本
 *
 * 退出码 = 子进程退出码；解析失败时 exit 1（--print 成功 exit 0）。
 */

"use strict";

const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const PROJECT_ROOT = path.resolve(__dirname, "..");
const IS_WINDOWS = process.platform === "win32";

function venvPythonPath() {
  if (IS_WINDOWS) {
    return path.join(PROJECT_ROOT, "backend", ".venv", "Scripts", "python.exe");
  }
  return path.join(PROJECT_ROOT, "backend", ".venv", "bin", "python");
}

function candidates() {
  const list = [];
  if (process.env.MRRS_PYTHON) {
    list.push({ cmd: process.env.MRRS_PYTHON, args: [], label: "MRRS_PYTHON" });
  }
  list.push({ cmd: venvPythonPath(), args: [], label: "backend/.venv" });
  if (IS_WINDOWS) {
    list.push({ cmd: "py", args: ["-3.11"], label: "py -3.11" });
  } else {
    list.push({ cmd: "python3.11", args: [], label: "python3.11" });
    list.push({ cmd: "python3", args: [], label: "python3" });
  }
  return list;
}

function probe(candidate) {
  const res = spawnSync(candidate.cmd, candidate.args.concat(["--version"]), {
    encoding: "utf8",
    windowsHide: true,
  });
  if (res.error || res.status !== 0) {
    return null;
  }
  const out = (res.stdout || "").trim();
  if (!/^Python 3\./.test(out)) {
    return null;
  }
  return out;
}

function resolvePython() {
  const tried = [];
  for (const candidate of candidates()) {
    if (/[\\/]/.test(candidate.cmd) && !fs.existsSync(candidate.cmd)) {
      tried.push(candidate.label + ": not found (" + candidate.cmd + ")");
      continue;
    }
    const version = probe(candidate);
    if (version) {
      return { cmd: candidate.cmd, args: candidate.args, version: version };
    }
    tried.push(candidate.label + ": unavailable");
  }
  console.error("[run-python] ERROR: no usable Python interpreter found.");
  console.error("[run-python] Tried:");
  for (const line of tried) {
    console.error("  - " + line);
  }
  console.error("[run-python] Fix: install 64-bit Python 3.11, then:");
  console.error("  cd backend && py -3.11 -m venv .venv");
  console.error("  cd backend && .venv\\Scripts\\python.exe -m pip install -r requirements.txt -r requirements-dev.txt");
  console.error("  (Linux/macOS: python3.11 -m venv .venv)");
  console.error("[run-python] Or set MRRS_PYTHON to an explicit interpreter path.");
  return null;
}

function main(argv) {
  const python = resolvePython();
  if (!python) {
    return 1;
  }

  if (argv.indexOf("--print") >= 0) {
    process.stdout.write(python.cmd + (python.args.length ? " " + python.args.join(" ") : "") + "\n");
    return 0;
  }

  const args = argv.filter(function (a) {
    return a !== "--print";
  });
  const res = spawnSync(python.cmd, python.args.concat(args), {
    stdio: "inherit",
    cwd: process.cwd(),
    env: process.env,
  });
  if (res.error) {
    console.error("[run-python] failed to spawn " + python.cmd + ": " + res.error.message);
    return 1;
  }
  return typeof res.status === "number" ? res.status : 1;
}

process.exitCode = main(process.argv.slice(2));
